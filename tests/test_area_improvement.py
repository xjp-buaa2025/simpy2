import csv
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.area_capacity import AreaSimulationEngine, expansion_packages, verified_catalog
from app.main import app
from app.models.capacity_model import AreaResources
from app.models.enums import OpType
from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessDefinition, ProcessNode


def scenario():
    config = GlobalConfig(work_hours_per_day=1, work_days_per_month=2, num_workers=2,
        rest_time_threshold=1e9, rest_load_threshold=10, random_seed=42,
        critical_equipment={"test": 1}, evaluation={"mode":"capacity", "max_wip":8,"sampling_scheme":"paired_v1"},
        capacity_model={"enabled":True,"areas":{"A":{}},"workstations":{
            "W1":{"area_id":"A"},"W2":{"area_id":"A"}}})
    process = ProcessDefinition(nodes=[
        ProcessNode(step_id="p",task_name="prepare",op_type="A",station="A",workstation_id="W1",std_duration=5),
        ProcessNode(step_id="q",task_name="test",op_type="A",station="A",workstation_id="W2",std_duration=20,predecessors="p",required_tools=["test"])])
    return config,process


def test_efficiency_shortens_actual_time_without_changing_standard():
    config,process=scenario()
    process.nodes=process.nodes[:1]
    process.nodes[0].std_duration=30
    config.capacity_model.areas["A"].efficiency_multiplier=1.25
    result=AreaSimulationEngine(config,process).run()
    work=[e for e in result.gantt_events if e.event_type.value=="NORMAL"]
    assert work and all(e.duration==24 for e in work)
    assert process.nodes[0].std_duration==30
    assert result.area_stats[0]["effective_standard_minutes"]==24


def test_complete_package_uses_station_maximum_and_deduplicates_equipment():
    config,process=scenario()
    config.capacity_model.workstations["W1"].capacity=2
    process.nodes[0].required_workers=3
    process.nodes[0].required_tools=["test","test","unlimited"]
    process.nodes.append(process.nodes[0].model_copy(update={"step_id":"r","required_workers":2}))
    config.capacity_model.areas["A"].resource_sets=2
    package=expansion_packages(config,process)["A"]
    assert "workers" not in package and package["equipment"]=={"test":3}
    assert package["station_slots"]==3
    config.capacity_model.areas["A"].resource_sets=3
    assert expansion_packages(config,process)["A"]["equipment"]=={"test":6}


def test_expansion_is_repeatable_conserved_and_respects_area_serial_rule():
    config,process=scenario()
    before=AreaSimulationEngine(config,process).run()
    config.capacity_model.areas["A"].resource_sets=2
    snapshot=config.model_dump()
    after=AreaSimulationEngine(config,process).run()
    again=AreaSimulationEngine(config,process).run()
    assert after.engines_completed==before.engines_completed
    assert again.engines_completed==after.engines_completed
    assert config.model_dump()==snapshot
    assert after.resource_snapshot["worker_supply_mode"]=="on_demand"
    assert after.resource_snapshot["total_workers"] > 0
    assert after.resource_snapshot["added_equipment"]=={"test":1}
    assert after.resource_snapshot["effective_workstations"]["W2"]["capacity"]==2
    for e in after.gantt_events:
        if e.event_type.value in {"NORMAL","REWORK","IN_PROGRESS"}:
            assert len(e.worker_ids)==1
    for stats in after.worker_stats+after.equipment_stats:
        assert 0<=stats.utilization_rate<=1


def test_non_bottleneck_improvement_can_leave_line_output_unchanged():
    config,process=scenario()
    config.capacity_model.areas['B']=AreaResources()
    config.capacity_model.workstations['W2'].area_id='B'
    process.nodes[1].station='B'
    before=AreaSimulationEngine(config,process).run()
    config.capacity_model.areas['A'].efficiency_multiplier=2
    after=AreaSimulationEngine(config,process).run()
    assert after.engines_completed==before.engines_completed
    assert after.area_stats[0]['effective_standard_minutes']==2.5


def test_workers_are_reserved_atomically_when_physical_resources_are_ready():
    config,process=scenario()
    process.nodes[0].required_workers=3
    engine=AreaSimulationEngine(config,process)
    node=engine.process.nodes[0]
    event=engine._request(1,node,"shared",engine._requirements(node))
    workers,resources=engine.env.run(until=event)
    assert len({w.id for w in workers})==3
    assert resources==["workstation:W1"]
    assert engine.available["workstation:W1"]==0


def test_added_resource_does_not_borrow_another_areas_inventory():
    config,process=scenario()
    config.capacity_model.areas["A"].resource_sets=2
    config.capacity_model.areas["B"]=AreaResources(dedicated_workers=1,equipment={"test":1})
    config.capacity_model.workstations["WB"]=config.capacity_model.workstations["W1"].model_copy(update={"area_id":"B"})
    process.nodes.append(ProcessNode(step_id="b",task_name="other",op_type="A",station="B",workstation_id="WB",std_duration=10,required_tools=["test"]))
    process.nodes[1].required_workers=2  # original public pool alone is insufficient
    result=AreaSimulationEngine(config,process).run()
    assert result.engines_completed>0
    for event in result.gantt_events:
        if event.area_id=="B":
            assert all(not worker.startswith("expansion:A:") for worker in event.worker_ids)
            assert "equipment:expansion:A:test" not in event.equipment_used
        if event.area_id=="A":
            assert "equipment:B:test" not in event.equipment_used


