import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.area_capacity import AreaSimulationEngine, verified_catalog
from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessDefinition, ProcessNode
from app.main import app


def case(capacity=1, *, workers=8, mode="capacity", wip=8, tools=False):
    cfg = GlobalConfig(work_hours_per_day=1, work_days_per_month=2, num_workers=workers,
        critical_equipment={"test": 2}, rest_time_threshold=1e9, rest_duration_time=0,
        rest_load_threshold=10, rest_duration_load=0, random_seed=42, target_output=1,
        evaluation={"mode": mode, "max_wip": wip}, capacity_model={"enabled": True,
            "areas": {"A": {"label": "测试工区"}}, "workstations": {
                "W1": {"area_id": "A", "capacity": 1},
                "W2": {"area_id": "A", "capacity": capacity}}})
    process = ProcessDefinition(nodes=[
        ProcessNode(step_id="p", task_name="prepare", op_type="A", station="A", workstation_id="W1", std_duration=5),
        ProcessNode(step_id="q", task_name="test", op_type="A", station="A", workstation_id="W2", predecessors="p", std_duration=20,
                    required_tools=["test"] if tools else [])])
    return cfg, process


def test_station_expansion_respects_area_serial_rule_and_ignores_target():
    cfg, process = case()
    before = AreaSimulationEngine(cfg, process).run()
    cfg.capacity_model.workstations["W2"].capacity = 2
    after = AreaSimulationEngine(cfg, process).run()
    assert after.engines_completed == before.engines_completed > cfg.target_output + 2
    assert before.evaluation_context["peak_wip"] <= 8
    cfg.target_output = 100
    assert AreaSimulationEngine(cfg, process).run().engines_completed == after.engines_completed
    assert process.nodes[0].area_id == ""  # private normalized snapshots


def test_non_bottleneck_expansion_does_not_create_output():
    cfg, process = case()
    before = AreaSimulationEngine(cfg, process).run()
    cfg.capacity_model.workstations["W1"].capacity = 4
    after = AreaSimulationEngine(cfg, process).run()
    assert before.engines_completed == after.engines_completed


def test_station_capacity_cannot_bypass_area_serial_rule():
    cfg, process = case(capacity=2)
    cfg.station_constraint_mode = True  # mandatory in both engines
    result = AreaSimulationEngine(cfg, process).run()
    work = [e for e in result.gantt_events if e.event_type.value in {"NORMAL", "IN_PROGRESS"}]
    for sid, cap in [("W1", 1), ("W2", 2)]:
        for t in range(120):
            assert sum(e.start_time <= t < e.end_time for e in work if e.workstation_id == sid) <= cap
    assert not any(a.start_time < b.end_time and b.start_time < a.end_time
               for a in work for b in work if a.workstation_id != b.workstation_id)


def test_obsolete_worker_allocations_are_ignored():
    cfg, process = case(workers=3)
    before = AreaSimulationEngine(cfg, process).run()
    cfg.num_workers = 1
    cfg.capacity_model.areas["A"].dedicated_workers = 999
    after = AreaSimulationEngine(cfg, process).run()
    assert after.engines_completed == before.engines_completed
    assert [e.to_dict() for e in after.gantt_events] == [e.to_dict() for e in before.gantt_events]
    assert after.resource_snapshot["worker_supply_mode"] == "on_demand"


def test_equipment_inventory_and_binding():
    cfg, process = case(capacity=4, tools=True)
    cfg.capacity_model.areas["A"].equipment = {"test": 1}
    a = AreaSimulationEngine(cfg, process).run()
    assert next(r for r in a.resource_snapshot["resources"] if r["resource_id"] == "equipment:shared:test")["capacity"] == 1
    cfg.capacity_model.areas["A"].equipment["test"] = 2
    b = AreaSimulationEngine(cfg, process).run()
    assert b.engines_completed == a.engines_completed
    cfg.capacity_model.areas["A"].equipment["test"] = 3
    with pytest.raises(ValueError, match="库存"):
        AreaSimulationEngine(cfg, process)
    cfg.capacity_model.areas["A"].equipment["test"] = 1
    process.nodes[1].required_tools = []
    assert AreaSimulationEngine(cfg, process).run().evaluation_context["warnings"]


