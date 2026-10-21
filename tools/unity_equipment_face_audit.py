"""Photograph actual equipment faces in both scenes without changing shared playback."""
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path
from tools import unity_navigation_validation as nav
from tools import unity_pc_ui_validation as review

OUT=nav.ROOT/'results/unity_validation/equipment_faces_20261009'
FOLDER=nav.PROJECT/'SimPyValidation/equipment_faces'
PROTECTED=['Assets/Scenes/PC_Main.unity','Assets/Scenes/FactoryContent.unity','Assets/Scenes/VR_Main.unity','Assets/Scenes/FactoryVRContent.unity','ProjectSettings/QualitySettings.asset','ProjectSettings/GraphicsSettings.asset']
def clock():
    with urllib.request.urlopen('http://127.0.0.1:8000/api/simulation/unity/playback.json',timeout=5) as r:return json.load(r)
def photo(role,sid,rear=False,overview=False):
    name=f'{role}_{sid}_'+('overview' if overview else 'rear' if rear else 'front')
    path=FOLDER/(name+'.json');path.unlink(missing_ok=True)
    review.atomic_json(FOLDER/'request.json',dict(name=name,id=sid,rear=rear,overview=overview))
    report=nav.wait(path,60)
    if not report['success']:raise RuntimeError(report)
    for extension in ['json','png']:shutil.copy2(FOLDER/(name+'.'+extension),OUT/(name+'.'+extension))
    print(name,report['model'],report['primaryEuler'],report['lod'],flush=True)
    return report
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    before={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest() for p in PROTECTED}
    cb=clock();(OUT/'clock_before.json').write_text(json.dumps(cb,indent=2),encoding='utf-8')
    nav.control('face_stop','set_play',play=False);nav.control('face_refresh','refresh')
    reports=[]
    try:
        for role in ['pc','vr']:
            nav.control('face_'+role+'_open','open_scene',scene='Assets/Scenes/'+('PC_Main' if role=='pc' else 'VR_Main')+'.unity')
            nav.control('face_'+role+'_play','set_play',play=True)
            for sid in ['P011','P013','P062','D042','G023','F013']:
                reports.append(photo(role,sid))
                if sid in ['P011','P013']:reports.append(photo(role,sid,rear=True))
            if role=='pc':
                reports.append(photo(role,'P011',overview=True));reports.append(photo(role,'P013',overview=True))
            nav.control('face_'+role+'_stop','set_play',play=False)
    finally:
        nav.control('face_restore_stop','set_play',play=False)
        nav.control('face_restore_pc','open_scene',scene='Assets/Scenes/PC_Main.unity')
    ca=clock()
    result={'photos':reports,'protected':{p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in before.items()},'clock_before':cb,'clock_after':ca}
    (OUT/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Complete',flush=True)
if __name__=='__main__':main()
