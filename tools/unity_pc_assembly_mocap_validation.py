from pathlib import Path
import json,math
from tools import unity_pc_cells_validation as c
from tools import unity_pc_production_validation as v
OUT=Path('C:/xjp/simpy2/results/unity_validation/pc_assembly_mocap_20261019')
c.OUT=OUT;c.CONTROL=OUT/'native_control';c.PACKAGE=Path('C:/xjp/simpy2/builds/UnityPC_20261019_AssemblyMoCap');v.OUT=OUT

def ground(data):return all(abs(w['left_sole_gap'])<.002 and abs(w['right_sole_gap'])<.002 for w in data['workers'])
def main(smoke=False):
    proc=c.start()
    try:
        r=v.Runner(c.CONTROL);r.delivery=OUT/'assembly';r.delivery.mkdir(exist_ok=True)
        for sid,clip in [('S002','RecordedScrewingCycle'),('P001','RecordedAssemblyCycle'),('F013','RecordedAssemblyCycle'),('A001','RecordedAssemblyCycle')]:
            task=next(t for t in r.replay['events'] if t['station_id']==sid and t.get('worker_ids') and t['event_type']=='NORMAL');minute=(task['start_time']+task['end_time'])/2
            data=r.case('clip_'+sid,minute,[v.action('SelectStation',sid)],capture=True)
            workers=[w for w in data['workers'] if w['station']==sid and w['action'] not in ['休息','辅助观察','待机']]
            r.check(sid+'_original_recording',bool(workers) and all(w['motion_clip']==clip for w in workers))
            r.check(sid+'_actual_boot_support',ground(data));r.check(sid+'_no_ik',all(w['contact_weight']==0 for w in data['workers']))
            paused=r.case('pause_'+sid,settle=.6);pose=lambda d:[(w['id'],w['left_hand'],w['right_hand']) for w in d['workers']]
            r.check(sid+'_pause',pose(paused)==pose(data))
            c.record(r,'motion_'+sid,sid,minute)
        if smoke:
            for path in c.CONTROL.glob('motion_*.motion.json'):
                frames=json.loads(path.read_text(encoding='utf-8-sig'));r.check(path.stem+'_boot_contacts',all(ground(frame) for frame in frames))
            c.encode();(OUT/'cycle_summary.json').write_text((r.delivery/'functional_summary.json').read_text(encoding='utf-8'),encoding='utf-8');print('FINAL ORIGINAL CYCLES ACCEPTED',flush=True);return
        sweep={}
        for sid in sorted({t['station_id'] for t in r.replay['events'] if t.get('worker_ids') and t['event_type']=='NORMAL'}):
            task=next(t for t in r.replay['events'] if t['station_id']==sid and t.get('worker_ids') and t['event_type']=='NORMAL');data=r.case('sole_'+sid,(task['start_time']+task['end_time'])/2,settle=.2)
            maximum=max((max(abs(w['left_sole_gap']),abs(w['right_sole_gap'])) for w in data['workers']),default=0);sweep[sid]=maximum;r.check(sid+'_left_and_right_soles',maximum<.002)
        (OUT/'ground_sweep.json').write_text(json.dumps(sweep,indent=2))
        for path in c.CONTROL.glob('motion_*.motion.json'):
            frames=json.loads(path.read_text(encoding='utf-8-sig'));r.check(path.stem+'_recorded_boot_contacts',all(ground(frame) for frame in frames))
        (OUT/'assembly_summary.json').write_text((r.delivery/'functional_summary.json').read_text(encoding='utf-8'),encoding='utf-8');c.encode()
        c.functional();c.layout_preview()
        r=v.Runner(c.CONTROL);r.delivery=OUT/'hidden_support';r.delivery.mkdir(exist_ok=True)
        import copy
        from tools.unity_pc_production_integration import upload
        published=v.http(v.API+'layout.json');candidate=copy.deepcopy(published['layout'])
        for row in candidate['stations']:row['show_model']=False
        assert upload(candidate)['valid'];path=OUT/'all_hidden.json';path.write_text(json.dumps(candidate,ensure_ascii=False),encoding='utf-8')
        hidden=r.case('all_models_hidden',2950,[v.action('OpenFactoryLayoutPanel'),v.action('ImportFactoryLayout',str(path))],settle=2)
        r.check('all_hidden_soles_on_floor',ground(hidden) and all(abs(w['support_height'])<.001 for w in hidden['workers']))
        shown=r.case('all_hidden_cancel',2950,[v.action('CancelFactoryLayoutPreview')],settle=2);r.check('all_hidden_cancel_restores_support',ground(shown))
        candidate=copy.deepcopy(published['layout']);next(row for row in candidate['stations'] if row['station_id']=='P001')['show_model']=False
        assert upload(candidate)['valid'];path=OUT/'single_hidden.json';path.write_text(json.dumps(candidate,ensure_ascii=False),encoding='utf-8')
        task=next(t for t in r.replay['events'] if t['station_id']=='P001' and t.get('worker_ids') and t['event_type']=='NORMAL');minute=(task['start_time']+task['end_time'])/2
        preview=r.case('single_model_hidden',minute,[v.action('OpenFactoryLayoutPanel'),v.action('ImportFactoryLayout',str(path))],settle=2)
        r.check('single_hidden_soles_on_floor',ground(preview) and all(abs(w['support_height'])<.001 for w in preview['workers'] if w['station']=='P001'))
        restored=r.case('single_hidden_cancel',minute,[v.action('CancelFactoryLayoutPreview')],settle=2);r.check('single_hidden_cancel_restores_support',ground(restored));r.save()
        print('ASSEMBLY MOCAP AND FOOT SUPPORT ACCEPTED',flush=True)
    finally:proc.terminate();proc.wait(30)
if __name__=='__main__':
    import sys
    smoke='--cycle-smoke' in sys.argv
    if smoke:
        OUT=OUT/'cycle';OUT.mkdir(exist_ok=True);c.OUT=OUT;c.CONTROL=OUT/'native_control';v.OUT=OUT
    main(smoke)
