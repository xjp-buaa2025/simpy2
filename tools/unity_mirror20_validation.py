"""Exercise actual capture/worker encoding/HTTP/decode with an isolated read-only clock."""
import json,os,shutil,socket,subprocess,threading,time,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tools import unity_navigation_validation as nav
from tools import unity_pc_ui_validation as ui
from tools import unity_mirror_auto_validation as auto

OUT=nav.ROOT/'results/unity_validation/mirror20_20261014'
FOLDER=nav.PROJECT/'SimPyValidation/mirror20'
EXE=OUT/'portable/VRMirrorRelay/VRMirrorRelay.exe'

def bench(name,operation='audit',address='http://127.0.0.1:8031'):
    FOLDER.mkdir(exist_ok=True);result=FOLDER/(name+'.json');result.unlink(missing_ok=True)
    ui.atomic_json(FOLDER/'review.request.json',dict(name=name,operation=operation,address=address))
    r=nav.wait(result,60);shutil.copy2(result,OUT/result.name);assert r['success'],r;return r

class IsolatedClock:
    def __init__(self):
        self.replay=json.loads((nav.PROJECT/'Assets/StreamingAssets/simpy_replay.json').read_text())
        self.minute=2950.;self.playing=False;self.revision=1;self.requests=[]
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def reply(self,status,data):
                body=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def do_GET(self):
                owner.requests.append(self.path)
                if '/replay.json' in self.path:self.reply(200,owner.replay)
                elif '/playback.json' in self.path:self.reply(200,owner.state())
                elif '/sync_status.json' in self.path:self.reply(200,dict(success=True,sim_id=owner.replay['sim_id']))
                else:self.reply(404,{})
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length',0)));self.reply(409,{'detail':'Isolated read-only clock fixture'})
            def do_PUT(self):self.rfile.read(int(self.headers.get('Content-Length',0)));self.reply(403,{})
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',8039),Handler);threading.Thread(target=self.server.serve_forever,daemon=True).start()
    def state(self):return dict(schema_version=1,sim_id=self.replay['sim_id'],minute=self.minute,playing=self.playing,speed=60,duration=self.replay['duration'],revision=self.revision,controller_id='fixture_readonly',controller_connected=True,server_unix_ms=time.time()*1000)
    def close(self):self.server.shutdown();self.server.server_close()

