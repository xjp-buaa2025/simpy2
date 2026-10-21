"""Disposable local UI acceptance server; no client publication, optional model fault."""
import argparse
import re
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn
from app.api import simulation, process, config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8047)
    args = parser.parse_args()
    app = FastAPI()
    root = Path(__file__).resolve().parents[1]
    fault = {'model': False}

    @app.get('/', response_class=HTMLResponse)
    def index():
        return (root/'frontend/index.html').read_text(encoding='utf-8')

    @app.post('/api/simulation/run')
    def run(request: simulation.SimulationRequest):
        request.publish_to_clients = False
        return simulation.run_simulation(request, None)

    @app.post('/__validation/model-fault')
    def model_fault(enabled: bool):
        fault['model'] = enabled
        return fault

    @app.get('/static/assets/home-engine.glb')
    def model():
        return Response(status_code=503) if fault['model'] else FileResponse(root/'frontend/assets/home-engine.glb')

    @app.get('/__validation/engine-full.glb')
    def reference():
        return FileResponse(root/'.cache/home-engine/engine-full.glb')

    @app.get('/__validation/full', response_class=HTMLResponse)
    def reference_page():
        html = (root/'frontend/index.html').read_text(encoding='utf-8')
        html = html.replace('href="css/', 'href="/css/').replace('src="js/', 'src="/js/')
        return re.sub(r'src="/js/home_engine.js[^\"]*"', 'src="/__validation/reference-viewer.js"', html)

    @app.get('/__validation/reference-viewer.js')
    def reference_viewer():
        source = (root/'frontend/js/home_engine.js').read_text(encoding='utf-8')
        return Response(source.replace('/static/assets/home-engine.glb', '/__validation/engine-full.glb'),
                        media_type='text/javascript')

    @app.post('/__validation/stop')
    def stop():
        server.should_exit = True
        return {'stopping': True}

    app.include_router(simulation.router, prefix='/api/simulation')
    app.include_router(process.router, prefix='/api/process')
    app.include_router(config.router, prefix='/api/config')
    for name in ('js', 'css'):
        app.mount('/'+name, StaticFiles(directory=root/'frontend'/name))
    app.mount('/static', StaticFiles(directory=root/'frontend'))
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, access_log=False))
    server.run()


if __name__ == '__main__':
    main()
