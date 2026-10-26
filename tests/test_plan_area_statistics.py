"""Area reporting must be independent of optional resource constraints."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.core.area_statistics import build_plan_area_statistics, with_plan_area_statistics
from app.core.simulation_engine import SimulationEngine
from app.core.task_executor import TaskExecutor
from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessDefinition, ProcessNode
from app.api import results, simulation
from app.main import app


def scenario(*, first=10, second=100, load=5):
    config = GlobalConfig(work_hours_per_day=1, work_days_per_month=1, pipeline_mode=False,
        rest_time_threshold=1e9, rest_load_threshold=7, rest_duration_load=3, random_seed=42,
        capacity_model={"enabled": False, "areas": {"A": {"efficiency_multiplier": 2, "resource_sets": 4}}})
    process = ProcessDefinition(station_catalog=[{"station_id": "A", "label": "预装工区"}], nodes=[
        ProcessNode(step_id="p", task_name="prepare", op_type="A", station="A",
                    std_duration=first, work_load_score=load),
        ProcessNode(step_id="q", task_name="finish", op_type="A", station="B",
                    predecessors="p", std_duration=second)])
    return config, process


def test_disabled_model_reports_all_areas_without_applying_saved_resource_settings():
    config, process = scenario()
    result = SimulationEngine(config, process).run()
    a, b = result.area_stats
    assert not result.config.capacity_model.enabled
    assert a["area_id"] == "A" and a["label"] == "预装工区"
    assert a["completed_units"] == 1 and a["avg_cycle_time"] == 10 and a["wip"] == 0
    assert a["standard_minutes"] == a["effective_standard_minutes"] == 10
    assert b["area_id"] == "B" and b["completed_units"] == 0 and b["wip"] == 1
    assert b["avg_cycle_time"] is None
    assert b["labor_minutes"] == 50
    assert result.engines_completed == 0
    assert result.area_completion_events == [dict(area_id="A", engine_id=1, start_time=0, end_time=10)]


@pytest.mark.parametrize("duration,completed,cycle,wip", [(10, 1, 13, 0), (59, 0, None, 1), (60, 0, None, 1)])
def test_completion_follows_mandatory_rest_and_excludes_horizon(duration, completed, cycle, wip):
    config, process = scenario(first=duration, load=8)
    result = SimulationEngine(config, process).run()
    a, b = result.area_stats
    assert (a["completed_units"], a["avg_cycle_time"], a["wip"]) == (completed, cycle, wip)
    assert b["completed_units"] == 0
    if not completed:
        assert b["wip"] == 0 and b["avg_cycle_time"] is None  # downstream never started
        assert result.area_completion_events == []


def test_all_steps_in_area_must_release_and_rework_is_not_completion(monkeypatch):
    config, process = scenario(first=5)
    from app.models.enums import OpType
    process.nodes[0].op_type = OpType.M
    attempts = iter([True, False])
    monkeypatch.setattr(TaskExecutor, "_check_rework", lambda self, probability: next(attempts))
    process.nodes[1].station = "A"
    result = SimulationEngine(config, process).run()
    a, = result.area_stats
    assert a["completed_units"] == 0 and a["wip"] == 1
    assert a["standard_minutes"] == 105 and a["labor_minutes"] == 60
    assert result.area_completion_events == []


def test_multiple_workstations_in_one_area_zero_duration_and_parallel_area_identity():
    nodes = [dict(step_id="a", area_id="A", station="legacy", workstation_id="W1", std_duration=0),
             dict(step_id="b", area_id="A", station="legacy", workstation_id="W2", std_duration=5),
             dict(step_id="c", station="B", std_duration=10)]
    work = [dict(engine_id=1, step_id="b", start_time=0, end_time=5, event_type="NORMAL", worker_ids=[]),
            dict(engine_id=2, step_id="b", start_time=5, end_time=8, event_type="IN_PROGRESS", worker_ids=[])]
    done = [dict(engine_id=1, step_id="a", completed_at=0), dict(engine_id=1, step_id="b", completed_at=5)]
    before = deepcopy((nodes, work, done))
    rows, events = build_plan_area_statistics(config={}, process={"nodes": nodes},
        gantt_events=work, task_completion_events=done + done)  # duplicated transport cannot inflate output
    a, b = rows
    assert a["completed_units"] == 1 and a["wip"] == 1 and a["avg_cycle_time"] == 5
    assert a["workstation_count"] == 2
    assert b["completed_units"] == b["wip"] == 0
    assert len(events) == 1
    assert (nodes, work, done) == before


def test_api_new_and_retained_results_report_areas_without_mutating_history(monkeypatch):
    store = {}
    monkeypatch.setattr(simulation, "simulation_results", store)
    monkeypatch.setattr(results, "simulation_results", store)
    config, process = scenario()
    with TestClient(app) as client:
        body = client.post("/api/simulation/run", json=dict(config=config.model_dump(),
            process=process.model_dump(), publish_to_clients=False)).json()
        assert body["success"], body
        data = body["data"]
        assert len(data["area_stats"]) == 2
        sid = data["sim_id"]
        assert client.get(f"/api/results/{sid}").json()["data"]["area_stats"] == data["area_stats"]
        store[sid].area_stats = []
        store[sid].area_completion_events = []
        original = store[sid].model_dump()
        restored = client.get(f"/api/results/{sid}").json()["data"]
        assert restored["area_stats"] == data["area_stats"]
        assert restored["area_completion_events"] == data["area_completion_events"]
        assert store[sid].model_dump() == original
        report = client.post("/api/results/export/report", params={"sim_id": sid}).json()
        assert report["area_stats"] == data["area_stats"]
        assert report["area_completion_events"] == data["area_completion_events"]


def test_history_without_authoritative_completion_evidence_is_not_fabricated():
    data = dict(input_snapshot={"config": {}, "process": {"nodes": [dict(step_id="p", station="A", std_duration=5)]}},
                gantt_events=[dict(engine_id=1, step_id="p", event_type="NORMAL", start_time=0, end_time=5)],
                area_stats=[], task_completion_events=[], station_progress=None)
    assert with_plan_area_statistics(data) is data
