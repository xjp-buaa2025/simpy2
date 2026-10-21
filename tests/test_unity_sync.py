"""Regression coverage for Windows replay readers and atomic publication."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import simulation
from tools import unity_validation as adapter


def windows_error(code):
    error = PermissionError("snapshot is in use")
    error.winerror = code
    return error


@pytest.mark.parametrize("code", [5, 32, 33])
def test_atomic_write_retries_transient_windows_locks(tmp_path, monkeypatch, code):
    target = tmp_path / "replay.json"
    target.write_bytes(b"old")
    replace = os.replace
    attempts, sleeps = [], []

    def locked_then_free(source, destination):
        attempts.append(1)
        if len(attempts) <= 2:
            assert target.read_bytes() == b"old"
            raise windows_error(code)
        replace(source, destination)

    monkeypatch.setattr(adapter.os, "replace", locked_then_free)
    monkeypatch.setattr(adapter.time, "sleep", sleeps.append)
    adapter.atomic_write(target, b"new")
    assert target.read_bytes() == b"new"
    assert len(attempts) == 3 and sleeps == [0.1, 0.1]
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("code,expected_attempts", [(5, 21), (32, 21), (33, 21), (112, 1)])
def test_atomic_write_failure_keeps_original_and_cleans_temp(
        tmp_path, monkeypatch, code, expected_attempts):
    target = tmp_path / "replay.json"
    target.write_bytes(b"old")
    attempts, sleeps = [], []
    error = windows_error(code)

    def fail(*args):
        attempts.append(1)
        raise error

    monkeypatch.setattr(adapter.os, "replace", fail)
    monkeypatch.setattr(adapter.time, "sleep", sleeps.append)
    with pytest.raises(PermissionError) as caught:
        adapter.atomic_write(target, b"new")
    assert caught.value is error
    assert len(attempts) == expected_attempts
    assert len(sleeps) == expected_attempts - 1
    assert sum(sleeps) == pytest.approx(2 if code in (5, 32, 33) else 0)
    assert target.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.skipif(os.name != "nt", reason="Windows file-sharing semantics")
def test_atomic_write_recovers_from_real_windows_reader(tmp_path, monkeypatch):
    target = tmp_path / "replay.json"
    target.write_bytes(b"old")
    reader = target.open("rb")
    sleep = adapter.time.sleep
    retried = []

    def release_reader(delay):
        retried.append(delay)
        reader.close()
        sleep(delay)

    monkeypatch.setattr(adapter.time, "sleep", release_reader)
    try:
        adapter.atomic_write(target, b"new")
    finally:
        reader.close()
    assert retried == [0.1]
    assert target.read_bytes() == b"new"


def snapshot_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(simulation, "__file__", str(tmp_path / "app/api/simulation.py"))
    directory = tmp_path / "results/unity_validation"
    directory.mkdir(parents=True)
    return directory


def test_slow_response_does_not_block_publication(tmp_path, monkeypatch):
    directory = snapshot_directory(tmp_path, monkeypatch)
    target = directory / "replay.json"
    before = json.dumps({"sim_id": "old", "events": ["装配"] * 5000}).encode()
    after = b'{"sim_id":"new"}'
    target.write_bytes(before)

    async def exercise():
        response = simulation.unity_replay()
        started, resume = asyncio.Event(), asyncio.Event()
        messages = []

        async def send(message):
            messages.append(message)
            if message["type"] == "http.response.body":
                started.set()
                await resume.wait()

        async def receive():
            return {"type": "http.request", "body": b""}

        task = asyncio.create_task(response({"type": "http", "method": "GET"}, receive, send))
        await asyncio.wait_for(started.wait(), 3)
        try:
            adapter.atomic_write(target, after)
            assert simulation.unity_replay().body == after
        finally:
            resume.set()
            await task
        assert b"".join(m.get("body", b"") for m in messages) == before
        assert response.headers["content-type"] == "application/json"
        assert response.headers["cache-control"] == "no-store"

    asyncio.run(exercise())


def test_missing_snapshot_keeps_existing_404(tmp_path, monkeypatch):
    snapshot_directory(tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as caught:
        simulation.unity_replay()
    assert caught.value.status_code == 404
    assert caught.value.detail == "请先完成一次网页仿真以生成 Unity 回放"


def test_status_write_failure_does_not_fail_completed_simulation(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise windows_error(5)

    monkeypatch.setattr(adapter, "publish_result", unavailable)
    monkeypatch.setattr(adapter, "atomic_write", unavailable)
    monkeypatch.setattr(adapter, "OUTPUT", tmp_path)
    monkeypatch.setattr(simulation, "simulation_results", {})
    app = FastAPI()
    app.include_router(simulation.router, prefix="/simulation")
    with TestClient(app) as client:
        response = client.post("/simulation/run", json={
            "config": {"num_workers": 2, "target_output": 1, "random_seed": 42},
            "process": {"name": "sync regression", "nodes": [
                {"step_id": "S1", "task_name": "装配", "op_type": "A", "std_duration": 1}]}})
    assert response.status_code == 200
    result = response.json()
    assert result["success"]
    assert result["data"]["unity_sync"]["success"] is False
    assert result["data"]["sim_id"] in simulation.simulation_results
    saved = simulation.simulation_results[result["data"]["sim_id"]]
    assert result["data"]["engines_completed"] == saved.engines_completed > 0


def publication_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "OUTPUT", tmp_path)
    player = tmp_path / "player/simpy_replay.json"
    player.parent.mkdir()
    monkeypatch.setattr(adapter, "PLAYER_REPLAY", player)
    process = SimpleNamespace(nodes=[SimpleNamespace(model_dump=lambda **kw: {})])
    return process, player


def test_concurrent_publications_are_serial_and_mark_ready_last(tmp_path, monkeypatch):
    process, player = publication_fixture(tmp_path, monkeypatch)
    first_entered, release_first, second_started, second_entered = (
        threading.Event() for _ in range(4))
    writes = []
    atomic_write = adapter.atomic_write

    def track_write(path, content):
        writes.append((Path(path).name, json.loads(content)["sim_id"]
                       if Path(path).name != "current_result.json"
                       else json.loads(content)["data"]["sim_id"]))
        atomic_write(path, content)

    def build(csv_path=None, *, result, rows):
        if result["sim_id"] == "A":
            first_entered.set()
            assert release_first.wait(3)
        else:
            second_entered.set()
        payload = dict(result, stations=[])
        track_write(tmp_path / "replay.json", json.dumps(payload).encode())
        return payload

    def second():
        second_started.set()
        return adapter.publish_result({"sim_id": "B", "engines_completed": 2}, process)

    monkeypatch.setattr(adapter, "_build", build)
    monkeypatch.setattr(adapter, "atomic_write", track_write)
    # A publication must never re-read a potentially replaced shared replay.
    read_bytes = Path.read_bytes
    def no_shared_read(path):
        if path == tmp_path / "replay.json":
            raise AssertionError("publication re-read shared replay")
        return read_bytes(path)
    monkeypatch.setattr(Path, "read_bytes", no_shared_read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(adapter.publish_result, {"sim_id": "A", "engines_completed": 1}, process)
        try:
            assert first_entered.wait(3)
            b = pool.submit(second)
            assert second_started.wait(3)
            assert not second_entered.wait(0.1)
        finally:
            release_first.set()
        assert a.result(timeout=3)["sim_id"] == "A"
        assert b.result(timeout=3)["sim_id"] == "B"
    assert writes == [(name, sid) for sid in ("A", "B") for name in (
        "replay.json", "current_result.json", "simpy_replay.json", "sync_status.json")]
    assert json.loads(player.read_text())["sim_id"] == "B"
    assert json.loads((tmp_path / "current_result.json").read_text())["data"]["sim_id"] == "B"


def test_failed_player_copy_never_marks_publication_ready(tmp_path, monkeypatch):
    process, player = publication_fixture(tmp_path, monkeypatch)
    atomic_write = adapter.atomic_write
    payload = {"sim_id": "new", "stations": [], "engines_completed": 1}
    monkeypatch.setattr(adapter, "_build", lambda **kw: payload)
    (tmp_path / "sync_status.json").write_text('{"sim_id":"old","success":true}')

    def fail_player(path, content):
        if path == player:
            raise windows_error(5)
        atomic_write(path, content)

    monkeypatch.setattr(adapter, "atomic_write", fail_player)
    with pytest.raises(PermissionError):
        adapter.publish_result(payload, process)
    assert json.loads((tmp_path / "sync_status.json").read_text())["sim_id"] == "old"


def test_standalone_build_still_marks_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "OUTPUT", tmp_path)
    payload = {"sim_id": "standalone"}
    monkeypatch.setattr(adapter, "_build", lambda *args, **kwargs: payload)
    assert adapter.build("process.csv") is payload
    status = json.loads((tmp_path / "sync_status.json").read_text())
    assert status["success"] and status["sim_id"] == "standalone"
