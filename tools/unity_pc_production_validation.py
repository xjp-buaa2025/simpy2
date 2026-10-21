"""Acceptance against real Unity rendering, physics picking and live HTTP playback."""
from __future__ import annotations
import argparse
import copy
import json
import shutil
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path('C:/AllUnityProjects/MainProject/MainProject')
OUT=ROOT/'results/unity_validation/pc_production_20261017'
API='http://127.0.0.1:8042/api/simulation/unity/'

def http(url, value=None, method=None):
    req=urllib.request.Request(url, data=None if value is None else json.dumps(value).encode(), headers={'Content-Type':'application/json'},method=method)
    with urllib.request.urlopen(req,timeout=90) as response:return json.load(response)

def action(method,*args):return dict(method=method,args=[str(a).lower() if isinstance(a,bool) else str(a) for a in args])

class Runner:
    def __init__(self,folder,editor=False):
        self.folder=Path(folder);self.editor=editor;self.checks={};self.records={};self.size=(1920,1080)
        self.delivery=OUT/('editor' if editor else 'native');self.delivery.mkdir(parents=True,exist_ok=True)
        self.replay=http(API+'replay.json')
    def check(self,name,value):
        self.checks[name]=bool(value);self.save();print(name, bool(value),flush=True)
        if not value:raise AssertionError(name)
    def save(self):
        (self.delivery/'functional_summary.json').write_text(json.dumps(dict(passed=all(self.checks.values()),checks=self.checks,records=self.records),ensure_ascii=False,indent=2),encoding='utf-8')
    def case(self,name,minute=-1,actions=(),capture=False,playing=False,speed=10,settle=1.2):
        path=self.folder/'request.json'
        if path.exists():raise RuntimeError('An existing acceptance request is pending')
        result=self.folder/(name+'.json');error=self.folder/(name+'.error.txt')
        result.unlink(missing_ok=True);error.unlink(missing_ok=True)
        req=dict(name=name,minute=minute,width=self.size[0],height=self.size[1],actions=list(actions),capture=capture,playing=playing,speed=speed,settle=settle)
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(req),encoding='utf-8');temporary.replace(path)
        end=time.monotonic()+90
        while time.monotonic()<end:
            if error.exists():raise RuntimeError(error.read_text(encoding='utf-8'))
            if result.exists():
                r=json.loads(result.read_text(encoding='utf-8-sig'));shutil.copy2(result,self.delivery/result.name)
                png=self.folder/(name+'.png')
                if capture:
                    for _ in range(40):
                        if png.exists() and png.stat().st_size>2000:break
                        time.sleep(.1)
                    shutil.copy2(png,self.delivery/png.name)
                self.records[name]={k:r[k] for k in ['sim_id','mode','focused_station','visible_workers','minute','finished','width','height','enabled_cameras','progress']}
                self.save();return r
            time.sleep(.2)
        raise TimeoutError(name)
    def size_view(self,width,height):
        if self.editor:
            from tools import unity_pc_ui_validation as ui
            ui.OUTPUT=self.delivery
            name='viewport_'+str(width)
            ui.record(name,{'request':dict(name=name,width=width,height=height,seek_minute=-1,layout_only=True,settle_frames=8,settle_seconds=.5,capture=True,actions=[]),'expected':dict(width=width,height=height,stations=79,role='PCController',preview=False)},90)
        self.size=(width,height)
    def expected_workers(self,minute):
        return {w for t in self.replay['events'] if t['start_time']<=minute<t['end_time'] and t['event_type'] in ['NORMAL','REWORK','IN_PROGRESS','REST'] for w in t.get('worker_ids',[])}
    def worker_check(self,name,r):
        actual=[w['id'] for w in r['workers']]
        self.check(name+'_unique_actual_assignments',len(actual)==len(set(actual)) and set(actual)==self.expected_workers(r['minute']))
        self.check(name+'_human_scale',all(1.5<w['height']<2 for w in r['workers']))
    def run(self):
        reset=[action('RestoreDefaultViews'),action('ClosePcDrawer'),action('SetFirstPersonWindowVisible',False)]
        r=self.case('overview',2950,reset,capture=True);self.check('all_79_visible',r['stations']==79 and r['labels']==79 and r['enabled_cameras']==1);self.worker_check('overview',r)
        for sid in ['S002','F012','F013','A001']:
            t=next(t for t in self.replay['events'] if t['station_id']==sid and t['event_type']=='NORMAL')
            minute=(t['start_time']+t['end_time'])/2
            r=self.case('focus_'+sid,minute,[action('SelectStation',sid)],capture=True)
            self.check(sid+'_main_camera_focus',r['mode']=='station' and r['focused_station']==sid and r['enabled_cameras']==1 and .1<r['focus_viewport']['x']<.68 and .2<r['focus_viewport']['y']<.8)
            self.check(sid+'_progress_from_event',abs(r['progress']-.5)<.015);self.worker_check(sid,r)
        self.case('before_physics_pick',1082.2563,reset)
        r=self.case('physics_pick',actions=[action('pick_station','F012')],capture=True);self.check('model_collider_station_binding',r['picked_station']=='F012' and r['focused_station']=='F012')
        before=self.case('paused_pose');after=self.case('paused_pose_later',settle=2)
        poses=lambda r:{w['id']:(w['position'],w['left_hand'],w['right_hand']) for w in r['workers']}
        self.check('pause_freezes_worker_pose',poses(before)==poses(after) and abs(before['minute']-after['minute'])<.001)
        r=self.case('orbit',actions=[action('orbit',90)],capture=True);self.check('orbit_keeps_selection_and_clock',r['focused_station']=='F012' and r['minute']==after['minute'] and r['camera_position']!=after['camera_position'])
        r=self.case('area',actions=[action('FocusSelectedPcArea')],capture=True);self.check('area_camera_and_subset',r['mode']=='area' and 0<r['labels']<79)
        r=self.case('agv_follow',2950,[action('ToggleAgvCamera'),action('OpenPcDrawer',2)],capture=True);self.check('agv_follow_leaves_station_mode',r['mode']=='overview' and r['enabled_cameras']==1)
        r=self.case('local_preview',actions=reset+[action('SetFirstPersonWindowVisible',True)],capture=True);self.check('local_preview_opens',r['preview'] and r['enabled_cameras']==2)
        r=self.case('preview_closed',actions=[action('SetFirstPersonWindowVisible',False)]);self.check('closed_preview_stops_camera',not r['preview'] and r['enabled_cameras']==1)
        self.case('engine_filter',2950,[action('CycleEngine',1),action('OpenPcDrawer',1)],capture=True)
        r=self.case('filter_workers');self.worker_check('filter',r)
        self.case('clear_filter',actions=[action('CycleEngine',-1)])
        wait=next(t for t in self.replay['events'] if t['event_type']=='WAITING' and not t.get('worker_ids') and t['end_time']>t['start_time']+1)
        r=self.case('waiting',(wait['start_time']+wait['end_time'])/2,[action('SelectStation',wait['station_id'])],capture=True);self.worker_check('waiting',r)
        self.check('waiting_does_not_fabricate_progress',r['progress']==0 or any(t['station_id']==wait['station_id'] and t['event_type'] in ['NORMAL','REWORK'] and t['start_time']<=r['minute']<t['end_time'] for t in self.replay['events']))
        r=self.case('month_end',self.replay['duration'],reset+[action('OpenPcDrawer',1)],capture=True);self.check('month_end_matches_web',r['finished']==self.replay['engines_completed'] and r['visible_workers']==0)
        r=self.case('seek_back',1082.2563,[action('SelectStation','F012')]);self.worker_check('seek_back',r)
        self.check('seek_restores_progress',abs(r['progress']-.5)<.015)
        for width,height in [(1366,768),(1920,1080),(2560,1440)]:
            self.case('before_resize_'+str(width),actions=reset)
            self.size_view(width,height)
            r=self.case('overview_'+str(width),2950,reset,capture=True);self.check('resolution_'+str(width),(r['width'],r['height'])==(width,height) and r['labels']==79)
            r=self.case('focus_'+str(width),1082.2563,[action('SelectStation','F012')],capture=True)
            # Scrollable detail bodies are intentionally taller than their viewport.
            chart_names={'OperationPercent','PhysicalWorkState','AssignedWorkers','OperationTimeCaption','OperationTimeValue','CapacityText','TimelineLegend','ProcessFlow'}
            clipped=[t for t in r['texts'] if t['active'] and t['name'] in chart_names and t['preferred_height']>t['height']+1]
            self.check('chart_labels_fit_'+str(width),not clipped)
        self.size_view(1920,1080)
        r=self.case('standard_quality',actions=[action('TogglePcProductionQuality')],capture=True);self.check('standard_quality_switch',not r['high_quality'])
        r=self.case('high_quality',actions=[action('TogglePcProductionQuality')]);self.check('high_quality_restored',r['high_quality'])
        r=self.case('speed_play',1082.2563,[action('SelectStation','F012')],playing=True,speed=60,settle=.5);self.check('speed_play_preserved',r['playing'] and r['speed']==60 and r['minute']>1082.2563)
        r=self.case('speed_pause',1082.2563,playing=False,speed=10);self.check('pause_and_seek_preserved',not r['playing'] and abs(r['minute']-1082.2563)<.01)
        self.case('settings',actions=[action('TogglePcMenu','settings')],capture=True)
        self.case('finished',2950,reset,capture=True)
        return self.checks

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--native-folder');args=parser.parse_args()
    runner=Runner(args.native_folder or PROJECT/'SimPyValidation/pc_production',editor=not args.native_folder)
    runner.run();runner.save();print('All functional checks passed',flush=True)
