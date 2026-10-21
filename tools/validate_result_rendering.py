"""Isolated UI acceptance using a saved result or its input; never publish."""
import argparse
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.api import simulation, config, process, results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8048)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    fixture = args.fixture.resolve()
    app = FastAPI()

    @app.get('/', response_class=HTMLResponse)
    def index():
        source = (root/'frontend/index.html').read_text(encoding='utf-8')
        return source.replace('</body>', '<script src="/__validation/setup.js"></script></body>')

    @app.get('/__validation/fixture')
    def saved_result():
        return FileResponse(fixture, media_type='application/json')

    @app.get('/__validation/setup.js')
    def setup():
        return Response('''document.addEventListener('DOMContentLoaded',async()=>{
          const start=performance.now();
          try{
            const payload=await fetch('/__validation/fixture').then(r=>r.json());
            const result=payload.data||payload,input=result.input_snapshot;
            const scenario={schema_version:1,input,result:location.search.includes('input')?null:result};
            const file=new File([JSON.stringify(scenario)],'validation.json');
            await importCapacityScenario({target:{files:[file],value:''}});
            document.body.dataset.validationMs=(performance.now()-start).toFixed(0);
            document.body.dataset.validationReady='true';
          }catch(e){document.body.dataset.validationError=String(e);console.error(e);}
        });''', media_type='text/javascript')

    @app.post('/api/simulation/run')
    def run(request: simulation.SimulationRequest):
        request.publish_to_clients = False
        return simulation.run_simulation(request, None)

    app.include_router(simulation.router, prefix='/api/simulation')
    app.include_router(results.router, prefix='/api/results')
    app.include_router(process.router, prefix='/api/process')
    app.include_router(config.router, prefix='/api/config')
    for name in ('js', 'css'):
        app.mount('/'+name, StaticFiles(directory=root/'frontend'/name))
    app.mount('/static', StaticFiles(directory=root/'frontend'))
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
