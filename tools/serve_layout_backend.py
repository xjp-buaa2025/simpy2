"""Start the updated backend, optionally preserving a captured playback clock on upgrade."""
import argparse,json,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--restore-clock');parser.add_argument('--restore-records');args=parser.parse_args()
from app.main import app
from app.api.unity_playback import clock
if args.restore_records:
    from app.api.simulation import simulation_results,SimulationResult
    for record in json.loads(Path(args.restore_records).read_text()):
        result=SimulationResult.model_validate(record);simulation_results[result.sim_id]=result
if args.restore_clock:
    saved=json.loads(Path(args.restore_clock).read_text())
    with clock._lock:
        clock._refresh()
        if saved['sim_id']==clock.sim_id:
            elapsed=max(0,time.time()-saved['server_unix_ms']/1000)
            clock.minute=min(clock.duration,saved['minute']+(elapsed*saved['speed'] if saved['playing'] else 0))
            clock.playing=saved['playing'];clock.speed=saved['speed'];clock.anchor=clock._now();clock.revision=saved['revision']+1
            clock.controller=saved['controller_id'] if saved['controller_connected'] else ''
            clock.lease_until=clock._now()+clock.lease_seconds if clock.controller else 0
import uvicorn
uvicorn.run(app,host='0.0.0.0',port=8000,access_log=False)
