import copy,json,hashlib
from pathlib import Path
import pytest
from app.core import unity_active as active
from app.core.station_progress import build_station_progress,sample_station_progress

@pytest.fixture
def result():
    process=dict(nodes=[dict(step_id='r',task_name='rotor',workstation_id='WS-R01',station='WS-R01',area_id='WS-R01',std_duration=10,predecessors=''),dict(step_id='g',task_name='assemble',workstation_id='WS-G01',station='WS-G01',area_id='WS-G01',std_duration=20,predecessors='r')])
    events=[dict(engine_id=1,step_id='r',task_name='rotor',start_time=0,end_time=10,event_type='NORMAL',worker_ids=['w1']),dict(engine_id=1,step_id='g',task_name='assemble',start_time=13,end_time=33,event_type='NORMAL',worker_ids=['w1'])]
    progress=build_station_progress(sim_id='new',config={},process=process,gantt_events=events,task_completion_events=[dict(engine_id=1,step_id='r',completed_at=13),dict(engine_id=1,step_id='g',completed_at=33)],engine_release_times={1:0},time_minutes=60)
    return dict(sim_id='new',sim_duration=60,engines_completed=1,config=dict(work_hours_per_day=1,work_days_per_month=1),gantt_events=events,station_progress=progress,engine_completion_events=[dict(engine_id=1,end_time=33)],input_snapshot=dict(process=process))

def test_publication_is_immutable_and_preserves_source(tmp_path,monkeypatch,result):
    monkeypatch.setenv('SIMPY_UNITY_ACTIVE_STORE',str(tmp_path))
    before=copy.deepcopy(result);info=active.publish(result,result['input_snapshot']['process'])
    payload=active.snapshot();assert result==before
    assert info['mode']=='pt6a29' and len(payload['stations'])==29 and payload['schema_version']==4
    assert payload['station_progress']==result['station_progress']
    assert payload['engine_completion_events']==result['engine_completion_events']
    assert active.active()['sim_id']=='new'
    assert hashlib.sha256(active.run_bytes(info['publication_id'])).hexdigest()==info['sha256']
    assert all(t['trigger_time']==13 for t in payload['transfers'])
    assert active.publish(result,result['input_snapshot']['process'])==info

def test_invalid_mapping_preserves_last_active(tmp_path,monkeypatch,result):
    monkeypatch.setenv('SIMPY_UNITY_ACTIVE_STORE',str(tmp_path));info=active.publish(result,result['input_snapshot']['process'])
    invalid=copy.deepcopy(result);invalid['input_snapshot']['process']['nodes'][0]['workstation_id']='ST01'
    with pytest.raises(ValueError,match='r → ST01'):active.publish(invalid,invalid['input_snapshot']['process'])
    assert active.active()['publication_id']==info['publication_id']

def test_progress_retains_release_semantics(result):
    payload=active.compile_result(result,result['input_snapshot']['process'])
    assert sample_station_progress(payload['station_progress'],10)['stations'][0]['engines'][0]['progress']==0
    assert sample_station_progress(payload['station_progress'],13)['stations'][0]['engines'][0]['progress']==1

def test_snapshot_paths_cannot_escape(tmp_path,monkeypatch):
    monkeypatch.setenv('SIMPY_UNITY_ACTIVE_STORE',str(tmp_path))
    with pytest.raises(FileNotFoundError):active.run_bytes('../active')

def test_failed_compatibility_write_never_activates_new_result(tmp_path,monkeypatch,result):
    monkeypatch.setenv('SIMPY_UNITY_ACTIVE_STORE',str(tmp_path));active.publish(result,result['input_snapshot']['process']);old=active.active()
    changed=copy.deepcopy(result);changed['sim_id']='next';changed['station_progress']['sim_id']='next'
    original=active.atomic
    def unavailable(path,content):
        if path.name=='station_progress.json':raise PermissionError('locked')
        original(path,content)
    monkeypatch.setattr(active,'atomic',unavailable)
    with pytest.raises(PermissionError):active.publish(changed,changed['input_snapshot']['process'],progress_path=tmp_path/'station_progress.json')
    assert active.active()==old

def test_changed_publication_releases_controller_even_for_same_run():
    from app.core.unity_playback import UnityPlaybackClock
    metadata=['same',60,'a'];clock=UnityPlaybackClock(lambda:tuple(metadata));state=clock.claim('pc')
    clock.control('pc','same',state['revision'],minute=20,playing=True)
    metadata[2]='b';state=clock.snapshot()
    assert state['minute']==0 and not state['playing'] and not state['controller_connected']

def test_physical_layout_uses_current_web_bindings_and_compact_routes(tmp_path,monkeypatch,result):
    from app.core.pt6a29_layout import PhysicalLayoutStore
    monkeypatch.setenv('SIMPY_UNITY_ACTIVE_STORE',str(tmp_path/'active'));active.publish(result,result['input_snapshot']['process'])
    store=PhysicalLayoutStore(tmp_path/'layout');document=store.snapshot();assert document['sim_id']=='new'
    target=next(s for s in document['slots'] if s['zone_id']=='WS-R01');target['x']+=.01
    validated=store.validate(document);assert validated['changes'][0]['affected_steps']==['r']
    assert len(store.export('json'))<2*1024*1024

def test_mode_guard_and_clock_reset(tmp_path,monkeypatch,result):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import unity_playback as api
    from app.core.unity_playback import UnityPlaybackClock
    monkeypatch.setenv('SIMPY_UNITY_ACTIVE_STORE',str(tmp_path));active.publish(result,result['input_snapshot']['process'])
    monkeypatch.setattr(api,'clock',UnityPlaybackClock(api.replay_metadata))
    app=FastAPI();app.include_router(api.router,prefix='/unity')
    with TestClient(app) as client:
        assert client.post('/unity/playback/claim',json={'client_id':'old'}).status_code==409
        state=client.post('/unity/playback/claim',json={'client_id':'new','mode':'pt6a29'}).json();assert state['sim_id']=='new'
        assert client.put('/unity/playback',json=dict(client_id='new',mode='pt6a29',sim_id='new',revision=state['revision'],minute=30)).status_code==200
