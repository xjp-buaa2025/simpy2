"""Immutable web-result publications shared by the 29-station clients."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading

ROOT = Path(__file__).resolve().parents[2]
lock = threading.RLock()

def directory():
    return Path(os.getenv('SIMPY_UNITY_ACTIVE_STORE', ROOT/'results/unity_validation/active'))

def legacy_path():
    return Path(os.getenv('SIMPY_REPLAY_PATH', ROOT/'results/unity_validation/replay.json'))

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')

def atomic(path, content):
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def active():
    path = directory()/'active.json'
    if path.exists(): return read(path)
    replay = read(legacy_path())
    return dict(schema_version=1, mode='legacy79', sim_id=replay['sim_id'], duration=replay['duration'],
                profile_id='pt6a29-original', publication_id='legacy', replay_url='/api/simulation/unity/replay.json')

def snapshot():
    info = active()
    return read(directory()/'runs'/(info['publication_id']+'.json')) if info['mode']=='pt6a29' else read(legacy_path())

def compile_result(result, process):
    process = process.model_dump(mode='json') if hasattr(process, 'model_dump') else copy.deepcopy(process)
    profile = read(ROOT/'data/factory_layout/pt6a29-original/layout.json')
    zones = {z['station_id']:z for z in profile['zones'] if z['kind']=='workstation'}
    nodes = {n['step_id']:n for n in process['nodes']}
    if len(nodes)!=len(process['nodes']): raise ValueError('工步编号重复，不能同步Unity')
    station = lambda n:n.get('workstation_id') or n.get('area_id') or n.get('station')
    invalid = [f"{n['step_id']} → {station(n)}" for n in nodes.values() if station(n) not in zones]
    if invalid: raise ValueError('未映射工位：'+'；'.join(invalid))
    progress = copy.deepcopy(result.get('station_progress'))
    if not progress or progress.get('sim_id')!=result['sim_id']:
        raise ValueError('缺少同一运行的真实工位放行时间线，请重新仿真')
    if {s['station_id'] for s in progress['stations']}!={station(n) for n in nodes.values()}:
        raise ValueError('工位进度与工艺快照不一致')
    duration = float(result['sim_duration'])
    if not math.isfinite(duration) or duration<0 or progress['time_minutes']!=duration:
        raise ValueError('工位时间线时长不一致')
    events=[]
    for i, original in enumerate(result['gantt_events']):
        event=copy.deepcopy(original);node=nodes[event['step_id']]
        if not 0<=event['start_time']<=event['end_time']<=duration+1e-5:raise ValueError('事件时间超出仿真范围')
        if event.get('workstation_id') and event['workstation_id']!=station(node):raise ValueError('事件工位与工艺快照不一致')
        event.update(event_id=str(i),station_id=station(node),area_id=node.get('area_id') or station(node))
        events.append(event)
    config=(result.get('input_snapshot') or {}).get('config') or result['config']
    release={}
    for s in progress['stations']:
        own={key:node for key,node in nodes.items() if station(node)==s['station_id']}
        if s['total_steps']!=len(own) or not math.isclose(s['total_standard_minutes'],math.fsum(n['std_duration'] for n in own.values()),abs_tol=1e-6):
            raise ValueError('工位进度的工步总量与工艺快照不一致')
        engine_seen=set()
        for engine in s['engines']:
            if engine['engine_id'] in engine_seen or not 0<=engine['released_at']<=duration:raise ValueError('发动机投产记录无效')
            engine_seen.add(engine['engine_id']);seen=set()
            for e in engine['completion_events']:
                if e['step_id'] not in own or e['step_id'] in seen or not engine['released_at']<=e['completed_at']<=duration or not math.isclose(e['std_duration'],own[e['step_id']]['std_duration'],abs_tol=1e-6):raise ValueError('工步放行记录与工艺快照不一致')
                seen.add(e['step_id']);release[(engine['engine_id'],e['step_id'])]=e['completed_at']
            engine['completion_events'].sort(key=lambda e:(e['completed_at'],e['step_id']))
    engine_ids=sorted({e['engine_id'] for s in progress['stations'] for e in s['engines']})
    completions={int(e['engine_id']):float(e['end_time']) for e in result.get('engine_completion_events',[])}
    if len(completions)!=result['engines_completed']:raise ValueError('整机完成事件与产量不一致')
    if any(eid not in engine_ids or not 0<=time<=duration for eid,time in completions.items()):raise ValueError('整机完成事件超出仿真范围')
    def milestone(eid,sid):
        row=next((s for s in progress['stations'] if s['station_id']==sid),None)
        engine=next((e for e in row['engines'] if e['engine_id']==eid),None) if row else None
        return engine['completed_at'] if engine and engine['completed'] else -1
    labels={s['station_id']:s['label'] for s in progress['stations']}
    effective=result.get('resource_snapshot',{}).get('effective_workstations',{})
    payload=dict(schema_version=4,mode='pt6a29',sim_id=result['sim_id'],time_unit='minute',duration=duration,
        work_hours_per_day=config['work_hours_per_day'],work_days_per_month=config['work_days_per_month'],
        engines_completed=result['engines_completed'],target_output=config.get('monthly_target',0) or 0,
        source_scene='pt6a29-original',agv_mode='物流示意 · 不参与排产',station_constraint_mode=False,
        stations=[dict(station_id=sid,area_id=sid,scene_label=labels.get(sid,z['label']),position=dict(x=z['x'],y=0,z=z['z']),capacity=effective.get(sid,{}).get('capacity',1)) for sid,z in zones.items()],
        events=sorted(events,key=lambda e:(e['start_time'],e['end_time'],int(e['event_id']))),
        process=process,station_progress=progress,engine_completion_events=copy.deepcopy(result.get('engine_completion_events',[])),
        engine_completion=[dict(engine_id=eid,assembly=milestone(eid,'WS-M05'),inspection=milestone(eid,'WS-TC01'),finished=completions.get(eid,-1)) for eid in engine_ids],
        area_stats=copy.deepcopy(result.get('area_stats',[])),area_completion_events=copy.deepcopy(result.get('area_completion_events',[])),
        evaluation_context=copy.deepcopy(result.get('evaluation_context',{})),time_mapping=copy.deepcopy(result.get('time_mapping',{})))
    # Each engine has an independent illustrative queue. No queue modifies real events.
    trips=[];crane=[]
    chain={('WS-G01','WS-G02'),('WS-G02','WS-G03'),('WS-G03','WS-G04'),('WS-G04','WS-M05')}
    for eid in engine_ids:
        candidates=[]
        for node in nodes.values():
            for pred in node.get('predecessors','').split(';'):
                source=nodes.get(pred.strip())
                trigger=release.get((eid,pred.strip()))
                if source and trigger is not None and station(source)!=station(node):
                    candidates.append((trigger,station(source),station(node),pred.strip(),node['step_id']))
        available=0;previous='AGV_START';crane_available=0
        for index,(trigger,src,dst,ss,ts) in enumerate(sorted(set(candidates))):
            base=dict(engine_id=eid,source_station=src,target_station=dst,source_step=ss,target_step=ts,trigger_time=trigger,visualization_only=True)
            if (src,dst) in chain:
                start=max(crane_available,trigger);crane.append(dict(base,trip_id=f'crane-{eid}-{index}',start_time=start,end_time=start+20));crane_available=start+20;continue
            if previous!=src:
                start=max(available,trigger);trips.append(dict(trip_id=f'empty-{eid}-{index}',engine_id=eid,source_station=previous,target_station=src,source_step='',target_step='',loaded=False,trigger_time=trigger,start_time=start,end_time=start+20,visualization_only=True));available=start+20
            start=max(available,trigger);trips.append(dict(base,trip_id=f'load-{eid}-{index}',loaded=True,start_time=start,end_time=start+20));available=start+20;previous=dst
    from tools.pt6a29_integrated import reroutes
    routes=reroutes(profile,dict(transfers=trips))
    for trip,route in zip(trips,routes):trip['route']=route['points']
    payload.update(transfers=trips,crane_transfers=crane)
    return payload

def publish(result,process,store_directory=None,progress_path=None):
    with lock:
        payload=compile_result(result,process)
        content=encoded(payload);digest=hashlib.sha256(content).hexdigest();identity=digest
        destination=Path(os.getenv('SIMPY_UNITY_ACTIVE_STORE',str(store_directory))) if store_directory is not None else directory()
        atomic(destination/'runs'/(identity+'.json'),content)
        info=dict(schema_version=1,mode='pt6a29',sim_id=payload['sim_id'],duration=payload['duration'],profile_id='pt6a29-original',
                  publication_id=identity,sha256=digest,replay_url=f'/api/simulation/unity/runs/{identity}/replay.json')
        if progress_path is not None:atomic(Path(progress_path),encoded(payload['station_progress']))
        atomic(destination/'active.json',encoded(info))
        return dict(info,success=True,stations=29,engines_completed=payload['engines_completed'])

def run_bytes(identity):
    if not re.fullmatch('[0-9a-f]{64}',identity):raise FileNotFoundError(identity)
    return (directory()/'runs'/(identity+'.json')).read_bytes()
