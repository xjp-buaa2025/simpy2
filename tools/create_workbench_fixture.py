from pathlib import Path
import json
out=Path('results/workbench_validation');out.mkdir(exist_ok=True)
d=json.loads(Path('results/area_capacity_validation/baseline-scenario.json').read_text(encoding='utf-8'))
r=d['result'];events=[]
for i in range(100000):
 start=(i//200)*20;rid=i%200
 events.append(dict(engine_id=rid+1,step_id='S001',task_name='固定性能样本',area_id='ST01',workstation_id=None,start_time=start,end_time=start+15,event_type='NORMAL',worker_ids=[f'shared:Worker_{rid:03}'],equipment_used=[f'equipment:shared:fixture_{rid:03}'],is_complete=True,rework_count=0))
r['gantt_events']=events;r['sim_duration']=10000;r['engines_completed']=200;r['worker_fatigue_data']=[];r['worker_stats']=[dict(resource_id=f'shared:Worker_{i:03}',work_time=7500,rest_time=0,utilization_rate=.75,tasks_completed=500) for i in range(200)]
r['equipment_stats']=[];r['resource_snapshot']['resources']=[dict(resource_id=f'equipment:shared:fixture_{i:03}',label=f'测试资源 {i}',capacity=1,owner='shared') for i in range(200)];r['area_stats']=[];r['area_completion_events']=[];d['baseline']=None
(out/'synthetic-100k.json').write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8')
print('Fixture:',(out/'synthetic-100k.json').stat().st_size,'bytes')
