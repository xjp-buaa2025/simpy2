"""Verify the PC console against a real web run and restore the original inputs."""
import copy
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.unity_pc_ui_validation import action, baseline, record, OUTPUT


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(name, value):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run(payload):
    request = urllib.request.Request("http://127.0.0.1:8000/api/simulation/run",
        json.dumps(payload, ensure_ascii=False).encode("utf-8"), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.load(response)
    if not result["success"] or not result["data"]["unity_sync"]["success"]:
        raise RuntimeError(str(result.get("message")))
    return result


def frame(name, replay, minute, actions):
    return record(name, {
        "request": {"name": name, "sim_id": replay["sim_id"], "width": 1920, "height": 1080,
            "seek_minute": minute, "speed": 20, "settle_frames": 30, "settle_seconds": 1.5,
            "capture": True, "actions": baseline() + actions},
        "expected": {"width": 1920, "height": 1080, "stations": 79, "preview": False,
            "role": "PCController", "synchronized": True, "authority": True,
            "month_end_output": replay["engines_completed"]},
    }, 40)


def check_station_data(replay, report):
    """Compare visible station values with the newly exported task timestamps."""
    minute = report["minute"]
    mismatches = []
    active_count = 0
    for label in report["labels"]:
        events = [event for event in replay["events"] if event["station_id"] == label["id"]]
        completed = {event["engine_id"] for event in events
                     if event["event_type"] in ("NORMAL", "REWORK") and event["end_time"] <= minute}
        if label["completed"] != len(completed):
            mismatches.append({"station": label["id"], "field": "completed",
                               "actual": label["completed"], "expected": len(completed)})
        active = [event for event in events if event["start_time"] <= minute < event["end_time"]]
        work = sorted((event for event in active if event["event_type"] in ("NORMAL", "REWORK")),
                      key=lambda event: event["start_time"])
        if work:
            event = work[0]
            state = "返工" if event["event_type"] == "REWORK" else "加工中"
            progress = (minute - event["start_time"]) / (event["end_time"] - event["start_time"])
            active_count += 1
            if label["state"] != state or abs(label["progress"] - progress) > .0001:
                mismatches.append({"station": label["id"], "field": "active_state_progress",
                                   "actual": [label["state"], label["progress"]], "expected": [state, progress]})
        elif active:
            types = {event["event_type"] for event in active}
            state = "等待" if "WAITING" in types else "人员休息" if "REST" in types else None
            if state and (label["state"] != state or abs(label["progress"]) > .0001):
                mismatches.append({"station": label["id"], "field": "waiting_rest_state",
                                   "actual": [label["state"], label["progress"]], "expected": [state, 0]})
    expected_finished = sum(0 <= item["finished"] <= minute for item in replay["engine_completion"])
    save("web_station_data_checks.json", {"stations_checked": len(report["labels"]),
         "active_stations_checked": active_count, "mismatches": mismatches,
         "expected_finished": expected_finished, "actual_finished": report["finished"]})
    return not mismatches and active_count > 0, report["finished"] == expected_finished


def main():
    original = read(ROOT / "results/unity_validation/sync_baseline_request.json")
    original_replay = read(ROOT / "results/unity_validation/replay.json")
    changed = copy.deepcopy(original)
    changed["config"].update(work_hours_per_day=6, work_days_per_month=15, target_output=5)
    for node in changed["process"]["nodes"]:
        if node["step_id"] == "F012":
            node["task_name"] += "（同步验收）"
    evidence = {}
    try:
        print("Running a changed schedule through the web endpoint...", flush=True)
        result = run(changed)
        save("web_changed_result.json", result)
        replay = read(ROOT / "results/unity_validation/replay.json")
        save("web_changed_replay.json", replay)
        frame("web_changed_ui", replay, 2950, [action("SelectStation", "F012")])
        report = read(OUTPUT / "web_changed_ui.json")
        evidence["new_replay_loaded"] = report["sim_id"] == replay["sim_id"] != original_replay["sim_id"]
        evidence["changed_target"] = report["target"] == 5 and "/ 5" in report["finished_text"]
        evidence["changed_calendar"] = "第9工作日" in report["calendar"]
        evidence["changed_process_name"] = any("同步验收" in row["text"] for row in report["texts"])
        evidence["changed_station_states_and_progress"], evidence["changed_current_finished"] = check_station_data(replay, report)
        frame("web_changed_month_end", replay, replay["duration"], [action("OpenPcDrawer", 1)])
        end = read(OUTPUT / "web_changed_month_end.json")
        evidence["changed_finished_count"] = end["finished"] == replay["engines_completed"]
        save("web_sync_checks.json", evidence)
    finally:
        print("Restoring the original schedule inputs...", flush=True)
        run(original)
        restored = read(ROOT / "results/unity_validation/replay.json")
        frame("web_restored_ui", restored, 2950, [])
        final = read(OUTPUT / "web_restored_ui.json")
        evidence["original_events_restored"] = restored["events"] == original_replay["events"]
        evidence["original_stations_restored"] = restored["stations"] == original_replay["stations"]
        evidence["original_counts_restored"] = restored["engines_completed"] == original_replay["engines_completed"]
        evidence["original_target_and_calendar_restored"] = final["target"] == 3 and "第7工作日" in final["calendar"]
        evidence["restored_ui_connected"] = final["synchronized"] and final["authority"]
        save("web_sync_checks.json", evidence)
    print(json.dumps(evidence, ensure_ascii=False), flush=True)
    if not all(evidence.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
