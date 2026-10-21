"""Launch an isolated copy of the real layout/clock HTTP APIs for Unity tests."""
import os,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/unity_validation/layout_20261015'
OUT.mkdir(parents=True,exist_ok=True)
os.environ['SIMPY_LAYOUT_STORE']=str(OUT/'test_store')
os.environ['SIMPY_REPLAY_PATH']=str(OUT/'test_replay.json')
if not Path(os.environ['SIMPY_REPLAY_PATH']).exists():Path(os.environ['SIMPY_REPLAY_PATH']).write_bytes((ROOT/'results/unity_validation/replay.json').read_bytes())
from fastapi import FastAPI
from app.api import unity_playback,factory_layout
app=FastAPI();app.include_router(unity_playback.router,prefix='/api/simulation/unity');app.include_router(factory_layout.router,prefix='/api/simulation/unity')
@app.get('/api/simulation/unity/replay.json')
def replay():return factory_layout.store.replay
@app.get('/api/simulation/unity/sync_status.json')
def status():return dict(success=True,sim_id=factory_layout.store.replay['sim_id'],layout_revision=factory_layout.store.current['revision'])
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8041)
