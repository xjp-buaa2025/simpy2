"""Station progress follows real releases, including rest and finite horizons."""
from copy import deepcopy
import hashlib
import json

import pytest

from app.core.area_capacity import AreaSimulationEngine
from app.core.event_collector import EventCollector
from app.core.simulation_engine import SimulationEngine
from app.core.station_progress import build_station_progress, sample_station_progress
from app.core.task_executor import TaskExecutor
from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessDefinition, ProcessNode


def timeline(durations=(10, 30), completion_times=(10, 40)):
    nodes = [dict(step_id=str(i), std_duration=duration, station="WS-G01", area_id="WS-G01",
                  workstation_id="WS-G01") for i, duration in enumerate(durations)]
    completions = [dict(engine_id=1, step_id=str(i), completed_at=end)
                   for i, end in enumerate(completion_times) if end is not None]
    return build_station_progress(sim_id="test", config={}, process={"nodes": nodes},
        gantt_events=[dict(engine_id=1, step_id="0", start_time=0),
                      dict(engine_id=2, step_id="0", start_time=5)],
        task_completion_events=completions, engine_release_times={1: 0, 2: 5}, time_minutes=60)


def row(payload, minute=None, engine=1):
    return sample_station_progress(payload, minute, engine_id=engine)["stations"][0]["engines"][0]


def test_completed_only_weighting_and_lightweight_immutable_samples():
    payload = timeline()
    before = deepcopy(payload)
    assert row(payload, 9)["progress"] == 0  # no interpolation during execution
    at_boundary = row(payload, 10)
    assert at_boundary["progress"] == .25 and at_boundary["completed_steps"] == 1
    assert row(payload, 39)["progress"] == .25
    finished = row(payload, 40)
    assert finished["completed"] and finished["progress"] == 1 and finished["completed_at"] == 40
    assert "completion_events" not in finished
    assert payload == before
    assert payload["stations"][0]["label"] != "WS-G01"  # canonical layout label


def test_multiple_engines_and_filters_preserve_each_identity():
    payload = timeline()
    assert [e["engine_id"] for e in sample_station_progress(payload, 4)["stations"][0]["engines"]] == [1]
    at_five = sample_station_progress(payload, 5)["stations"][0]["engines"]
    assert [e["engine_id"] for e in at_five] == [1, 2]
    assert all(e["state"] == "in_progress" for e in at_five)
    assert row(payload, 60, 2)["progress"] == 0
    assert sample_station_progress(payload, 0, engine_id=2)["stations"][0]["engines"] == []
    assert sample_station_progress(payload, station_id="absent")["stations"] == []


def test_future_station_start_is_not_leaked_and_same_time_milestones_all_apply():
    payload = timeline(completion_times=(20, 20))
    payload["stations"][0]["engines"][0]["started_at"] = 15
    assert row(payload, 14)["started_at"] is None
    assert row(payload, 14)["state"] == "not_started"
    assert row(payload, 19)["completed_steps"] == 0
    assert row(payload, 20)["completed_steps"] == 2


@pytest.mark.parametrize("minute", [-1, 61, float("nan"), float("inf"), -float("inf")])
def test_invalid_sample_times_are_rejected(minute):
    with pytest.raises(ValueError):
        sample_station_progress(timeline(), minute)


def test_zero_duration_tasks_keep_completion_independent_from_weight():
    mixed = timeline((10, 0), (10, 20))
    assert row(mixed, 10)["progress"] == 1 and not row(mixed, 10)["completed"]
    assert row(mixed, 20)["completed"]
    empty_work = timeline((0, 0), (0, 20))
    assert row(empty_work, 0)["progress"] == 0
    assert row(empty_work, 20)["progress"] == 1


def test_collector_records_unique_releases_and_rejects_conflicts():
    collector = EventCollector()
    node = ProcessNode(step_id="p", task_name="prepare", op_type="A", std_duration=1)
    collector.add_task_completion(1, node, 3)
    collector.add_task_completion(1, node, 3)
    assert len(collector.task_completion_events) == 1
    with pytest.raises(ValueError, match="冲突"):
        collector.add_task_completion(1, node, 4)


def test_process_catalog_preserves_order_and_labels_with_configuration_override():
    payload = build_station_progress(sim_id="catalog", config={"capacity_model": {
        "workstations": {"WS-G01": {"label": "configured"}}}},
        process={"station_catalog": [{"station_id": "WS-G02", "label": "custom second"},
                                    {"station_id": "WS-G01", "label": "custom first"}],
                 "nodes": [dict(step_id="first", workstation_id="WS-G01", std_duration=1),
                           dict(step_id="second", workstation_id="WS-G02", std_duration=1)]},
        gantt_events=[], task_completion_events=[], engine_release_times={1: 0}, time_minutes=60)
    assert [(s["station_id"], s["label"]) for s in payload["stations"]] == [
        ("WS-G02", "custom second"), ("WS-G01", "configured")]


