"""Real replay/layout/clock APIs on a separate port; never touches the user's run."""
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("SIMPY_VALIDATION_OUT", str(ROOT / "results/unity_validation/pc_production_20261017")))
OUT.mkdir(parents=True, exist_ok=True)
os.environ["SIMPY_LAYOUT_STORE"] = str(OUT / "test_store")
os.environ["SIMPY_REPLAY_PATH"] = str(OUT / "test_replay.json")
replay_path = Path(os.environ["SIMPY_REPLAY_PATH"])
if not replay_path.exists():
    with urllib.request.urlopen("http://127.0.0.1:8000/api/simulation/unity/replay.json", timeout=15) as response:
        replay_path.write_bytes(response.read())
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api import unity_playback, factory_layout

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(ROOT / "frontend")), name="static")
for folder in ("css", "js"):
    app.mount("/" + folder, StaticFiles(directory=str(ROOT / "frontend" / folder)), name=folder)
@app.get("/")
def frontend():
    return FileResponse(ROOT / "frontend/index.html")

app.include_router(unity_playback.router, prefix="/api/simulation/unity")
app.include_router(factory_layout.router, prefix="/api/simulation/unity")

@app.get("/api/simulation/unity/replay.json")
def replay():
    return factory_layout.store.replay

@app.get("/api/simulation/unity/sync_status.json")
def status():
    return dict(success=True, sim_id=factory_layout.store.replay["sim_id"], layout_revision=factory_layout.store.current["revision"])

# Exercise the webpage's actual scheduling endpoint, redirecting every publication
# into this test folder (including the otherwise fixed StreamingAssets snapshot).
from tools import unity_validation as publisher
publisher.OUTPUT = OUT / "publication"
publisher.OUTPUT.mkdir(exist_ok=True)
publisher.PLAYER_REPLAY = replay_path
from app.api import simulation
app.include_router(simulation.router, prefix="/api/simulation")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8042)
