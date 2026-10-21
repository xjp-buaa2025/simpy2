"""Real UDP/HTTP discovery and PC auto-window tests, clearly marked editor image fixture."""
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from tools import unity_navigation_validation as nav
from tools import unity_pc_ui_validation as ui
from tools.unity_equipment_face_audit import clock

OUT=nav.ROOT/'results/unity_validation/mirror_auto_20261013'
FOLDER=nav.PROJECT/'SimPyValidation/mirror_auto'
BASE='http://127.0.0.1:8011/vr-mirror'


def http(base,path,value=None,image=None):
    data=image if image is not None else json.dumps(value).encode() if value is not None else None
    with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers={'Content-Type':'image/jpeg' if image is not None else 'application/json'}),timeout=3) as r:
        body=r.read();return json.loads(body) if body else None


def audit(name,operation='audit',**args):
    FOLDER.mkdir(exist_ok=True);result=FOLDER/(name+'.json');result.unlink(missing_ok=True)
    ui.atomic_json(FOLDER/'review.request.json',dict(name=name,operation=operation,**args))
    r=nav.wait(result,60);assert r['success'],r;shutil.copy2(result,OUT/result.name);return r


def main():
    checks={};nav.OUT=OUT
    nav.control('auto_validation_stop','set_play',play=False);nav.control('auto_validation_refresh','refresh')
    nav.control('auto_validation_pc','open_scene',scene='Assets/Scenes/PC_Main.unity');nav.control('auto_validation_play','set_play',play=True)
    time.sleep(3)
    state=audit('pc_initial','allow_editor');checks['existing_relay_reused']=state['ready'];checks['no_empty_popup']=not state['visible']
    udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(('127.0.0.1',0));udp.settimeout(5)
    nonce='test_nonce_auto_v1';request=dict(protocol='simpy-vr-mirror',version=1,type='discover',id='editor_headset_test',name='编辑器测试头显',nonce=nonce)
    udp.sendto(json.dumps(request).encode(),('127.0.0.1',8012));offer=json.loads(udp.recv(2048));checks['real_udp_offer']=offer['type']=='offer' and offer['nonce']==nonce and offer['port']==8011
    audit('pc_pair','pair',device=request['id']);pair=json.loads(udp.recv(2048));checks['explicit_pair_targets_device']=pair['type']=='pair' and pair['device_id']==request['id'] and pair['id']==offer['id'];udp.close()
    image=(nav.PROJECT/'SimPyValidation/vr_mirror/editor_fixture.jpg').read_bytes()
    stop=threading.Event();sent=[0];errors=[];publisher_id='auto_editor_fixture_'+str(time.time_ns())
    def publisher():
        while not stop.is_set():
            try:
                s=http(BASE,'/publisher',dict(publisher_id=publisher_id,source='editor_test',detail='Editor-only auto-connect test'))
                if s['demand']:
                    http(BASE,'/frame?publisher_id='+publisher_id+'&sequence='+str(sent[0]),image=image);sent[0]+=1
            except Exception as e:errors.append(str(e))
            stop.wait(.16)
    worker=threading.Thread(target=publisher,daemon=True);worker.start()
    try:
        time.sleep(5);state=audit('pc_first_frame');checks['valid_frame_auto_opens']=state['visible'] and state['remote'] and state['live'] and state['frames']>2 and not state['local_camera'];checks['fixture_label_not_real_headset']='编辑器' in state['title']
        for w,h in [(1366,768),(1920,1080),(2560,1440)]:
            ui.OUTPUT=OUT
            result=ui.record('auto_pc_'+str(w),{'request':dict(name='auto_pc_'+str(w),width=w,height=h,seek_minute=-1,layout_only=True,capture=True,settle_seconds=1,settle_frames=20,actions=[]),'expected':dict(width=w,height=h,stations=79,role='PCController',synchronized=True,preview=True,firstperson_camera_enabled=False)},90)
            checks['layout_'+str(w)]=result['passed']
        audit('pc_user_closed','close');time.sleep(4);before=sent[0];time.sleep(2);state=audit('pc_stays_closed');checks['close_stops_demand_and_popup']=not state['visible'] and state['suppressed'] and not state['receiving'] and not http(BASE,'/state')['demand'] and sent[0]==before
        audit('pc_resume','resume');time.sleep(4);state=audit('pc_reopened');checks['manual_resume_receives']=state['live'] and state['visible']
        audit('pc_local_switch','local');time.sleep(4);state=audit('pc_local_after_wait');checks['local_mode_preserved']=state['local_camera'] and state['suppressed'] and not state['remote'] and not state['receiving']
    finally:stop.set();worker.join(5)
    checks['upload_errors']=not errors
    nav.audit('auto_pc_geometry_navigation')
    nav.control('auto_validation_pc_end','set_play',play=False)
    # No fake XR capture is injected. A discoverable PC must connect, then report XR absence.
    emitter_stop=threading.Event();port=[8031];device=[]
    def emitter():
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('0.0.0.0',8012));s.settimeout(.3)
        try:
            while not emitter_stop.is_set():
                try:
                    data,remote=s.recvfrom(2048);q=json.loads(data);device.append(q['id'])
                    s.sendto(json.dumps(dict(protocol='simpy-vr-mirror',version=1,type='offer',id='remembered_pc_fixture',name='只读测试 PC',nonce=q['nonce'],port=port[0])).encode(),remote)
                except socket.timeout:pass
        finally:s.close()
    cfg=nav.PROJECT/'SimPyValidation/mirror_auto_editor/VRViewer.json';original=cfg.read_bytes() if cfg.exists() else None
    exe=OUT/'portable/VRMirrorRelay/VRMirrorRelay.exe';processes=[]
    try:
        for p in [8031,8032]:processes.append(subprocess.Popen([str(exe),'--port',str(p)],cwd=os.environ['TEMP'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW))
        cfg.parent.mkdir(exist_ok=True);cfg.write_text(json.dumps(dict(serverUrl='http://10.33.244.29:8000',mirrorServerUrl='http://127.0.0.1:8099',vrMirrorEnabled=False,unrelatedSetting=37)),encoding='utf8')
        emitter_thread=threading.Thread(target=emitter,daemon=True);emitter_thread.start()
        nav.control('auto_validation_vr','open_scene',scene='Assets/Scenes/VR_Main.unity');nav.control('auto_validation_vr_play','set_play',play=True)
        time.sleep(9);state=audit('vr_discovered');checks['vr_udp_discovers_connects']=state['ready'] and state['paired_id']=='remembered_pc_fixture' and state['endpoint'].endswith(':8031') and bool(device)
        migrated=json.loads(cfg.read_text());checks['legacy_migrated_preserving_values']=migrated['serverUrl']=='http://10.33.244.29:8000' and migrated['unrelatedSetting']==37 and migrated['vrMirrorMode']=='auto' and Path(str(cfg)+'.before-auto.bak').exists()
        port[0]=8032;time.sleep(8);state=audit('vr_address_changed');checks['remembered_pc_new_address']=state['ready'] and state['paired_id']=='remembered_pc_fixture' and state['endpoint'].endswith(':8032')
        audit('vr_off','off');time.sleep(1);state=audit('vr_off_state');checks['explicit_off_stops_capture']=state['mode']=='off' and not state['publishing'] and not state['capture']
        audit('vr_on','on');time.sleep(5);state=audit('vr_on_state');checks['reenable_connects']=state['ready'] and state['publishing']
        audit('vr_pause','pause');time.sleep(1);state=audit('vr_paused_state');checks['sleep_stops_publisher']=not state['publishing'] and not state['capture']
        audit('vr_resume','unpause');time.sleep(5);state=audit('vr_resumed_state');checks['sleep_resume_reconnects']=state['ready'] and state['publishing']
        audit('vr_manual','manual',address='http://127.0.0.1:8031');time.sleep(4);state=audit('vr_manual_state');checks['manual_address_fallback']=state['ready'] and state['endpoint']=='http://127.0.0.1:8031' and state['paired_id']=='manual'
        http('http://127.0.0.1:8031/vr-mirror','/viewer',dict(viewer_id='no_xr_probe',active=True));time.sleep(1);state=audit('vr_no_xr');checks['no_fake_eye_capture']=not state['capture'] and not state['live']
        audit('vr_settings','settings');nav.capture('auto_vr_settings','VRViewer');nav.audit('auto_vr_navigation','test')
        nav.control('auto_validation_vr_end','set_play',play=False)
    finally:
        emitter_stop.set();emitter_thread.join(3)
        for p in processes:
            if p.poll() is None:p.terminate();p.wait(5)
        if original is not None:cfg.write_bytes(original)
        else:cfg.unlink(missing_ok=True)
        nav.control('auto_validation_restore_stop','set_play',play=False);nav.control('auto_validation_restore_pc','open_scene',scene='Assets/Scenes/PC_Main.unity')
    before=json.loads((OUT/'clock_guarded_before.json').read_text());after=clock();checks['shared_clock_preserved']=all(before[k]==after[k] for k in ['sim_id','minute','playing','speed','revision'])
    protected=json.loads((OUT/'protected_before.json').read_text());import hashlib
    checks['protected_scenes_quality']=all(hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in protected.items())
    result={'passed':all(checks.values()),'checks':checks,'errors':errors,'clock_after':after,'hardware_tested':False}
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2));assert result['passed']


if __name__=='__main__':main()
