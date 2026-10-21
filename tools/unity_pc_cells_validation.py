"""PC production-cell release acceptance; all mutations use isolated SimPy port 8042."""
from pathlib import Path
import argparse,json,os,subprocess,time,shutil,sys
from tools import unity_pc_production_validation as v

OUT=Path('C:/xjp/simpy2/results/unity_validation/pc_cells_20261018')
CONTROL=OUT/'native_control'
PACKAGE=Path('C:/xjp/simpy2/builds/UnityPC_20261018_ProductionCells')
SERVER_OUT=OUT.parent/'pc_production_20261017'
v.OUT=OUT

def start():
    CONTROL.mkdir(exist_ok=True);(CONTROL/'connection.json').write_text(json.dumps(dict(serverUrl='http://127.0.0.1:8042',vrMirrorMode='off')))
    proc=subprocess.Popen([str(PACKAGE/'EngineFactoryPC.exe'),'--simpy-server=http://127.0.0.1:8042','--pc-production-test='+str(CONTROL),'-screen-fullscreen','0','-screen-width','1920','-screen-height','1080','-logFile',str(OUT/'native.log')],cwd=os.environ['TEMP'])
    (OUT/'native_pid.json').write_text(json.dumps(dict(pid=proc.pid,exe=str(PACKAGE/'EngineFactoryPC.exe'))));return proc

def record(r,name,sid,minute):
    path=CONTROL/'request.json';assert not path.exists()
    result=CONTROL/(name+'.json');result.unlink(missing_ok=True)
    request=dict(name=name,minute=minute,width=1920,height=1080,playing=True,speed=.2,settle=.5,record_seconds=10,record_fps=12,capture=True,actions=[v.action('SelectStation',sid)])
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(request));temp.replace(path);deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        error=CONTROL/(name+'.error.txt')
        if error.exists():raise RuntimeError(error.read_text())
        if result.exists():break
        time.sleep(.3)
    else:raise TimeoutError(name)
    data=json.loads((CONTROL/(name+'.motion.json')).read_text(encoding='utf-8-sig'))
    working=[w for frame in data for w in frame['workers'] if w['station']==sid and w['action'] not in ['休息','辅助观察','待机'] and w['contact_weight']>=.99]
    valid=[w for w in working if w['contact_valid']]
    stats=dict(samples=len(data),contact_samples=len(working),valid_contacts=len(valid),max_error=max((w['contact_error'] for w in valid),default=-1),workers=list({w['id'] for f in data for w in f['workers'] if w['station']==sid}))
    print(name,stats,flush=True)
    shutil.copy2(CONTROL/(name+'.png'),r.delivery/(name+'.png'));shutil.copy2(result,r.delivery/result.name)
    return stats

def functional():
    r=v.Runner(CONTROL);r.run()
    for name,sid in [('cell_overview',''),('cell_washer','S002'),('cell_nitrogen','P011'),('cell_test','F013'),('cell_assembly','P001'),('cell_gantry','A001')]:
        tasks=[t for t in r.replay['events'] if t['station_id']==sid and t.get('worker_ids') and t['event_type'] in ['NORMAL','REWORK','IN_PROGRESS']]
        minute=2950 if not tasks else (tasks[0]['start_time']+tasks[0]['end_time'])/2
        data=r.case(name,minute,[v.action('SelectStation',sid)] if sid else [v.action('RestoreDefaultViews'),v.action('ClosePcDrawer')],capture=True)
        r.check(name+'_cell_clearance',data['cell_route_conflicts']==0 and data['cell_keepout_conflicts']==0)
        r.check(name+'_cells_present',data['cell_props']>=60 and data['cell_shared_groups']>=10)
        r.check(name+'_materials',data['missing_materials']==0 and data['unsupported_shaders']==0)
        r.check(name+'_no_action_text',not any(any(word in t['text'] for word in ['双手装配','面板操作','俯身检测']) for t in data['texts']))
        r.check(name+'_grounded',all(abs(row['gap'])<.002 for row in data['ground']))
        if sid:
            expected=len({worker for t in r.replay['events'] if t['station_id']==sid and t['event_type'] in ['NORMAL','REWORK','IN_PROGRESS'] and t['start_time']<=minute<t['end_time'] for worker in t.get('worker_ids',[])})
            caption=next(t['text'] for t in data['texts'] if t['name']=='AssignedWorkers')
            r.check(name+'_count_matches_events',caption==f'当前投入 {expected} 人')
    (r.delivery/'full_regression.json').write_bytes((r.delivery/'functional_summary.json').read_bytes())

def films():
    r=v.Runner(CONTROL);r.delivery=OUT/'films';r.delivery.mkdir(exist_ok=True);results={}
    for sid in ['S002','P011','F013','P001','A001']:
        task=next(t for t in r.replay['events'] if t['station_id']==sid and t.get('worker_ids') and t['event_type']=='NORMAL')
        results[sid]=record(r,'motion_'+sid,sid,(task['start_time']+task['end_time'])/2)
    (OUT/'motion_summary.json').write_text(json.dumps(results,indent=2))
    assert all(x['valid_contacts']>0 and x['max_error']<=.03 for x in results.values()),results
    encode()

