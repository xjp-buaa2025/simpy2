"""Mandatory area exclusion across products, branches, rest and rework."""
from collections import defaultdict

import pytest

from app.core.area_capacity import AreaSimulationEngine
from app.core.simulation_engine import SimulationEngine, SimulationEngineNoRest
from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessDefinition, ProcessNode


def run_case(kind, *, separate=False, pipeline=True, legacy_flag=False):
    config = GlobalConfig(work_hours_per_day=1, work_days_per_month=2,
        pipeline_mode=pipeline, station_constraint_mode=legacy_flag,
        random_seed=42, rest_time_threshold=8, rest_duration_time=3,
        rest_load_threshold=7, rest_duration_load=2, critical_equipment={},
        capacity_model={'enabled': kind.startswith('area'),
            'areas': {'A': {'resource_sets': 3}, 'B': {}},
            'workstations': {'W1': {'area_id': 'A', 'capacity': 3},
                'W2': {'area_id': 'B' if separate else 'A', 'capacity': 3}}},
        evaluation={'mode': 'capacity' if kind == 'area-capacity' else 'plan', 'max_wip': 4})
    # Independent DAG branches would overlap without the area gate. The second
    # branch uses an explicit area ID while the first uses the station fallback.
    process = ProcessDefinition(nodes=[
        ProcessNode(step_id='p', task_name='assembly', op_type='A',
            station='A', workstation_id='W1', std_duration=10, required_workers=2),
        ProcessNode(step_id='q', task_name='inspection', op_type='M',
            station='B' if separate else 'A', area_id='B' if separate else 'A',
            workstation_id='W2', std_duration=7, required_workers=3,
            work_load_score=8, rework_prob=.5)])
    if kind.startswith('area'):
        return AreaSimulationEngine(config, process, no_rest=kind == 'area-no-rest').run()
    if kind == 'legacy-no-rest':
        return SimulationEngineNoRest(config, process).run()
    return SimulationEngine(config, process).run()


@pytest.mark.parametrize('kind', ['legacy', 'area-plan', 'area-capacity', 'area-no-rest'])
@pytest.mark.parametrize('pipeline,flag', [(True, False), (True, True), (False, False)])
def test_area_is_serial_regardless_of_legacy_flag_and_resource_expansion(kind, pipeline, flag):
    result = run_case(kind, pipeline=pipeline, legacy_flag=flag)
    spans = defaultdict(list)
    for event in result.gantt_events:
        if event.event_type.value in {'NORMAL', 'REWORK', 'IN_PROGRESS', 'REST'} and event.duration > 0:
            spans[event.area_id].append((event.start_time, event.end_time))
    assert spans and result.engines_completed > 0
    for rows in spans.values():
        rows.sort()
        assert all(a[1] <= b[0] for a, b in zip(rows, rows[1:]))
    waits = [e for e in result.gantt_events if e.wait_reason == 'area']
    assert waits and all(e.wait_resource_ids == ['area:A'] for e in waits)
    assert all(e.end_time <= result.sim_duration for e in result.gantt_events)


@pytest.mark.parametrize('kind', ['legacy', 'area-plan', 'area-capacity', 'area-no-rest'])
def test_different_areas_can_work_in_parallel(kind):
    result = run_case(kind, separate=True)
    work = [e for e in result.gantt_events if e.event_type.value in {'NORMAL', 'REWORK', 'IN_PROGRESS'}]
    assert any(a.area_id != b.area_id and a.start_time < b.end_time and b.start_time < a.end_time
               for a in work for b in work)


def test_legacy_no_rest_also_uses_area_exclusion():
    result = run_case('legacy-no-rest')
    assert result['engines_completed'] > 0
    assert result['evaluation_context']['peak_working_workers'] <= 3
