"""Isolated UI validation server. All runs explicitly skip PC/VR publication."""
import argparse
from pathlib import Path
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.api import simulation, process, config
from app.core.run_progress import run_progress


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8047)
    args = parser.parse_args()
    app = FastAPI()
    root = Path(__file__).resolve().parents[1] / 'frontend'
    update = run_progress.update

    def slow_update(*values, **details):
        update(*values, **details)
        if len(values) > 3 and values[3] in ('main', 'comparison'):
            time.sleep(.04)
    run_progress.update = slow_update

    @app.post('/api/simulation/run')
    def isolated_run(request: simulation.SimulationRequest):
        request.publish_to_clients = False
        return simulation.run_simulation(request, None)

    @app.post('/__validation/stop')
    def stop():
        server.should_exit = True
        return {'stopping': True}

    @app.get('/', response_class=HTMLResponse)
    def index():
        return root.joinpath('index.html').read_text(encoding='utf-8')

    app.include_router(simulation.router, prefix='/api/simulation')
    app.include_router(process.router, prefix='/api/process')
    app.include_router(config.router, prefix='/api/config')
    for name in ('js', 'css'):
        app.mount('/' + name, StaticFiles(directory=root / name))
    app.mount('/static', StaticFiles(directory=root))
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, access_log=False))
    server.run()


if __name__ == '__main__':
    main()
