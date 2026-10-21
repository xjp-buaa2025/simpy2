"""Live HTTP -> published replay -> running Unity Editor acceptance checks.

Use --record NAME after a real web UI run, or --api-matrix for isolated request
variations. The latter restores the original request on exit. Never bypasses
Unity's normal HTTP watcher or replaces a player's replay directly.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/unity_validation/parameters_20261003"
PUBLISHED = OUT.parent
UNITY = Path("C:/AllUnityProjects/MainProject/MainProject/SimPyValidation/parameters")
BASE = "http://127.0.0.1:8000"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def request(route, value=None):
    req = urllib.request.Request(BASE + route, data=json.dumps(value).encode() if value is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def signature(events):
    return hashlib.sha256(json.dumps(events, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def agv_position(replay, minute):
    trips = replay["transfers"]
    if not trips:
        return None
    index = 0
    while index < len(trips)-1 and trips[index]["end_time"] <= minute:
        index += 1
    while index > 0 and trips[index]["start_time"] > minute:
        index -= 1
    trip = trips[index]
    if minute < trip["start_time"]:
        return trips[index-1]["route"][-1] if index else dict(x=8.011127471923828,y=-.3840000033378601,z=4.330870628356934)
    route = trip["route"]
    lengths = [math.dist([a[k] for k in "xyz"], [b[k] for k in "xyz"]) for a,b in zip(route,route[1:])]
    raw = max(0,min(1,(minute-trip["start_time"])/max(.001,trip["end_time"]-trip["start_time"])))
    remaining = sum(lengths)*max(0,min(1,(raw-.08)/.84))
    for i, length in enumerate(lengths):
        if remaining <= length or i == len(lengths)-1:
            t=max(0,min(1,remaining/length)) if length>.001 else 1
            return {k:route[i][k]+(route[i+1][k]-route[i][k])*t for k in "xyz"}
        remaining -= length


def validate_frame(replay, frame):
    assert frame["sim_id"] == replay["sim_id"], "Unity kept an old sim_id"
    assert frame["synchronized"], "Unity clock not synchronized"
    parsed = frame["replay"]
    for field in ["work_hours_per_day","work_days_per_month","target_output","engines_completed","duration","station_constraint_mode"]:
        assert parsed[field] == replay[field], field
    assert len(parsed["events"]) == len(replay["events"]), "event count"
    for actual, expected in zip(parsed["events"],replay["events"]):
        for field in actual:
            assert (abs(actual[field]-expected[field]) < .005 if isinstance(actual[field],float) else actual[field]==expected[field]), (field,actual,expected)
    assert len(parsed["stations"]) == len(replay["stations"]), "station count"
    for actual,expected in zip(parsed["stations"],replay["stations"]):
        for field in actual:
            if field=="position":assert all(abs(actual[field][k]-expected[field][k])<.002 for k in "xyz"), "station position"
            else:assert actual[field]==expected[field], "station labels/areas differ"
    assert len(parsed["transfers"]) == len(replay["transfers"]), "AGV route count"
    for actual, expected in zip(parsed["transfers"], replay["transfers"]):
        for field in actual:
            if isinstance(actual[field],float): assert abs(actual[field]-expected[field]) < .005, field
            elif field=="route":
                for a,b in zip(actual[field],expected[field]):
                    assert all(abs(a[k]-b[k])<.002 for k in "xyz"), "AGV route point"
                assert len(actual[field])==len(expected[field]), "AGV route points"
            else: assert actual[field]==expected[field], field
    minute = frame["minute"]
    for field, milestone in [("finished","finished"),("assembled","assembly"),("inspected","inspection")]:
        expected=sum(0<=e[milestone]<=minute+.005 for e in replay["engine_completion"])
        assert frame[field]==expected,(field,frame[field],expected)
    active_checked = 0
    for station in frame["stations"]:
        source=next(s for s in replay["stations"] if s["station_id"]==station["id"])
        assert station["label"]==source["scene_label"] and station["area"]==source["area_id"], "station label/area"
        active=[e for e in replay["events"] if e["station_id"]==station["id"] and e["start_time"]<=minute<e["end_time"]]
        working=[e for e in active if e["event_type"] in ("NORMAL","REWORK")]
        selected = min(working,key=lambda e:e["start_time"]) if working else next((e for e in active if e["event_type"]=="WAITING"),None) or next((e for e in active if e["event_type"]=="REST"),None)
        if selected:
            states=dict(NORMAL="加工中",REWORK="返工",WAITING="等待",REST="人员休息")
            assert station["state"]==states[selected["event_type"]],(station, selected)
            assert station["concurrent"]==len(working)
            if working:
                progress=(minute-selected["start_time"])/(selected["end_time"]-selected["start_time"])
                assert abs(station["progress"]-progress)<.001,(station["id"],station["progress"],progress)
            active_checked += 1
    agv=agv_position(replay,minute)
    if agv: assert math.dist([agv[k] for k in "xyz"],[frame["agv"][k] for k in "xyz"])<.02, "AGV position"
    return dict(events_checked=len(parsed["events"]),stations_checked=len(frame["stations"]),active_stations_checked=active_checked,agv_checked=bool(agv))


def frame_for(name, replay, minute=None, capture=False, preserve=False):
    if minute is None:
        interesting=next((e for typ in ["REWORK","REST","WAITING","NORMAL"] for e in replay["events"] if e["event_type"]==typ and e["end_time"]-e["start_time"]>1),None)
        minute=(interesting["start_time"]+interesting["end_time"])/2 if interesting else 0
    save(UNITY/"request.json",dict(name=name,sim_id=replay["sim_id"],minute=minute,capture=capture,preserveOld=preserve))
    target=UNITY/(name+".json"); start=time.monotonic()
    while time.monotonic()-start<35:
        if target.exists() and target.stat().st_mtime>time.time()-(time.monotonic()-start)-1:
            frame=read(target);shutil.copy2(target,OUT/(name+"_unity.json"));return frame
        time.sleep(.25)
    raise TimeoutError(f"Unity did not capture {name}; inspect {UNITY}/error.txt")


def record(name, response=None, minute=None, capture=False):
    response=response or read(PUBLISHED/"current_result.json")
    result=response["data"]
    status=request('/api/simulation/unity/sync_status.json')
    assert status['success'] and status['sim_id']==result['sim_id'], "latest web run failed Unity publication"
    replay=request('/api/simulation/unity/replay.json')
    assert result['sim_id']==replay['sim_id'], "web result not published"
    assert result['engines_completed']==replay['engines_completed'], "web completion differs"
    frame=frame_for(name,replay,minute,capture)
    checks=validate_frame(replay,frame)
    save(OUT/(name+"_result.json"),response)
    save(OUT/(name+"_replay.json"),replay)
    summary=dict(name=name,sim_id=result['sim_id'],config=result['config'],finished=result['engines_completed'],events=len(result['gantt_events']),event_types={typ:sum(e['event_type']==typ for e in result['gantt_events']) for typ in ['NORMAL','REST','WAITING','REWORK']},event_signature=signature(result['gantt_events']),transfers_signature=signature(replay['transfers']),quality=result['quality_stats'],unity_checks=checks,calendar=frame['calendar'],minute=frame['minute'])
    save(OUT/(name+"_summary.json"),summary)
    print(json.dumps(dict(name=name,finished=summary['finished'],events=summary['event_types'],unity='PASS'),ensure_ascii=True),flush=True)
    return summary


def matrix():
    original=read(OUT/'original_request.json')
    cases=[]
    def node(req,step):return next(n for n in req['process']['nodes'] if n['step_id']==step)
    def add(name,modify):
        req=copy.deepcopy(original);modify(req);cases.append((name,req))
    add('api_baseline',lambda r:None)
    for key,val in [('work_hours_per_day',6),('work_days_per_month',12),('num_workers',4),('target_output',5),('rest_time_threshold',20),('rest_duration_time',15),('rest_load_threshold',4),('pipeline_mode',False),('station_constraint_mode',True)]:
        add('api_'+key,lambda r,k=key,v=val:r['config'].__setitem__(k,v))
    for duration in [2,15]:
        add('api_rest_load_duration_'+str(duration),lambda r,d=duration:r['config'].update(rest_load_threshold=4,rest_duration_load=d))
    for key,val in [('task_name','零件接收与登记（参数验证）'),('std_duration',180),('time_variance',30),('work_load_score',10),('required_workers',4),('station','ST03'),('op_type','M'),('rework_prob',.8)]:
        add('api_node_'+key,lambda r,k=key,v=val:node(r,'S001').__setitem__(k,v))
    add('api_node_predecessors',lambda r:node(r,'S003').__setitem__('predecessors','S001'))
    for op in ['H','T','D']:
        add('api_op_'+op,lambda r,o=op:node(r,'S001').__setitem__('op_type',o))
    for prob in [0,.8,1]:
        add('api_measurement_rework_'+str(prob),lambda r,p=prob:node(r,'Q003').update(op_type='M',rework_prob=p))
    for name in original['config']['critical_equipment']:
        for count in [1,3]:
            def equip(r,n=name,c=count):
                r['config']['critical_equipment'][n]=c
                for sid in ['B001','B011']:node(r,sid)['required_tools']=[n]
            add('api_equipment_'+str(list(original['config']['critical_equipment']).index(name))+'_'+str(count),equip)
    add('api_equipment_added',lambda r:(r['config']['critical_equipment'].__setitem__('验证检测台',1),node(r,'B001').__setitem__('required_tools',['验证检测台']),node(r,'B011').__setitem__('required_tools',['验证检测台'])))
    add('api_unlimited_tool',lambda r:node(r,'B001').__setitem__('required_tools',['普通扭力扳手']))
    add('api_combined',lambda r:r['config'].update(work_hours_per_day=6,work_days_per_month=16,num_workers=4,target_output=2,rest_time_threshold=25,rest_duration_time=12,rest_load_threshold=4,rest_duration_load=8,pipeline_mode=False,station_constraint_mode=True))
    summaries=[]
    try:
        for name,req in cases:
            save(OUT/(name+'_request.json'),req)
            response=request('/api/simulation/run',req)
            assert response['success'] and response['data']['unity_sync']['success'], response.get('message') or response
            summaries.append(record(name,response))
        save(OUT/'api_matrix_summary.json',summaries)
    finally:
        response=request('/api/simulation/run',original)
        save(OUT/'restored_result.json',response)
        if response['success'] and response['data']['unity_sync']['success']:record('restored',response,minute=2950,capture=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--record');parser.add_argument('--api-matrix',action='store_true');parser.add_argument('--minute',type=float);parser.add_argument('--capture',action='store_true');parser.add_argument('--expect');args=parser.parse_args()
    if args.expect:
        key,value=args.expect.split('=',1); expected=json.loads(value); start=time.monotonic()
        while read(PUBLISHED/'current_result.json')['data']['config'].get(key)!=expected:
            if time.monotonic()-start>30:raise TimeoutError('Web result config did not match '+args.expect)
            time.sleep(.25)
    if args.record:record(args.record,minute=args.minute,capture=args.capture)
    if args.api_matrix:matrix()
