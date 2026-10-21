"""Native PC acceptance against an isolated live replay, using existing probes."""
from pathlib import Path
import re
from tools import unity_pc_production_validation as validation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/unity_validation/on_demand_workers_20261020'


def main():
    validation.OUT = OUT
    runner = validation.Runner(OUT / 'native_control')
    reset = [validation.action('RestoreDefaultViews'), validation.action('ClosePcDrawer'),
             validation.action('SetFirstPersonWindowVisible', False)]
    replay = runner.replay
    assert 'target_output' not in replay
    runner.check('on_demand_replay', replay['evaluation_context']['worker_supply_mode'] == 'on_demand')
    row = runner.case('overview', 2950, reset, capture=True)
    runner.check('same_simulation_and_all_79_stations', row['sim_id'] == replay['sim_id'] and row['stations'] == 79)
    runner.worker_check('overview', row)
    runner.check('roster_tracks_actual_demand', row['worker_roster'] == replay['resource_snapshot']['total_workers'])
    for event_kind in ('NORMAL', 'REST', 'IN_PROGRESS'):
        event = next(e for e in replay['events'] if e['event_type'] == event_kind and e['end_time'] > e['start_time'] + 1)
        minute = (event['start_time'] + event['end_time']) / 2
        row = runner.case(event_kind.lower(), minute, [validation.action('SelectStation', event['station_id'])], capture=True)
        runner.worker_check(event_kind.lower(), row)
    for tab in (1, 4):
        row = runner.case('details_' + str(tab), 2950, [validation.action('OpenPcDrawer', tab)], capture=True)
        texts = '\n'.join(t['text'] for t in row['texts'] if t['active'])
        runner.check('no_obsolete_production_target_' + str(tab), not re.search(r'月度目标|目标产出|已完工 / 目标|/ 目标|达成率', texts))
        if tab == 4:
            runner.check('area_uses_on_demand_labor_label', '按需到岗' in texts and '可用人员池利用率' not in texts)
    row = runner.case('horizon', replay['duration'], reset + [validation.action('OpenPcDrawer', 1)], capture=True)
    runner.check('finished_count_matches_scheduler_at_horizon', row['finished'] == replay['engines_completed'])
    unfinished = {w for e in replay['events'] if not e.get('is_complete', True) and abs(e['end_time']-replay['duration'])<.001 and e['event_type'] in ('NORMAL','REWORK','IN_PROGRESS','REST') for w in e.get('worker_ids', [])}
    runner.check('horizon_displays_only_recorded_unfinished_workers', {w['id'] for w in row['workers']} == unfinished)
    before = runner.case('paused_before', 2950, reset)
    after = runner.case('paused_after', settle=1.5)
    runner.check('pause_preserved', before['minute'] == after['minute'] and not after['playing'])
    row = runner.case('speed', 2950, playing=True, speed=60, settle=.5)
    runner.check('speed_preserved', row['playing'] and row['speed'] == 60 and row['minute'] > 2950)
    runner.case('complete', 2950, reset, playing=False, capture=True)
    runner.save()
    print('Native on-demand client acceptance passed', flush=True)


if __name__ == '__main__':
    main()
