"""Rendered Editor acceptance for worker progress; uses a private HTTP replay/clock.

Run with Unity Editor open. Never builds players or publishes to the normal service.
"""
from __future__ import annotations
import copy
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path('C:/AllUnityProjects/MainProject/MainProject')
OUT = ROOT / 'results/unity_validation/worker_progress_20261020'
UI = PROJECT / 'SimPyValidation/pc_ui'
PC = PROJECT / 'SimPyValidation/pc_production'
API = 'http://127.0.0.1:8046/api/simulation/unity/'
CHECKS = {}
RECORDS = {}


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def wait_json(path, timeout=100):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding='utf-8-sig'))
            except json.JSONDecodeError:
                pass
        time.sleep(.25)
    raise TimeoutError(str(path))


def check(name, passed):
    CHECKS[name] = bool(passed)
    complete = bool(CHECKS.get('all_editor_cases_complete'))
    atomic(OUT / 'validation_summary.json', dict(passed=complete and all(CHECKS.values()), complete=complete,
        checks=CHECKS, functional_check_count=sum(k != 'all_editor_cases_complete' for k in CHECKS),
        records=RECORDS, validation='Unity Editor only; no headset or player build',
        fixture_notes=dict(baseline='Existing pc_production_20261017/test_replay.json (2335 events, 15 workers)',
            cooperation_rework_in_progress='Isolated edge fixtures, not production scheduling results',
            occlusion='Temporary solid collider cube in Editor, removed after the test')))
    print(name, bool(passed), flush=True)
    if not passed:
        raise AssertionError(name)


def control(name, operation, **values):
    result = UI / (name + '.control.json')
    result.unlink(missing_ok=True)
    request = UI / 'control.request.json'
    if request.exists():
        wait_json(UI / 'worker_progress_compile.control.json')
        until = time.monotonic() + 90
        while request.exists() and time.monotonic() < until:
            time.sleep(.25)
    assert not request.exists(), 'Editor has an existing control request'
    atomic(request, dict(name=name, operation=operation, **values))
    r = wait_json(result)
    if not r['success']:
        raise RuntimeError(r.get('error', r))
    time.sleep(.7)


def action(method, *args):
    return dict(method=method, args=[str(a).lower() if isinstance(a, bool) else str(a) for a in args])


def record(name, folder=UI, **values):
    result = folder / (name + '.json')
    error = folder / (name + '.error.txt')
    result.unlink(missing_ok=True)
    error.unlink(missing_ok=True)
    (folder / (name + '.png')).unlink(missing_ok=True)
    request = folder / ('review.request.json' if folder == UI else 'request.json')
    assert not request.exists(), str(request)
    defaults = dict(name=name, capture=True, settle_seconds=.8, settle_frames=6, layout_only=True,
                    seek_minute=-1, width=1920, height=1080, actions=[])
    if folder == PC:
        defaults = dict(name=name, capture=True, settle=1.5, minute=-1, width=1920, height=1080,
                        speed=10, playing=False, actions=[])
    defaults.update(values)
    atomic(request, defaults)
    until = time.monotonic() + 110
    while time.monotonic() < until:
        if error.exists():
            raise RuntimeError(error.read_text(encoding='utf-8-sig'))
        if result.exists():
            r = wait_json(result)
            shutil.copy2(result, OUT / result.name)
            if defaults['capture']:
                png = folder / (name + '.png')
                for _ in range(80):
                    if png.exists() and png.stat().st_size > 2000:
                        shutil.copy2(png, OUT / png.name)
                        break
                    time.sleep(.1)
            RECORDS[name] = dict(minute=r['minute'], role=r.get('role', 'PCController'),
                visible=[x['worker_id'] for x in r['worker_progress'] if x['visible']])
            return r
        time.sleep(.25)
    raise TimeoutError(name)


