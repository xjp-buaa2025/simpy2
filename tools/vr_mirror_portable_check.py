"""Run the frozen service with no Python paths and exercise actual lifecycle/HTTP."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/unity_validation/mirror_auto_20261013'
EXE=OUT/'portable/VRMirrorRelay/VRMirrorRelay.exe'


def main():
    checks={}
    env={'SystemRoot':os.environ['SystemRoot'],'WINDIR':os.environ['WINDIR'],'PATH':str(Path(os.environ['SystemRoot'])/'System32'),'TEMP':tempfile.gettempdir(),'TMP':tempfile.gettempdir()}
    base='http://127.0.0.1:8031/vr-mirror'
    def http(path,value=None):
        data=json.dumps(value).encode() if value is not None else None
        with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'}),timeout=2) as r:return json.load(r)
    with tempfile.TemporaryDirectory(prefix='vr-relay-isolated-') as cwd:
        bundle=Path(cwd)/'服务 测试'/ 'VRMirrorService'
        shutil.copytree(EXE.parent,bundle)
        with (OUT/'portable_console.log').open('w',encoding='utf8') as log:
            process=subprocess.Popen([str(bundle/'VRMirrorRelay.exe'),'--port','8031','--managed','--log-file',str(Path(cwd)/'service.log')],cwd=cwd,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                for _ in range(60):
                    if process.poll() is not None:raise RuntimeError((OUT/'portable_console.log').read_text(encoding='utf8'))
                    try:
                        state=http('/state');break
                    except OSError:time.sleep(.2)
                else:raise TimeoutError('Portable relay startup')
                checks['no_python_or_workspace_required']=state['schema_version']==1
                checks['managed_info']=http('/service')['managed']
                checks['two_hosts']=http('/host',{'client_id':'test_a','active':True})['host_count']==1 and http('/host',{'client_id':'test_b','active':True})['host_count']==2
                checks['one_release_retains_other']=http('/host',{'client_id':'test_a','active':False})['host_count']==1
                time.sleep(1.2);checks['service_still_alive']=process.poll() is None
                http('/host',{'client_id':'test_b','active':False});process.wait(timeout=8)
                checks['last_host_release_closes_owned_service']=process.returncode==0
            finally:
                if process.poll() is None:process.terminate();process.wait(5)
    result={'passed':all(checks.values()),'checks':checks,'clean_environment':True,'separate_clean_pc_tested':False}
    (OUT/'portable_validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2));assert result['passed']


if __name__=='__main__':main()
