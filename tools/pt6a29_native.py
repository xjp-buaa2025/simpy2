"""Acceptance against the actual standalone player, including its local clock and UI captures."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import time

from pt6a29_delivery import atomic,wait,ROOT,OUT

PACKAGE=ROOT/'builds/UnityPC_20261021_PT6A29'
CONTROL=OUT/'native'

def command(name,**options):
    result=CONTROL/(name+'.json');result.unlink(missing_ok=True)
    atomic(CONTROL/'request.json',dict(name=name,**options))
    value=wait(result,30)
    if options.get('capture'):
        deadline=time.monotonic()+15
        while not (CONTROL/(name+'.png')).exists() and time.monotonic()<deadline:time.sleep(.1)
        assert (CONTROL/(name+'.png')).exists(),name
    return value

def views():
    layout=json.loads((ROOT/'data/factory_layout/pt6a29/layout.json').read_text(encoding='utf-8'))
    return [('pc_overview','oblique','',0),('pc_layout','top','',0),('pc_assembly','focus','WS-G01',0),
            ('pc_prefab','focus','WS-AGB01',0),('pc_test_cell','focus','WS-TC01',layout['timeline']['duration']-25),
            ('pc_cleaning','focus','WS-CL01',layout['timeline']['duration'])]

def capture_views():
    for name,camera,station,seconds in views():
        command(name+'_setup',operation='play',playing=False,camera=camera,station=station,seconds=seconds)
        time.sleep(.35)
        command(name,capture=True)
    command('delivery_ready_setup',operation='reset',camera='oblique',station='WS-G01')
    time.sleep(.35);command('delivery_ready',capture=True)
    print('Updated screenshots after camera and labels settled',flush=True)

def run(soak_seconds=0):
    CONTROL.mkdir(parents=True,exist_ok=True)
    exe=PACKAGE/'EngineFactoryPC.exe';assert exe.exists(),exe
    (CONTROL/'ready.json').unlink(missing_ok=True)
    proc=subprocess.Popen([str(exe),'--pt6a29-test='+str(CONTROL),'-screen-fullscreen','0','-screen-width','1920','-screen-height','1080','-logFile',str(OUT/'native_player.log')],cwd=str(PACKAGE))
    (OUT/'native_player_pid.json').write_text(json.dumps(dict(pid=proc.pid,exe=str(exe))),encoding='utf-8')
    ready=wait(CONTROL/'ready.json',90)
    checks=[]
    def check(name,ok,detail=''):checks.append(dict(name=name,passed=bool(ok),detail=detail))
    check('native_initial_paused',ready['ready'] and not ready['playing'] and ready['seconds']==0)
    check('native_29_stations_3_buffers',ready['stations']==29 and ready['buffers']==3)
    check('native_no_legacy_clients',ready['legacy_runtime_absent'] and ready['legacy_bootstrap_absent'])
    layout=json.loads((ROOT/'data/factory_layout/pt6a29/layout.json').read_text(encoding='utf-8'))
    for name,camera,station,seconds in views():
        command(name+'_setup',operation='play',playing=False,camera=camera,station=station,seconds=seconds)
        time.sleep(.3)
        value=command(name,capture=True)
        check(name+'_metadata',value['fixture_count']==137 and all(x['contained'] for x in value['fixtures']))
    initial=command('paused_start',operation='play',playing=False,seconds=120)
    time.sleep(1.2);frozen=command('paused_after')
    check('pause_holds_pose',initial['seconds']==frozen['seconds'] and initial['agv_position']==frozen['agv_position'] and initial['hook_position']==frozen['hook_position'])
    rates={}
    for speed in [1,5,10]:
        a=command('speed_'+str(speed)+'_start',operation='play',playing=True,seconds=100,speed=speed)
        started=time.monotonic();time.sleep(2);b=command('speed_'+str(speed)+'_end',operation='play',playing=False)
        elapsed=time.monotonic()-started;rate=(b['seconds']-a['seconds'])/elapsed;rates[speed]=rate
        check('native_speed_'+str(speed),abs(rate-speed)<speed*.25,dict(actual_rate=rate,requested=speed))
    reset=command('reset',operation='reset');check('reset_restores_defaults',not reset['playing'] and reset['seconds']==0 and reset['speed']==1 and reset['agv_position']==ready['agv_position'])
    # Inspect each handoff's move and each crane stroke, not merely a handful of selected times.
    snapshots=[]
    for i,step in enumerate(layout['timeline']['steps']):
        if step['kind'] not in ['loaded','gantry']:continue
        value=command('transfer_'+str(i),seconds=step['start']+step['duration']/2)
        snapshots.append(dict(index=i,kind=step['kind'],payload=value['payload'],agv_position=value['agv_position'],hook_position=value['hook_position']))
        check('transfer_'+str(i),value['step_kind']==step['kind'])
    final=command('complete',seconds=layout['timeline']['duration'],operation='play',playing=True)
    check('completion_is_paused',not final['playing'] and abs(final['seconds']-layout['timeline']['duration'])<.01)
    performance=[]
    if soak_seconds:
        command('soak_start',seconds=0,operation='play',playing=True,speed=10,camera='oblique')
        start=time.monotonic()
        while time.monotonic()-start<soak_seconds:
            time.sleep(min(10,max(.1,soak_seconds-(time.monotonic()-start))))
            v=command('soak_'+str(len(performance)));performance.append(dict(wall_seconds=time.monotonic()-start,fps=v['fps'],seconds=v['seconds'],playing=v['playing']))
        check('continuous_run_completed',proc.poll() is None,dict(wall_seconds=time.monotonic()-start,samples=len(performance)))
    command('delivery_ready',operation='reset',camera='oblique',station='WS-G01',capture=True)
    report=dict(passed=all(x['passed'] for x in checks),checks=checks,rates=rates,transfers=snapshots,performance=performance,pid=proc.pid,headset_tested=False)
    (OUT/'native_acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=report['passed'],checks=len(checks),failures=[x for x in checks if not x['passed']],rates=rates),ensure_ascii=False,indent=2),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--soak',type=int,default=0);p.add_argument('--capture-only',action='store_true');a=p.parse_args()
    if a.capture_only:capture_views()
    else:run(a.soak)
