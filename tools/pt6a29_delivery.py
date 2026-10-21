"""Drive the isolated Unity preview's editor/player acceptance protocol."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path('C:/AllUnityProjects/MainProject/MainProject')
FOLDER=PROJECT/'SimPyValidation/pt6a29'
OUT=ROOT/'results/pt6a29_20261020'

def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');temp.replace(path)

def wait(path,timeout=120,terminal=None):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if path.exists():
            try:
                data=json.loads(path.read_text(encoding='utf-8-sig'))
                if terminal is None or terminal(data):return data
            except (OSError,json.JSONDecodeError):pass
        time.sleep(.3)
    raise TimeoutError(str(path))

def editor(operation,name=None,timeout=120,**options):
    name=name or operation
    result=FOLDER/(name+'.json');result.unlink(missing_ok=True)
    request=FOLDER/'request.json'
    if request.exists():raise RuntimeError('Editor already has a pending request')
    atomic(request,dict(name=name,operation=operation,**options))
    data=wait(result,timeout,lambda d:d.get('phase') not in ('switching','building'))
    OUT.mkdir(parents=True,exist_ok=True);(OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    if not data.get('success'):raise RuntimeError(json.dumps(data,ensure_ascii=False)[:3500])
    return data

def main():
    p=argparse.ArgumentParser();p.add_argument('operation');p.add_argument('--name');p.add_argument('--camera');p.add_argument('--station');p.add_argument('--seconds',type=float);p.add_argument('--output');p.add_argument('--timeout',type=int,default=120)
    a=p.parse_args();kwargs={k:v for k,v in vars(a).items() if k not in ('operation','name','timeout') and v is not None}
    d=editor(a.operation,a.name,a.timeout,**kwargs)
    print(json.dumps({k:v for k,v in d.items() if k!='audit'},ensure_ascii=False,indent=2))
    if d.get('audit'):print(json.dumps({k:v for k,v in d['audit'].items() if k not in ('geometry','fixtures')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
