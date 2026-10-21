"""Validate geometry/animation in both real entry scenes without changing the shared clock."""
import hashlib
import json
import shutil
from tools import unity_navigation_validation as nav
from tools import unity_pc_ui_validation as ui
from tools.unity_equipment_face_audit import clock

OUT=nav.ROOT/'results/unity_validation/gantry_20261012'
FOLDER=nav.PROJECT/'SimPyValidation/gantry'


def request(folder,file,name,timeout=120):
    result=folder/(name+'.json');result.unlink(missing_ok=True)
    ui.atomic_json(folder/file,dict(name=name))
    report=nav.wait(result,timeout);shutil.copy2(result,OUT/result.name)
    assert report['passed'],report
    return report


def main():
    nav.OUT=OUT
    nav.control('gantry_validate_stop','set_play',play=False)
    nav.control('gantry_validate_refresh','refresh')
    reports={}
    try:
        for role in ['pc','vr']:
            nav.control('gantry_'+role+'_scene','open_scene',scene='Assets/Scenes/'+('PC_Main' if role=='pc' else 'VR_Main')+'.unity')
            nav.control('gantry_'+role+'_run','set_play',play=True)
            reports[role+'_navigation']=nav.audit('gantry_'+role+'_navigation','test' if role=='vr' else 'audit')
            reports[role+'_motion']=request(FOLDER,'review.request.json',role+'_motion')
            shutil.copytree(FOLDER/(role+'_motion'),OUT/(role+'_motion'),dirs_exist_ok=True)
            reports[role+'_geometry']=request(nav.PROJECT/'SimPyValidation/equipment_geometry','request.json',role+'_geometry')
            nav.capture('gantry_'+role+'_overview','PCController' if role=='pc' else 'VRViewer')
            nav.control('gantry_'+role+'_end','set_play',play=False)
    finally:
        nav.control('gantry_return_stop','set_play',play=False)
        nav.control('gantry_return_pc','open_scene',scene='Assets/Scenes/PC_Main.unity')
    protected=json.loads((OUT/'protected_before.json').read_text())
    unchanged={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in protected.items()}
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    source_unchanged=hashlib.sha256(__import__('pathlib').Path(manifest['source']).read_bytes()).hexdigest()==manifest['sha256']
    before=json.loads((OUT/'clock_before.json').read_text());after=clock()
    clock_same=all(before[k]==after[k] for k in ['sim_id','minute','playing','speed','revision'])
    reports.update(protected=unchanged,source_unchanged=source_unchanged,clock_before=before,clock_after=after,clock_same=clock_same)
    reports['passed']=all(unchanged.values()) and source_unchanged and clock_same and all(reports[k]['passed'] for k in ['pc_motion','vr_motion','pc_geometry','vr_geometry','pc_navigation','vr_navigation'])
    (OUT/'validation.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
    assert reports['passed']
    print('PC/VR passed; source/scenes/settings/shared clock preserved',flush=True)


if __name__=='__main__':main()
