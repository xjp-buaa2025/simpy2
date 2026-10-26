"""Read-only area summaries for plans without the optional resource model.

An area completes only when all its operations have real scheduler releases.
Gantt work segments alone cannot establish completion after rework or rest.
"""
from collections import defaultdict
from math import fsum
from types import SimpleNamespace

from app.core.production_policy import labor_summary


def _record(value):
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return vars(value)


def build_plan_area_statistics(*, config, process, gantt_events, task_completion_events):
    config, process = _record(config), _record(process)
    nodes = {n["step_id"]: n for n in map(_record, process.get("nodes", []))}
    groups, own_events = defaultdict(list), defaultdict(list)
    starts, done = defaultdict(dict), defaultdict(dict)
    productive = {"NORMAL", "REWORK", "IN_PROGRESS"}
    for node in nodes.values():
        aid = node.get("area_id") or node.get("station")
        if aid:
            groups[aid].append(node)
    for source in gantt_events:
        event = _record(source)
        node = nodes.get(event["step_id"])
        if node is None:
            continue
        aid = node.get("area_id") or node.get("station")
        own_events[aid].append(event)
        kind = getattr(event["event_type"], "value", event["event_type"])
        if kind in productive:
            eid = event["engine_id"]
            starts[aid][eid] = min(starts[aid].get(eid, event["start_time"]), event["start_time"])
    for source in task_completion_events:
        event = _record(source)
        node = nodes.get(event["step_id"])
        if node is None:
            continue
        aid = node.get("area_id") or node.get("station")
        eid, sid = event["engine_id"], event["step_id"]
        done[(aid, eid)][sid] = event["completed_at"]
        # Zero-duration operations may have no positive work interval.
        starts[aid][eid] = min(starts[aid].get(eid, event["completed_at"]), event["completed_at"])
    labels = {row.get("area_id") or row["station_id"]: row.get("label")
              for row in process.get("station_catalog", [])}
    configured = config.get("capacity_model", {}).get("areas", {})
    rows, completion_events = [], []
    for aid, area_nodes in groups.items():
        finishes, cycles = [], []
        for eid, start in starts[aid].items():
            milestones = done[(aid, eid)]
            if all(node["step_id"] in milestones for node in area_nodes):
                end = max(milestones[node["step_id"]] for node in area_nodes)
                finishes.append(end)
                cycles.append(end - start)
                completion_events.append(dict(area_id=aid, engine_id=eid, start_time=start, end_time=end))
        finishes.sort()
        events = own_events[aid]
        waits = {reason: fsum(e["end_time"] - e["start_time"] for e in events
                 if e["event_type"] == "WAITING" and e.get("wait_reason") == reason)
                 for reason in ("workers", "equipment", "workstation", "area")}
        standard = fsum(node["std_duration"] for node in area_nodes)
        rows.append(dict(area_id=aid, label=configured.get(aid, {}).get("label") or labels.get(aid) or aid,
            process_count=len(area_nodes),
            workstation_count=len({n.get("workstation_id") or n.get("station") for n in area_nodes}),
            # Disabled resource settings must not affect the reported standard time.
            standard_minutes=standard, effective_standard_minutes=standard,
            standard_labor_minutes=fsum(n["std_duration"] * n.get("required_workers", 1) for n in area_nodes),
            efficiency_multiplier=1, resource_sets=1, completed_units=len(finishes),
            avg_completion_interval=(finishes[-1] - finishes[0]) / (len(finishes) - 1) if len(finishes) > 1 else None,
            avg_cycle_time=fsum(cycles) / len(cycles) if cycles else None,
            wip=len(starts[aid]) - len(finishes), wait_minutes=waits,
            **labor_summary([SimpleNamespace(**{**e, "duration": e["end_time"] - e["start_time"]})
                             for e in events])))
    return rows, completion_events


def with_plan_area_statistics(data):
    """Enrich retained results without changing their stored input or timeline."""
    snapshot = data.get("input_snapshot") or {}
    config = snapshot.get("config") or data.get("config") or {}
    if (data.get("area_stats") or config.get("capacity_model", {}).get("enabled")
            or not snapshot.get("process")
            or not (data.get("task_completion_events") or data.get("station_progress"))):
        return data
    completions = data.get("task_completion_events")
    if not completions:
        completions = [dict(event, engine_id=engine["engine_id"])
                       for station in (data.get("station_progress") or {}).get("stations", [])
                       for engine in station.get("engines", [])
                       for event in engine.get("completion_events", [])]
    rows, events = build_plan_area_statistics(config=config, process=snapshot["process"],
        gantt_events=data.get("gantt_events", []), task_completion_events=completions)
    return {**data, "area_stats": rows, "area_completion_events": events}
