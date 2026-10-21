"""Targeted legacy service regression after fixing the editor-only endpoint switch."""
import json,os,subprocess,time,shutil
from tools.unity_mirror20_validation import OUT,IsolatedClock,bench,nav,ui,auto

def main():
    mock=IsolatedClock();cfg=nav.PROJECT/'SimPyValidation/mirror_auto_editor/PCController.json';old=cfg.read_bytes() if cfg.exists() else None;process=None
    nav.control('legacy20_stop','set_play',play=False)
    try:
        cfg.write_text(json.dumps(dict(serverUrl='http://127.0.0.1:8039',mirrorServerUrl='http://127.0.0.1:8032',vrMirrorMode='auto')),encoding='utf8')
        process=subprocess.Popen([str(nav.ROOT/'builds/UnityPC_20261013_AutoConnect/VRMirrorService/VRMirrorRelay.exe'),'--port','8032'],cwd=os.environ['TEMP'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        nav.control('legacy20_refresh','refresh');nav.control('legacy20_open','open_scene',scene='Assets/Scenes/PC_Main.unity');nav.control('legacy20_play','set_play',play=True)
        time.sleep(3);auto.OUT=OUT;auto.audit('legacy20_endpoint','endpoint',address='http://127.0.0.1:8032');auto.audit('legacy20_allow','allow_editor');time.sleep(4)
        bench('legacy20_start','start',address='http://127.0.0.1:8032');time.sleep(12);r=bench('legacy20_running')
        checks=dict(old_relay_compatible=r['target']==8 and r['sent']>20 and 0<r['sent_fps']<=8.5 and r['live'],old_relay_diagnostic='目标8' in r['status'])
        auto.audit('legacy20_menu','menu');ui.OUTPUT=OUT
        result=ui.record('legacy20_diagnostic_ui',{'request':dict(name='legacy20_diagnostic_ui',width=1366,height=768,seek_minute=-1,layout_only=True,capture=True,settle_seconds=1,settle_frames=15,actions=[]),'expected':dict(width=1366,height=768,stations=79,role='PCController',synchronized=True,preview=True,firstperson_camera_enabled=False)},90)
        report=json.loads((OUT/'legacy20_diagnostic_ui.json').read_text(encoding='utf-8-sig'));checks['old_service_warning_visible']=any('旧服务限速' in t['text'] for t in report['texts']) and result['passed'] and not result['warnings']['pc_text_overflow']
        bench('legacy20_stop_pipeline','stop')
    finally:
        nav.control('legacy20_end','set_play',play=False);mock.close()
        if process and process.poll() is None:process.terminate();process.wait(10)
        if old is None:cfg.unlink(missing_ok=True)
        else:cfg.write_bytes(old)
    result=dict(passed=all(checks.values()),checks=checks,hardware_tested=False)
    (OUT/'legacy_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert result['passed']
    main=json.loads((OUT/'validation.json').read_text());main['checks'].update(checks);main['passed']=all(main['checks'].values());main['legacy_rerun_report']='legacy_validation.json';(OUT/'validation.json').write_text(json.dumps(main,indent=2));assert main['passed']

if __name__=='__main__':main()
