"""Actual packaged PC: cold-host its relay and receive a paced 20 FPS labelled fixture."""
import json,os,re,subprocess,time,uuid
from pathlib import Path
from tools.unity_mirror20_delivery import PC
from tools.unity_mirror20_validation import OUT,IsolatedClock,nav
from tools.unity_mirror_auto_validation import http

def main():
    mock=IsolatedClock();base='http://127.0.0.1:8036/vr-mirror';checks={};log=OUT/'native_pc20.log'
    cfg=Path(os.environ['USERPROFILE'])/'AppData/LocalLow/DefaultCompany/MainProject/simpy_connection.json';original=cfg.read_bytes() if cfg.exists() else None
    process=None
    try:
        info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
        process=subprocess.Popen([str(PC/'EngineFactoryPC.exe'),'-batchmode','-logFile',str(log),'--simpy-server=http://127.0.0.1:8039','--vr-mirror-port=8036','--vr-mirror-editor-test'],cwd=os.environ['TEMP'],startupinfo=info)
        for _ in range(150):
            if process.poll() is not None:raise RuntimeError('Player exited')
            try:
                state=http(base,'/service')
                if state['host_count']==1:break
            except OSError:pass
            time.sleep(.5)
        else:raise TimeoutError('Packaged relay did not start')
        checks['cold_start_twenty_fps_service']=state['managed'] and http(base,'/state')['target_fps']==20
        image=(nav.PROJECT/'SimPyValidation/vr_mirror/editor_fixture.jpg').read_bytes();publisher='native20_'+uuid.uuid4().hex;frames=0;next_at=time.monotonic();end=next_at+20;errors=[]
        while time.monotonic()<end:
            state=http(base,'/publisher',dict(publisher_id=publisher,source='editor_test',detail='20 FPS native PC fixture, not headset'))
            if state['demand']:
                remaining=next_at-time.monotonic()
                if remaining>0:time.sleep(remaining)
                try:http(base,'/frame?publisher_id='+publisher+'&sequence='+str(frames),image=image);frames+=1
                except OSError as e:errors.append(str(e))
                next_at=time.monotonic()+.05
            else:time.sleep(.1)
        text=log.read_text(encoding='utf8',errors='replace');samples=[float(x) for x in re.findall(r'\[VR Mirror Receive\] ([0-9.]+) FPS',text)]
        checks['native_decodes_above_old_cap']=len(samples)>=2 and max(samples)>=15
        checks['first_frame_auto_popup']='[VR Mirror View] 编辑器测试画面' in text
        checks['no_upload_errors']=not errors
        checks['no_runtime_exception']=not any(s in text for s in ['NullReferenceException','MissingReferenceException','IndexOutOfRangeException'])
        process.terminate();process.wait(45);process=None
        for _ in range(35):
            try:http(base,'/service')
            except OSError:checks['last_client_exit_cleans_relay']=True;break
            time.sleep(.5)
        else:checks['last_client_exit_cleans_relay']=False
    finally:
        if process is not None and process.poll() is None:process.terminate();process.wait(45)
        mock.close()
        if original is None:cfg.unlink(missing_ok=True)
        else:cfg.write_bytes(original)
    result=dict(passed=all(checks.values()),checks=checks,received_fps_samples=samples,uploaded_frames=frames,hardware_tested=False,production_clock_used=False)
    result['errors']=errors
    (OUT/'native_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert result['passed']

if __name__=='__main__':main()
