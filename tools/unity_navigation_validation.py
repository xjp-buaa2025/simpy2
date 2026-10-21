"""Exercise station orientation and VR navigation in the open Unity Editor."""
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request

from tools import unity_pc_ui_validation as review

ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path('C:/AllUnityProjects/MainProject/MainProject')
OUT=ROOT/'results/unity_validation/navigation_20261008'

def wait(path, timeout=120):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if path.exists():
            try:return json.loads(path.read_text(encoding='utf-8-sig'))
            except json.JSONDecodeError:pass
        time.sleep(.25)
    raise TimeoutError(str(path))

def control(name, operation, **args):
    folder=PROJECT/'SimPyValidation/pc_ui'; result=folder/(name+'.control.json')
    result.unlink(missing_ok=True)
    if (folder/'control.request.json').exists():raise RuntimeError('Pending Editor request')
    review.atomic_json(folder/'control.request.json',dict(name=name,operation=operation,**args))
    report=wait(result)
    if not report['success']:raise RuntimeError(report['error'])
    time.sleep(1)

def audit(name, operation='audit'):
    folder=PROJECT/'SimPyValidation/navigation_20261008';folder.mkdir(parents=True,exist_ok=True)
    result=folder/(name+'.json');result.unlink(missing_ok=True)
    review.atomic_json(folder/'review.request.json',dict(name=name,operation=operation))
    report=wait(result);shutil.copy2(result,OUT/result.name)
    print(name+': '+str(report.get('passed'))+' '+str([(c['name'],c['detail']) for c in report.get('checks',[]) if not c['passed']]),flush=True)
    if not report['passed']:raise RuntimeError(report.get('error') or str([c for c in report.get('checks',[]) if not c['passed']]))
    return report

def capture(name, role, actions=None):
    review.OUTPUT=OUT
    case={'request':{'name':name,'width':1920,'height':1080,'seek_minute':-1,'layout_only':True,'settle_seconds':2,'settle_frames':40,'capture':True,'actions':actions or []},
          'expected':{'width':1920,'height':1080,'stations':79,'role':role,'synchronized':True,'preview':False}}
    result=review.record(name,case,90)
    print(name+': UI '+str(result['passed']),flush=True)
    if not result['passed']:raise RuntimeError(str(result))
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    control('nav_stop','set_play',play=False)
    control('nav_refresh','refresh')
    generated=PROJECT/'SimPyValidation/vr_performance/generation.json';generated.unlink(missing_ok=True)
    (generated.parent/'generate.request').write_text('generate')
    result=wait(generated,180)
    if not result['success']:raise RuntimeError(str(result))
    shutil.copy2(generated,OUT/'vr_generation.json');print('VR generated',flush=True)
    control('nav_vr_open','open_scene',scene='Assets/Scenes/VR_Main.unity')
    control('nav_vr_play','set_play',play=True)
    vr=audit('vr_navigation_tests','test')
    capture('vr_navigation_default','VRViewer')
    audit('vr_valid_ray','aim');capture('vr_navigation_ray','VRViewer');audit('vr_ray_end','end')
    for sid in ['S002','S003','F012','F013']:
        p=next(row['position'] for row in vr['stations'] if row['id']==sid)
        yaw=next(row['expected'] for row in vr['stations'] if row['id']==sid)
        import math
        x=p['x']+math.sin(math.radians(yaw))*5
        z=p['z']+math.cos(math.radians(yaw))*5
        capture('vr_front_'+sid,'VRViewer',[review.action('SetVrReviewObserver',x,1.7,z,(yaw+180)%360)])
    control('nav_vr_stop','set_play',play=False)
    control('nav_pc_open','open_scene',scene='Assets/Scenes/PC_Main.unity')
    control('nav_pc_play','set_play',play=True)
    pc=audit('pc_orientation')
    capture('pc_factory_corrected','PCController',[review.action('SetFirstPersonWindowVisible',False),review.action('RestoreDefaultViews')])
    capture('pc_station_details','PCController',[review.action('SelectStation','F012')])
    capture('pc_agv_follow','PCController',[review.action('ToggleAgvCamera')])
    control('nav_pc_stop','set_play',play=False)
    hashes=json.loads((OUT/'protected_hashes_before.json').read_text())
    protected={f:hashlib.sha256((PROJECT/f).read_bytes()).hexdigest()==sha for f,sha in hashes.items()}
    checks={'vr':vr['passed'],'pc':pc['passed'],'same_heading_positions':all(a['id']==b['id'] and a['yaw']==b['yaw'] and a['position']==b['position'] for a,b in zip(vr['stations'],pc['stations'])),'protected':protected}
    checks['passed']=all([checks['vr'],checks['pc'],checks['same_heading_positions'],all(protected.values())])
    (OUT/'validation_summary.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False),flush=True)
    if not checks['passed']:raise SystemExit(1)

if __name__=='__main__':main()