def test_partial_work_and_waits_are_flushed_at_horizon():
    cfg, process = case(workers=2)
    process.nodes[1].std_duration = 1000
    result = AreaSimulationEngine(cfg, process).run()
    stats = result.area_stats[0]
    assert stats["completed_units"] == 0 and stats["avg_cycle_time"] is None
    assert stats["wip"] > 0 and stats["labor_minutes"] > 100
    assert any(e.event_type.value == "IN_PROGRESS" and not e.is_complete for e in result.gantt_events)
    assert any(e.wait_reason and not e.is_complete for e in result.gantt_events)
    assert all(0 <= w.utilization_rate <= 1 for w in result.worker_stats)
    json.dumps(result.to_dict(), allow_nan=False)


def test_fork_join_and_rework_never_double_count_area_completion():
    cfg, process = case(wip=2)
    process.nodes[1].predecessors = ""
    process.nodes.append(ProcessNode(step_id="join", task_name="join", op_type="M", station="A", workstation_id="W1",
        predecessors="p;q", std_duration=2, rework_prob=.5))
    result = AreaSimulationEngine(cfg, process).run()
    records = result.area_completion_events
    assert len(records) == result.engines_completed
    assert len({(r["area_id"], r["engine_id"]) for r in records}) == len(records)
    assert result.quality_stats.total_reworks > 0
    assert result.area_stats[0]["completed_units"] == result.engines_completed


def test_api_roundtrip_and_failed_runs_do_not_publish(monkeypatch):
    calls = []
    monkeypatch.setattr("tools.unity_validation.publish_result", lambda *args: calls.append(args) or {"success": True})
    cfg, process = case()
    client = TestClient(app)
    response = client.post("/api/simulation/run", json={"config": cfg.model_dump(), "process": process.model_dump()}).json()
    assert response["success"], response
    data = response["data"]
    assert data["area_stats"] and data["input_snapshot"]["config"]["evaluation"]["max_wip"] == 8
    assert data["input_snapshot"]["process"]["nodes"][0]["area_id"] == "A"
    assert len(calls) == 1
    assert any(e["wait_reason"] == "area" and e["wait_resource_ids"] == ["area:A"] for e in data["gantt_events"])
    cfg.capacity_model.workstations["W1"].area_id = "missing"
    response = client.post("/api/simulation/run", json={"config": cfg.model_dump(), "process": process.model_dump()}).json()
    assert not response["success"] and len(calls) == 1
    assert client.get("/api/simulation/capacity/catalog").json()["data"] == verified_catalog()


def test_verified_79_station_migration():
    catalog = verified_catalog()
    assert len(catalog) == 79
    # Use the canonical published CSV rather than inferring stations from labels.
    import csv
    rows = list(csv.DictReader(Path("3.csv").read_text(encoding="utf-8-sig").splitlines()))
    nodes = [ProcessNode(**dict(r, required_tools=[t for t in r["required_tools"].split(";") if t])) for r in rows]
    cfg = GlobalConfig(num_workers=8, random_seed=42, capacity_model={"enabled": True,
        "areas": {n.station: {} for n in nodes}, "workstations": catalog}, evaluation={"mode":"capacity"})
    result = AreaSimulationEngine(cfg, ProcessDefinition(nodes=nodes)).run()
    assert sum(s["process_count"] for s in result.area_stats) == 79
    assert result.engines_completed > 0
    assert len(result.gantt_events) < 100000


def test_zero_duration_rest_does_not_spin_without_advancing_time():
    cfg, process = case()
    cfg.rest_time_threshold = 0
    cfg.rest_duration_time = 0
    assert AreaSimulationEngine(cfg, process).run().engines_completed > 0


@pytest.mark.parametrize("reason,workers,capacity,tools", [("area",8,4,True),("area",8,1,False)])
def test_waits_identify_actual_blocked_resource(reason,workers,capacity,tools):
    cfg,process=case(workers=workers,capacity=capacity,tools=tools)
    result=AreaSimulationEngine(cfg,process).run()
    waits=[e for e in result.gantt_events if e.wait_reason==reason]
    assert waits
    known={r["resource_id"] for r in result.resource_snapshot["resources"]} | {"area:A"}
    for event in waits:
        assert event.wait_resource_ids
        assert all(resource in known for resource in event.wait_resource_ids)
        assert event.to_dict()["wait_resource_ids"] == event.wait_resource_ids
