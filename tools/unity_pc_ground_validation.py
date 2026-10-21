"""Verify PC model support against the actual rendered floor, not a fixed expected Y."""
from pathlib import Path
import json, os, shutil, subprocess
from tools import unity_pc_production_validation as v

OUT=Path('C:/xjp/simpy2/results/unity_validation/pc_ground_20261018')
PACKAGE=Path('C:/xjp/simpy2/builds/UnityPC_20261018_GroundFix')
CONTROL=OUT/'native_control'
v.OUT=OUT

def main():
    CONTROL.mkdir(parents=True,exist_ok=True)
    (CONTROL/'connection.json').write_text(json.dumps(dict(serverUrl='http://127.0.0.1:8042',vrMirrorMode='off')))
    proc=subprocess.Popen([str(PACKAGE/'EngineFactoryPC.exe'),'--simpy-server=http://127.0.0.1:8042','--pc-production-test='+str(CONTROL),'-screen-fullscreen','0','-screen-width','1920','-screen-height','1080','-logFile',str(OUT/'native.log')],cwd=os.environ['TEMP'])
    (OUT/'pid.json').write_text(json.dumps(dict(pid=proc.pid,exe=str(PACKAGE/'EngineFactoryPC.exe'))))
    try:
        runner=v.Runner(CONTROL)
        for name,station,minute in [('ground_overview','',2950),('ground_washer','S002',259),('ground_nitrogen','F012',1082),('ground_test','F013',2950),('ground_gantry','A001',2950)]:
            actions=[v.action('RestoreDefaultViews'),v.action('ClosePcDrawer')] if not station else [v.action('SelectStation',station)]
            data=runner.case(name,minute=minute,actions=actions,capture=True,settle=3)
            rows=data['ground'];bases=[r for r in rows if r['kind']=='station_base']
            runner.check(name+'_79_bases',len(bases)==79)
            runner.check(name+'_floor_zero',abs(data['floor_top'])<.001)
            failures=[r for r in rows if abs(r['gap'])>.002]
            (OUT/(name+'_gaps.json')).write_text(json.dumps(dict(passed=not failures,failures=failures,rows=rows),ensure_ascii=False,indent=2),encoding='utf-8')
            print(name,'support failures',failures,flush=True)
            runner.check(name+'_actual_support',not failures)
        runner.run()
        (OUT/'native/full_regression.json').write_bytes((OUT/'native/functional_summary.json').read_bytes())
        print('GROUND AND FUNCTIONAL CHECKS COMPLETE',flush=True)
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(30)

if __name__=='__main__':main()
