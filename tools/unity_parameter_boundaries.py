"""Supplemental live checks for parameter semantics, AGV motion and completion."""
import copy
import shutil
import math
import sys
from unity_parameter_validation import *
sys.path.insert(0,str(ROOT))


def run():
    original=read(OUT/'original_request.json')
    summaries=[]
    try:
        cases=[]
        removed=copy.deepcopy(original)
        equipment=next(iter(removed['config']['critical_equipment']))
        removed['config']['critical_equipment'].pop(equipment)
        for n in removed['process']['nodes']:
            if n['step_id'] in ('B001','B011'):n['required_tools']=[equipment]
        cases.append(('extra_equipment_removed',removed))
        short=copy.deepcopy(original);short['config'].update(work_hours_per_day=1,work_days_per_month=1)
        cases.append(('extra_short_month',short))
        moved=copy.deepcopy(original)
        moved['process']['nodes'][0].update(x=10000,y=-10000)
        cases.append(('extra_web_layout_only',moved))
        impossible=copy.deepcopy(original);impossible['config']['num_workers']=1
        next(n for n in impossible['process']['nodes'] if n['step_id']=='B001')['required_workers']=2
        cases.append(('extra_insufficient_workers',impossible))
        area=copy.deepcopy(original);area['config']['station_constraint_mode']=True
        area['process']['nodes'][0]['station']='ST03'
        cases.append(('extra_area_with_constraint',area))
        for name,req in cases:
            if '--resume' in sys.argv and (OUT/(name+'_summary.json')).exists():
                summaries.append(read(OUT/(name+'_summary.json')))
                continue
            save(OUT/(name+'_request.json'),req)
            response=request('/api/simulation/run',req)
            assert response['success'] and response['data']['unity_sync']['success'],response
            summaries.append(record(name,response,minute=req['config']['work_hours_per_day']*60*req['config']['work_days_per_month']))
        added=read(OUT/'api_equipment_added_request.json')
        response=request('/api/simulation/run',added)
        from app.utils.csv_parser import parse_process_csv
        parsed=parse_process_csv((PUBLISHED/'current_process.csv').read_text(encoding='utf-8-sig'))
        assert parsed.success,parsed.errors
        assert {n.step_id:n.required_tools for n in parsed.process.nodes}=={n['step_id']:n['required_tools'] for n in added['process']['nodes']}
        shutil.copy2(PUBLISHED/'current_process.csv',OUT/'tool_roundtrip.csv')
        save(OUT/'csv_roundtrip_summary.json',{'passed':True,'nodes':len(parsed.process.nodes),'tools_preserved':True})
        response=request('/api/simulation/run',original)
        replay=request('/api/simulation/unity/replay.json')
        points=[]
        trip=next(t for t in replay['transfers'] if len(t['route'])>1 and t['end_time']-t['start_time']>1)
        for i,fraction in enumerate([.1,.5,.9]):
            minute=trip['start_time']+(trip['end_time']-trip['start_time'])*fraction
            frame=frame_for('agv_motion_'+str(i),replay,minute,capture=i==1)
            validate_frame(replay,frame);points.append(frame['agv'])
        assert math.dist([points[0][k] for k in 'xyz'],[points[-1][k] for k in 'xyz'])>1,'AGV did not move'
        first=min(c['finished'] for c in replay['engine_completion'] if c['finished']>=0)
        before=frame_for('finish_before',replay,first-.25)
        after=frame_for('finish_after',replay,first+.25,capture=True)
        validate_frame(replay,before);validate_frame(replay,after)
        assert after['finished']==before['finished']+1
        end=frame_for('finish_month_end',replay,replay['duration'],capture=True)
        validate_frame(replay,end);assert end['finished']==replay['engines_completed']
        save(OUT/'motion_completion_summary.json',dict(passed=True,agv_points=points,first_finish_minute=first,before=before['finished'],after=after['finished'],month_end=end['finished']))
        save(OUT/'extra_parameter_summary.json',summaries)
    finally:
        response=request('/api/simulation/run',original)
        record('restored',response,minute=2950,capture=True)


if __name__=='__main__':run()
