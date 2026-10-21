"""Acceptance of removed inputs, retained rest, and finite-horizon production."""
import json
from collections import defaultdict
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.simulation_engine import SimulationEngine, SimulationEngineNoRest
from app.core.area_capacity import AreaSimulationEngine
from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessDefinition, ProcessNode
from app.utils.statistics import analyze_bottlenecks


def scenario(kind='legacy', pipeline=True, obsolete=None):
    data = dict(work_hours_per_day=1, work_days_per_month=2, random_seed=42,
        pipeline_mode=pipeline, rest_time_threshold=25, rest_duration_time=4,
        rest_load_threshold=7, rest_duration_load=3, critical_equipment={'test': 1},
        capacity_model={'enabled': kind != 'legacy', 'areas': {'A': {}},
            'workstations': {'W1': {'area_id': 'A'}, 'W2': {'area_id': 'A'}}},
        evaluation={'mode': 'capacity' if kind == 'capacity' else 'plan',
            'max_wip': 4, 'sampling_scheme': 'paired_v1'})
    if obsolete is not None:
        data.update(num_workers=obsolete, target_output=obsolete)
        data['capacity_model']['areas']['A']['dedicated_workers'] = obsolete
    config = GlobalConfig.model_validate(data)
    process = ProcessDefinition(nodes=[
        ProcessNode(step_id='p', task_name='prepare', op_type='A', station='A',
            workstation_id='W1', std_duration=5, required_workers=2),
        ProcessNode(step_id='q', task_name='inspect', op_type='M', station='A',
            workstation_id='W2', predecessors='p', std_duration=12, time_variance=2,
            required_workers=3, work_load_score=8, rework_prob=.2, required_tools=['test'])])
    return config, process


def run(kind, pipeline, obsolete=None, no_rest=False):
    config, process = scenario(kind, pipeline, obsolete)
    if kind == 'legacy':
        engine = SimulationEngineNoRest(config, process) if no_rest else SimulationEngine(config, process)
    else:
        engine = AreaSimulationEngine(config, process, no_rest=no_rest)
    return engine.run()


@pytest.mark.parametrize('kind,pipeline', [('legacy', True), ('legacy', False), ('plan', True), ('plan', False), ('capacity', True)])
@pytest.mark.parametrize('no_rest', [False, True])
def test_obsolete_counts_and_targets_cannot_change_production(kind, pipeline, no_rest):
    reference = run(kind, pipeline, no_rest=no_rest)
    for value in (1, 1000, 'unused'):
        result = run(kind, pipeline, value, no_rest)
        if isinstance(result, dict):
            assert result == reference
        else:
            assert result.engines_completed == reference.engines_completed
            assert result.avg_cycle_time == reference.avg_cycle_time
            assert result.quality_stats == reference.quality_stats
            assert result.engine_completion_events == reference.engine_completion_events
            assert [e.to_dict() for e in result.gantt_events] == [e.to_dict() for e in reference.gantt_events]
            assert analyze_bottlenecks(result).to_dict() == analyze_bottlenecks(reference).to_dict()
            assert result.target_achievement_rate is None


@pytest.mark.parametrize('kind', ['legacy', 'plan', 'capacity'])
def test_personnel_intervals_never_overlap_and_completion_follows_rest(kind):
    result = run(kind, False)
    spans = defaultdict(list)
    for e in result.gantt_events:
        if e.event_type.value in {'NORMAL', 'REWORK', 'REST', 'IN_PROGRESS'}:
            for wid in e.worker_ids:
                spans[wid].append((e.start_time, e.end_time))
    for rows in spans.values():
        rows.sort()
        assert all(a[1] <= b[0] for a, b in zip(rows, rows[1:]))
    finished = {e['engine_id']: e['end_time'] for e in result.engine_completion_events}
    for e in result.gantt_events:
        if e.event_type.value == 'REST' and e.engine_id in finished:
            assert finished[e.engine_id] >= e.end_time
    assert result.engines_completed == len(finished)
    assert not any(e.wait_reason == 'workers' for e in result.gantt_events)


@pytest.mark.parametrize('kind', ['legacy', 'plan'])
def test_serial_reuse_retains_time_rest_and_partial_horizon(kind):
    config, process = scenario(kind, False)
    process.nodes = process.nodes[:1]
    process.nodes[0].std_duration = 20
    config.rest_time_threshold = 10
    config.rest_duration_time = 5
    engine = SimulationEngine(config, process) if kind == 'legacy' else AreaSimulationEngine(config, process)
    result = engine.run()
    assert len(result.worker_stats) == 2
    assert any(e.event_type.value == 'REST' for e in result.gantt_events)
    assert any(e.event_type.value == 'IN_PROGRESS' and not e.is_complete for e in result.gantt_events)
    assert all(e.end_time <= 120 for e in result.gantt_events)


@pytest.mark.parametrize('kind', ['legacy', 'plan', 'capacity'])
def test_all_zero_work_rejected_and_zero_entry_advances(kind):
    config, process = scenario(kind)
    process.nodes[0].std_duration = 0
    engine = SimulationEngine(config, process) if kind == 'legacy' else AreaSimulationEngine(config, process)
    assert engine.run().engines_completed > 0
    for n in process.nodes:
        n.std_duration = n.time_variance = 0
    with pytest.raises(ValueError, match='正工时'):
        engine = SimulationEngine(config, process) if kind == 'legacy' else AreaSimulationEngine(config, process)
        engine.run()


def test_api_roundtrip_report_and_completion_metadata():
    config, process = scenario('capacity', obsolete=999)
    client = TestClient(app)
    response = client.post('/api/simulation/run', json=dict(config=config.model_dump(), process=process.model_dump(), publish_to_clients=False)).json()
    assert response['success'], response
    data = response['data']; sid = data['sim_id']
    assert 'num_workers' not in data['config'] and 'target_output' not in data['config']
    assert 'dedicated_workers' not in data['config']['capacity_model']['areas']['A']
    assert data['target_achievement_rate'] is None
    assert len(data['engine_completion_events']) == data['engines_completed']
    assert data['evaluation_context']['worker_supply_mode'] == 'on_demand'
    assert client.get(f'/api/results/{sid}/kpi').json()['success']
    assert client.get(f'/api/results/{sid}/bottleneck').json()['success']
    report = client.post('/api/results/export/report', params={'sim_id': sid})
    assert report.status_code == 200
    json.loads(report.content)


@pytest.mark.parametrize('kind', ['legacy', 'plan'])
def test_terminal_rest_crossing_horizon_is_not_a_finished_product(kind):
    config, process = scenario(kind, False)
    config.work_days_per_month = 1
    process.nodes = process.nodes[:1]
    process.nodes[0].std_duration = 59
    process.nodes[0].work_load_score = 8
    config.rest_duration_load = 3
    engine = SimulationEngine(config, process) if kind == 'legacy' else AreaSimulationEngine(config, process)
    result = engine.run()
    assert result.engines_completed == 0 and result.engine_completion_events == []
    assert [(e.start_time, e.end_time, e.is_complete) for e in result.gantt_events if e.event_type.value == 'REST'] == [(59, 60, False)]
    assert sum(w.rest_time for w in result.worker_stats) == 2
    assert result.evaluation_context['labor_minutes'] == 118