def main():
    nav.OUT=OUT;ui.OUTPUT=OUT;auto.OUT=OUT
    mock=IsolatedClock();processes=[];original={};checks={}
    configs=nav.PROJECT/'SimPyValidation/mirror_auto_editor'
    nav.control('mirror20_stop','set_play',play=False)
    for role in ['PCController','VRViewer']:
        path=configs/(role+'.json');original[path]=path.read_bytes() if path.exists() else None
        path.write_text(json.dumps(dict(serverUrl='http://127.0.0.1:8039',mirrorServerUrl='http://127.0.0.1:8031',vrMirrorMode='auto',pairedMirrorPcId='manual')),encoding='utf8')
    try:
        for exe,port in [(EXE,8031),(nav.ROOT/'builds/UnityPC_20261013_AutoConnect/VRMirrorService/VRMirrorRelay.exe',8032)]:
            processes.append(subprocess.Popen([str(exe),'--port',str(port)],cwd=os.environ['TEMP'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW))
        nav.control('mirror20_refresh_all','refresh');nav.control('mirror20_open_pc','open_scene',scene='Assets/Scenes/PC_Main.unity');nav.control('mirror20_play_pc','set_play',play=True)
        time.sleep(3);auto.audit('mirror20_endpoint','endpoint',address='http://127.0.0.1:8031');auto.audit('mirror20_allow','allow_editor');time.sleep(4)
        r=bench('worker_codec','codec');checks['background_codec_and_deadline']=r['codec_ok'] and r['remaining_ok']
        udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(('127.0.0.1',0));udp.settimeout(5);q=dict(protocol='simpy-vr-mirror',version=1,type='discover',id='mirror20_fixture_device',name='20FPS editor fixture',nonce='mirror20')
        udp.sendto(json.dumps(q).encode(),('127.0.0.1',8034));offer=json.loads(udp.recv(2048));checks['automatic_discovery']=offer['port']==8031 and offer['nonce']=='mirror20';udp.close()
        bench('pipeline_start','start');time.sleep(14);r=bench('pipeline_running');checks['actual_pipeline_sends_and_decodes']=r['sent']>25 and r['received']>25 and r['live'] and r['visible'] and r['remote'];checks['pipeline_delivers_measured_rate']=r['received']>=r['sent']*.8;checks['cpu_encoding_and_diagnostics']=r['encode_ms']>0 and r['read_ms']>=0 and r['upload_ms']>0 and r['bytes']>0
        state=auto.http('http://127.0.0.1:8031/vr-mirror','/state');checks['explicit_fixture_identity']=state['source']=='editor_test';checks['service_target_twenty']=state['target_fps']==20
        for w,h in [(1366,768),(1920,1080),(2560,1440)]:
            result=ui.record('mirror20_pc_'+str(w),{'request':dict(name='mirror20_pc_'+str(w),width=w,height=h,seek_minute=-1,layout_only=True,capture=True,settle_seconds=1,settle_frames=20,actions=[]),'expected':dict(width=w,height=h,stations=79,role='PCController',synchronized=True,preview=True,firstperson_camera_enabled=False)},90)
            checks['layout_'+str(w)]=result['passed']
        # Check diagnostics drawer with the longest real pipeline status.
        auto.audit('mirror20_open_diagnostics','menu')
        result=ui.record('mirror20_diagnostics',{'request':dict(name='mirror20_diagnostics',width=1366,height=768,seek_minute=-1,layout_only=True,capture=True,settle_seconds=1,settle_frames=15,actions=[]),'expected':dict(width=1366,height=768,stations=79,role='PCController',synchronized=True,preview=True,firstperson_camera_enabled=False)},90);checks['diagnostics_layout']=result['passed'] and not result['warnings']['pc_text_overflow'] and not result['warnings']['chrome_outside_screen']
        auto.audit('mirror20_closed','close');time.sleep(5);r=bench('pipeline_no_viewer');checks['close_releases_capture']=not r['capture'] and not r['live'] and not r['visible'];time.sleep(2);state=auto.http('http://127.0.0.1:8031/vr-mirror','/state');checks['no_viewer_no_demand']=not state['demand'];auto.audit('mirror20_resume','resume');time.sleep(6);r=bench('pipeline_reopened');checks['reopen_receives']=r['live'] and r['visible']
        bench('pipeline_stop','stop');r=bench('pipeline_stopped');checks['stop_releases_resources']=not r['publishing'] and not r['capture'];time.sleep(3);r=bench('stale_hidden');checks['stale_hidden']=not r['live']
        bench('sync_start','sync');time.sleep(7);r=bench('sync_running');checks['sync_fallback_two_fps']=r['sync'] and 0<r['sent_fps']<=2.5 and r['live'];bench('sync_stop','stop');time.sleep(4)
        bench('failure_start','failure');time.sleep(7);r=bench('failure_fallback');checks['async_error_falls_back']=r['sync'] and r['sent']>0 and r['live'];bench('failure_stop','stop');time.sleep(4)
        auto.audit('legacy_endpoint','endpoint',address='http://127.0.0.1:8032');time.sleep(4);bench('legacy_pipeline','start',address='http://127.0.0.1:8032');time.sleep(8);r=bench('legacy_running');checks['old_relay_compatible']=r['target']==8 and 0<r['sent_fps']<=8.5 and r['live'];checks['old_relay_diagnostic']='8' in r['status'];bench('legacy_stop','stop');time.sleep(4)
        auto.audit('local_roaming','local');r=auto.audit('local_roaming_state');checks['local_roaming_preserved']=r['local_camera'] and not r['remote'] and not r['receiving'];nav.audit('mirror20_pc_geometry')
        initial=mock.replay;mock.replay=json.loads(json.dumps(initial));mock.replay['sim_id']='mirror20-replan-fixture';mock.replay['target_output']=4;mock.replay['engines_completed']=4;mock.replay['work_hours_per_day']=7;mock.replay['work_days_per_month']=26;mock.replay['duration']=10920
        mock.replay['events']=[e for e in mock.replay['events'] if e['engine_id']<=4];mock.replay['transfers']=[t for t in mock.replay['transfers'] if t['engine_id']<=4];mock.replay['engine_completion']=[e for e in mock.replay['engine_completion'] if e['engine_id']<=4];mock.minute=10920.;mock.revision+=1
        time.sleep(8);r=bench('replanned_sync');checks['replan_clock_calendar_output']=r['sim_id']=='mirror20-replan-fixture' and r['finished']==4 and r['month_end']==4 and '第26工作日' in r['calendar'] and '07:00' in r['calendar']
        mock.replay=initial;mock.minute=2950.;mock.revision+=1;time.sleep(6)
        nav.control('mirror20_pc_end','set_play',play=False);nav.control('mirror20_vr_open','open_scene',scene='Assets/Scenes/VR_Main.unity');nav.control('mirror20_vr_play','set_play',play=True);time.sleep(5)
        nav.audit('mirror20_vr_navigation','test');checks['vr_navigation']=True
        r=auto.audit('vr_no_xr_capture');checks['no_fake_headset_capture']=not r['capture']
        nav.capture('mirror20_vr_overview','VRViewer')
        checks['isolated_clock_used']=bool(mock.requests) and all('api/simulation/unity/' in p for p in mock.requests)
    finally:
        nav.control('mirror20_restore_stop','set_play',play=False);nav.control('mirror20_restore_pc','open_scene',scene='Assets/Scenes/PC_Main.unity')
        for path,data in original.items():
            if data is None:path.unlink(missing_ok=True)
            else:path.write_bytes(data)
        mock.close()
        for p in processes:
            if p.poll() is None:p.terminate();p.wait(10)
    import hashlib
    protected=json.loads((OUT/'protected_before.json').read_text());checks['protected_scenes_quality']=all(hashlib.sha256((nav.PROJECT/p).read_bytes()).hexdigest()==sha for p,sha in protected.items())
    result=dict(passed=all(checks.values()),checks=checks,hardware_tested=False,production_clock_used=False)
    (OUT/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert result['passed']

if __name__=='__main__':main()
