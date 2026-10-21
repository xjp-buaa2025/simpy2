"""Original replay and clocks on an isolated review port; no formal-state writes."""
from pathlib import Path
import os,shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/pt6a29_original_20261021/server'/os.getenv('SIMPY_PT29_REVIEW_ID','initial')
OUT.mkdir(parents=True,exist_ok=True)
REPLAY=OUT/'replay.json'
if not REPLAY.exists():shutil.copy2(ROOT/'results/unity_validation/replay.json',REPLAY)
os.environ['SIMPY_REPLAY_PATH']=str(REPLAY)
os.environ['SIMPY_LAYOUT_STORE']=str(OUT/'legacy_store')
os.environ['SIMPY_PHYSICAL_LAYOUT_STORE']=str(OUT/'physical_store')
from fastapi import FastAPI
from app.api import unity_playback,factory_layout,pt6a29_layout
app=FastAPI()
for router in [unity_playback.router,factory_layout.router,pt6a29_layout.router]:app.include_router(router,prefix='/api/simulation/unity')
@app.get('/api/simulation/unity/replay.json')
def replay():return factory_layout.store.replay
@app.get('/api/simulation/unity/sync_status.json')
def status():return dict(success=True,sim_id=factory_layout.store.replay['sim_id'],layout_revision=factory_layout.store.current['revision'])
if __name__=='__main__':
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=8056)
