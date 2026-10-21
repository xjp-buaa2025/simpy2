"""Shared production rules for finite-horizon, on-demand-labor simulations."""


def validate_production_process(process):
    if not process.nodes:
        raise ValueError("工艺流程不能为空")
    if not any(n.std_duration > 0 for n in process.nodes):
        raise ValueError("持续生产至少需要一道正工时工序")
    for node in process.nodes:
        if (str(getattr(node.op_type, "value", node.op_type)) == "M"
                and node.rework_prob == 1 and node.std_duration == 0
                and node.time_variance == 0):
            raise ValueError(f"工序 {node.step_id} 会产生无限次零工时返工")


def release_interval(process, first, efficiency=1):
    duration = first.std_duration or next(n.std_duration for n in process.nodes if n.std_duration > 0)
    return max(duration / efficiency * .5, .01)


def labor_summary(events):
    changes, minutes = [], 0.
    for event in events:
        kind = getattr(event.event_type, "value", event.event_type)
        if kind not in {"NORMAL", "REWORK", "IN_PROGRESS"}:
            continue
        count = len(event.worker_ids)
        minutes += event.duration * count
        if event.end_time > event.start_time:
            changes.extend(((event.start_time, count), (event.end_time, -count)))
    current = peak = 0
    for _, delta in sorted(changes):  # Ends precede starts at equal timestamps.
        current += delta
        peak = max(peak, current)
    return dict(worker_supply_mode="on_demand", labor_minutes=minutes, peak_working_workers=peak)
