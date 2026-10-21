"""Event-driven, opt-in area simulation with conserved resource inventories.

The legacy engine is deliberately not changed. IDs in this model represent
physical stations; a layout's display-only area never overrides scheduling.
"""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import json
import hashlib
import random
import uuid

import numpy as np
import simpy

from app.core.dag_scheduler import DAGScheduler
from app.core.event_collector import EventCollector
from app.core.worker_pool import WorkerPool
from app.core.production_policy import validate_production_process, release_interval, labor_summary
from app.core.station_progress import build_station_progress
from app.models.enums import GanttEventType, OpType
from app.models.gantt_model import GanttEvent
from app.models.result_model import (SimulationResult, ResourceUtilization,
                                     QualityStats, HumanFactorsStats)


def verified_catalog():
    root = Path(__file__).resolve().parents[2]
    layout = json.loads((root / "data/factory_layout/default.json").read_text(encoding="utf-8-sig"))
    bindings = json.loads((root / "tools/factory_process_mapping.json").read_text(encoding="utf-8-sig"))
    return {row["station_id"]: dict(area_id=row["area"], label=row["label"], capacity=1)
            for row in layout["stations"] if row["station_id"] in bindings}


def expansion_packages(config, process):
    """Complete support for added station slots; original inventory is untouched."""
    packages = {}
    for aid, area in config.capacity_model.areas.items():
        groups = defaultdict(list)
        for node in process.nodes:
            if (node.area_id or node.station) == aid:
                sid = node.workstation_id or node.step_id
                if sid in config.capacity_model.workstations:
                    groups[sid].append(node)
        slots, gear = 0, defaultdict(int)
        for sid, nodes in groups.items():
            capacity = config.capacity_model.workstations[sid].capacity
            slots += capacity
            for name in {t for n in nodes for t in n.required_tools if t in config.critical_equipment}:
                gear[name] += capacity
        copies = area.resource_sets - 1
        packages[aid] = dict(equipment={k:v*copies for k,v in gear.items()},
            station_slots=slots*copies, base_station_slots=slots,
            per_set_equipment=dict(gear))
    return packages


def prepare_model(config, process):
    """Validate and resolve a private run snapshot, never mutate caller input."""
    config, process = config.model_copy(deep=True), process.model_copy(deep=True)
    model = config.capacity_model
    if not model.enabled:
        raise ValueError("请先启用工区资源模型")
    valid, message = DAGScheduler(process).validate()
    if not valid:
        raise ValueError(message)
    if not process.nodes:
        raise ValueError("工艺流程不能为空")
    if any(n.std_duration < 0 or n.time_variance < 0 for n in process.nodes):
        raise ValueError("工时与波动不得为负")
    validate_production_process(process)
    allocated = defaultdict(int)
    for aid, area in model.areas.items():
        if aid == "shared":
            raise ValueError("shared 为公共资源池保留编号，请使用其他工区编号")
        for name, quantity in area.equipment.items():
            if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 0:
                raise ValueError(f"{aid} 的设备分配必须是非负整数")
            if name not in config.critical_equipment:
                raise ValueError(f"{aid} 分配了不存在的全局设备：{name}")
            allocated[name] += quantity
    for name, quantity in config.critical_equipment.items():
        if quantity < 1 or allocated[name] > quantity:
            raise ValueError(f"设备 {name} 的专属分配超过全局库存，或库存无效")
    catalog = verified_catalog()
    expansions = expansion_packages(config, process)
    if any(f"expansion:{aid}" in model.areas for aid in model.areas):
        raise ValueError("工区编号与新增资源池保留编号冲突")
    used = set()
    for node in process.nodes:
        node.area_id = node.area_id or node.station
        if node.area_id not in model.areas:
            raise ValueError(f"工序 {node.step_id} 未配置所属工区 {node.area_id}")
        # Implicit migration is allowed only for a verified physical mapping.
        node.workstation_id = node.workstation_id or (node.step_id if node.step_id in catalog else "")
        station = model.workstations.get(node.workstation_id)
        if station is None:
            raise ValueError(f"工序 {node.step_id} 尚未绑定已配置的实体工位")
        if station.area_id != node.area_id:
            raise ValueError(f"工序 {node.step_id} 与工位 {node.workstation_id} 的工区归属不一致")
        area = model.areas[node.area_id]
        node.required_tools = list(dict.fromkeys(node.required_tools))
        for name in node.required_tools:
            if name in config.critical_equipment:
                quantity = area.equipment.get(name, 0) or (config.critical_equipment[name] - allocated[name])
                quantity += expansions[node.area_id]["equipment"].get(name, 0)
                if quantity < 1:
                    raise ValueError(f"工序 {node.step_id} 的共享设备 {name} 已全部分配给其他工区")
        if node.op_type == OpType.M and node.rework_prob == 1 and node.std_duration == 0 and node.time_variance == 0:
            raise ValueError(f"工序 {node.step_id} 会产生无限次零工时返工")
        used.add(node.workstation_id)
    if config.evaluation.max_wip is None:
        config.evaluation.max_wip = max(2, sum(model.workstations[s].capacity * model.areas[model.workstations[s].area_id].resource_sets for s in used))
        if config.evaluation.max_wip > 10000:
            raise ValueError("自动在制上限超过10000，请在高级设置中指定较小的评估上限")
    return config, process, dict(allocated)