def http(endpoint, value=None, method=None):
    req = urllib.request.Request(API + endpoint, None if value is None else json.dumps(value).encode(),
        {'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def vr_clock(minute):
    until = time.monotonic() + 16
    while True:
        try:
            state = http('playback/claim', {'client_id': 'worker_progress_editor_test'})
            break
        except urllib.error.HTTPError as error:
            if error.code != 409 or time.monotonic() > until:
                raise
            time.sleep(.5)
    return http('playback', dict(client_id=state['controller_id'], sim_id=state['sim_id'],
        revision=state['revision'], minute=minute, playing=False, speed=10), 'PUT')


def rows(report, visible=False):
    return {x['worker_id']: x for x in report['worker_progress'] if not visible or x['visible']}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = json.loads((ROOT / 'results/unity_validation/pc_production_20261017/test_replay.json').read_text(encoding='utf-8-sig'))
    baseline = copy.deepcopy(source)
    baseline['sim_id'] = 'worker-progress-' + uuid.uuid4().hex
    atomic(OUT / 'test_replay.json', baseline)
    backups = {}
    config_dir = PROJECT / 'SimPyValidation/mirror_auto_editor'
    for role in ('PCController', 'VRViewer'):
        path = config_dir / (role + '.json')
        backups[path] = path.read_bytes() if path.exists() else None
    atomic(OUT / 'connection_backups.json', {str(p): None if b is None else b.decode('utf-8-sig') for p, b in backups.items()})
    env = dict(os.environ, SIMPY_VALIDATION_OUT=str(OUT))
    log = (OUT / 'test_server.log').open('w', encoding='utf-8')
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tools.unity_pc_production_server:app', '--host', '127.0.0.1', '--port', '8046'],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(60):
            if server.poll() is not None:
                raise RuntimeError('Isolated server stopped; see test_server.log')
            try:
                http('replay.json')
                break
            except Exception:
                time.sleep(.25)
        else:
            raise TimeoutError('Isolated server did not start')
        control('wp_stop', 'set_play', play=False)
        for path, backup in backups.items():
            value = json.loads(backup.decode('utf-8-sig')) if backup else {}
            value.update(serverUrl='http://127.0.0.1:8046', vrMirrorMode='off')
            atomic(path, value)
        minute = 13.741785382528082
        vr_only = '--vr-only' in sys.argv
        if vr_only and (OUT / 'validation_summary.json').exists():
            previous = json.loads((OUT / 'validation_summary.json').read_text(encoding='utf-8-sig'))
            CHECKS.update({k: v for k, v in previous['checks'].items() if not k.startswith('vr_')})
            RECORDS.update(previous['records'])
        if not vr_only:
            control('wp_pc_open', 'open_scene', scene='Assets/Scenes/PC_Main.unity')
            control('wp_pc_content', 'open_scene_additive', scene='Assets/Scenes/FactoryContent.unity')
            control('wp_pc_play', 'set_play', play=True)
            minute = 13.741785382528082
            record('pc_loaded', PC, minute=minute, settle=3, capture=False)
            r = record('pc_two_workers', PC, minute=minute, actions=[action('SelectStation', 'S001')])
            people = rows(r, True)
            check('pc_per_worker_task_progress', set(people) == {'Worker_01', 'Worker_07'} and people['Worker_01']['percent'] == 50 and people['Worker_07']['percent'] == 4)
            check('pc_fill_matches_task_fraction', all(abs(x['rendered_fraction']-x['progress']) < .0001 for x in people.values()))
            check('pc_head_anchors_and_overlay', all(x['anchor']['y'] > x['worker_position']['y'] + 1.5 and x['canvas_mode'] == 'ScreenSpaceOverlay' and not x['blocked_by_chrome'] for x in people.values()))
            before = {k: v['progress'] for k, v in people.items()}
            r = record('pc_pause', PC, capture=False, settle=2)
            check('pause_freezes_progress', before == {k: v['progress'] for k, v in rows(r, True).items()})
            record('pc_seek_forward', PC, minute=20, capture=False)
            r = record('pc_seek_back', PC, minute=minute)
            check('seek_restores_progress', before == {k: v['progress'] for k, v in rows(r, True).items()})
            r = record('pc_orbit', PC, actions=[action('orbit', 90)])
            check('pc_orbit_keeps_worker_binding', set(rows(r, True)) == set(before))
            for width, height in [(1366, 768), (1920, 1080), (2560, 1440)]:
                r = record('pc_size_' + str(width), width=width, height=height)
                shown = list(rows(r, True).values())
                overlap = False
                for i, a in enumerate(shown):
                    for b in shown[i+1:]:
                        x, y = a['screen_rect'], b['screen_rect']
                        overlap |= x['x'] < y['x']+y['width'] and x['x']+x['width'] > y['x'] and x['y'] < y['y']+y['height'] and x['y']+x['height'] > y['y']
                check('pc_resolution_' + str(width), r['width'] == width and r['height'] == height and len(shown) == 2 and not overlap and all(not x['blocked_by_chrome'] for x in shown))
            r = record('pc_area', PC, actions=[action('FocusSelectedPcArea')])
            check('pc_area_hides_bars', not rows(r, True))
            r = record('pc_overview', PC, actions=[action('RestoreDefaultViews')])
            check('pc_overview_hides_bars', not rows(r, True))
            r = record('pc_rest', PC, minute=244.3086784941441, actions=[action('SelectStation', 'S002')])
            rest = rows(r)['Worker_02']
            check('rest_has_no_work_percentage', rest['visible'] and rest['state'] == '休息' and rest['text'] == '休息' and rest['rendered_fraction'] == 0)
            r = record('pc_speed', PC, minute=minute, playing=True, speed=2, actions=[action('SelectStation', 'S001')], settle=.6)
            check('speed_uses_shared_time', r['minute'] > minute and rows(r)['Worker_01']['progress'] > .5)
            r = record('pc_task_boundary', PC, minute=27.483570765056164, actions=[action('SelectStation', 'S001')])
            check('completed_task_not_left_at_100', all(not x['visible'] or x['event_id'] != '0' for x in r['worker_progress']))

            # Isolated edge fixtures retain the actual factory/station mapping.
            def publish_fixture(name, event, area_stats=None):
                data = copy.deepcopy(source)
                data['sim_id'] = 'worker-progress-' + name + '-' + uuid.uuid4().hex
                data['events'] = [event]
                if area_stats is not None:
                    data['area_stats'] = area_stats
                atomic(OUT / (name + '_fixture.json'), data)
                atomic(OUT / 'test_replay.json', data)
                time.sleep(4)
                return data

            event = copy.deepcopy(source['events'][0])
            event['worker_ids'] = ['Worker_01', 'Worker_07']
            publish_fixture('cooperation', event)
            r = record('pc_cooperation', PC, minute=minute, actions=[action('SelectStation', 'S001')])
            check('cooperation_shares_task_progress', len(rows(r, True)) == 2 and all(x['percent'] == 50 for x in rows(r, True).values()))
            event['event_type'] = 'REWORK'
            publish_fixture('rework', event)
            r = record('pc_rework', PC, minute=minute)
            check('rework_task_progress', len(rows(r, True)) == 2 and all(x['state'] == '返工' and x['percent'] == 50 for x in rows(r, True).values()))
            event.update(event_type='IN_PROGRESS', start_time=0, end_time=10, planned_end_time=20, is_complete=False)
            publish_fixture('in_progress', event, [dict(area_id='ST01', label='工区', equipment=[], wait_minutes={})])
            r = record('pc_planned_end', PC, minute=10)
            check('in_progress_keeps_planned_duration', len(rows(r, True)) == 2 and all(abs(x['progress']-.5) < .001 for x in rows(r, True).values()))
            atomic(OUT / 'test_replay.json', baseline)
            time.sleep(4)
            r = record('pc_reload', PC, minute=minute, actions=[action('SelectStation', 'S001')])
            check('replay_reload_clears_old_views', len(r['worker_progress']) == 15 and len(rows(r, True)) == 2 and len(set(rows(r))) == 15)
            control('wp_pc_stop', 'set_play', play=False)
        control('wp_vr_open', 'open_scene', scene='Assets/Scenes/VR_Main.unity')
        vr_clock(minute)
        control('wp_vr_play', 'set_play', play=True)
        r = record('vr_initial', sim_id=baseline['sim_id'])
        check('vr_only_world_space', all(x['canvas_mode'] == 'WorldSpace' for x in r['worker_progress']) and r['active_screen_canvases'] == 0)
        target = rows(r)['Worker_01']
        feet = target['worker_position']
        # Find an open viewing direction in the real factory, not an artificial empty scene.
        chosen = None
        def viewpoint(distance, angle, yaw_offset=0):
            h = 1.7
            radius = math.sqrt(distance*distance-h*h)
            x = feet['x'] + math.sin(math.radians(angle))*radius
            z = feet['z'] + math.cos(math.radians(angle))*radius
            yaw = math.degrees(math.atan2(feet['x']-x, feet['z']-z)) + yaw_offset
            return action('SetVrReviewObserver', x, feet['y']+h, z, yaw)
        for angle in range(0, 360, 45):
            vr_clock(minute)
            r = record('vr_direction_' + str(angle), actions=[viewpoint(7.5, angle)], capture=False)
            if rows(r)['Worker_01']['visible']:
                chosen = angle
                break
        check('vr_near_worker_visible', chosen is not None)
        actual = []
        for i, distance in enumerate([10.5, 9, 7.5, 9, 10.5]):
            vr_clock(minute)
            r = record('vr_distance_' + str(i), actions=[viewpoint(distance, chosen)])
            actual.append(rows(r)['Worker_01']['visible'])
        check('vr_distance_hysteresis', actual == [False, False, True, True, False])
        vr_clock(minute)
        r = record('vr_near', actions=[viewpoint(7.5, chosen)])
        check('vr_uses_individual_task_values', rows(r)['Worker_01']['percent'] == 50 and rows(r)['Worker_07']['percent'] == 4)
        vr_clock(minute)
        r = record('vr_turned_away', actions=[viewpoint(7.5, chosen, 180)])
        check('vr_behind_camera_hidden', not rows(r)['Worker_01']['visible'])
        vr_clock(minute)
        record('vr_before_occluder', actions=[viewpoint(7.5, chosen)], capture=False)
        control('wp_occluder_on', 'worker_progress_occluder', play=True)
        r = record('vr_physical_occlusion')
        check('vr_physical_occlusion_hides_bar', rows(r)['Worker_01']['in_range'] and not rows(r)['Worker_01']['visible'])
        control('wp_occluder_off', 'worker_progress_occluder', play=False)
        r = record('vr_after_occluder')
        check('vr_occluder_removal_restores_bar', rows(r)['Worker_01']['visible'])
        vr_clock(244.3086784941441)
        r = record('vr_rest_data', capture=False)
        check('vr_rest_uses_shared_status', rows(r)['Worker_02']['state'] == '休息' and rows(r)['Worker_02']['percent'] == -1)
        control('wp_vr_stop', 'set_play', play=False)
        control('wp_pc_reopen', 'open_scene', scene='Assets/Scenes/PC_Main.unity')
        control('wp_pc_recontent', 'open_scene_additive', scene='Assets/Scenes/FactoryContent.unity')
        # Let the temporary VR controller lease expire before PC reclaims it.
        time.sleep(12.2)
        control('wp_pc_replay', 'set_play', play=True)
        r = record('pc_reenter_play', PC, minute=minute, actions=[action('SelectStation', 'S001')])
        check('reenter_play_has_one_view_per_worker', len(r['worker_progress']) == 15 and len(rows(r, True)) == 2)
        check('all_editor_cases_complete', True)
    finally:
        try:
            control('wp_cleanup_stop', 'set_play', play=False)
        except Exception as error:
            print('Editor cleanup:', error, flush=True)
        for path, backup in backups.items():
            if backup is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(backup)
        server.terminate()
        server.wait(timeout=10)
        log.close()


if __name__ == '__main__':
    main()
