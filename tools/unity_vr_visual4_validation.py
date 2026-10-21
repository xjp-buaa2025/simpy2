"""Verify the VR original-model presentation in the open Unity Editor; no hardware claims."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
from tools import unity_navigation_validation as nav
from tools import unity_pc_ui_validation as review

OUT=Path(__file__).resolve().parents[1]/'results/unity_validation/vr_visual_v4_20261008'
POSES={'entrance':[-75,1.7,-25,70],'middle':[-12,1.7,10,70],'inspection':[50,1.7,20,100],'washer':[-92,1.7,-11,0],
       'pressure_washer':[-94,1.7,0,180],'pressure_cold':[-42,1.7,-17,0],'pressure_all':[0,3,10,270]}

def request(folder,name,operation):
    folder=nav.PROJECT/'SimPyValidation'/folder
    folder.mkdir(exist_ok=True)
    result=folder/(name+'.json');result.unlink(missing_ok=True)
    if (folder/'review.request.json').exists():raise RuntimeError('Pending review')
    review.atomic_json(folder/'review.request.json',dict(name=name,operation=operation))
    report=nav.wait(result,90);shutil.copy2(result,OUT/result.name)
    print(name,report.get('passed'),flush=True)
    if not report.get('passed'):raise RuntimeError(str(report))
    return report

def geometry(name):
    folder=nav.PROJECT/'SimPyValidation/vr_performance'
    result=folder/(name+'.json');result.unlink(missing_ok=True)
    review.atomic_json(folder/'audit.request.json',dict(name=name))
    report=nav.wait(result,60);shutil.copy2(result,OUT/(name+'.geometry.json'))
    print(name,report['frustum_triangles'],'triangles',report['batches'],'batches',report['setpass'],'SetPass',flush=True)
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['vr','pc','all'],default='all');parser.add_argument('--web-sync',action='store_true');args=parser.parse_args()
    OUT.mkdir(exist_ok=True);nav.OUT=review.OUTPUT=OUT
    summary={};nav.control('visual4_test_stop','set_play',play=False);nav.control('visual4_test_refresh','refresh')
    if args.phase in ['vr','all']:
        nav.control('visual4_test_open','open_scene',scene='Assets/Scenes/VR_Main.unity');nav.control('visual4_test_play','set_play',play=True)
        try:
            summary['visual']=request('vr_visual_v4','visual_final','visual')['passed']
            summary['input']=request('rhino_fix_20261008','input_final','input')['passed']
            summary['agv']=request('rhino_fix_20261008','agv_final','agv')['passed']
            summary['navigation']=nav.audit('navigation_final','test')['passed']
            metrics=[]
            for name,pose in POSES.items():
                nav.capture('after_'+name,'VRViewer',[review.action('SetVrReviewObserver',*pose),review.action('SetVrReviewHudVisible',True)])
                metrics.append(geometry('after_'+name))
            summary['pressure_geometry']=all(r['frustum_triangles']<=500000 for r in metrics)
            summary['editor_batches']=all(r['batches']<=250 and r['setpass']<=80 for r in metrics)
            for name in ['entrance','middle','washer']:
                nav.capture('clean_'+name,'VRViewer',[review.action('SetVrReviewObserver',*POSES[name]),review.action('SetVrReviewHudVisible',False)])
        finally:nav.control('visual4_test_vr_stop','set_play',play=False)
    if args.web_sync:
        from tools import unity_pc_standalone_sync_validation as sync
        sync.OUT=OUT/'native_sync';sync.main();summary['web_sync']=all(json.loads((sync.OUT/'checks.json').read_text()).values())
    if args.phase in ['pc','all']:
        nav.control('visual4_test_pc','open_scene',scene='Assets/Scenes/PC_Main.unity');nav.control('visual4_test_pc_play','set_play',play=True)
        try:
            summary['pc']=nav.audit('pc_final')['passed'];nav.capture('pc_final','PCController',[review.action('SetFirstPersonWindowVisible',False),review.action('RestoreDefaultViews')])
        finally:nav.control('visual4_test_pc_stop','set_play',play=False)
    before=json.loads((OUT/'protected_hashes_before.json').read_text());summary['pc_assets_unchanged']=all(hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in before.items())
    summary['hardware_tested']=False
    (OUT/('validation_'+args.phase+'.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if not all(v for k,v in summary.items() if k!='hardware_tested'):raise SystemExit(1)

if __name__=='__main__':main()
