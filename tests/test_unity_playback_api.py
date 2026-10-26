from fastapi import FastAPI
import asyncio
import json
from app.api import unity_playback
from app.core.unity_playback import UnityPlaybackClock


def request(app, method, path, payload=None):
    """Exercise the ASGI HTTP boundary without an optional HTTP client dependency."""
    async def invoke():
        messages = []
        body = json.dumps(payload).encode() if payload is not None else b""
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        async def send(message):
            messages.append(message)
        scope = dict(type="http", asgi={"version": "3.0"}, http_version="1.1",
                     method=method, scheme="http", path=path, raw_path=path.encode(),
                     query_string=b"", root_path="", headers=[(b"content-type", b"application/json")],
                     client=("127.0.0.1", 1000), server=("localhost", 80))
        await app(scope, receive, send)
        status = next(m["status"] for m in messages if m["type"] == "http.response.start")
        data = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        return status, json.loads(data)
    return asyncio.run(invoke())


def test_http_clock_claim_controls_and_read_only_viewer(monkeypatch, tmp_path):
    monkeypatch.setenv("SIMPY_UNITY_ACTIVE_STORE", str(tmp_path / "active"))
    now = [10.0]
    clock = UnityPlaybackClock(lambda: ("api-run", 1000), lambda: now[0])
    monkeypatch.setattr(unity_playback, "clock", clock)
    app = FastAPI()
    app.include_router(unity_playback.router, prefix="/unity")
    assert request(app, "GET", "/unity/playback.json")[1]["minute"] == 0
    claim = request(app, "POST", "/unity/playback/claim", {"client_id": "pc"})[1]
    command = dict(client_id="pc", sim_id="api-run", revision=claim["revision"],
                   minute=40, speed=5, playing=True)
    assert request(app, "PUT", "/unity/playback", command)[0] == 200
    now[0] += 2
    viewer = request(app, "GET", "/unity/playback.json")[1]
    assert viewer["minute"] == 50 and viewer["playing"]
    assert request(app, "POST", "/unity/playback/claim", {"client_id": "pc2"})[0] == 409
    command.update(client_id="vr", revision=viewer["revision"])
    assert request(app, "PUT", "/unity/playback", command)[0] == 409
    command.update(client_id="pc", sim_id="old-run")
    assert request(app, "PUT", "/unity/playback", command)[0] == 409
    command.update(sim_id="api-run", minute=-1)
    assert request(app, "PUT", "/unity/playback", command)[0] == 400
