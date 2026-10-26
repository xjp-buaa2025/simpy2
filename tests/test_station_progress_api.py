"""Station timeline transport, result retention, and legacy replay isolation."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import process, results, simulation
from tools import unity_validation as adapter


@pytest.fixture
def client(monkeypatch):
    store = {}
    monkeypatch.setattr(simulation, "simulation_results", store)
    monkeypatch.setattr(results, "simulation_results", store)
    app = FastAPI()
    app.include_router(simulation.router, prefix="/api/simulation")
    app.include_router(results.router, prefix="/api/results")
    app.include_router(process.router, prefix="/api/process")
    with TestClient(app) as http:
        yield http


def run_result(client, publish=False):
    response = client.post("/api/simulation/run", json={
        "publish_to_clients": publish,
        "config": {"work_days_per_month": 1, "work_hours_per_day": 1,
                   "pipeline_mode": False, "random_seed": 42},
        "process": {"name": "工位接口验证", "station_catalog": [
            {"station_id": "WS-R01", "area_id": "WS-R01", "label": "压气机转子部装"}],
            "nodes": [dict(step_id=sid, task_name=sid, op_type="A", std_duration=duration,
                           predecessors=pred, station="WS-R01", area_id="WS-R01",
                           workstation_id="WS-R01")
                      for sid, duration, pred in [("R01-01", 10, ""), ("R01-02", 30, "R01-01")]]}})
    assert response.status_code == 200
    body = response.json()
    assert body["success"], body
    return body["data"]


def test_station_timeline_survives_run_query_and_report(client):
    run = run_result(client)
    sid = run["sim_id"]
    timeline = run["station_progress"]
    assert timeline["sim_id"] == sid
    assert timeline["stations"][0]["station_id"] == "WS-R01"
    assert client.get(f"/api/results/{sid}").json()["data"]["station_progress"] == timeline
    snapshot = client.get(f"/api/results/{sid}/station-progress", params={
        "time_minutes": 10, "station_id": "WS-R01", "engine_id": 1}).json()["data"]
    engine = snapshot["stations"][0]["engines"][0]
    assert engine["progress"] == pytest.approx(0.25)
    assert engine["completed_steps"] == 1 and not engine["completed"]
    assert "completion_events" not in engine
    assert client.get(f"/api/results/{sid}/station-progress").json()["data"]["stations"][0]["engines"][0]["completed"]
    report = client.post("/api/results/export/report", params={"sim_id": sid})
    assert report.status_code == 200
    assert report.json()["station_progress"] == timeline
    assert run["input_snapshot"]["process"]["station_catalog"][0]["label"] == "压气机转子部装"


@pytest.mark.parametrize("time", ["-1", "61", "nan", "inf", "-inf", "not-a-number"])
def test_snapshot_rejects_invalid_time(client, time):
    run = run_result(client)
    response = client.get(f"/api/results/{run['sim_id']}/station-progress", params={"time_minutes": time})
    assert response.status_code == 422


def test_old_or_missing_result_never_fabricates_zero_progress(client):
    assert client.get("/api/results/missing/station-progress").status_code == 404
    run = run_result(client)
    simulation.simulation_results[run["sim_id"]].station_progress = None
    response = client.get(f"/api/results/{run['sim_id']}/station-progress")
    assert response.status_code == 409
    assert "重新仿真" in response.json()["detail"]


def test_station_publication_activates_new_snapshot_and_keeps_legacy_files(tmp_path, monkeypatch, client):
    monkeypatch.setattr(adapter, "OUTPUT", tmp_path)
    monkeypatch.setenv("SIMPY_UNITY_ACTIVE_STORE",str(tmp_path/"active"))
    monkeypatch.setattr(adapter,"PLAYER_REPLAY",tmp_path/"player.json")
    legacy=[tmp_path/name for name in ("replay.json","current_result.json","sync_status.json","player.json")]
    for path in legacy:path.write_bytes(b"legacy-snapshot")
    run=run_result(client,publish=True)
    assert run["unity_sync"]["success"] and run["unity_sync"]["mode"]=="pt6a29"
    assert json.loads((tmp_path/"active/active.json").read_bytes())["sim_id"]==run["sim_id"]
    assert all(path.read_bytes()==b"legacy-snapshot" for path in legacy)
    published=client.post(f"/api/results/{run['sim_id']}/publish-unity")
    assert published.status_code==200 and published.json()["success"]


def test_failed_station_publication_does_not_replace_legacy_status(tmp_path, monkeypatch, client):
    monkeypatch.setattr(adapter, "OUTPUT", tmp_path)
    legacy_status = tmp_path / "sync_status.json"
    legacy_status.write_bytes(b'{"sim_id":"old","success":true}')
    def unavailable(*args, **kwargs):
        raise PermissionError("station timeline is temporarily locked")
    monkeypatch.setattr(adapter, "publish_result", unavailable)
    run = run_result(client, publish=True)
    assert run["unity_sync"]["success"] is False
    assert legacy_status.read_bytes() == b'{"sim_id":"old","success":true}'
    status = json.loads((tmp_path / "station_progress_status.json").read_bytes())
    assert status["sim_id"] == run["sim_id"] and not status["success"]


def test_matching_legacy_process_still_publishes_replay_and_station_data(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "OUTPUT", tmp_path)
    monkeypatch.setattr(adapter, "PLAYER_REPLAY", tmp_path / "player.json")
    mapping = json.loads((adapter.ROOT / "tools/factory_process_mapping.json").read_text(encoding="utf-8"))
    process = SimpleNamespace(nodes=[SimpleNamespace(model_dump=lambda sid=sid, **kw: {"step_id": sid})
                                     for sid in mapping])
    progress = {"schema_version": 1, "sim_id": "legacy-run", "stations": []}
    replay = {"schema_version": 3, "sim_id": "legacy-run", "stations": [], "engines_completed": 1}
    monkeypatch.setattr(adapter, "_build", lambda **kw: replay)
    published = adapter.publish_result({"sim_id": "legacy-run", "engines_completed": 1,
                                        "station_progress": progress}, process)
    assert published["mode"] == "legacy_replay" and published["legacy_replay_published"]
    assert json.loads((tmp_path / "player.json").read_bytes()) == replay
    assert json.loads((tmp_path / "station_progress.json").read_bytes()) == progress
    assert json.loads((tmp_path / "sync_status.json").read_bytes())["success"]


def test_latest_station_endpoint_is_independent_and_uncached(tmp_path, monkeypatch, client):
    monkeypatch.setattr(simulation, "__file__", str(tmp_path / "app/api/simulation.py"))
    response = client.get("/api/simulation/unity/station-progress.json")
    assert response.status_code == 404
    directory = tmp_path / "results/unity_validation"
    directory.mkdir(parents=True)
    payload = {"schema_version": 1, "sim_id": "latest", "stations": []}
    (directory / "station_progress.json").write_text(json.dumps(payload), encoding="utf-8")
    response = client.get("/api/simulation/unity/station-progress.json")
    assert response.status_code == 200 and response.json() == payload
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.skipif(not os.getenv("SIMPY_PT6A_XLSX"), reason="Set SIMPY_PT6A_XLSX to validate the supplied workbook")
def test_supplied_workbook_import_roundtrip_and_complete_simulation(client):
    workbook = Path(os.environ["SIMPY_PT6A_XLSX"])
    with workbook.open("rb") as stream:
        parsed = client.post("/api/process/parse-file", files={
            "file": (workbook.name, stream, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert parsed.status_code == 200
    body = parsed.json()
    assert body["success"], body
    definition = body["data"]
    assert len(definition["nodes"]) == 269
    assert len(definition["station_catalog"]) == 29
    assert {"A", "S-Move", "S-Rest", "Coop"} == {n["op_type"] for n in definition["nodes"]}
    assert all(n["station"] == n["area_id"] == n["workstation_id"] for n in definition["nodes"])
    exported = client.post("/api/process/export-csv", json=definition)
    assert exported.status_code == 200
    restored = client.post("/api/process/parse-file", files={"file": ("roundtrip.csv", exported.content, "text/csv")}).json()
    assert restored["success"], restored
    for field in ("step_id", "task_name", "op_type", "predecessors", "std_duration", "time_variance",
                  "work_load_score", "rework_prob", "required_workers", "required_tools", "station", "area_id", "workstation_id"):
        assert [n[field] for n in restored["data"]["nodes"]] == [n[field] for n in definition["nodes"]], field
    response = client.post("/api/simulation/run", json={
        "publish_to_clients": False, "process": definition,
        "config": {"work_days_per_month": 22, "work_hours_per_day": 8,
                   "pipeline_mode": False, "station_constraint_mode": False, "random_seed": 42}})
    assert response.status_code == 200
    run = response.json()
    assert run["success"], run
    data = run["data"]
    assert data["engines_completed"] >= 1
    assert not data["config"]["capacity_model"]["enabled"]
    assert len(data["station_progress"]["stations"]) == 29
    assert sum(len(s["engines"][0]["completion_events"]) for s in data["station_progress"]["stations"]) == 269
    assert all(s["engines"][0]["completed"] and s["engines"][0]["progress"] == 1
               for s in data["station_progress"]["stations"])
    sid = data["sim_id"]
    early = client.get(f"/api/results/{sid}/station-progress", params={"time_minutes": 120}).json()["data"]
    later = client.get(f"/api/results/{sid}/station-progress", params={"time_minutes": 480}).json()["data"]
    again = client.get(f"/api/results/{sid}/station-progress", params={"time_minutes": 120}).json()["data"]
    assert early == again
    assert sum(s["engines"][0]["completed_steps"] for s in later["stations"]) >= sum(s["engines"][0]["completed_steps"] for s in early["stations"])
