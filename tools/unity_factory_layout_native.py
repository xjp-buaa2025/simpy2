"""Validate layout synchronization in the packaged Windows client, including offline cache."""
import json,os,re,subprocess,time,urllib.request
from pathlib import Path
from tools.unity_factory_layout_delivery import PC,OUT
BASE='http://127.0.0.1:8041/api/simulation/unity/'
def call(endpoint,method='GET',body=None):
    request=urllib.request.Request(BASE+endpoint,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'},method=method)
    return json.load(urllib.request.urlopen(request,timeout=15))
def main():
    cfg=Path(os.environ['USERPROFILE'])/'AppData/LocalLow/DefaultCompany/MainProject/simpy_connection.json'
    original=cfg.read_bytes() if cfg.exists() else None;process=None;checks={}
    def launch(log):
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        return subprocess.Popen([str(PC/'EngineFactoryPC.exe'),'-batchmode','-logFile',str(log),'--simpy-server=http://127.0.0.1:8041','--vr-mirror-port=8046'],cwd=os.environ['TEMP'],startupinfo=startup)
    def await_log(log,needle,seconds=75):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if process.poll() is not None:raise RuntimeError('Player exited')
            text=log.read_text(encoding='utf-8',errors='replace') if log.exists() else ''
            if needle in text:return text
            time.sleep(.5)
        raise TimeoutError(needle)
    try:
        log=OUT/'native_layout.log';revision=call('layout.json')['layout']['revision'];process=launch(log)
        await_log(log,'[Factory Layout] r'+str(revision))
        state=call('playback.json');owner=state['controller_id'];assert owner
        call('playback','PUT',dict(client_id=owner,sim_id=state['sim_id'],revision=state['revision'],minute=2950,playing=False,speed=20))
        doc=call('layout.json')['layout'];doc['stations'][0]['label']='原生PC布局同步测试'
        result=call('layout','PUT',dict(client_id=owner,sim_id=state['sim_id'],expected_revision=revision,layout=doc));revision=result['layout']['revision']
        text=await_log(log,'[Factory Layout] r'+str(revision));checks['native_receives_revision']=True
        time.sleep(3);checks['paused_clock_preserved']=abs(call('playback.json')['minute']-2950)<.1
        restored=call('layout/restore','POST',dict(client_id=owner,sim_id=state['sim_id'],expected_revision=revision,source='default'));revision=restored['layout']['revision'];await_log(log,'[Factory Layout] r'+str(revision));time.sleep(2)
        checks['no_runtime_exceptions']=not any(s in log.read_text(encoding='utf-8',errors='replace') for s in ['NullReferenceException','MissingReferenceException','IndexOutOfRangeException','[Layout]'])
        process.terminate();process.wait(40);process=None
        # Stop only our isolated test server, never the production service.
        os.kill(int((OUT/'test_server.pid').read_text()),15);time.sleep(1)
        offline=OUT/'native_layout_offline.log';process=launch(offline)
        await_log(offline,'[Factory Layout] r'+str(revision),90)
        checks['offline_cached_layout_and_replay']=True
        process.terminate();process.wait(40);process=None
        checks['packaged_default_layout']=(PC/'EngineFactoryPC_Data/StreamingAssets/factory_layout_default.json').exists()
    finally:
        if process is not None and process.poll() is None:process.terminate();process.wait(40)
        if original is None:cfg.unlink(missing_ok=True)
        else:cfg.write_bytes(original)
    report=dict(passed=all(checks.values()),checks=checks,headset_tested=False,production_clock_used=False)
    (OUT/'native_validation.json').write_text(json.dumps(report,indent=2));print(report,flush=True);assert report['passed']
if __name__=='__main__':main()
