"""Visual axis audit and post-repair checks using the open Unity Editor."""
import hashlib
import json
import shutil
import sys
from pathlib import Path
from tools import unity_navigation_validation as nav
from tools import unity_pc_ui_validation as review
from tools.unity_equipment_face_audit import clock, FOLDER, PROTECTED

OUT=nav.ROOT/'results/unity_validation/model_axes_fixed_20261009'
def photograph(name, sid='P013', **options):
    path=FOLDER/(name+'.json');path.unlink(missing_ok=True)
    review.atomic_json(FOLDER/'request.json',dict(name=name,id=sid,**options))
    report=nav.wait(path,60)
    if not report['success']:raise RuntimeError(report)
    for ext in ['json','png']:shutil.copy2(FOLDER/(name+'.'+ext),OUT/(name+'.'+ext))
    print(name,report['model'],flush=True)
    return report
def inspect():
    OUT.mkdir(parents=True,exist_ok=True)
    before={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest() for p in PROTECTED}
    (OUT/'protected_before.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    (OUT/'clock_before.json').write_text(json.dumps(clock(),indent=2),encoding='utf-8')
    backup=OUT/'source_before';backup.mkdir(exist_ok=True)
    for f in ['Assets/Scripts/SimPyReplayDressing.cs','Assets/Scripts/SimPyReplayPCVisuals.cs','Assets/Editor/SimPyNavigationReview.cs']:
        shutil.copy2(nav.PROJECT/f,backup/Path(f).name)
    photos=[]
    for index in range(10):
        for axis in ([-90,0] if index in [0,1,2,3,4,5,7] else [0]):
            photos.append(photograph(f'asset_{index}_axis{axis}',original=True,asset=index,axis=axis))
    rows=json.loads((nav.PROJECT/'PlantSimulationImport/process_library/station_models.json').read_text(encoding='utf-8-sig'))['stations']
    kinds={}
    for row in rows:kinds.setdefault(row['asset'],row['id'])
    for kind in ['WorkTable','Inspection','PressingMachine','Packing','Repair','RobotKuka']:photos.append(photograph('library_'+kind,original=True,library=True,libraryName=kind,axis=0))
    (OUT/'asset_inspection.json').write_text(json.dumps(photos,ensure_ascii=False,indent=2),encoding='utf-8')
    nav.control('axis_inspect_stop','set_play',play=False)
def geometry(role):
    folder=nav.PROJECT/'SimPyValidation/equipment_geometry';folder.mkdir(exist_ok=True)
    name='fixed_'+role+'_geometry';result=folder/(name+'.json');result.unlink(missing_ok=True)
    review.atomic_json(folder/'request.json',dict(name=name))
    report=nav.wait(result,60);shutil.copy2(result,OUT/result.name)
    print(name,report['passed'],[(x['id'],x) for x in report.get('rows',[]) if not all(x[k] for k in ['upright','grounded','attachments_supported','inside_table','screen_faces_aisle'])],flush=True)
    if not report['passed']:raise RuntimeError(report)
    return report
def verify():
    nav.OUT=OUT
    nav.control('axis_verify_stop','set_play',play=False);nav.control('axis_verify_refresh','refresh')
    checks={}
    try:
        for role in ['pc','vr']:
            nav.control('axis_verify_'+role+'_open','open_scene',scene='Assets/Scenes/'+('PC_Main' if role=='pc' else 'VR_Main')+'.unity')
            nav.control('axis_verify_'+role+'_play','set_play',play=True)
            checks[role]=geometry(role)
            checks[role+'_headings']=nav.audit('fixed_'+role+'_headings')
            for sid in ['P011','P013','P062','D042','G023','F013','S002','S003','P012','F012','F062']:
                photograph('fixed_'+role+'_'+sid,sid)
            nav.capture('fixed_'+role+'_overview','PCController' if role=='pc' else 'VRViewer')
            nav.control('axis_verify_'+role+'_stop','set_play',play=False)
    finally:
        nav.control('axis_verify_return_stop','set_play',play=False);nav.control('axis_verify_return_pc','open_scene',scene='Assets/Scenes/PC_Main.unity')
    before=json.loads((OUT/'protected_before.json').read_text())
    checks['protected']={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in before.items()}
    checks['clock_after']=clock()
    checks['same_fixed_headings']=checks['pc_headings']['stations']==checks['vr_headings']['stations']
    checks['passed']=checks['pc']['passed'] and checks['vr']['passed'] and checks['same_fixed_headings'] and all(checks['protected'].values())
    (OUT/'validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    assert checks['passed']
if __name__=='__main__':verify() if 'verify' in sys.argv else inspect()
