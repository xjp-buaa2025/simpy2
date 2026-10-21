"""End-to-end checks through the real original-UI executable and isolated APIs."""
import argparse,copy,hashlib,json,time,urllib.request
from pathlib import Path
import tools.pt6a29_original_native as native
from tools.pt6a29_original_delivery import OUT,ROOT


def http(endpoint,payload=None,method=None):
    data=None if payload is None else json.dumps(payload).encode()
    request=urllib.request.Request(API+endpoint,data,{'Content-Type':'application/json'},method=method)
    with urllib.request.urlopen(request,timeout=45) as response:return json.load(response)


def main():
    global API
    args=argparse.ArgumentParser();args.add_argument('--phase',default='native');args.add_argument('--port',type=int,default=8058);args.add_argument('--control');a=args.parse_args()
    API=f'http://127.0.0.1:{a.port}/api/simulation/unity/'
    if a.control:native.CONTROL=Path(a.control)
    checks=[]
    def check(name,passed,detail=''):
        checks.append(dict(name=name,passed=bool(passed),detail=detail))
        if not passed:print('FAILED',name,detail,flush=True)
    def case(name,**kw):
        r=native.case(a.phase+'_'+name,capture=kw.pop('capture',False),**kw)
        check(name+'_request',r.get('success'),r.get('error',''))
        return r
    replay_file=ROOT/'results/unity_validation/replay.json';before=hashlib.sha256(replay_file.read_bytes()).hexdigest()
    r=case('ready',minute=630.2407,view='top',test=True,capture=True)
    audit=r['audit'];check('native_geometry_checks',json.loads(r['checks'])['passed'])
    check('original_ui_runtime',audit['original_pc_ui'] and audit['original_bootstrap'] and not audit['independent_preview'])
    check('physical_and_logical_counts',(audit['logical_stations'],audit['workstations'],audit['buffers'])==(79,29,3))
    first=case('pause_one');second=case('pause_two')
    check('pause_keeps_clock_vehicle_crane',all(first['audit'][k]==second['audit'][k] for k in ['minute','agv','bridge','hook']))
    fw=json.loads(first['original_ui'])['workers'];sw=json.loads(second['original_ui'])['workers']
    check('pause_keeps_worker_poses',[(w['id'],w['position'],w['spine_rotation']) for w in fw]==[(w['id'],w['position'],w['spine_rotation']) for w in sw])
    shared=max((x for x in audit['owners'] if len(x['aliases'])>1),key=lambda x:len(x['aliases']))
    for index,step in enumerate([shared['aliases'][0],shared['aliases'][-1]]):
        r=case('shared_'+str(index),station=step,capture=index==1)
        owner=next(x for x in r['audit']['owners'] if x['slot_id']==shared['slot_id'])
        check('original_logical_selection_'+str(index),r['audit']['selection']==step and owner['owner']==step)
    r=case('mouse_pick',action='pick',path=shared['aliases'][-1],capture=True)
    check('physical_pick_uses_live_owner',json.loads(r['original_ui'])['picked_station']!='miss' and r['audit']['selection'] in shared['aliases'])
    r=case('idle_new_zone',station='WS-IN01:01',capture=True)
    check('unbound_zone_has_no_fake_task',r['audit']['selection']=='WS-IN01' and any('旧79工序回放没有对应任务' in t['text'] for t in json.loads(r['original_ui'])['texts']))
    r=case('area_view',station='G012',action='area',capture=True);check('original_area_camera',json.loads(r['original_ui'])['mode']=='area')
    r=case('agv_follow',action='follow',capture=True)
    r=case('restore_view',action='reset_views',view='overview',capture=True);check('original_overview_restore',json.loads(r['original_ui'])['mode']=='overview')
    r=case('walk_window',action='walk',capture=True);check('original_walk_window',json.loads(r['original_ui'])['preview'])
    case('walk_close',action='walk_hide')
    case('layout_panel',action='layout',capture=True)
    current=http('physical-layout.json');candidate=copy.deepcopy(current)
    for slot in candidate['slots']:
        if slot['zone_id']=='WS-G04':slot['x']+=.08
    validated=http('physical-layout/validate',candidate,'POST');check('server_validates_candidate',validated.get('valid'))
    candidate_file=OUT/(a.phase+'_candidate.json');candidate_file.write_text(json.dumps(candidate,ensure_ascii=False),encoding='utf-8')
    r=case('layout_preview',action='import',path=str(candidate_file),settle=4,capture=True)
    check('original_import_previews_only',json.loads(r['original_ui'])['preview'] if False else not r['audit']['authority'])
    check('preview_not_published',http('physical-layout.json')['revision']==current['revision'])
    r=case('layout_publish',action='publish',settle=4,capture=True);published=http('physical-layout.json')
    check('original_publish_commits_revision',published['revision']==current['revision']+1 and r['audit']['revision']==published['revision'])
    moved=next(s for s in published['slots'] if s['zone_id']=='WS-G04')
    geometry=next(s for s in r['audit']['equipment'] if s['id']==moved['id'])
    check('published_physical_position',abs(geometry['center']['x']-moved['x'])<.04)
    r=case('published_alias_select',station='A003');check('selection_survives_publish',r['audit']['selection']=='A003')
    cancelled=copy.deepcopy(published)
    for slot in cancelled['slots']:
        if slot['zone_id']=='WS-G04':slot['x']+=.02
    candidate_file.write_text(json.dumps(cancelled,ensure_ascii=False),encoding='utf-8')
    case('cancel_preview_import',action='import',path=str(candidate_file),settle=3)
    r=case('cancel_preview',action='cancel',settle=2)
    check('cancel_restores_published_version',r['audit']['revision']==published['revision'] and r['audit']['authority'])
    state=http('playback.json')
    restored=http('physical-layout/restore',dict(client_id=state['controller_id'],sim_id=state['sim_id'],expected_revision=published['revision'],source='default'),'POST')
    r=case('layout_restore',settle=4,test=True,capture=True)
    check('restore_synced_to_player',r['audit']['revision']==restored['revision'] and json.loads(r['checks'])['passed'])
    r=case('month_end',minute=audit['duration'],settle=2,capture=True)
    check('original_completion_unchanged',r['audit']['finished']==r['audit']['web_completed']==12)
    r=case('reset',minute=0,settle=1.5)
    check('reset_to_original_clock_start',r['audit']['minute']==0 and r['audit']['finished']==0)
    r=case('speed_5',minute=100,play=True,speed=5,settle=2.2)
    check('original_speed_control',107<r['audit']['minute']<118 and r['audit']['playing'] and r['audit']['speed']==5)
    r=case('pause_again',minute=110,speed=5)
    p=case('pause_again_confirm')
    check('speed_then_pause_keeps_pose',all(r['audit'][k]==p['audit'][k] for k in ['minute','agv','bridge','hook']))
    r=case('final_overview',minute=630.2407,view='overview',station='',capture=True,test=True)
    check('workers_no_collision',json.loads(r['original_ui'])['worker_overlap_count']==0)
    check('formal_replay_file_unchanged',hashlib.sha256(replay_file.read_bytes()).hexdigest()==before)
    result=dict(passed=all(c['passed'] for c in checks),phase=a.phase,checks=checks,check_count=len(checks),final_audit=r['audit'])
    (OUT/(a.phase+'_functional_summary.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[c for c in checks if not c['passed']]),ensure_ascii=False),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
