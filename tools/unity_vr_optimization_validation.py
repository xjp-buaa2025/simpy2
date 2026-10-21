"""Read-only clock regression and geometry audit for VR optimization.

The existing PC executable retains clock authority. Never change its playback.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path('C:/AllUnityProjects/MainProject/MainProject')
OUT=ROOT/'results/unity_validation/vr_optimization_20261007'
sys.path.insert(0,str(ROOT))
from tools import unity_pc_ui_validation as review


def wait(path,timeout=60):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if path.exists():
            try:return json.loads(path.read_text(encoding='utf-8-sig'))
            except json.JSONDecodeError:pass
        time.sleep(.25)
    raise TimeoutError(str(path))


def control(name,operation,**args):
    folder=PROJECT/'SimPyValidation/pc_ui'
    result=folder/(name+'.control.json')
    result.unlink(missing_ok=True)
    request=folder/'control.request.json'
    if request.exists():raise RuntimeError('An Editor control request is already pending')
    review.atomic_json(request,dict(name=name,operation=operation,**args))
    report=wait(result)
    if not report['success']:raise RuntimeError(report['error'])
    time.sleep(1)


def capture(name,role='VRViewer',actions=None):
    review.OUTPUT=OUT
    case={'request':{'name':name,'width':1920,'height':1080,'seek_minute':-1,
        'layout_only':True,'settle_seconds':2,'settle_frames':40,'capture':True,'actions':actions or []},
        'expected':{'width':1920,'height':1080,'stations':79,'role':role,
            'authority':False,'synchronized':True,'preview':False}}
    result=review.record(name,case,40)
    folder=PROJECT/'SimPyValidation/vr_performance'
    folder.mkdir(parents=True,exist_ok=True)
    report=folder/(name+'.json')
    report.unlink(missing_ok=True)
    review.atomic_json(folder/'audit.request.json',{'name':name})
    audit=wait(report,20)
    shutil.copy2(report,OUT/report.name.replace('.json','.geometry.json'))
    return {'ui':result,'geometry':audit}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=['baseline','after'],required=True)
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    control('vr_'+args.phase+'_stop','set_play',play=False)
    control('vr_'+args.phase+'_open','open_scene',scene='Assets/Scenes/VR_Main.unity')
    control('vr_'+args.phase+'_play','set_play',play=True)
    result=capture('vr_'+args.phase)
    (OUT/(args.phase+'_checks.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    control('vr_'+args.phase+'_finish','set_play',play=False)
    if not result['ui']['passed']:raise SystemExit(1)


if __name__=='__main__':main()
