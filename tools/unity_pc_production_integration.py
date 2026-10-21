"""Native package: real layout publication, real rescheduling, legacy replay."""
import copy,json,time,uuid,urllib.request,urllib.error
from pathlib import Path
from tools.unity_pc_production_validation import Runner,action,http,API,OUT

def upload(document):
    boundary='pc-production-check';blob=json.dumps(document,ensure_ascii=False).encode()
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="candidate.json"\r\nContent-Type: application/json\r\n\r\n'.encode()+blob+f'\r\n--{boundary}--\r\n'.encode())
    request=urllib.request.Request(API+'layout/validate',body,{'Content-Type':'multipart/form-data; boundary='+boundary})
    return json.load(urllib.request.urlopen(request,timeout=90))

def main():
    runner=Runner(OUT/'native_control');runner.delivery=OUT/'integration';runner.delivery.mkdir(exist_ok=True)
    runner.case('integration_ready',1082.2563,[action('SelectStation','F012')])
    snapshot=http(API+'layout.json');candidate=copy.deepcopy(snapshot['layout']);row=next(r for r in candidate['stations'] if r['station_id']=='F012');row['label']+='（布局检查）';row['yaw']=(row['yaw']+10)%360;row['x']+=.1
    validation=upload(candidate)
    if not validation.get('valid'):
        row['yaw']=(row['yaw']-10)%360;row['x']-=.1;validation=upload(candidate)
    runner.check('candidate_service_validation',validation.get('valid'))
    state=http(API+'playback.json');published=http(API+'layout',dict(client_id=state['controller_id'],sim_id=state['sim_id'],expected_revision=snapshot['layout']['revision'],layout=candidate),'PUT')
    r=runner.case('published_layout',settle=4,capture=True);g=next(g for g in r['geometry'] if g['id']=='F012')
    runner.check('layout_camera_and_label_refresh',r['mode']=='station' and r['focused_station']=='F012' and g['label']==row['label'] and abs(g['yaw']-row['yaw'])<.1 and abs(g['position']['x']-row['x'])<.01)
    runner.worker_check('published_layout',r)
    try:
        http(API+'layout',dict(client_id=state['controller_id'],sim_id=state['sim_id'],expected_revision=snapshot['layout']['revision'],layout=candidate),'PUT');conflict=False
    except urllib.error.HTTPError as e:conflict=e.code==409
    runner.check('stale_layout_revision_rejected',conflict)
    original=json.loads((OUT/'source_input.json').read_text(encoding='utf-8'));changed=copy.deepcopy(original);changed['config'].update(work_hours_per_day=6,work_days_per_month=18,target_output=7);changed['publish_to_clients']=True
    response=http('http://127.0.0.1:8042/api/simulation/run',changed)
    (runner.delivery/'actual_web_run.json').write_text(json.dumps(response,ensure_ascii=False),encoding='utf-8')
    runner.check('real_simpy_run_published',response.get('success') and response['data']['unity_sync']['success'])
    def wait_sim(sim_id,name):
        for n in range(12):
            r=runner.case(name+'_'+str(n),settle=.7)
            if r['sim_id']==sim_id:return r
            time.sleep(.5)
        raise TimeoutError('Replay not received '+sim_id)
    r=wait_sim(response['data']['sim_id'],'new_run_received');runner.check('native_received_real_web_run',r['target']==7)
    runner.replay=http(API+'replay.json');r=runner.case('new_run_details',2950,[action('SelectStation','F012')],capture=True)
    runner.check('custom_layout_name_survives_replan',next(g for g in r['geometry'] if g['id']=='F012')['label']==row['label'])
    runner.check('calendar_from_new_workday_config',any(t['name']=='CalendarCaption' and '18' in t['text'] for t in r['texts']))
    runner.worker_check('new_run',r)
    r=runner.case('new_run_month_end',runner.replay['duration'],[action('OpenPcDrawer',1)],capture=True);runner.check('replan_completed_count_matches_web',r['finished']==response['data']['engines_completed'])
    original['publish_to_clients']=True;restored=http('http://127.0.0.1:8042/api/simulation/run',original);runner.check('restore_run_published',restored.get('success') and restored['data']['unity_sync']['success']);wait_sim(restored['data']['sim_id'],'restored_run');runner.replay=http(API+'replay.json')
    runner.case('before_layout_restore',1082.2563,settle=2)
    state=http(API+'playback.json');layout=http(API+'layout.json');http(API+'layout/restore',dict(client_id=state['controller_id'],sim_id=state['sim_id'],expected_revision=layout['layout']['revision'],source='default'))
    r=runner.case('layout_restored',settle=4,capture=True);runner.check('layout_restore_rebuilds_visuals',next(g for g in r['geometry'] if g['id']=='F012')['label']==next(g for g in snapshot['layout']['stations'] if g['station_id']=='F012')['label'])
    runner.worker_check('restored_layout',r)
    # A schema-3 client must also accept older snapshots with no worker field.
    replay_path=OUT/'test_replay.json';saved=replay_path.read_bytes();legacy=json.loads(saved);legacy['sim_id']='legacy_'+uuid.uuid4().hex
    for t in legacy['events']:t.pop('worker_ids',None)
    replay_path.write_text(json.dumps(legacy,ensure_ascii=False),encoding='utf-8');r=wait_sim(legacy['sim_id'],'legacy_received');r=runner.case('legacy_without_workers',2950,[action('SelectStation','F012')],capture=True)
    runner.check('legacy_has_no_fabricated_workers',r['worker_roster']==0 and r['visible_workers']==0 and r['stations']==79)
    replay_path.write_bytes(saved);wait_sim(json.loads(saved)['sim_id'],'legacy_restored');runner.replay=http(API+'replay.json');runner.case('integration_finished',2950,[action('RestoreDefaultViews'),action('ClosePcDrawer')],capture=True)
    runner.save();print('Integration checks passed',flush=True)

if __name__=='__main__':main()
