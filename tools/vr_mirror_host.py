"""Optional relay on a separate port; importing this cannot restart SimPy."""
import argparse
from fastapi import FastAPI
import uvicorn
import json
import urllib.request
import logging
import threading
import time
from pathlib import Path


def main(vr_mirror):
    app = FastAPI(title="VR LAN Mirror")
    app.include_router(vr_mirror.router, prefix="/vr-mirror")
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8011)
    parser.add_argument('--managed', action='store_true')
    parser.add_argument('--log-file')
    args = parser.parse_args()
    if args.log_file:
        Path(args.log_file).parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=args.log_file, level=logging.INFO)
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/vr-mirror/state', timeout=1) as response:
            if json.load(response).get('schema_version') == 1:
                print(f'VR mirror relay is already running on port {args.port}.')
                raise SystemExit(0)
    except (OSError, ValueError):
        pass
    vr_mirror.managed_service = args.managed
    config = uvicorn.Config(app, host='0.0.0.0', port=args.port, access_log=False, log_config=None if args.log_file else uvicorn.config.LOGGING_CONFIG)
    server = uvicorn.Server(config)
    if args.managed:
        started = time.monotonic()
        def watchdog():
            while not server.should_exit:
                time.sleep(1)
                if not vr_mirror.hosts.count() and (vr_mirror.hosts.ever_registered or time.monotonic()-started > 20):
                    server.should_exit = True
        threading.Thread(target=watchdog, daemon=True).start()
    server.run()
