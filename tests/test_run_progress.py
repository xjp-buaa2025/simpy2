from concurrent.futures import ThreadPoolExecutor
from threading import Event
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.run_progress import RunProgressStore, run_progress
from app.core.simulation_engine import SimulationEngine, SimulationEngineNoRest
from app.core.area_capacity import AreaSimulationEngine
from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessDefinition, ProcessNode


def test_progress_is_monotonic_and_failure_never_fakes_completion():
    store = RunProgressStore()
    store.start('one')
    store.update('one', 65, '计算', 'main')
    store.update('one', 20, '整理', 'results')
    store.finish('one', False, 'controlled failure')
    result = store.snapshot('one')
    assert result['percent'] == 65
    assert result['status'] == 'failed'
    assert result['phase'] == 'controlled failure'
    store.update('one', 100, 'late update', 'complete')
    assert store.snapshot('one')['percent'] == 65
    assert store.snapshot('missing') is None
    with pytest.raises(ValueError):
        store.start('one')


def test_completed_progress_expires_without_affecting_active_runs(monkeypatch):
    import app.core.run_progress as module
    now = [100]
    monkeypatch.setattr(module, 'monotonic', lambda: now[0])
    store = RunProgressStore()
    store.start('done'); store.finish('done', True)
    store.start('active')
    now[0] += 901
    assert store.snapshot('done') is None
    store.start('new')
    assert 'done' not in store.records
    assert store.snapshot('active')['status'] == 'running'


@pytest.mark.parametrize('kind', ['main', 'no_rest', 'area'])
def test_observing_progress_does_not_change_simulation_results(kind):
    config = GlobalConfig(work_hours_per_day=1, work_days_per_month=1,
                          num_workers=2, target_output=2, random_seed=42)
    process = ProcessDefinition(nodes=[ProcessNode(step_id='one', task_name='Test', op_type='A',
                                                   std_duration=5, time_variance=1, station='A')])
    engine_class = {'main': SimulationEngine, 'no_rest': SimulationEngineNoRest, 'area': AreaSimulationEngine}[kind]
    if kind == 'area':
        config.capacity_model = type(config.capacity_model).model_validate({'enabled': True,
            'areas': {'A': {'label': 'A'}}, 'workstations': {'W': {'area_id': 'A', 'capacity': 1}}})
        process.nodes[0].workstation_id = 'W'
    before = engine_class(config.model_copy(deep=True), process.model_copy(deep=True)).run()
    engine = engine_class(config.model_copy(deep=True), process.model_copy(deep=True))
    samples = []
    engine.progress_callback = lambda fraction, minute, total: samples.append((fraction, minute, total))
    after = engine.run()
    assert len(samples) >= 90
    assert samples == sorted(samples)
    assert samples[-1][0] >= .98
    if kind == 'no_rest':
        assert before == after
    else:
        assert before.engines_completed == after.engines_completed
        assert before.gantt_events == after.gantt_events


def test_progress_can_be_read_while_request_runs_and_only_finishes_after_processing(monkeypatch):
    from app.api import simulation
    app = FastAPI(); app.include_router(simulation.router, prefix='/api/simulation')
    entered, resume = Event(), Event()
    original = SimulationEngine.run
    def slow_run(engine):
        result = original(engine)
        entered.set()
        assert resume.wait(5)
        return result
    monkeypatch.setattr(SimulationEngine, 'run', slow_run)
    run_id = str(uuid.uuid4())
    payload = {'progress_id': run_id, 'publish_to_clients': False,
               'config': {'work_hours_per_day': 1, 'work_days_per_month': 1, 'target_output': 1, 'num_workers': 2},
               'process': {'nodes': [{'step_id': 'one', 'task_name': 'Test', 'op_type': 'A', 'std_duration': 5}]}}
    with TestClient(app) as client, ThreadPoolExecutor() as pool:
        future = pool.submit(client.post, '/api/simulation/run', json=payload)
        try:
            assert entered.wait(5)
            live = client.get('/api/simulation/progress/' + run_id).json()['data']
            assert live['status'] == 'running'
            assert 4 < live['percent'] < 100
            assert not future.done()
        finally:
            resume.set()
        result = future.result(timeout=5).json()
        assert result['success']
        done = client.get('/api/simulation/progress/' + run_id).json()['data']
        assert done['percent'] == 100 and done['status'] == 'completed'
        assert result['data']['unity_sync']['skipped']
        simulation.simulation_results.pop(result['data']['sim_id'], None)
        assert client.get('/api/simulation/progress/unknown').status_code == 404


def test_invalid_dag_ends_progress_with_error():
    from app.api.simulation import run_simulation, SimulationRequest
    run_id = str(uuid.uuid4())
    response = run_simulation(SimulationRequest.model_validate({'progress_id': run_id, 'publish_to_clients': False,
        'config': {}, 'process': {'nodes': [{'step_id': 'one', 'task_name': 'Test', 'op_type': 'A',
                                            'predecessors': 'missing', 'std_duration': 5}]}}), None)
    assert not response.success
    assert run_progress.snapshot(run_id)['status'] == 'failed'
    assert run_progress.snapshot(run_id)['percent'] < 100
