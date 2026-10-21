"""Drive the integrated original-scene editor, keeping compact evidence."""
from pathlib import Path
import argparse,json,time

ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path('C:/AllUnityProjects/MainProject/MainProject')
FOLDER=PROJECT/'SimPyValidation/pt6a29-original'
OUT=ROOT/'results/pt6a29_original_20261021'

def editor(operation,name=None,timeout=60,**kwargs):
    name=name or operation;FOLDER.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    result=FOLDER/(name+'.json');result.unlink(missing_ok=True)
    request=FOLDER/'request.json'
    if request.exists():raise RuntimeError('Another integrated editor request is pending')
    temp=request.with_suffix('.tmp');temp.write_text(json.dumps(dict(operation=operation,name=name,**kwargs),ensure_ascii=False),encoding='utf-8');temp.replace(request)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if result.exists():
            try:r=json.loads(result.read_text(encoding='utf-8-sig'))
            except (OSError,json.JSONDecodeError):time.sleep(.3);continue
            if r.get('phase') in ('switching','building'):time.sleep(.3);continue
            (OUT/(name+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
            if r.get('checks'):(OUT/(name+'_checks.json')).write_text(r['checks'],encoding='utf-8')
            if r.get('report'):(OUT/(name+'_original_ui.json')).write_text(r['report'],encoding='utf-8')
            return r
        time.sleep(.3)
    raise TimeoutError(str(result))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation');p.add_argument('--name');p.add_argument('--timeout',type=int,default=60)
    for key in ['server','station','view','output','version']:p.add_argument('--'+key)
    p.add_argument('--minute',type=float);p.add_argument('--speed',type=float);p.add_argument('--version-code',type=int)
    a=vars(p.parse_args());operation=a.pop('operation');name=a.pop('name');timeout=a.pop('timeout')
    options={('versionCode' if k=='version_code' else k):v for k,v in a.items() if v is not None}
    r=editor(operation,name,timeout,**options)
    shown={k:v for k,v in r.items() if k not in ('report','checks','audit') and v not in ('',[],None)}
    if r.get('audit'):shown['audit']={k:v for k,v in r['audit'].items() if k not in ('equipment','owners')}
    if r.get('checks'):
        c=json.loads(r['checks']);shown['checks_passed']=c['passed'];shown['check_count']=len(c['checks']);shown['failed']=[x for x in c['checks'] if not x['passed']]
    print(json.dumps(shown,ensure_ascii=False,indent=2))
    if not r.get('success'):raise SystemExit(1)

if __name__=='__main__':main()
