"""Live representative parameter checks against the running VR Editor viewer."""
import copy,time
from unity_parameter_validation import *


def at(name,replay,minute):
    save(OUT/'vr_clock_target.json',dict(minute=minute,speed=20))
    start=time.monotonic()
    while time.monotonic()-start<25:
        clock=request('/api/simulation/unity/playback.json')
        if clock['sim_id']==replay['sim_id'] and abs(clock['minute']-minute)<.01:break
        time.sleep(.25)
    else:raise TimeoutError('VR fixture did not position the shared clock')
    frame=frame_for(name,replay,minute=-1,capture=True)
    assert frame['role']=='VRViewer' and not frame['authority'],frame['role']
    assert abs(frame['minute']-minute)<.01,(frame['minute'],minute)
    checks=validate_frame(replay,frame)
    colors={'加工中':(.12,.62,.95),'等待':(1,.68,.16),'人员休息':(.65,.48,.85),'返工':(.65,.48,.85)}
    checked=0
    for station in frame['stations']:
        if station['state'] in colors:
            for field in ('fillColor','haloColor'):
                assert all(abs(station[field][k]-v)<.001 for k,v in zip('rgb',colors[station['state']])),(station['id'],field)
            checked+=1
    summary=dict(name=name,role=frame['role'],finished=frame['finished'],minute=frame['minute'],calendar=frame['calendar'],authority=False,checks=checks,colors_checked=checked)
    save(OUT/(name+'_vr_checks.json'),summary);print(summary,flush=True);return summary


if __name__=='__main__':
    original=read(OUT/'original_request.json');summaries=[]
    try:
        changed=copy.deepcopy(original)
        changed['config'].update(work_hours_per_day=6,work_days_per_month=12,num_workers=4,target_output=4,rest_time_threshold=20,rest_duration_time=15,rest_load_threshold=4,rest_duration_load=10)
        equipment=next(iter(changed['config']['critical_equipment']));changed['config']['critical_equipment'][equipment]=1
        for n in changed['process']['nodes']:
            if n['step_id']=='S001':n.update(task_name='零件接收检测（VR参数验证）',op_type='M',rework_prob=.6,std_duration=60,time_variance=12,work_load_score=9,required_workers=2,station='ST03')
            if n['step_id'] in ['B001','B011']:n['required_tools']=[equipment]
            if n['step_id']=='S003':n['predecessors']='S001'
        save(OUT/'vr_changed_request.json',changed)
        for name,req in [('vr_changed',changed),('vr_rework',read(OUT/'api_measurement_rework_1_request.json'))]:
            response=request('/api/simulation/run',req);assert response['success'] and response['data']['unity_sync']['success']
            save(OUT/(name+'_result.json'),response);replay=request('/api/simulation/unity/replay.json');save(OUT/(name+'_replay.json'),replay)
            e=next(e for e in replay['events'] if e['event_type']=='REWORK')
            summaries.append(at(name+'_active',replay,(e['start_time']+e['end_time'])/2))
            summaries.append(at(name+'_end',replay,replay['duration']))
        save(OUT/'vr_parameter_summary.json',summaries)
    finally:
        response=request('/api/simulation/run',original)
        replay=request('/api/simulation/unity/replay.json')
        at('vr_restored',replay,2950)
