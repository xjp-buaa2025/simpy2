"""Hold a paused test clock lease so editor startups cannot reset shared playback."""
import json
import time
import urllib.request
from tools.unity_mirror_auto_validation import OUT

BASE='http://127.0.0.1:8000/api/simulation/unity/playback'
CLIENT='mirror_auto_validation_guard'

def request(url,value=None,method=None):
    data=json.dumps(value).encode() if value is not None else None
    with urllib.request.urlopen(urllib.request.Request(url,data=data,method=method,headers={'Content-Type':'application/json'}),timeout=5) as r:return json.load(r)

def main():
    current=request(BASE+'.json')
    if current['controller_connected']:raise RuntimeError('A user controller is active; do not override it')
    original=json.loads((OUT/'clock_before.json').read_text())
    assert original['sim_id']==current['sim_id'] and not original['playing']
    owned=request(BASE+'/claim',dict(client_id=CLIENT))
    restored=request(BASE,dict(client_id=CLIENT,sim_id=owned['sim_id'],revision=owned['revision'],minute=original['minute'],playing=original['playing'],speed=original['speed']),method='PUT')
    (OUT/'clock_restoration.json').write_text(json.dumps(dict(before=current,restored=restored,reason='Existing PC initialization claimed the unowned clock and reset playback during the first editor test; restore original paused position before further tests.'),indent=2))
    (OUT/'clock_guarded_before.json').write_text(json.dumps(restored,indent=2))
    stop=OUT/'clock_guard.stop';stop.unlink(missing_ok=True)
    print('Original paused clock restored; test lease active.',flush=True)
    deadline=time.monotonic()+2400
    while not stop.exists() and time.monotonic()<deadline:
        request(BASE+'/claim',dict(client_id=CLIENT));time.sleep(3)
    print('Test lease released by expiry.',flush=True)

if __name__=='__main__':main()