def execution(kind, *, first_duration=10, first_load=8, second_duration=100, rework=False):
    config = GlobalConfig(work_hours_per_day=1, work_days_per_month=1,
        pipeline_mode=False, random_seed=42, rest_time_threshold=1e9,
        rest_load_threshold=7, rest_duration_load=3,
        capacity_model={"enabled": kind == "area", "areas": {"A": {}},
                        "workstations": {"W1": {"area_id": "A"}}})
    process = ProcessDefinition(nodes=[
        ProcessNode(step_id="p", task_name="prepare", op_type="M" if rework else "A",
            station="A", area_id="A", workstation_id="W1", std_duration=first_duration,
            work_load_score=first_load, rework_prob=.5 if rework else 0),
        ProcessNode(step_id="q", task_name="finish", op_type="A", predecessors="p",
            station="A", area_id="A", workstation_id="W1", std_duration=second_duration)])
    return SimulationEngine(config, process) if kind == "legacy" else AreaSimulationEngine(config, process)


@pytest.mark.parametrize("kind", ["legacy", "area"])
def test_release_waits_for_mandatory_rest_and_partial_work_never_counts(kind):
    result = execution(kind).run()
    assert any(e.event_type.value == "NORMAL" and e.end_time == 10 for e in result.gantt_events)
    assert result.task_completion_events == [dict(engine_id=1, step_id="p", station_id="W1",
        area_id="A", completed_at=13., std_duration=10.)]
    assert row(result.station_progress, 10)["completed_steps"] == 0
    assert row(result.station_progress, 13)["progress"] == pytest.approx(10 / 110)
    assert any(e.event_type.value == "IN_PROGRESS" for e in result.gantt_events)
    assert row(result.station_progress)["completed_steps"] == 1
    assert not row(result.station_progress)["completed"]


@pytest.mark.parametrize("kind", ["legacy", "area"])
def test_rework_attempt_does_not_release_a_step(kind, monkeypatch):
    if kind == "legacy":
        attempts = iter([True, False])
        monkeypatch.setattr(TaskExecutor, "_check_rework", lambda self, probability: next(attempts))
    else:
        monkeypatch.setattr(AreaSimulationEngine, "_failed", lambda self, eid, node, attempt: node.step_id == "p" and attempt == 0)
    result = execution(kind, first_duration=5, first_load=5, rework=True).run()
    assert any(e.event_type.value == "REWORK" for e in result.gantt_events)
    assert row(result.station_progress, 5)["completed_steps"] == 0
    assert row(result.station_progress, 10)["completed_steps"] == 1
    assert len(result.task_completion_events) == 1


@pytest.mark.parametrize("kind", ["legacy", "area"])
def test_terminal_rest_or_exact_horizon_is_not_a_release(kind):
    rested = execution(kind, first_duration=59).run()
    assert rested.task_completion_events == []
    assert row(rested.station_progress)["progress"] == 0
    exact = execution(kind, first_duration=60, first_load=5).run()
    assert exact.task_completion_events == []
    assert row(exact.station_progress)["completed_steps"] == 0


@pytest.mark.parametrize("kind", ["legacy", "area"])
def test_zero_duration_step_records_real_same_time_release(kind):
    result = execution(kind, first_duration=0, first_load=5).run()
    assert result.task_completion_events[0]["completed_at"] == 0
    assert row(result.station_progress, 0)["completed_steps"] == 1
    assert row(result.station_progress, 0)["progress"] == 0


@pytest.mark.parametrize("kind,expected", [
    ("legacy", "133f870799087a9997f87f5cf9b46c0ebd364c72999748ed1b1772e2f87cf972"),
    ("plan", "5f8d5265b306a0f04e7323af948cd63ef3c90f9493593e28c7f1cebff8abf6fc"),
    ("capacity", "c0cbb7641ee5d856ca749131e698788beabdd9c251dd78050ec13114b338139a"),
])
def test_observer_leaves_seeded_schedule_unchanged(kind, expected):
    # Captured before adding the observer: includes every task/worker/equipment
    # event, fatigue sample, quality statistic, and authoritative engine release.
    from tests.test_on_demand_production import scenario
    config, process = scenario(kind, True)
    result = (SimulationEngine(config, process) if kind == "legacy" else AreaSimulationEngine(config, process)).run()
    original = dict(events=[e.to_dict() for e in result.gantt_events],
        workers=[w.to_dict() for w in result.worker_stats], equipment=[e.to_dict() for e in result.equipment_stats],
        quality=result.quality_stats.to_dict(), engines=result.engines_completed,
        engine_completion=result.engine_completion_events)
    digest = hashlib.sha256(json.dumps(original, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    assert digest == expected
