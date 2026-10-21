"""Preserve the running service's result snapshots across a code-update restart.

snapshot reads the existing local API without changing it. serve restores the
API-compatible cache while retaining the untouched original responses on disk.
"""
import argparse
import json
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def snapshot(folder, base):
    folder.mkdir(parents=True, exist_ok=True)
    with urlopen(base + '/api/simulation/list', timeout=15) as response:
        listing = json.load(response)
    assert listing['success'], listing.get('message')
    ids = [row['sim_id'] for row in listing['data']]
    for sid in ids:
        # IDs are filenames, not arbitrary request-controlled paths.
        if any(c not in '0123456789abcdef-' for c in sid.lower()):
            raise ValueError('Unexpected simulation ID')
        with urlopen(base + '/api/results/' + sid, timeout=60) as response:
            content = response.read()
        result = json.loads(content)
        assert result['success'] and result['data']['sim_id'] == sid
        (folder / (sid + '.json')).write_bytes(content)
    (folder / 'index.json').write_text(json.dumps(dict(ids=ids, count=len(ids)), indent=2), encoding='utf-8')
    print(f'Preserved {len(ids)} original result snapshots in {folder}', flush=True)


def serve(folder, port=8000):
    sys.path.insert(0, str(ROOT))
    from app.main import app
    from app.api.simulation import SimulationResult, simulation_results
    index = json.loads((folder / 'index.json').read_text(encoding='utf-8'))
    restored = {}
    for sid in index['ids']:
        data = json.loads((folder / (sid + '.json')).read_text(encoding='utf-8'))['data']
        restored[sid] = SimulationResult.model_validate(data)
    simulation_results.update(restored)
    print(f'Restored {len(restored)} cached results; original JSON snapshots are retained.', flush=True)
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=port)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['snapshot', 'serve'])
    parser.add_argument('folder', type=Path)
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if args.operation == 'snapshot':
        snapshot(args.folder.resolve(), args.base.rstrip('/'))
    else:
        serve(args.folder.resolve(), args.port)
