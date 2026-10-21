"""External animation regression against a real Windows player; isolated service 8042."""
from pathlib import Path
import json,shutil,time
from tools import unity_pc_cells_validation as c
from tools import unity_pc_production_validation as v

OUT=Path('C:/xjp/simpy2/results/unity_validation/pc_upperbody_20261019')
c.OUT=OUT;c.CONTROL=OUT/'native_control';c.PACKAGE=Path('C:/xjp/simpy2/builds/UnityPC_20261019_SubtleWorkers');v.OUT=OUT

def main():
    proc=c.start()
    try:
        c.functional()
        r=v.Runner(c.CONTROL);r.delivery=OUT/'animation';r.delivery.mkdir(exist_ok=True)
        for sid,clip in [('S002','Working_A'),('P001','Working_A'),('F013','Working_A'),('A001','Working_A')]:
            task=next(t for t in r.replay['events'] if t['station_id']==sid and t.get('worker_ids') and t['event_type']=='NORMAL');minute=(task['start_time']+task['end_time'])/2
            base=r.case('clip_'+sid,minute,[v.action('SelectStation',sid)],capture=True)
            workers=[w for w in base['workers'] if w['station']==sid and w['action'] not in ['休息','辅助观察','待机']]
            r.check(sid+'_external_clip',bool(workers) and all(w['motion_clip']==clip for w in workers))
            r.check(sid+'_no_procedural_ik',all(w['contact_weight']==0 for w in workers))
            paused=r.case('paused_'+sid,settle=1)
            stable=lambda data:[(w['id'],w['motion_time'],w['left_hand'],w['right_hand']) for w in data['workers'] if w['station']==sid]
            r.check(sid+'_pause_unchanged',stable(paused)==stable(base))
            first=r.case('play_'+sid,minute,playing=True,speed=.2,settle=.15)
            later=r.case('play_later_'+sid,playing=True,speed=.2,settle=.4)
            r.check(sid+'_motion_advances',stable(first)!=stable(later))
            c.record(r,'motion_'+sid,sid,minute)
        r.case('stop',2950,playing=False)
        body={}
        def distance(a,b):return sum((a[k]-b[k])**2 for k in ['x','y','z'])**.5
        for path in c.CONTROL.glob('motion_*.motion.json'):
            sid=path.name.split('.')[0].replace('motion_','');frames=json.loads(path.read_text(encoding='utf-8-sig'));groups={}
            for frame in frames:
                for worker in frame['workers']:
                    if worker['station']==sid and worker['action'] not in ['休息','辅助观察','待机']:groups.setdefault(worker['id'],[]).append(worker)
            fixed=all(all(distance(rows[0][key],row[key])<.0001 for row in rows for key in ['left_foot','right_foot','hips_position']) for rows in groups.values())
            torso=all(all(rows[0][key]==row[key] for row in rows for key in ['spine_rotation','head_rotation']) for rows in groups.values())
            travel=max(distance(rows[0][key],row[key]) for rows in groups.values() for row in rows for key in ['left_hand','right_hand'])
            r.check(sid+'_feet_hips_fixed',bool(groups) and fixed);r.check(sid+'_torso_head_fixed',torso);r.check(sid+'_only_small_hand_motion',.001<travel<.08)
            body[sid]=dict(samples=len(frames),fixed_feet_hips=fixed,fixed_torso_head=torso,max_hand_motion_m=travel)
        (OUT/'body_motion.json').write_text(json.dumps(body,indent=2))
        c.encode()
        (OUT/'animation_summary.json').write_text((r.delivery/'functional_summary.json').read_text(encoding='utf-8'),encoding='utf-8')
        print('EXTERNAL MOTION ACCEPTANCE PASSED',flush=True)
    finally:
        proc.terminate();proc.wait(30)

if __name__=='__main__':main()
