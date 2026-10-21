"""Repeat Rhino VR input/visual regression in the open Editor; never claims hardware success."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
from tools import unity_navigation_validation as nav
from tools import unity_pc_ui_validation as review

OUT = Path(__file__).resolve().parents[1] / 'results/unity_validation/rhino_fix_20261008'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--web-sync', action='store_true', help='Temporarily reschedule and restore the guarded web baseline using a running PC controller')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    nav.OUT = OUT
    review.OUTPUT = OUT
    protected = json.loads((OUT/'protected_hashes_before.json').read_text())
    nav.control('rhino_repeat_stop', 'set_play', play=False)
    nav.control('rhino_repeat_refresh', 'refresh')
    nav.control('rhino_repeat_open', 'open_scene', scene='Assets/Scenes/VR_Main.unity')
    nav.control('rhino_repeat_play', 'set_play', play=True)
    reports = {}
    try:
        folder = nav.PROJECT/'SimPyValidation/rhino_fix_20261008'
        folder.mkdir(parents=True, exist_ok=True)
        for name, operation in [('input_chain_final', 'input'), ('visual_final', 'visual'), ('agv_samples_final', 'agv')]:
            result = folder/(name+'.json')
            result.unlink(missing_ok=True)
            if (folder/'review.request.json').exists():
                raise RuntimeError('Pending Rhino review request')
            review.atomic_json(folder/'review.request.json', dict(name=name, operation=operation))
            report = nav.wait(result)
            shutil.copy2(result, OUT/result.name)
            reports[name] = report['passed']
            if not report['passed']:
                raise RuntimeError(str(report))
        nav.audit('navigation_final', 'test')
        for name, pose in [('vr_entrance_final', [-75, 1.7, -25, 70]), ('vr_middle_final', [-12, 1.7, 10, 70]), ('vr_inspection', [50, 1.7, 20, 100])]:
            nav.capture(name, 'VRViewer', [review.action('SetVrReviewObserver', *pose)])
    finally:
        nav.control('rhino_repeat_vr_stop', 'set_play', play=False)
    if args.web_sync:
        from tools import unity_pc_standalone_sync_validation as sync
        sync.OUT = OUT/'native_sync'
        sync.main()
    nav.control('rhino_repeat_pc', 'open_scene', scene='Assets/Scenes/PC_Main.unity')
    nav.control('rhino_repeat_pc_play', 'set_play', play=True)
    try:
        reports['pc'] = nav.audit('pc_final')['passed']
        nav.capture('pc_final', 'PCController', [review.action('SetFirstPersonWindowVisible', False), review.action('RestoreDefaultViews')])
    finally:
        nav.control('rhino_repeat_pc_stop', 'set_play', play=False)
    reports['protected'] = all(hashlib.sha256((nav.PROJECT/f).read_bytes()).hexdigest() == sha for f, sha in protected.items())
    reports['hardware_tested'] = False
    (OUT/'repeat_summary.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    if not all(v for k, v in reports.items() if k != 'hardware_tested'):
        raise SystemExit(1)
    print(json.dumps(reports, ensure_ascii=False))

if __name__ == '__main__':
    main()
