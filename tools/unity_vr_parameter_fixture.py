"""Temporary HTTP controller for testing the Editor VR viewer without a PC player."""
import json,time,urllib.request,urllib.error
from unity_parameter_validation import OUT,read

client='parameter-vr-validation'
base='http://127.0.0.1:8000/api/simulation/unity/'
last=None
until=time.monotonic()+420

def call(route,body,method):
    req=urllib.request.Request(base+route,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method=method)
    with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)

while time.monotonic()<until and not (OUT/'vr_fixture.stop').exists():
    try:
        state=call('playback/claim',{'client_id':client},'POST')
        target=read(OUT/'vr_clock_target.json')
        key=(state['sim_id'],target['minute'],target['speed'])
        if key!=last:
            state=call('playback',dict(client_id=client,sim_id=state['sim_id'],revision=state['revision'],minute=min(state['duration'],target['minute']),speed=target['speed'],playing=False),'PUT')
            last=key;print(json.dumps(state),flush=True)
    except (urllib.error.URLError,TimeoutError) as error:
        print(str(error),flush=True)
    time.sleep(2)
print('Fixture stopped',flush=True)
