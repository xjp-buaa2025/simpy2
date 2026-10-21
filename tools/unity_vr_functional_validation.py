"""Read-only Editor VR LOD/AGV and PC regression; does not alter server playback."""
import json
from tools import unity_vr_optimization_validation as v

def main():
    v.control('vr_details_refresh','refresh')
    v.control('vr_details_open','open_scene',scene='Assets/Scenes/VR_Main.unity')
    v.control('vr_details_play','set_play',play=True)
    base=json.loads((v.OUT/'vr_after.geometry.json').read_text())
    p=next(s['position'] for s in base['stations'] if s['id']=='F012')
    checks={}
    for name,dist in [('near',8),('hold_near',24),('far',42),('hold_far',24)]:
        result=v.capture('vr_lod_'+name,actions=[v.review.action('SetVrReviewObserver',p['x'],1.65,p['z']-dist,0)])
        row=next(s for s in result['geometry']['stations'] if s['id']=='F012')
        checks[name]={'passed':result['ui']['passed'],'station':row,'synchronized':result['geometry']['synchronized'],'finished':result['geometry']['finished'],'unsupported_materials':result['geometry']['unsupported_materials']}
    result=v.capture('vr_agv_close',actions=[v.review.action('SetVrReviewObserver',59.1686,1.65,-31.6,323)])
    checks['agv']={'passed':result['ui']['passed'],'geometry':{k:result['geometry'][k] for k in ['bindings','finished','engine_renderers','unsupported_materials','missing_materials','cameras','screen_canvases','agv_center','agv_size','agv_renderers','agv_enabled_renderers']}}
    v.control('vr_details_stop','set_play',play=False)
    v.control('pc_regression_open','open_scene',scene='Assets/Scenes/PC_Main.unity')
    v.control('pc_regression_play','set_play',play=True)
    result=v.capture('pc_after_vr',role='PCController',actions=[v.review.action('SetFirstPersonWindowVisible',False),v.review.action('RestoreDefaultViews')])
    checks['pc']=result
    v.control('pc_regression_stop','set_play',play=False)
    checks['lod_passed']=all(checks[k]['station']['near']>0 and checks[k]['station']['far']==0 for k in ['near','hold_near']) and all(checks[k]['station']['near']==0 and checks[k]['station']['far']==2 for k in ['far','hold_far'])
    (v.OUT/'functional_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'lod_passed':checks['lod_passed'],'pc_passed':checks['pc']['ui']['passed'],'agv':checks['agv']},ensure_ascii=False),flush=True)
    
    if not checks["lod_passed"] or not checks["pc"]["ui"]["passed"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
