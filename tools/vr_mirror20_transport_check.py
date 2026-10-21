"""Measure 20 FPS HTTP upload/download on an owned isolated frozen relay."""
import json,os,subprocess,time,uuid,urllib.error
from tools.unity_mirror20_validation import OUT,EXE,nav
from tools.unity_mirror_auto_validation import http

def main():
    base='http://127.0.0.1:8037/vr-mirror'
    p=subprocess.Popen([str(OUT/'portable_final/VRMirrorRelay/VRMirrorRelay.exe'),'--port','8037','--managed'],cwd=os.environ['TEMP'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    checks={}
    try:
        for _ in range(100):
            try:s=http(base,'/state');break
            except OSError:time.sleep(.1)
        else:raise TimeoutError('Frozen relay')
        checks['new_service_twenty']=s['target_fps']==20
        http(base,'/host',dict(client_id='fps_transport_a',active=True));http(base,'/host',dict(client_id='fps_transport_b',active=True))
        http(base,'/viewer',dict(viewer_id='fps_transport_viewer',active=True))
        publisher='fps_transport_'+uuid.uuid4().hex;http(base,'/publisher',dict(publisher_id=publisher,source='editor_test',detail='Isolated transport test, not headset'))
        image=(nav.PROJECT/'SimPyValidation/vr_mirror/editor_fixture.jpg').read_bytes()
        timestamps=[];next_at=time.monotonic();rate_retries=0
        import urllib.request
        for i in range(100):
            remaining=next_at-time.monotonic()
            if remaining>0:time.sleep(remaining)
            if i%20==0:http(base,'/viewer',dict(viewer_id='fps_transport_viewer',active=True))
            frame_at=time.monotonic()
            try:state=http(base,'/frame?publisher_id='+publisher+'&sequence='+str(i),image=image)
            except urllib.error.HTTPError as error:
                if error.code!=429:raise
                print('Rate retry',i,http(base,'/state')['frame_age_ms'],flush=True);rate_retries+=1;time.sleep(.05);state=http(base,'/frame?publisher_id='+publisher+'&sequence='+str(i),image=image)
            timestamps.append(time.monotonic())
            next_at=max(frame_at+.05,timestamps[-1]+.034)
            with urllib.request.urlopen(base+'/frame.jpg?after='+str(i-1)+'&publisher_id='+publisher) as response:assert response.read()==image and response.headers['X-Frame-Sequence']==str(i)
        fps=(len(timestamps)-1)/(timestamps[-1]-timestamps[0]);checks['twenty_fps_upload_download']=18<=fps<=21
        checks['only_latest_sequence']=state['sequence']==99
        http(base,'/host',dict(client_id='fps_transport_a',active=False));checks['second_host_keeps_alive']=http(base,'/service')['host_count']==1
        http(base,'/host',dict(client_id='fps_transport_b',active=False));p.wait(10);checks['last_host_closes']=p.returncode==0
    finally:
        if p.poll() is None:p.terminate();p.wait(10)
    result=dict(passed=all(checks.values()),checks=checks,http_fps=fps,frames=100,rate_retries=rate_retries,hardware_tested=False)
    (OUT/'transport_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert result['passed']

if __name__=='__main__':main()
