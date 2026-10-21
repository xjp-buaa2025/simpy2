import json,time,urllib.request,urllib.error
from pathlib import Path
from tools.unity_factory_layout_validation import review,until,server,OUT,ROOT
from tools import unity_navigation_validation as nav
BASE='http://127.0.0.1:8041/api/simulation/unity/'
def call(endpoint,method='GET',body=None):
    request=urllib.request.Request(BASE+endpoint,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'},method=method)
    return json.load(urllib.request.urlopen(request,timeout=20))

def main():
    checks={};controller='layout_validation';deadline=time.monotonic()+16
    while True:
        try:call('playback/claim','POST',dict(client_id=controller));break
        except urllib.error.HTTPError:
            if time.monotonic()>deadline:raise
            time.sleep(.5)
    before=call('playback.json');assert not before['playing']
    revision=server()['layout']['revision'];history=[]
    for i in range(6):
        call('playback/claim','POST',dict(client_id=controller))
        if i%2:
            document=json.loads((OUT/'candidate.json').read_text())
            result=call('layout','PUT',dict(client_id=controller,sim_id=before['sim_id'],expected_revision=revision,layout=document))
        else:
            source='default' if i==0 else 'previous'
            result=call('layout/restore','POST',dict(client_id=controller,sim_id=before['sim_id'],expected_revision=revision,source=source))
        revision=result['layout']['revision']
        r=until('vr_switch_'+str(i),lambda r:r['revision']==revision and '已同步' in r['status'])
        history.append(dict(revision=revision,materials=r['materials'],obstacles=r['obstacles']))
        assert abs(r['minute']-before['minute'])<.1
    checks['repeated_switch_clock_stable']=True
    checks['no_material_growth']=abs(history[-1]['materials']-history[1]['materials'])<=4
    checks['stable_collisions']=len({r['obstacles'] for r in history})==1
    # New replay identity and calendar; retain all events, station IDs and completion facts.
    path=OUT/'test_replay.json';original=json.loads((ROOT/'results/unity_validation/replay.json').read_text());changed=json.loads(path.read_text());changed['sim_id']='layout-replan-'+str(time.time_ns());changed['work_days_per_month']=26;changed['work_hours_per_day']=7;path.write_text(json.dumps(changed))
    synced=until('vr_replan',lambda r:r['sim_id']==changed['sim_id'] and '已同步' in r['status'])
    checks['replan_keeps_layout']=synced['revision']==revision and '布局测试' in next(g['label'] for g in synced['geometry'] if g['station_id']=='P011')
    # Restore default by publishing a new version, then run the existing input/navigation suite.
    call('playback/claim','POST',dict(client_id=controller));state=call('playback.json');result=call('layout/restore','POST',dict(client_id=controller,sim_id=state['sim_id'],expected_revision=revision,source='default'));revision=result['layout']['revision']
    until('vr_restored_default',lambda r:r['revision']==revision)
    nav.OUT=OUT
    report=nav.audit('layout_vr_navigation','test');checks['existing_navigation']=report['passed']
    # Leave the isolated replay exactly as it started.
    path.write_text(json.dumps(original));until('vr_replay_restored',lambda r:r['sim_id']==original['sim_id'] and '已同步' in r['status'])
    result=dict(checks=checks,history=history,passed=all(checks.values()),hardware_tested=False)
    (OUT/'regression.json').write_text(json.dumps(result,indent=2));print(result,flush=True);assert result['passed']
if __name__=='__main__':main()
