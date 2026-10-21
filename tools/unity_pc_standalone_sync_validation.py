"""Exercise a user-started PC player via the real web scheduling endpoint.

The Editor must be stopped. The player log proves receipt; a renewed controller
lease and its initialization command prove traffic from the player to the server.
This does not claim to test native buttons or read the rendered UI.
"""
import copy
import json
import time
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/unity_validation/standalone_20261005"
LOG = Path("C:/Users/Administrator/AppData/LocalLow/DefaultCompany/MainProject/Player.log")
BASE = "http://127.0.0.1:8000"


def http(path, data=None, method=None):
    payload = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(BASE + path, payload,
        {"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def wait_player(sim_id, controller, offset):
    deadline = time.monotonic() + 25
    snapshots = []
    while time.monotonic() < deadline:
        log = LOG.read_text(encoding="utf-8", errors="replace")[offset:]
        state = http("/api/simulation/unity/playback.json")
        snapshots.append(state)
        received = f"自动载入网页仿真 {sim_id}" in log
        if received and state["sim_id"] == sim_id and state["controller_id"] == controller and state["controller_connected"]:
            # Wait for the player's initialization PUT (auto-play), not just our GET's reset.
            if state["playing"]:
                return {"received_log": log, "clock": state, "snapshots": snapshots}
        time.sleep(.5)
    raise TimeoutError(f"Player did not receive and initialize {sim_id}: {snapshots[-1:]}")


def run(payload):
    result = http("/api/simulation/run", payload)
    if not result["success"] or not result["data"]["unity_sync"]["success"]:
        raise RuntimeError(str(result))
    return result


def main():
    original = json.loads((ROOT / "results/unity_validation/sync_baseline_request.json").read_text(encoding="utf-8-sig"))
    replay = http("/api/simulation/unity/replay.json")
    clock = http("/api/simulation/unity/playback.json")
    # Guard against silently restoring stale user inputs.
    report = http("/api/results/export/report?sim_id=" + replay["sim_id"], method="POST")
    if report["config"] != original["config"]:
        raise RuntimeError("Current scheduling inputs differ from the saved baseline; capture the current inputs first")
    # Station labels also guard the saved process; baseline output is checked again after restoration.
    node_names = {node["step_id"]: node["task_name"] for node in original["process"]["nodes"]}
    if any(node_names.get(station["station_id"], "__missing__") not in station["scene_label"] for station in replay["stations"]):
        raise RuntimeError("Current process names differ from the saved baseline")
    if not clock["controller_connected"]:
        raise RuntimeError("No running PC controller")
    controller = clock["controller_id"]
    save("before.json", {"clock": clock, "config": report["config"], "sim_id": replay["sim_id"]})
    changed = copy.deepcopy(original)
    changed["config"].update(work_hours_per_day=6, work_days_per_month=15, target_output=5)
    for node in changed["process"]["nodes"]:
        if node["step_id"] == "F012":
            node["task_name"] += "（EXE同步测试）"
    checks = {}
    try:
        offset = len(LOG.read_text(encoding="utf-8", errors="replace"))
        result = run(changed)
        save("changed_result.json", result)
        print("Changed run: " + result["data"]["sim_id"], flush=True)
        evidence = wait_player(result["data"]["sim_id"], controller, offset)
        save("changed_player.json", evidence)
        checks["standalone_receives_new_replay"] = True
        checks["standalone_sends_initial_playback_command"] = evidence["clock"]["playing"]
        initial_revision = evidence["clock"]["revision"]
        # More than the lease TTL: only the player can keep its controller lease alive.
        time.sleep(13)
        alive = http("/api/simulation/unity/playback.json")
        save("lease_after_13_seconds.json", alive)
        checks["standalone_renews_controller_lease"] = alive["controller_id"] == controller and alive["controller_connected"]
        checks["shared_clock_advances"] = alive["minute"] > evidence["clock"]["minute"] and alive["revision"] == initial_revision
    finally:
        offset = len(LOG.read_text(encoding="utf-8", errors="replace"))
        result = run(original)
        print("Restored run: " + result["data"]["sim_id"], flush=True)
        restored = http("/api/simulation/unity/replay.json")
        evidence = wait_player(restored["sim_id"], controller, offset)
        save("restored_player.json", evidence)
        checks["original_events_restored"] = replay["events"] == restored["events"]
        checks["original_stations_restored"] = replay["stations"] == restored["stations"]
        checks["original_counts_restored"] = replay["engines_completed"] == restored["engines_completed"]
        # Restore the user's playback position using the documented clock API.
        state = http("/api/simulation/unity/playback.json")
        final = http("/api/simulation/unity/playback", {"client_id": controller,
            "sim_id": restored["sim_id"], "revision": state["revision"],
            "minute": clock["minute"], "playing": clock["playing"], "speed": clock["speed"]}, method="PUT")
        save("restored_clock.json", final)
        save("checks.json", checks)
    print(json.dumps(checks, ensure_ascii=False), flush=True)
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
