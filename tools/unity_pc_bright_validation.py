"""Native PC visual acceptance on isolated services; writes evidence alongside screenshots."""
from __future__ import annotations
import argparse,json,os,re,subprocess,time,uuid
from pathlib import Path
from tools import unity_pc_production_validation as v

OUT=Path('C:/xjp/simpy2/results/unity_validation/pc_bright_20261017')
CONTROL=OUT/'native_control'
PACKAGE=Path('C:/xjp/simpy2/builds/UnityPC_20261017_Bright')
SERVER_OUT=Path('C:/xjp/simpy2/results/unity_validation/pc_production_20261017')
v.OUT=OUT

def functional():
    r=v.Runner(CONTROL);r.run()
    r.check('all_screens_have_valid_materials',all(json.loads((r.delivery/(n+'.json')).read_text(encoding='utf-8-sig')).get('missing_materials')==0 for n in r.records))
    r.check('all_screens_have_supported_shaders',all(json.loads((r.delivery/(n+'.json')).read_text(encoding='utf-8-sig')).get('unsupported_shaders')==0 for n in r.records))
    r.check('source_factory_not_drawn_twice',all(json.loads((r.delivery/(n+'.json')).read_text(encoding='utf-8-sig')).get('visible_original_shell')==0 for n in r.records))
    r.save();(r.delivery/'full_regression.json').write_bytes((r.delivery/'functional_summary.json').read_bytes())

def integration():
    from tools import unity_pc_production_integration as i
    class BrightRunner(v.Runner):
        def __init__(self,*args,**kwargs):
            super().__init__(CONTROL);self.delivery=OUT/'integration';self.delivery.mkdir(exist_ok=True)
    i.OUT=SERVER_OUT;i.Runner=BrightRunner;i.main()
    import shutil
    shutil.copytree(SERVER_OUT/"integration",OUT/"integration",dirs_exist_ok=True)

def soak():
    CONTROL.mkdir(exist_ok=True)
    request=dict(name='soak15',minute=2950,width=1920,height=1080,profile_seconds=900,settle=3,capture=True,playing=True,speed=20,actions=[v.action('RestoreDefaultViews'),v.action('ClosePcDrawer'),v.action('SetFirstPersonWindowVisible',False)])
    end=CONTROL/'soak15.performance.json';end.unlink(missing_ok=True);(CONTROL/'soak15.segments.json').unlink(missing_ok=True)
    temp=CONTROL/'request.tmp';temp.write_text(json.dumps(request));temp.replace(CONTROL/'request.json')
    seen=0;deadline=time.monotonic()+1050
    while time.monotonic()<deadline:
        if end.exists():
            result=json.loads(end.read_text(encoding='utf-8-sig'));assert result['completed'] and result['seconds']>=900;print(json.dumps(result,indent=2),flush=True);return
        path=CONTROL/'soak15.segments.json'
        if path.exists():
            rows=json.loads(path.read_text(encoding='utf-8-sig'))['segments']
            if len(rows)>seen:
                seen=len(rows);print('segment',seen,rows[-1],flush=True)
        time.sleep(5)
    raise TimeoutError('15 minute native soak')

def mirror():
    from tools.unity_mirror20_validation import IsolatedClock,nav
    from tools.unity_mirror_auto_validation import http
    folder=OUT/'mirror_control';folder.mkdir(exist_ok=True);log=OUT/'mirror_native.log';base='http://127.0.0.1:8036/vr-mirror';mock=IsolatedClock();checks={};frames=0;errors=[];samples=[];proc=None;backoffs=0
    (folder/'connection.json').write_text(json.dumps(dict(serverUrl='http://127.0.0.1:8039',mirrorServerUrl='http://127.0.0.1:8036',vrMirrorMode='auto',pairedMirrorPcId='manual')))
    try:
        info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
        proc=subprocess.Popen([str(PACKAGE/'EngineFactoryPC.exe'),'-batchmode','--pc-production-test='+str(folder),'--simpy-server=http://127.0.0.1:8039','--vr-mirror-port=8036','--vr-mirror-editor-test','-logFile',str(log)],cwd=os.environ['TEMP'],startupinfo=info)
        deadline=time.monotonic()+100
        while time.monotonic()<deadline:
            if proc.poll() is not None:raise RuntimeError('Mirror fixture client exited')
            try:
                state=http(base,'/service')
                if state['host_count']==1:break
            except OSError:pass
            time.sleep(.5)
        else:raise TimeoutError('Portable relay cold start')
        checks['portable_relay_starts']=state['managed'] and http(base,'/state')['target_fps']==20
        jpeg=(nav.PROJECT/'SimPyValidation/vr_mirror/editor_fixture.jpg').read_bytes();publisher='bright_fixture_'+uuid.uuid4().hex;deadline=time.monotonic()+25;next_publisher=0
        while time.monotonic()<deadline:
            frame_started=time.monotonic()
            if frame_started>=next_publisher:
                state=http(base,'/publisher',dict(publisher_id=publisher,source='editor_test',detail='PC regression fixture; not a headset capture'));next_publisher=frame_started+1
            if state['demand']:
                try:http(base,'/frame?publisher_id='+publisher+'&sequence='+str(frames),image=jpeg);frames+=1
                except OSError as e:
                    if getattr(e,"code",None)==429:
                        backoffs+=1;time.sleep(.06)
                    else:errors.append(str(e))
            time.sleep(max(0,.05-(time.monotonic()-frame_started)))
        text=log.read_text(encoding='utf-8',errors='replace');samples=[float(n) for n in re.findall(r'\[VR Mirror Receive\] ([0-9.]+) FPS',text)]
        checks['native_receives_fixture']=bool(samples) and max(samples)>=15
        checks['first_frame_opens_window']='[VR Mirror View] 编辑器测试画面' in text
        checks['no_unexpected_upload_errors']=not errors
        checks['rate_limit_backoff_bounded']=backoffs<100
        checks['no_runtime_exception']=not any(s in text for s in ['NullReferenceException','MissingReferenceException','IndexOutOfRangeException'])
        proc.terminate();proc.wait(30);proc=None
        for _ in range(30):
            try:http(base,'/service')
            except OSError:checks['owned_relay_exits']=True;break
            time.sleep(.5)
        else:checks['owned_relay_exits']=False
    finally:
        if proc is not None and proc.poll() is None:proc.terminate();proc.wait(30)
        mock.close()
    result=dict(passed=all(checks.values()),checks=checks,uploaded_frames=frames,received_fps=samples,expected_rate_backoffs=backoffs,hardware_tested=False,errors=errors)
    (OUT/'mirror_regression.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));assert result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['functional','integration','soak','mirror']);a=p.parse_args();globals()[a.phase]()
