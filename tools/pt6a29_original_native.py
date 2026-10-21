"""Run real original-UI player cases against the opt-in local review probe."""
from pathlib import Path
import argparse,json,time
from tools.pt6a29_original_delivery import OUT

CONTROL=OUT/'native_control'

def case(name,timeout=90,**options):
    CONTROL.mkdir(parents=True,exist_ok=True)
    result=CONTROL/(name+'.json');result.unlink(missing_ok=True)
    request=CONTROL/'request.json'
    if request.exists():raise RuntimeError('A native review request is already pending')
    temp=request.with_suffix('.tmp');temp.write_text(json.dumps(dict(name=name,**options),ensure_ascii=False),encoding='utf-8');temp.replace(request)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if result.exists():
            try:r=json.loads(result.read_text(encoding='utf-8-sig'))
            except (OSError,json.JSONDecodeError):time.sleep(.2);continue
            dest=OUT/'native';dest.mkdir(parents=True,exist_ok=True)
            (dest/(name+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
            if r.get('original_ui'):(dest/(name+'_original_ui.json')).write_text(r['original_ui'],encoding='utf-8')
            if r.get('checks'):(dest/(name+'_checks.json')).write_text(r['checks'],encoding='utf-8')
            return r
        time.sleep(.2)
    raise TimeoutError(str(result))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('name');p.add_argument('--timeout',type=int,default=90)
    for key in ['station','action','path','view']:p.add_argument('--'+key)
    p.add_argument('--minute',type=float);p.add_argument('--speed',type=float);p.add_argument('--settle',type=float)
    p.add_argument('--play',action='store_true');p.add_argument('--test',action='store_true');p.add_argument('--no-capture',action='store_true')
    args=vars(p.parse_args());name=args.pop('name');timeout=args.pop('timeout');args['capture']=not args.pop('no_capture');options={k:v for k,v in args.items() if v is not None}
    r=case(name,timeout,**options);a=r.get('audit',{})
    shown=dict(success=r.get('success'),error=r.get('error'),audit={k:v for k,v in a.items() if k not in ['equipment','owners']})
    if r.get('checks'):
        c=json.loads(r['checks']);shown.update(checks_passed=c['passed'],check_count=len(c['checks']),failed=[x for x in c['checks'] if not x['passed']])
    print(json.dumps(shown,ensure_ascii=False,indent=2))
    if not r.get('success'):raise SystemExit(1)

if __name__=='__main__':main()
