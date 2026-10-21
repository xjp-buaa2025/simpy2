"""Record the real Unity Editor PC UI through SimPyPCUIReview, without changing scheduling inputs.

The editor must already be in Play mode with the new UI. This runner changes only
the current Game view, UI selections, and the existing shared playback controls.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import time

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path("C:/AllUnityProjects/MainProject/MainProject")
EDITOR_OUTPUT = PROJECT / "SimPyValidation/pc_ui"
OUTPUT = ROOT / "results/unity_validation/pc_ui_20261005"


def action(method: str, *args: object) -> dict:
    return {"method": method, "args": [str(value).lower() if isinstance(value, bool) else str(value) for value in args]}


def button(caption: str) -> dict:
    return {"method": "experience_button", "caption": caption}


def baseline() -> list[dict]:
    # OpenPcDrawer closes every menu. The real menu's All Engines action resets the filter.
    return [action("OpenPcDrawer", 1), action("ClosePcDrawer"),
            action("TogglePcMenu", "engine"), button("全部发动机"),
            action("SelectStation", ""), action("ClosePcDrawer"),
            action("SetFirstPersonWindowVisible", False), action("RestoreDefaultViews")]


def build_cases() -> dict[str, dict]:
    replay = json.loads((ROOT / "results/unity_validation/replay.json").read_text(encoding="utf-8"))
    duration = float(replay["duration"])
    trip = next((item for item in replay["transfers"] if item["start_time"] > 2950 and item["end_time"] > item["start_time"]), replay["transfers"][0])
    agv_minute = (trip["start_time"] + trip["end_time"]) / 2
    cases: dict[str, dict] = {}

    def case(name: str, actions=(), *, width=1920, height=1080, minute=2950, preview=False, drawer=None, menu=None,
             camera_motion_frames=0, camera_yaw_delta=0, **expected):
        if "minute_after" not in expected and "exact_minute" not in expected:
            expected["exact_minute"] = minute
        cases[name] = {
            "request": {"name": name, "sim_id": replay["sim_id"], "width": width, "height": height,
                        "seek_minute": minute, "speed": 20, "settle_frames": 30, "settle_seconds": 1.5,
                        "camera_motion_frames": camera_motion_frames, "camera_yaw_delta": camera_yaw_delta,
                        "capture": True, "actions": baseline() + list(actions)},
            "expected": {"width": width, "height": height, "stations": 79,
                         "role": "PCController", "authority": True, "synchronized": True,
                         "month_end_output": replay["engines_completed"], "preview": preview,
                         "drawer": drawer, "menu": menu, **expected},
        }

    for width, height in [(1366, 768), (1920, 1080), (2560, 1440)]:
        case(f"default_{width}", width=width, height=height, finished=0, visible_labels=79)
    for menu in ["settings", "speed", "jump", "engine"]:
        case(f"menu_{menu}", [action("TogglePcMenu", menu)], menu=menu, finished=0)
    case("drawer_station", [action("SelectStation", "F012")], drawer=0, selected_station="F012")
    case("drawer_engine", [action("OpenPcDrawer", 1)], drawer=1)
    case("drawer_agv", [action("OpenPcDrawer", 2)], drawer=2, minute=agv_minute)
    case("drawer_help", [action("OpenPcDrawer", 3)], drawer=3)
    case("preview_on", [action("SetFirstPersonWindowVisible", True)], preview=True)
    case("preview_off", [action("SetFirstPersonWindowVisible", True), action("SetFirstPersonWindowVisible", False)])
    case("month_end", [action("OpenPcDrawer", 1)], minute=duration, drawer=1, finished=replay["engines_completed"])
    case("reset", [button("回到起点")], finished=0, minute=2950, exact_minute=0, toast_hidden=True)
    case("speed_preset", [action("TogglePcMenu", "speed"), button("60 分钟 / 秒")], speed=60)
    case("jump_operation", [action("TogglePcMenu", "jump"), button("下一工序完成")], minute_after=2950, playing=False)
    case("jump_engine", [action("TogglePcMenu", "jump"), button("下一台完工")], minute_after=2950, finished=1, playing=False)
    case("engine_select", [action("CycleEngine", 1), action("OpenPcDrawer", 1)], drawer=1, selected_engine=1)
    case("follow_agv", [action("ToggleAgvCamera"), action("OpenPcDrawer", 2)], minute=agv_minute, drawer=2, following_agv=True)
    case("restore_overview", [action("ToggleAgvCamera"), action("RestoreDefaultViews")], finished=0, following_agv=False, visible_labels=79)
    case("camera_motion", camera_motion_frames=90, camera_yaw_delta=8, motion_frames=90, yaw_delta=8,
         motion_label_visibility_changes=0, motion_label_offset_changes=0, motion_layout_passes_delta=0,
         max_settled_layout_passes=1, label_mode="adaptive", visible_labels=79)
    case("narrow_drawer_1366", [action("SelectStation", "F012")], width=1366, height=768,
         drawer=0, selected_station="F012", visible_labels=79)
    case("all_names", [action("TogglePcMenu", "settings"), button("工位标签：自适应")],
         label_mode="all_names", full_names=79, visible_labels=79)
    return cases


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def png_dimensions(path: Path) -> tuple[int, int] | None:
    if not path.exists() or path.stat().st_size < 32:
        return None
    with path.open("rb") as stream:
        header = stream.read(24)
        stream.seek(-12, os.SEEK_END)
        ending = stream.read(12)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or ending[:8] != b"\0\0\0\0IEND":
        return None
    return struct.unpack(">II", header[16:24])


def assess(report: dict, expected: dict, dimensions: tuple[int, int] | None) -> dict:
    checks = {}
    for field in ["width", "height", "stations", "role", "authority", "synchronized", "month_end_output", "finished", "visible_labels", "selected_station", "selected_engine", "following_agv", "speed", "playing", "label_mode", "motion_label_visibility_changes", "motion_label_offset_changes", "motion_layout_passes_delta"]:
        if field in expected:
            checks[field] = {"expected": expected[field], "actual": report.get(field), "pass": report.get(field) == expected[field]}
    for field in ["firstperson_visible", "firstperson_camera_enabled"]:
        wanted = expected.get(field, expected["preview"])
        checks[field] = {"expected": wanted, "actual": report.get(field), "pass": report.get(field) == wanted}
    if dimensions:
        checks["screenshot_dimensions"] = {"expected": [expected["width"], expected["height"]], "actual": list(dimensions), "pass": tuple(dimensions) == (expected["width"], expected["height"])}
    if "minute_after" in expected:
        checks["minute_advanced"] = {"expected": f"> {expected['minute_after']}", "actual": report.get("minute"), "pass": report.get("minute", 0) > expected["minute_after"]}
    if "exact_minute" in expected:
        checks["exact_minute"] = {"expected": expected["exact_minute"], "actual": report.get("minute"), "pass": abs(report.get("minute", -1) - expected["exact_minute"]) < .001}
    if "motion_frames" in expected:
        checks["motion_frames"] = {"expected": expected["motion_frames"], "actual": report.get("motion_sampled_frames"), "pass": report.get("motion_sampled_frames") == expected["motion_frames"]}
    if "yaw_delta" in expected:
        delta = report.get("camera_yaw_end", 0) - report.get("camera_yaw_start", 0)
        checks["yaw_delta"] = {"expected": expected["yaw_delta"], "actual": delta, "pass": abs(delta - expected["yaw_delta"]) < .001}
    if "max_settled_layout_passes" in expected:
        actual = report.get("settled_layout_passes_delta", -1)
        checks["settled_layout_passes"] = {"expected": f"0..{expected['max_settled_layout_passes']}", "actual": actual, "pass": 0 <= actual <= expected["max_settled_layout_passes"]}
    if "full_names" in expected:
        full_names = sum(row.get("visible", False) and row.get("level") == 2 and row.get("label", "") in row.get("title", "") for row in report.get("labels", []))
        checks["full_names_rendered"] = {"expected": expected["full_names"], "actual": full_names, "pass": full_names == expected["full_names"]}
    chrome_names = {item["name"] for item in report.get("chrome", [])}
    if expected.get("toast_hidden"):
        checks["completion_toast_hidden"] = {"expected": True, "actual": "CompletionToast" not in chrome_names, "pass": "CompletionToast" not in chrome_names}
    if expected.get("drawer") is not None:
        checks["drawer"] = {"expected": expected["drawer"], "actual": report.get("active_tab"), "pass": report.get("active_tab") == expected["drawer"] and "ProductionDetails" in chrome_names}
    if expected.get("menu"):
        name = {"settings": "DisplayMenu", "speed": "SpeedMenu", "jump": "JumpMenu", "engine": "EngineMenu"}[expected["menu"]]
        checks["menu"] = {"expected": name, "actual": sorted(chrome_names), "pass": name in chrome_names}
    controls = [item for item in report.get("texts", []) if "SimPy_PC_Console" in item.get("path", "")]
    overflows = [item for item in controls if item.get("width_overflow") or item.get("height_overflow")]
    outside = [item for item in report.get("chrome", []) if item.get("outside_screen")]
    warnings = {"chrome_outside_screen": [item["name"] for item in outside],
                "pc_text_overflow": [{"path": item["path"], "text": item["text"], "height": item["rect"]["height"], "preferred_height": item["preferred_height"]} for item in overflows],
                "label_overlap_pairs": report.get("label_overlap_pairs", 0), "blocked_labels": report.get("blocked_labels", 0)}
    return {"passed": all(item["pass"] for item in checks.values()), "checks": checks, "warnings": warnings,
            "metrics": {key: report.get(key) for key in ["role", "sim_id", "calendar", "minute", "finished_text", "wip_text", "waiting_text", "label_mode", "label_layout_passes_delta", "label_visibility_changes", "label_offset_changes", "motion_sampled_frames", "motion_label_visibility_changes", "motion_label_offset_changes", "motion_layout_passes_delta", "settled_layout_passes_delta", "average_frame_ms", "enabled_cameras"]}}


def record(name: str, case: dict, timeout: float) -> dict:
    request_path = EDITOR_OUTPUT / "review.request.json"
    if request_path.exists():
        raise RuntimeError("An existing review request is still pending; leave it undisturbed")
    json_path, png_path, error_path = [EDITOR_OUTPUT / f"{name}.{extension}" for extension in ["json", "png", "error.txt"]]
    for path in [json_path, png_path, error_path]:
        path.unlink(missing_ok=True)
    atomic_json(request_path, case["request"])
    deadline = time.monotonic() + min(40, timeout)
    while time.monotonic() < deadline:
        if error_path.exists():
            raise RuntimeError(error_path.read_text(encoding="utf-8"))
        dimensions = png_dimensions(png_path)
        if json_path.exists() and dimensions:
            try:
                report = json.loads(json_path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                time.sleep(.2)
                continue
            OUTPUT.mkdir(parents=True, exist_ok=True)
            for path in [json_path, png_path]:
                shutil.copy2(path, OUTPUT / path.name)
            result = assess(report, case["expected"], dimensions)
            atomic_json(OUTPUT / f"{name}.checks.json", result)
            return result
        time.sleep(.25)
    raise TimeoutError(f"{name}: no complete JSON and PNG within {min(40, timeout):g}s; request is left intact")


def summarize(cases: dict[str, dict]) -> dict:
    summary = {"source": "real Unity Editor live runtime", "cases": {}, "functional_passed": 0, "functional_failed": 0}
    for name, case in cases.items():
        path = OUTPUT / f"{name}.json"
        if not path.exists():
            continue
        result = assess(json.loads(path.read_text(encoding="utf-8-sig")), case["expected"], png_dimensions(OUTPUT / f"{name}.png"))
        summary["cases"][name] = result
        summary["functional_passed" if result["passed"] else "functional_failed"] += 1
        atomic_json(OUTPUT / f"{name}.checks.json", result)
    atomic_json(OUTPUT / "validation_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", help="Selected cases, space or comma separated; default: the three overview resolutions")
    parser.add_argument("--summary", action="store_true", help="Reassess all copied reports without sending Editor requests")
    parser.add_argument("--list", action="store_true", help="List case names without running")
    parser.add_argument("--timeout", type=float, default=40)
    args = parser.parse_args()
    cases = build_cases()
    if args.list:
        print("\n".join(cases))
        return
    if args.summary:
        summary = summarize(cases)
        print(json.dumps({"passed": summary["functional_passed"], "failed": summary["functional_failed"], "cases": list(summary["cases"])}, ensure_ascii=False))
        return
    names = [name for part in (args.cases or ["default_1366", "default_1920", "default_2560"]) for name in part.split(",")]
    unknown = set(names) - cases.keys()
    if unknown:
        parser.error("Unknown cases: " + ", ".join(sorted(unknown)))
    for name in names:
        print(f"Recording {name}...", flush=True)
        result = record(name, cases[name], args.timeout)
        print(json.dumps({"case": name, "passed": result["passed"], "warnings": result["warnings"], "metrics": result["metrics"]}, ensure_ascii=False), flush=True)
        if name == "all_names":
            # Verify the real menu switch in both directions and leave the delivered UI adaptive.
            original = cases["default_1920"]
            restore = {**original, "request": {**original["request"], "actions": [
                action("OpenPcDrawer", 1), action("ClosePcDrawer"), action("TogglePcMenu", "settings"),
                button("工位标签：全部名称"), *baseline()]}, "expected": {**original["expected"], "label_mode": "adaptive"}}
            print("Restoring adaptive labels and recording default_1920...", flush=True)
            restored = record("default_1920", restore, args.timeout)
            print(json.dumps({"case": "default_1920", "restored_adaptive_labels": restored["passed"]}, ensure_ascii=False), flush=True)
    summarize(cases)


if __name__ == "__main__":
    main()
