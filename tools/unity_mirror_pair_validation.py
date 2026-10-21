"""Multiple actual UDP offers, explicit pairing and no-broadcast fallback."""
import json, os, socket, subprocess, threading, time
from tools.unity_mirror_auto_validation import OUT,audit
from tools import unity_navigation_validation as nav

def main():
    cfg=nav.PROJECT/'SimPyValidation/mirror_auto_editor/VRViewer.json';original=cfg.read_bytes() if cfg.exists() else None
    stop=threading.Event();pair=threading.Event();remote=[None];nonce=[None];offers=[True];checks={}
    def emitter():
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('0.0.0.0',8012));s.settimeout(.2)
        try:
            while not stop.is_set():
                try:
                    data,ep=s.recvfrom(2048);q=json.loads(data);remote[0]=ep;nonce[0]=q['nonce']
                    if offers[0]:
                        for i,p in [('pc_a',8031),('pc_b',8032)]:s.sendto(json.dumps(dict(protocol='simpy-vr-mirror',version=1,type='offer',id=i,name=i,nonce=q['nonce'],port=p)).encode(),ep)
                except socket.timeout:pass
                if pair.is_set() and remote[0]:
                    s.sendto(json.dumps(dict(protocol='simpy-vr-mirror',version=1,type='pair',id='pc_b',name='pc_b',nonce=nonce[0],device_id='pair_test_device',port=8032)).encode(),remote[0]);pair.clear()
        finally:s.close()
    processes=[];thread=threading.Thread(target=emitter,daemon=True)
    try:
        for p in [8031,8032]:processes.append(subprocess.Popen([str(OUT/'portable/VRMirrorRelay/VRMirrorRelay.exe'),'--port',str(p)],cwd=os.environ['TEMP'],creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        cfg.write_text(json.dumps(dict(serverUrl='http://127.0.0.1:8000',mirrorServerUrl='http://127.0.0.1:8099',vrMirrorMode='auto',mirrorDeviceId='pair_test_device',pairedMirrorPcId='')),encoding='utf8')
        thread.start();nav.control('pair_vr_open','open_scene',scene='Assets/Scenes/VR_Main.unity');nav.control('pair_vr_play','set_play',play=True)
        time.sleep(9);r=audit('vr_multiple_candidates');checks['multiple_requires_selection']=not r['ready'] and r['peers']==2 and not r['publishing']
        pair.set();time.sleep(6);r=audit('vr_multiple_selected');checks['explicit_target_pair_connects']=r['ready'] and r['paired_id']=='pc_b' and r['endpoint'].endswith(':8032')
        offers[0]=False;nav.control('pair_vr_stop','set_play',play=False);nav.control('pair_vr_restart','set_play',play=True)
        time.sleep(6);r=audit('vr_no_broadcast_fallback');checks['remembered_address_without_broadcast']=r['ready'] and r['paired_id']=='pc_b' and r['endpoint'].endswith(':8032') and r['peers']==0
        processes[1].terminate();processes[1].wait(5);time.sleep(6);r=audit('vr_network_lost');checks['loss_stops_publisher']=not r['ready'] and not r['publishing']
        processes[1]=subprocess.Popen([str(OUT/'portable/VRMirrorRelay/VRMirrorRelay.exe'),'--port','8032'],cwd=os.environ['TEMP'],creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        time.sleep(7);r=audit('vr_network_restored');checks['network_return_reconnects']=r['ready'] and r['publishing']
    finally:
        stop.set()
        if thread.is_alive():thread.join(3)
        nav.control('pair_restore_stop','set_play',play=False);nav.control('pair_restore_pc','open_scene',scene='Assets/Scenes/PC_Main.unity')
        for p in processes:
            if p.poll() is None:p.terminate();p.wait(5)
        if original is None:cfg.unlink(missing_ok=True)
        else:cfg.write_bytes(original)
    result=dict(passed=all(checks.values()),checks=checks,hardware_tested=False)
    (OUT/'pair_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert result['passed']

if __name__=='__main__':main()
