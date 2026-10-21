"""Serve the real UI with isolated simulation runs that never publish to Unity."""
import argparse
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.api import config, factory_layout, process, results, simulation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8049)
    args = parser.parse_args()
    app = FastAPI()
    root = Path(__file__).resolve().parents[1] / "frontend"

    @app.post("/api/simulation/run")
    def isolated_run(request: simulation.SimulationRequest):
        request.publish_to_clients = False
        return simulation.run_simulation(request, None)

    @app.post("/__validation/stop")
    def stop():
        server.should_exit = True
        return {"stopping": True}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return root.joinpath("index.html").read_text(encoding="utf-8")

    for prefix, router in (("/api/simulation", simulation.router), ("/api/process", process.router),
                           ("/api/config", config.router), ("/api/results", results.router),
                           ("/api/simulation/unity", factory_layout.router)):
        app.include_router(router, prefix=prefix)
    for name in ("js", "css"):
        app.mount("/" + name, StaticFiles(directory=root / name))
    app.mount("/static", StaticFiles(directory=root))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, access_log=False))
    server.run()


if __name__ == "__main__":
    main()
