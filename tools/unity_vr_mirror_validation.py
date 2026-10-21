"""Exercise the real relay and Unity receiver with an explicitly labelled Editor VR frame."""
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
import urllib.error
import urllib.request
from tools import unity_navigation_validation as nav
from tools import unity_pc_ui_validation as review

OUT = nav.ROOT / 'results/unity_validation/vr_mirror_20261009'
BASE = 'http://127.0.0.1:8011/vr-mirror'
FOLDER = nav.PROJECT / 'SimPyValidation/vr_mirror'


def http(path, value=None, image=None):
    data = image if image is not None else json.dumps(value).encode() if value is not None else None
    headers = {'Content-Type': 'image/jpeg' if image is not None else 'application/json'}
    with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, headers=headers), timeout=3) as response:
        body = response.read()
        return json.loads(body) if body else None


def audit(name, operation='audit'):
    FOLDER.mkdir(exist_ok=True)
    path = FOLDER / (name + '.json')
    path.unlink(missing_ok=True)
    review.atomic_json(FOLDER / 'review.request.json', dict(name=name, operation=operation))
    report = nav.wait(path, 60)
    shutil.copy2(path, OUT / path.name)
    assert report['success'], report
    print(name, report, flush=True)
    return report


def capture(name, actions=None, width=1920, height=1080):
    review.OUTPUT=OUT
    case={'request':{'name':name,'width':width,'height':height,'seek_minute':-1,'layout_only':True,'settle_seconds':2,'settle_frames':35,'capture':True,'actions':actions or []},
          'expected':{'width':width,'height':height,'stations':79,'role':'PCController','synchronized':True,'preview':name!='pc_closed','firstperson_camera_enabled':name in ['pc_local_default','pc_local_restored']}}
    result=review.record(name,case,90)
    assert result['passed'], result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    checks = {}
    protected = ['Assets/Scenes/PC_Main.unity','Assets/Scenes/FactoryContent.unity','Assets/Scenes/VR_Main.unity','Assets/Scenes/FactoryVRContent.unity','ProjectSettings/QualitySettings.asset','ProjectSettings/GraphicsSettings.asset']
    before={p:hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest() for p in protected}
    (OUT/'protected_hashes_before.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    with urllib.request.urlopen('http://127.0.0.1:8000/api/simulation/unity/playback.json') as r:
        (OUT/'clock_before.json').write_bytes(r.read())
    nav.OUT = OUT
    nav.control('mirror_stop_prepare','set_play',play=False)
    nav.control('mirror_refresh3','refresh')
    nav.control('mirror_vr_open','open_scene',scene='Assets/Scenes/VR_Main.unity')
    nav.control('mirror_vr_start','set_play',play=True)
    fixture=audit('fixture','fixture')
    checks['mirror_shader_2d']=fixture['blit_2d']
    checks['mirror_shader_array_slice']=fixture['blit_array']
    image=(FOLDER/'editor_fixture.jpg').read_bytes()
    shutil.copy2(FOLDER/'editor_fixture.jpg',OUT/'editor_fixture.jpg')
    nav.control('mirror_vrstop','set_play',play=False)
    nav.control('mirror_pcopen','open_scene',scene='Assets/Scenes/PC_Main.unity')
    nav.control('mirror_pcplay','set_play',play=True)
    stop = threading.Event()
    errors = []
    def publish():
        sequence = 0
        while not stop.is_set():
            try:
                state=http('/publisher',dict(publisher_id='editor_fixture_v1',source='editor_test',detail='Editor VR image'))
                if state['demand']:
                    http('/frame?publisher_id=editor_fixture_v1&sequence='+str(sequence),image=image)
                    sequence+=1
            except urllib.error.HTTPError as error:
                if error.code not in (409,429):errors.append(str(error))
            except Exception as error:errors.append(str(error))
            stop.wait(.13)
    worker=threading.Thread(target=publish,daemon=True)
    try:
        capture('pc_local_default',[review.action('SetFirstPersonWindowVisible',True)])
        local=audit('pc_local_default_state')
        checks['local_camera_original']=local['local_camera'] and not local['remote']
        worker.start()
        for w,h in [(1366,768),(1920,1080),(2560,1440)]:
            capture('pc_remote_'+str(w),[review.action('SetFirstPersonRemoteMode',True)],w,h)
            state=audit('pc_remote_'+str(w)+'_state')
            checks['receive_'+str(w)]=state['live'] and state['received_frames']>=3 and not state['local_camera'] and state['source']=='editor_test' and '编辑器' in state['title']
        stop.set();worker.join(4);time.sleep(3.2)
        capture('pc_remote_disconnected')
        state=audit('pc_disconnected_state')
        checks['stale_frame_hidden']=not state['live'] and not state['local_camera'] and not state['texture_width']
        capture('pc_local_restored',[review.action('SetFirstPersonRemoteMode',False)])
        state=audit('pc_local_restored_state')
        checks['local_restored']=state['local_camera'] and not state['remote'] and not state['receiving']
        capture('pc_closed',[review.action('SetFirstPersonWindowVisible',False)])
        state=audit('pc_closed_state')
        time.sleep(3.2)
        checks['closed_no_render_no_demand']=not state['local_camera'] and not state['receiving'] and not http('/state')['demand']
        nav.audit('pc_orientation_regression')
        checks['fixture_upload_errors']=not errors
    finally:
        stop.set()
        if worker.is_alive():worker.join(4)
        nav.control('mirror_pcstop','set_play',play=False)
    # A PC demand without XR must yield an explicit error, not a fake local camera feed.
    nav.control('mirror_noxr_open','open_scene',scene='Assets/Scenes/VR_Main.unity')
    nav.control('mirror_noxr_play','set_play',play=True)
    try:
        time.sleep(3.2)
        audit('publisher_started','publisher_start')
        for _ in range(4):http('/viewer',dict(viewer_id='editor_demand_probe',active=True));time.sleep(.6)
        state=audit('publisher_without_xr')
        checks['no_xr_no_fake_capture']=not state['sent_frames'] and 'XR 未运行' in state['status'] and not state['capture_resources']
        http('/viewer',dict(viewer_id='editor_demand_probe',active=False))
        time.sleep(1.5)
        state=audit('publisher_idle')
        checks['idle_no_capture_resources']=not state['capture_resources']
        audit('publisher_stopped','publisher_stop')
    finally:nav.control('mirror_noxr_stop','set_play',play=False)
    nav.control('mirror_return_pc','open_scene',scene='Assets/Scenes/PC_Main.unity')
    checks['protected_resources_unchanged']=all(hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==v for p,v in before.items())
    checks['passed']=all(checks.values())
    (OUT/'checks.json').write_text(json.dumps(dict(checks=checks,hardware_tested=False),ensure_ascii=False,indent=2),encoding='utf-8')
    print(checks,flush=True)
    assert checks['passed'], checks

if __name__=='__main__':main()