def encode():
    sys.path.insert(0,str(OUT.parents[2]/'.cache/pc_cells_video'));import imageio_ffmpeg
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();target=OUT/'films';target.mkdir(exist_ok=True)
    for folder in CONTROL.glob('motion_*_frames'):
        name=folder.name.removesuffix('_frames')
        subprocess.run([ffmpeg,'-y','-loglevel','error','-framerate','12','-i',str(folder/'%05d.png'),'-frames:v',str(len(json.loads((CONTROL/(name+'.motion.json')).read_text(encoding='utf-8-sig')))),'-vf','scale=1280:-2','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(target/(name+'.mp4'))],check=True)

def integration():
    from tools import unity_pc_production_integration as i
    class CellRunner(v.Runner):
        def __init__(self,*args,**kwargs):super().__init__(CONTROL)
        def case(self,*args,**kwargs):
            data=super().case(*args,**kwargs);assert data['cell_route_conflicts']==0 and data['cell_keepout_conflicts']==0;assert all(abs(r['gap'])<.002 for r in data['ground']);return data
    i.OUT=SERVER_OUT;i.Runner=CellRunner;i.main();shutil.copytree(SERVER_OUT/'integration',OUT/'integration',dirs_exist_ok=True)

def comparison():
    r=v.Runner(CONTROL);r.delivery=OUT/'after';r.delivery.mkdir(exist_ok=True)
    for name,sid,t in [('overview','',2950),('washer','S002',259),('nitrogen','F012',1082),('test','F013',2950),('assembly','A001',2950)]:
        r.case(name,t,[v.action('SelectStation',sid)] if sid else [v.action('RestoreDefaultViews'),v.action('ClosePcDrawer')],capture=True,settle=2)
    r.case('area',2950,[v.action('SelectStation','S002'),v.action('FocusSelectedPcArea')],capture=True,settle=2)

def layout_preview():
    import copy
    from tools.unity_pc_production_integration import upload
    r=v.Runner(CONTROL);r.delivery=OUT/'layout_preview';r.delivery.mkdir(exist_ok=True)
    task=next(t for t in r.replay['events'] if t['station_id']=='B002' and t.get('worker_ids') and t['event_type']=='NORMAL');minute=(task['start_time']+task['end_time'])/2
    base=r.case('ready',minute,[v.action('RestoreDefaultViews')]);before_size=next(g['size']['y'] for g in base['geometry'] if g['id']=='B002');published=v.http(v.API+'layout.json');candidate=copy.deepcopy(published['layout']);row=next(x for x in candidate['stations'] if x['station_id']=='B002');row['scale']*=1.1;row['yaw']=(row['yaw']+17)%360
    validation=upload(candidate);assert validation['valid'],validation.get('errors')
    path=OUT/'preview_candidate.json';path.write_text(json.dumps(candidate,ensure_ascii=False),encoding='utf-8')
    for index in range(5):
        preview=r.case('preview_'+str(index),minute,[v.action('OpenFactoryLayoutPanel'),v.action('ImportFactoryLayout',str(path))],capture=index==0,settle=3)
        current=next(g for g in preview['geometry'] if g['id']=='B002');r.check('rotation_applied_'+str(index),abs(current['yaw']-row['yaw'])<.1)
        r.check('scale_applied_'+str(index),abs(current['size']['y']/before_size-1.1)<.01)
        r.check('preview_clearance_'+str(index),preview['cell_route_conflicts']==0 and preview['cell_keepout_conflicts']==0 and all(abs(g['gap'])<.002 for g in preview['ground']))
        r.check('preview_not_published_'+str(index),v.http(v.API+'layout.json')['layout']['revision']==published['layout']['revision'])
        restored=r.case('cancel_'+str(index),minute,[v.action('CancelFactoryLayoutPreview')],capture=index==0,settle=2)
        original=next(x for x in published['layout']['stations'] if x['station_id']=='B002');actual=next(g for g in restored['geometry'] if g['id']=='B002')
        r.check('cancel_restores_'+str(index),abs(actual['yaw']-original['yaw'])<.1 and restored['cell_route_conflicts']==0 and restored['cell_keepout_conflicts']==0 and abs(restored['minute']-minute)<.1)
    r.save()

def main():
    arg=argparse.ArgumentParser();arg.add_argument('phase',choices=['functional','films','integration','preview','soak','mirror','encode','comparison','layout_preview']);phase=arg.parse_args().phase
    if phase=='encode':encode();return
    if phase=='mirror':
        from tools import unity_pc_bright_validation as b
        b.OUT=OUT;b.PACKAGE=PACKAGE;b.mirror();return
    if phase=='soak':
        from tools import unity_pc_bright_validation as b
        b.OUT=OUT;b.CONTROL=CONTROL;b.soak();return
    proc=start()
    try:
        if phase=='preview':
            r=v.Runner(CONTROL);r.delivery=OUT/'preview2';r.delivery.mkdir(exist_ok=True)
            for name,sid,minute in [('overview','',2950),('washer','S002',259),('nitrogen','P011',0),('test','F013',1120),('assembly','A001',2240)]:
                if sid=='P011':
                    task=next(t for t in r.replay['events'] if t['station_id']==sid and t.get('worker_ids') and t['event_type']=='NORMAL');minute=(task['start_time']+task['end_time'])/2
                data=r.case(name,minute,[v.action('SelectStation',sid)] if sid else [v.action('RestoreDefaultViews'),v.action('ClosePcDrawer')],capture=True)
                print(name,[(w['id'],w['action'],w['left_reach'],w['right_reach'],w['contact_weight'],w['contact_valid']) for w in data['workers'] if w['station']==sid],flush=True)
            record(r,'preview_motion','S002',259)
        else:globals()[phase]()
    finally:proc.terminate();proc.wait(30)

if __name__=='__main__':main()