def test_paired_samples_survive_resource_and_scheduling_changes():
    config,process=scenario()
    process.nodes[1].time_variance=3
    process.nodes[1].op_type=OpType.M
    # model_copy below retains the validated enum
    process=ProcessDefinition.model_validate(process.model_dump())
    process.nodes[1].rework_prob=.5
    before=AreaSimulationEngine(config,process)
    config.capacity_model.areas["A"].efficiency_multiplier=2
    config.capacity_model.areas["A"].resource_sets=3
    after=AreaSimulationEngine(config,process)
    for eid in (1,3,10):
        for attempt in range(5):
            assert before._duration_for(eid,before.process.nodes[1],attempt)==2*after._duration_for(eid,after.process.nodes[1],attempt)
            assert before._failed(eid,before.process.nodes[1],attempt)==after._failed(eid,after.process.nodes[1],attempt)


def test_expanded_rework_rest_and_partial_horizon_are_accounted():
    config,process=scenario()
    config.capacity_model.areas["A"].resource_sets=2
    config.capacity_model.areas["A"].efficiency_multiplier=1.5
    config.rest_time_threshold=10
    config.rest_duration_time=2
    process.nodes[1].op_type=OpType.M
    process=ProcessDefinition.model_validate(process.model_dump())
    process.nodes[1].rework_prob=.5
    result=AreaSimulationEngine(config,process).run()
    assert result.quality_stats.total_reworks>0
    assert any(e.event_type.value=="REST" for e in result.gantt_events)
    assert any(e.event_type.value=="IN_PROGRESS" for e in result.gantt_events)
    assert all(0<=s.utilization_rate<=1 for s in result.worker_stats)
    json.dumps(result.to_dict(),allow_nan=False)


def test_one_set_and_default_efficiency_keep_legacy_sampling_behavior():
    config,process=scenario()
    config.evaluation.sampling_scheme="legacy"
    old=config.model_dump()
    for area in old["capacity_model"]["areas"].values():
        area.pop("resource_sets");area.pop("efficiency_multiplier")
    old["evaluation"].pop("sampling_scheme")
    a=AreaSimulationEngine(GlobalConfig.model_validate(old),process).run()
    b=AreaSimulationEngine(config,process).run()
    assert [e.to_dict() for e in a.gantt_events]==[e.to_dict() for e in b.gantt_events]


@pytest.mark.parametrize("field,value",[("resource_sets",0),("resource_sets",5),("resource_sets",1.5),("efficiency_multiplier",.5),("efficiency_multiplier",2.1),("efficiency_multiplier",float("nan"))])
def test_invalid_simple_parameters_are_rejected(field,value):
    with pytest.raises(ValueError):
        AreaResources(**{field:value})


def test_baseline_run_does_not_publish_and_api_preserves_expansion(monkeypatch):
    config,process=scenario()
    calls=[]
    monkeypatch.setattr("tools.unity_validation.publish_result",lambda *args:calls.append(args) or {"success":True})
    client=TestClient(app)
    request={"config":config.model_dump(),"process":process.model_dump(),"publish_to_clients":False}
    baseline=client.post('/api/simulation/run',json=request).json()
    assert baseline["success"] and not calls
    config.capacity_model.areas["A"].resource_sets=2
    request["config"]=config.model_dump();request["publish_to_clients"]=True
    candidate=client.post('/api/simulation/run',json=request).json()
    assert candidate["success"] and len(calls)==1
    assert candidate["data"]["input_snapshot"]["config"]["capacity_model"]["areas"]["A"]["resource_sets"]==2
    assert candidate["data"]["evaluation_context"]["sampling_scheme"]=="paired_v1"
    assert "workers" not in client.post('/api/simulation/capacity/validate',json=request).json()["data"]["expansions"]["A"]


def test_79_station_expansion_replay_uses_effective_capacity(tmp_path,monkeypatch):
    import tools.unity_validation as adapter
    rows=list(csv.DictReader(Path('3.csv').read_text(encoding='utf-8-sig').splitlines()))
    nodes=[ProcessNode(**dict(row,required_tools=[t for t in row['required_tools'].split(';') if t])) for row in rows]
    config=GlobalConfig(random_seed=42,capacity_model={"enabled":True,"areas":{n.station:{} for n in nodes},"workstations":verified_catalog()},evaluation={"mode":"capacity","sampling_scheme":"paired_v1"})
    aid=nodes[0].station
    config.capacity_model.areas[aid].resource_sets=2
    config.capacity_model.areas[aid].efficiency_multiplier=1.25
    engine=AreaSimulationEngine(config,ProcessDefinition(nodes=nodes))
    result=engine.run()
    monkeypatch.setattr(adapter,'OUTPUT',tmp_path)
    payload=adapter.build(result=dict(result.to_dict(),gantt_events=[e.to_dict() for e in result.gantt_events]),rows=[n.model_dump(mode='json') for n in engine.process.nodes])
    assert payload['engines_completed']==result.engines_completed>0
    for station in payload['stations']:
        expected=result.resource_snapshot['effective_workstations'][station['station_id']]['capacity']
        assert station['capacity']==expected
    assert payload['area_stats']==result.area_stats
    for event in payload['events']:
        assert event['area_id'] in config.capacity_model.areas
