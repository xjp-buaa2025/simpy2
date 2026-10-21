"""Cold-start the actual PC package, auto decode a labelled fixture and clean up."""
import json, os, subprocess, threading, time, urllib.request, uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from tools.unity_mirror_auto_validation import OUT,http
from tools.unity_mirror_auto_delivery import PC

def main():
    checks={};base='http://127.0.0.1:8031/vr-mirror'
    cfg=os.path.join(os.environ['USERPROFILE'],'AppData/LocalLow/DefaultCompany/MainProject/simpy_connection.json')
    from pathlib import Path
    cfg=Path(cfg);original=cfg.read_bytes() if cfg.exists() else None
    log=OUT/'native_pc.log';conflict_log=OUT/'native_pc_conflict.log'
    def launch(port,path):
        info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
        return subprocess.Popen([str(PC/'EngineFactoryPC.exe'),'-batchmode','-screen-width','1366','-screen-height','768','-logFile',str(path),'--vr-mirror-port='+str(port),'--vr-mirror-editor-test','--simpy-server=http://127.0.0.1:8000'],cwd=os.environ['TEMP'],startupinfo=info)
    process=None;server=None
    try:
        process=launch(8031,log)
        for _ in range(120):
            if process.poll() is not None:raise RuntimeError('PC exited: '+log.read_text(errors='replace')[-3000:])
            try:
                state=http(base,'/service')
                if state['host_count']>=1:break
            except OSError:pass
            time.sleep(.5)
        else:raise TimeoutError('PC did not auto-host relay')
        checks['native_pc_auto_starts_bundled_service']=state['managed'] and state['host_count']==1
        checks['waiting_has_no_stale_popup']='实时画面' not in log.read_text(encoding='utf8',errors='replace')
        image=(Path('C:/AllUnityProjects/MainProject/MainProject/SimPyValidation/vr_mirror/editor_fixture.jpg')).read_bytes();pid='native_fixture_'+uuid.uuid4().hex
        frames=0;end=time.monotonic()+18
        while time.monotonic()<end:
            state=http(base,'/publisher',dict(publisher_id=pid,source='editor_test',detail='Native PC test fixture, not headset'))
            if state['demand']:http(base,'/frame?publisher_id='+pid+'&sequence='+str(frames),image=image);frames+=1
            time.sleep(.16)
        text=log.read_text(encoding='utf8',errors='replace');checks['native_pc_decodes_and_auto_opens']='[VR Mirror View] 编辑器测试画面' in text and frames>10
        checks['native_pc_no_runtime_exception']=not any(x in text for x in ['NullReferenceException','MissingReferenceException','IndexOutOfRangeException'])
        process.terminate();process.wait(45);process=None
        for _ in range(35):
            try:http(base,'/service')
            except OSError:checks['native_exit_releases_managed_service']=True;break
            time.sleep(.5)
        else:checks['native_exit_releases_managed_service']=False
        class Occupied(BaseHTTPRequestHandler):
            def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(b'{"schema_version":99}')
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',8033),Occupied);threading.Thread(target=server.serve_forever,daemon=True).start()
        process=launch(8033,conflict_log);time.sleep(14)
        text=conflict_log.read_text(encoding='utf8',errors='replace');checks['occupied_port_reports_error']='回传端口 8033 被其他服务占用' in text
        checks['occupied_service_untouched']=urllib.request.urlopen('http://127.0.0.1:8033/vr-mirror/state').read()==b'{"schema_version":99}'
    finally:
        if process is not None and process.poll() is None:process.terminate();process.wait(45)
        if server:server.shutdown();server.server_close()
        if original is None:cfg.unlink(missing_ok=True)
        else:cfg.write_bytes(original)
    result=dict(passed=all(checks.values()),checks=checks,frames_uploaded=frames,hardware_tested=False)
    (OUT/'native_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert result['passed']

if __name__=='__main__':main()