class AreaSimulationEngine:
    def __init__(self, config, process, *, no_rest=False):
        self.config, self.process, self.allocated = prepare_model(config, process)
        self.no_rest = no_rest
        self.env = simpy.Environment()
        self.rng = random.Random(self.config.random_seed)
        self.np_rng = np.random.default_rng(self.config.random_seed)
        self.collector = EventCollector(self.config.work_hours_per_day)
        self.phases, self.done, self.started, self.finished = {}, {}, {}, {}
        self.changed = self.env.event()
        self.worker_pool = WorkerPool(self.env, self.config)
        self.area_locks = {aid: simpy.PriorityResource(self.env, capacity=1)
                           for aid in self.config.capacity_model.areas}
        self.pools = {"shared": self.worker_pool}
        model = self.config.capacity_model
        self.expansions = expansion_packages(self.config, self.process)
        self.requests = []
        self.request_sequence = 0
        self.dispatch_pending = False
        self.capacities, self.owners, self.resource_names = {}, {}, {}
        for name, count in self.config.critical_equipment.items():
            self._resource(f"equipment:shared:{name}", count - self.allocated.get(name, 0), "shared", name)
        for aid, area in model.areas.items():
            for name, count in area.equipment.items():
                self._resource(f"equipment:{aid}:{name}", count, aid, name)
        for aid, package in self.expansions.items():
            for name, count in package["equipment"].items():
                if count:
                    self._resource(f"equipment:expansion:{aid}:{name}", count, f"expansion:{aid}", name)
        used_stations = {n.workstation_id for n in self.process.nodes}
        for sid, station in model.workstations.items():
            copies = model.areas[station.area_id].resource_sets if sid in used_stations else 1
            self._resource(f"workstation:{sid}", station.capacity*copies, station.area_id, station.label or sid)
        self.available = dict(self.capacities)
        self.nodes = {n.step_id: n for n in self.process.nodes}
        self.predecessors = {n.step_id: set(n.get_predecessor_list()) for n in self.process.nodes}
        self.active_peak = 0

    def _resource(self, key, capacity, owner, name):
        self.capacities[key], self.owners[key], self.resource_names[key] = capacity, owner, name

    def _notify(self):
        # Complete all normal events at this timestamp before assigning teams.
        if self.dispatch_pending:
            return
        self.dispatch_pending = True
        event = self.env.event()
        event._ok, event._value = True, None
        event.callbacks.append(lambda _: self._dispatch())
        self.env.schedule(event, priority=2)

    def _dispatch(self):
        self.dispatch_pending = False
        # Oldest released product first, with work-conserving bypass when its
        # resources are unavailable. This prevents an entrance backlog from
        # starving downstream operations in a large capacity evaluation.
        for ticket in sorted(self.requests, key=lambda t: (t["eid"], t["sequence"])):
            node, owner, base_resources = ticket["node"], ticket["owner"], ticket["resources"]
            resources = [base_resources[0]]
            blocked_gear = []
            for name, original in zip([t for t in node.required_tools if t in self.config.critical_equipment], base_resources[1:]):
                extra = f"equipment:expansion:{node.area_id}:{name}"
                choices = [r for r in (extra, original) if r in self.available]
                selected = next((r for r in choices if self.available[r] > 0), None)
                if selected is None:
                    blocked_gear.extend(choices)
                else:
                    resources.append(selected)
            reason = ("workstation" if self.available[resources[0]] < 1 else
                      "equipment" if blocked_gear else "")
            if reason:
                blocked = [resources[0]] if reason == "workstation" else blocked_gear
                self._phase(ticket["eid"], node, "WAITING", ticket.get("workers") or (),
                            reason=reason, wait_resources=blocked)
                continue
            workers = ticket.get("workers")
            if workers is None:
                workers = self.worker_pool.reserve_now(node.required_workers)
            for r in resources:
                self.available[r] -= 1
            self.requests.remove(ticket)
            self._close(ticket["eid"], node)
            ticket["event"].succeed((workers, resources))

    def _release_workers(self, workers):
        self.worker_pool.release_workers(workers)

    def _sample_seed(self, eid, node, attempt, kind):
        key = json.dumps([self.config.random_seed, eid, node.step_id, attempt, kind], ensure_ascii=False)
        return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:16], "big")

    def _duration_for(self, eid, node, attempt):
        rng = (np.random.default_rng(self._sample_seed(eid,node,attempt,"duration"))
               if self.config.evaluation.sampling_scheme == "paired_v1" else self.np_rng)
        raw = node.std_duration if node.time_variance == 0 else max(1., rng.normal(node.std_duration,node.time_variance))
        return raw / self.config.capacity_model.areas[node.area_id].efficiency_multiplier

    def _failed(self, eid, node, attempt):
        if node.op_type != OpType.M:
            return False
        rng = (random.Random(self._sample_seed(eid,node,attempt,"quality"))
               if self.config.evaluation.sampling_scheme == "paired_v1" else self.rng)
        return rng.random() < node.rework_prob

    def _request(self, eid, node, owner, resources, workers=None):
        event = self.env.event()
        self.request_sequence += 1
        self.requests.append(dict(eid=eid, node=node, owner=owner, resources=resources,
                                  sequence=self.request_sequence, event=event, workers=workers))
        self._notify()
        return event

    def _phase(self, eid, node, kind, workers=(), equipment=(), reason="", wait_resources=()):
        previous = self.phases.get((eid,node.step_id))
        if kind == "WAITING" and previous and previous["kind"] == kind and previous["reason"] == reason and previous.get("wait_resources",[]) == list(wait_resources):
            return
        self._close(eid, node)
        self.phases[(eid, node.step_id)] = dict(start=self.env.now, kind=kind,
            workers=[w.id for w in workers], equipment=list(equipment), reason=reason,
            wait_resources=list(wait_resources))

    def _close(self, eid, node, *, kind=None, complete=True, rework=0):
        phase = self.phases.pop((eid, node.step_id), None)
        if phase is None:
            return
        if self.env.now > phase["start"] or phase["kind"] == "NORMAL":
            event_kind = kind or phase["kind"]
            self.collector.add_event(GanttEvent(
                engine_id=eid, step_id=node.step_id, task_name=node.task_name,
                op_type=node.op_type.value, start_time=phase["start"], end_time=self.env.now,
                event_type=GanttEventType(event_kind), worker_ids=phase["workers"],
                equipment_used=phase["equipment"], rework_count=rework,
                area_id=node.area_id, workstation_id=node.workstation_id,
                wait_reason=phase["reason"], is_complete=complete,
                planned_end_time=phase.get("planned_end_time"),
                wait_resource_ids=phase.get("wait_resources",[])))

    def _requirements(self, node):
        area = self.config.capacity_model.areas[node.area_id]
        tools = [f"workstation:{node.workstation_id}"]
        for name in node.required_tools:
            if name in self.config.critical_equipment:
                owner = node.area_id if area.equipment.get(name, 0) else "shared"
                tools.append(f"equipment:{owner}:{name}")
        return tools

    def _task(self, eid, node, completed):
        # A whole operation retains the area through resource waits, rest and
        # rework. Extra station slots/resource sets cannot bypass this rule.
        with self.area_locks[node.area_id].request(priority=eid) as request:
            if not request.triggered:
                self._phase(eid, node, "WAITING", reason="area",
                            wait_resources=[f"area:{node.area_id}"])
            yield request
            self._close(eid, node)
            yield from self._serial_task(eid, node, completed)

    def _serial_task(self, eid, node, completed):
        pool, rework = self.worker_pool, 0
        while True:
            workers, resources = yield self._request(eid, node, "shared", self._requirements(node))
            if (not self.no_rest and pool.check_workers_need_rest(workers, self.config.rest_time_threshold)):
                for r in resources:
                    self.available[r] += 1
                self._phase(eid, node, "REST", workers)
                self._notify()
                yield from pool.execute_rest(workers, self.config.rest_duration_time, "time-triggered")
                self._close(eid, node)
                # Keep the rested team; reacquire only physical resources.
                workers, resources = yield self._request(eid, node, "shared", self._requirements(node), workers)
            self._phase(eid, node, "NORMAL", workers, resources)
            start = self.env.now
            duration = self._duration_for(eid, node, rework)
            self.phases[(eid,node.step_id)]["planned_end_time"] = start + duration
            yield self.env.timeout(duration)
            pool.add_work_time_to_workers(workers, duration, node.work_load_score, start)
            failed = self._failed(eid, node, rework)
            if failed:
                rework += 1
            self._close(eid, node, kind="REWORK" if failed else "NORMAL", rework=rework)
            for r in resources:
                self.available[r] += 1
            if failed:
                pool.release_workers(workers)
                self._notify()
                continue
            if not self.no_rest and node.work_load_score > self.config.rest_load_threshold:
                self._phase(eid, node, "REST", workers)
                self._notify()
                yield from pool.execute_rest(workers, self.config.rest_duration_load, "load-triggered")
                self._close(eid, node)
            pool.increment_tasks_completed(workers)
            pool.release_workers(workers)
            self.done[(eid, node.step_id)] = self.env.now
            self.collector.add_task_completion(eid, node, self.env.now)
            completed(node.step_id)
            self._notify()
            break

    def _product(self, eid):
        complete, running = set(), set()
        signal = self.env.event()

        def callback(sid):
            nonlocal signal
            complete.add(sid)
            old, signal = signal, self.env.event()
            if not old.triggered:
                old.succeed()

        while len(complete) < len(self.nodes):
            for sid, node in self.nodes.items():
                if sid not in running and self.predecessors[sid] <= complete:
                    running.add(sid)
                    self.env.process(self._task(eid, node, callback))
            yield signal
        self.finished[eid] = self.env.now

    def _capacity_lane(self):
        while True:
            eid = len(self.started) + 1
            self.started[eid] = self.env.now
            self.active_peak = max(self.active_peak, len(self.started) - len(self.finished))
            yield self.env.process(self._product(eid))

    def _plan_controller(self):
        starts = [n for n in self.process.nodes if not self.predecessors[n.step_id]]
        first = starts[0]
        eid = 0
        while self.env.now < self.config.sim_time_minutes:
            eid += 1
            self.started[eid] = self.env.now
            self.active_peak = max(self.active_peak, len(self.started)-len(self.finished))
            job = self.env.process(self._product(eid))
            if self.config.pipeline_mode:
                yield self.env.timeout(release_interval(self.process, first, self.config.capacity_model.areas[first.area_id].efficiency_multiplier))
            else:
                yield job

    def run(self):
        from app.core.run_progress import attach_progress_observer
        if self.config.evaluation.mode == "capacity":
            for _ in range(self.config.evaluation.max_wip):
                self.env.process(self._capacity_lane())
        else:
            self.env.process(self._plan_controller())
        attach_progress_observer(self)
        self.env.run(until=self.config.sim_time_minutes)
        # Flush unfinished segments without treating partial work as completion.
        for eid, sid in list(self.phases):
            phase = self.phases[(eid, sid)]
            held = [self.worker_pool.get_worker(wid) for wid in phase["workers"]]
            elapsed = self.env.now - phase["start"]
            if phase["kind"] == "NORMAL":
                self.worker_pool.add_work_time_to_workers(held, elapsed, self.nodes[sid].work_load_score, phase["start"])
            elif phase["kind"] == "REST":
                for worker in held:
                    worker.apply_rest(elapsed, phase["start"])
            self._close(eid, self.nodes[sid], kind="IN_PROGRESS" if phase["kind"] == "NORMAL" else None, complete=False)
        return self._result()

    def _result(self):
        horizon = self.config.sim_time_minutes
        events = self.collector.get_all_events()
        work, rest, gear_time = defaultdict(float), defaultdict(float), defaultdict(float)
        productive = {"NORMAL", "REWORK", "IN_PROGRESS"}
        for e in events:
            duration = e.end_time - e.start_time
            if e.event_type.value in productive:
                for wid in e.worker_ids:
                    work[wid] += duration
                for resource in e.equipment_used:
                    gear_time[resource] += duration
            elif e.event_type.value == "REST":
                for wid in e.worker_ids:
                    rest[wid] += duration
        workers = [w for p in self.pools.values() for w in p.get_all_workers()]
        worker_stats = [ResourceUtilization(resource_id=w.id, resource_type="WORKER", total_time=horizon,
            work_time=work[w.id], rest_time=rest[w.id], idle_time=max(0, horizon-work[w.id]-rest[w.id]),
            utilization_rate=work[w.id]/horizon, tasks_completed=w.tasks_completed,
            fatigue_level=w.fatigue_level, high_intensity_count=w.high_intensity_count,
            fatigue_history=w.fatigue_history) for w in workers]
        equipment_stats = [ResourceUtilization(resource_id=r, resource_type="WORKSTATION" if r.startswith("workstation:") else "EQUIPMENT",
            total_time=c*horizon, work_time=gear_time[r], idle_time=max(0,c*horizon-gear_time[r]),
            utilization_rate=gear_time[r]/(c*horizon)) for r,c in self.capacities.items() if c]
        area_stats, completion_events = [], []
        for aid, area in self.config.capacity_model.areas.items():
            nodes = [n for n in self.process.nodes if n.area_id == aid]
            if not nodes:
                continue
            own = [e for e in events if e.area_id == aid]
            began = {}
            for e in own:
                if e.event_type.value in productive:
                    began[e.engine_id] = min(began.get(e.engine_id, e.start_time), e.start_time)
            finishes, cycles = [], []
            for eid in began:
                if all((eid,n.step_id) in self.done for n in nodes):
                    end = max(self.done[(eid,n.step_id)] for n in nodes)
                    finishes.append(end)
                    cycles.append(end-began[eid])
                    completion_events.append(dict(area_id=aid, engine_id=eid, start_time=began[eid], end_time=end))
            finishes.sort()
            waits = {reason: sum(e.duration for e in own if e.event_type.value == "WAITING" and e.wait_reason == reason)
                     for reason in ("workers", "equipment", "workstation", "area")}
            labor = sum(e.duration*len(e.worker_ids) for e in own if e.event_type.value in productive)
            pool_owner = "on_demand"
            stations = sorted({n.workstation_id for n in nodes})
            station_slots = sum(self.capacities[f"workstation:{s}"] for s in stations)
            station_work = sum(gear_time[f"workstation:{s}"] for s in stations)
            area_stats.append(dict(area_id=aid, label=area.label or aid, workstation_count=len(stations),
                efficiency_multiplier=area.efficiency_multiplier, resource_sets=area.resource_sets,
                effective_standard_minutes=sum(n.std_duration for n in nodes)/area.efficiency_multiplier,
                expansion=self.expansions[aid], effective_station_slots=station_slots,
                process_count=len(nodes), standard_minutes=sum(n.std_duration for n in nodes),
                standard_labor_minutes=sum(n.std_duration*n.required_workers for n in nodes),
                worker_pool=pool_owner,
                **labor_summary(own),
                completed_units=len(finishes), avg_completion_interval=(finishes[-1]-finishes[0])/(len(finishes)-1) if len(finishes)>1 else None,
                avg_cycle_time=sum(cycles)/len(cycles) if cycles else None,
                wip=len(began)-len(finishes), wait_minutes=waits,
                workstation_utilization=station_work/(horizon*station_slots),
                equipment=[dict(resource_id=r, label=self.resource_names[r], owner=self.owners[r], capacity=c,
                    utilization=gear_time[r]/(horizon*c), area_use_minutes=sum(e.duration for e in own if r in e.equipment_used and e.event_type.value in productive))
                    for r,c in self.capacities.items() if r.startswith("equipment:") and c and (self.owners[r] in (aid,"shared",f"expansion:{aid}"))]))
        completed = len(self.finished)
        cycles = [end-self.started[eid] for eid,end in self.finished.items()]
        inspections = [e for e in events if e.op_type == "M" and e.event_type.value in ("NORMAL", "REWORK")]
        reworks = [e for e in inspections if e.event_type.value == "REWORK"]
        q = dict(total_inspections=len(inspections), total_reworks=len(reworks),
                 first_pass_rate=(len(inspections)-len(reworks))/len(inspections) if inspections else 1.,
                 rework_time_total=sum(e.duration for e in reworks))
        warnings = []
        for aid, area in self.config.capacity_model.areas.items():
            used = {t for n in self.process.nodes if n.area_id == aid for t in n.required_tools}
            for name, count in area.equipment.items():
                if count and name not in used:
                    warnings.append(f"{aid} 的专属设备 {name} 未绑定工序，此项配置不会直接提升该区产能")
        snapshot = dict(total_workers=len(workers), worker_supply_mode="on_demand", expansions=self.expansions,
            effective_workstations={sid: dict(base_capacity=s.capacity,capacity=self.capacities[f"workstation:{sid}"],area_id=s.area_id) for sid,s in self.config.capacity_model.workstations.items()},
            original_equipment=dict(self.config.critical_equipment),
            added_equipment={name:sum(p["equipment"].get(name,0) for p in self.expansions.values()) for name in self.config.critical_equipment},
            capacity_model=self.config.capacity_model.model_dump(),
            resources=[dict(resource_id=r, label=self.resource_names[r], owner=self.owners[r], capacity=c) for r,c in self.capacities.items()])
        context = dict(**labor_summary(events), mode=self.config.evaluation.mode, max_wip=self.config.evaluation.max_wip,
            horizon_minutes=horizon, initial_state="empty", sampling_scheme=self.config.evaluation.sampling_scheme, released_units=len(self.started),
            peak_wip=self.active_peak, random_seed=self.config.random_seed,
            output_label="本评估条件下的产出" if self.config.evaluation.mode == "capacity" else "当前计划下的产出",
            warnings=warnings)
        sim_id = str(uuid.uuid4())
        return SimulationResult(sim_id=sim_id, config=self.config, sim_duration=horizon,
            engines_completed=completed, avg_cycle_time=sum(cycles)/len(cycles) if cycles else 0,
            worker_stats=worker_stats, equipment_stats=equipment_stats,
            quality_stats=QualityStats(**q), human_factors_stats=HumanFactorsStats(
                total_rest_time=sum(rest.values()), avg_fatigue_level=sum(w.fatigue_level for w in workers)/len(workers) if workers else 0,
                max_fatigue_level=max((w.fatigue_level for w in workers), default=0),
                total_high_intensity_exposure=sum(w.high_intensity_count for w in workers),
                rest_events_count=sum(e.event_type.value == "REST" for e in events)),
            gantt_events=events, area_stats=area_stats, area_completion_events=completion_events,
            engine_completion_events=[dict(engine_id=eid, end_time=t) for eid,t in sorted(self.finished.items())],
            task_completion_events=self.collector.task_completion_events,
            station_progress=build_station_progress(sim_id=sim_id, config=self.config,
                process=self.process, gantt_events=events,
                task_completion_events=self.collector.task_completion_events,
                engine_release_times=self.started, time_minutes=horizon),
            resource_snapshot=snapshot, evaluation_context=context,
            time_mapping=dict(minutes_per_day=self.config.minutes_per_day, total_days=self.config.work_days_per_month,
                              total_minutes=horizon, work_hours_per_day=self.config.work_hours_per_day),
            created_at=datetime.now().isoformat(), completed_at=datetime.now().isoformat())
