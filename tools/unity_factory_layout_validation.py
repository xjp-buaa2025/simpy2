"""Exercise the actual PC layout UI and shared HTTP service on isolated port 8041."""
import json,time,shutil,urllib.request
from pathlib import Path
from tools.unity_navigation_validation import control,wait
from tools.unity_pc_ui_validation import atomic_json
ROOT=Path(__file__).resolve().parents[1];PROJECT=Path('C:/AllUnityProjects/MainProject/MainProject');OUT=ROOT/'results/unity_validation/layout_20261015';FOLDER=PROJECT/'SimPyValidation/factory_layout'

def review(name,operation='audit',path=None):
    result=FOLDER/(name+'.json');result.unlink(missing_ok=True)
    atomic_json(FOLDER/'review.request.json',dict(name=name,operation=operation,path=path or ''))
    r=wait(result,90);shutil.copy2(result,OUT/result.name)
    if not r['success']:raise AssertionError(r.get('error'))
    return r

def until(name,predicate,seconds=45):
    end=time.monotonic()+seconds;index=0
    while time.monotonic()<end:
        r=review(name+'_'+str(index));index+=1
        if predicate(r):
            (OUT/(name+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');return r
        time.sleep(.5)
    raise AssertionError((name,{k:v for k,v in r.items() if k!='geometry'}))

def server():return json.load(urllib.request.urlopen('http://127.0.0.1:8041/api/simulation/unity/layout.json'))

def pc():
    control('layout_test_pc_play','set_play',play=True)
    baseline=until('pc_default',lambda r:r['revision']==0 and '已同步' in r['status'])
    from tools import unity_pc_ui_validation as ui
    ui.OUTPUT=OUT
    for width,height in [(1366,768),(1920,1080),(2560,1440)]:
        request=dict(name='layout_panel_'+str(width),width=width,height=height,seek_minute=2950,speed=20,playing=False,layout_only=False,settle_frames=25,settle_seconds=1,capture=True,actions=[ui.action('OpenFactoryLayoutPanel')])
        result=ui.record(request['name'],{'request':request,'expected':{'width':width,'height':height,'stations':79,'role':'PCController','synchronized':True,'preview':False}},90)
        assert result['passed'],result
    review('pc_preview_begin','ImportFactoryLayout',str(OUT/'candidate.json'))
    preview=until('pc_preview',lambda r:r['preview'])
    assert server()['layout']['revision']==0
    byid={g['station_id']:g for g in preview['geometry']}
    assert abs(byid['A001']['root']['x']-35.7)<.01 and abs(byid['A001']['yaw']-315)<.1
    assert not byid['Q003']['visible'] and byid['A007']['model_key']=='washer_none'
    assert '布局测试' in byid['P011']['label'] and not byid['P004']['animation']
    review('pc_cancel','CancelFactoryLayoutPreview')
    canceled=until('pc_cancelled',lambda r:not r['preview'] and r['revision']==0)
    assert abs(canceled['minute']-preview['minute'])<.1
    assert next(g for g in canceled['geometry'] if g['station_id']=='A001')['root']['x']==next(g for g in baseline['geometry'] if g['station_id']=='A001')['root']['x']
    review('pc_second_preview','ImportFactoryLayout',str(OUT/'candidate.json'))
    until('pc_second_ready',lambda r:r['preview'])
    review('pc_publish','PublishFactoryLayoutPreview')
    applied=until('pc_applied',lambda r:r['revision']==1 and not r['preview'])
    assert server()['layout']['revision']==1 and abs(applied['minute']-preview['minute'])<.1
    control('layout_test_pc_stop','set_play',play=False)
    return dict(pc=True,preview_local_only=True,cancel_preserves_clock=True,publish_preserves_clock=True,resolutions=[1366,1920,2560])

def vr():
    control('layout_test_vr_open','open_scene',scene='Assets/Scenes/VR_Main.unity');control('layout_test_vr_play','set_play',play=True)
    applied=until('vr_applied',lambda r:r['vr'] and r['revision']==1 and '已同步' in r['status'])
    pc=json.loads((OUT/'pc_applied.json').read_text());p={g['station_id']:g for g in pc['geometry']}
    assert applied['obstacles']>=79
    for g in applied['geometry']:
        assert all(abs(g['root'][a]-p[g['station_id']]['root'][a])<.01 for a in ['x','y','z'])
        assert abs(g['yaw']-p[g['station_id']]['yaw'])<.1
        assert g['visible']==p[g['station_id']]['visible']
    assert abs(applied['minute']-pc['minute'])<.1
    return dict(vr=True,same_79_positions=True,same_headings=True,vr_collision_count=applied['obstacles'],headset_tested=False)

if __name__=='__main__':
    result=pc();result.update(vr());(OUT/'unity_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(result)
