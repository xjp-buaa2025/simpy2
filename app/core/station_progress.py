"""Completed-operation progress, independent of replay scenes and scheduling.

Only the scheduler's real task-release milestones contribute standard minutes.
Waiting, rest, failed inspections and partial work never imply task completion.
"""
from collections import defaultdict
from functools import lru_cache
import json
import math
from pathlib import Path


def _record(value):
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return vars(value)


def _station(node):
    return node.get("workstation_id") or node.get("area_id") or node.get("station") or "ST01"


@lru_cache(maxsize=1)
def _catalog_labels():
    path = Path(__file__).resolve().parents[2] / "data/factory_layout/pt6a29/layout.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {row["station_id"]: row["label"] for row in data["zones"] if row["kind"] == "workstation"}


def _engine_snapshot(engine, total_steps, total_minutes, minute):
    # A step can be released only once. Keep defensive de-duplication here too,
    # so a repeated transport record cannot inflate the displayed progress.
    done = {}
    for event in engine["completion_events"]:
        if event["completed_at"] <= minute:
            done.setdefault(event["step_id"], event)
    completed_steps = len(done)
    completed = total_steps > 0 and completed_steps == total_steps
    completed_minutes = math.fsum(event["std_duration"] for event in done.values())
    progress = min(1.0, completed_minutes / total_minutes) if total_minutes > 0 else float(completed)
    started_at = engine["started_at"]
    if started_at is not None and started_at > minute:
        started_at = None
    completed_at = max((event["completed_at"] for event in done.values()), default=None) if completed else None
    return dict(engine_id=engine["engine_id"], released_at=engine["released_at"],
        started_at=started_at, completed_at=completed_at, completed_steps=completed_steps,
        completed_standard_minutes=completed_minutes, progress=progress, completed=completed,
        state="completed" if completed else "in_progress" if started_at is not None or done else "not_started")


def build_station_progress(*, sim_id, config, process, gantt_events,
                           task_completion_events, engine_release_times, time_minutes):
    """Build a self-contained v1 timeline plus its final per-engine snapshot.

    ``engine_release_times`` maps every actually released engine ID to its
    simulation release minute. Input objects are never mutated.
    """
    minute = float(time_minutes)
    if not math.isfinite(minute) or minute < 0:
        raise ValueError("工位进度时间必须为非负有限分钟数")
    config = _record(config)
    process = _record(process)
    process_catalog = {row["station_id"]: row for row in process.get("station_catalog", [])}
    nodes = {node["step_id"]: node for node in map(_record, process.get("nodes", []))}
    groups = defaultdict(list)
    for node in nodes.values():
        groups[_station(node)].append(node)
    starts = {}
    for source in gantt_events:
        event = _record(source)
        node = nodes.get(event["step_id"])
        if node is None:
            continue
        key = (_station(node), int(event["engine_id"]))
        starts[key] = min(starts.get(key, float("inf")), float(event["start_time"]))
    completions = defaultdict(dict)
    for source in task_completion_events:
        event = _record(source)
        node = nodes.get(event["step_id"])
        if node is None:
            continue
        key = (_station(node), int(event["engine_id"]))
        item = dict(step_id=node["step_id"], completed_at=float(event["completed_at"]),
                    std_duration=float(node["std_duration"]))
        existing = completions[key].get(node["step_id"])
        if existing is not None and existing != item:
            raise ValueError("同一发动机工序存在冲突的放行记录")
        completions[key][node["step_id"]] = item
    capacity = config.get("capacity_model", {})
    workstation_config = capacity.get("workstations", {})
    area_config = capacity.get("areas", {})
    labels = _catalog_labels()
    stations = []
    station_order = list(dict.fromkeys([sid for sid in process_catalog if sid in groups] + list(groups)))
    for sid in station_order:
        own_nodes = groups[sid]
        aid = own_nodes[0].get("area_id") or own_nodes[0].get("station") or sid
        configured = workstation_config.get(sid, {})
        label = configured.get("label") or process_catalog.get(sid, {}).get("label") or area_config.get(aid, {}).get("label") or labels.get(sid) or sid
        total_minutes = math.fsum(float(node["std_duration"]) for node in own_nodes)
        engines = []
        for eid, released_at in sorted(engine_release_times.items(), key=lambda pair: int(pair[0])):
            eid = int(eid)
            if released_at > minute:
                continue
            milestones = sorted(completions[(sid, eid)].values(), key=lambda row: (row["completed_at"], row["step_id"]))
            source = dict(engine_id=eid, released_at=float(released_at),
                          started_at=starts.get((sid, eid)), completion_events=milestones)
            engines.append(dict(_engine_snapshot(source, len(own_nodes), total_minutes, minute),
                                completion_events=milestones))
        stations.append(dict(station_id=sid, area_id=aid, label=label,
            total_steps=len(own_nodes), total_standard_minutes=total_minutes, engines=engines))
    return dict(schema_version=1, sim_id=sim_id, time_unit="minute", time_minutes=minute, stations=stations)


def sample_station_progress(payload, time_minutes=None, station_id=None, engine_id=None):
    """Return a lightweight immutable sample; no future engine releases leak out."""
    if payload.get("schema_version") != 1:
        raise ValueError("不支持的工位进度数据版本")
    minute = payload["time_minutes"] if time_minutes is None else float(time_minutes)
    if not math.isfinite(minute) or minute < 0 or minute > payload["time_minutes"]:
        raise ValueError("工位进度时间超出仿真范围")
    stations = []
    for source in payload["stations"]:
        if station_id is not None and source["station_id"] != station_id:
            continue
        engines = [_engine_snapshot(row, source["total_steps"], source["total_standard_minutes"], minute)
            for row in source["engines"] if row["released_at"] <= minute
            and (engine_id is None or row["engine_id"] == engine_id)]
        stations.append({key: value for key, value in source.items() if key != "engines"} | {"engines": engines})
    return dict(schema_version=1, sim_id=payload["sim_id"], time_unit="minute", time_minutes=minute, stations=stations)
