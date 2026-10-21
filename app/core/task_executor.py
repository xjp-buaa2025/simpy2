"""Task execution with on-demand teams, retained fatigue, and separate rest phases.

Physical resources must be ready before assigning a new team. Time-triggered rest
releases equipment while retaining that team; load rest precedes node completion.
Unfinished phases are clipped and recorded at the evaluation horizon.
"""

from typing import Generator, List, Tuple, Optional, Any
import random
import numpy as np
import simpy

from app.models.process_model import ProcessNode
from app.models.config_model import GlobalConfig
from app.models.enums import OpType, GanttEventType
from app.models.gantt_model import GanttEvent
from app.models.worker_model import WorkerAgent
from app.core.worker_pool import WorkerPool
from app.core.equipment_manager import EquipmentManager
from app.core.event_collector import EventCollector


class TaskExecutor:
    """
    任务执行器
    
    负责执行单个工艺任务的完整流程
    包含资源获取、任务执行、休息处理、返工判断
    """
    
    def __init__(
        self,
        env: simpy.Environment,
        config: GlobalConfig,
        worker_pool: WorkerPool,
        equipment_mgr: EquipmentManager,
        event_collector: EventCollector
    ):
        """
        初始化任务执行器
        
        Args:
            env: SimPy环境
            config: 全局配置
            worker_pool: 工人池
            equipment_mgr: 设备管理器
            event_collector: 事件收集器
        """
        self.env = env
        self.config = config
        self.worker_pool = worker_pool
        self.equipment_mgr = equipment_mgr
        self.event_collector = event_collector
        self.phases = {}
    
    def _phase(self, eid, node, kind, workers=(), equipment=(), reason="", planned_end=None):
        self._close(eid, node)
        self.phases[(eid, node.step_id)] = dict(node=node, start=self.env.now, kind=kind,
            workers=list(workers), equipment=list(equipment), reason=reason, planned_end=planned_end)

    def _close(self, eid, node, *, kind=None, complete=True, rework=0):
        phase = self.phases.pop((eid, node.step_id), None)
        if phase is None:
            return
        event_kind = kind or phase["kind"]
        if self.env.now > phase["start"] or event_kind == "NORMAL":
            self.event_collector.add_event(GanttEvent(
                engine_id=eid, step_id=node.step_id, task_name=node.task_name,
                op_type=node.op_type.value, start_time=phase["start"], end_time=self.env.now,
                event_type=GanttEventType(event_kind), worker_ids=[w.id for w in phase["workers"]],
                equipment_used=[] if phase["reason"] else phase["equipment"], rework_count=rework,
                area_id=node.area_id or node.station, workstation_id=node.workstation_id,
                wait_reason=phase["reason"], wait_resource_ids=phase["equipment"] if phase["reason"] else [],
                is_complete=complete, planned_end_time=phase["planned_end"]))

    def flush(self):
        for (eid, _), phase in list(self.phases.items()):
            duration = self.env.now - phase["start"]
            if phase["kind"] == "NORMAL":
                self.worker_pool.add_work_time_to_workers(phase["workers"], duration,
                    phase["node"].work_load_score, phase["start"])
            elif phase["kind"] == "REST":
                for worker in phase["workers"]:
                    worker.apply_rest(duration, phase["start"])
            self._close(eid, phase["node"],
                        kind="IN_PROGRESS" if phase["kind"] == "NORMAL" else None, complete=False)

    def _equipment(self, eid, node):
        requests, critical = self.equipment_mgr.request_equipment(node.required_tools)
        if requests:
            self._phase(eid, node, "WAITING", equipment=critical, reason="equipment")
            yield self.env.all_of(requests)
            self._close(eid, node)
        return requests, critical

    def execute_task(self, engine_id, node):
        area_id = node.area_id or node.station
        if not area_id:
            return (yield from self._execute_task(engine_id, node))
        lock = self.worker_pool.area_locks.setdefault(area_id, simpy.PriorityResource(self.env, capacity=1))
        with lock.request(priority=engine_id) as request:
            if not request.triggered:
                self._phase(engine_id, node, "WAITING", equipment=[f"area:{area_id}"], reason="area")
            yield request
            self._close(engine_id, node)
            return (yield from self._execute_task(engine_id, node))

    def _execute_task(self, engine_id, node):
        rework_count = 0
        while True:
            requests, critical = yield from self._equipment(engine_id, node)
            workers = self.worker_pool.reserve_now(node.required_workers)
            if self.worker_pool.check_workers_need_rest(workers, self.config.rest_time_threshold):
                self.equipment_mgr.release_equipment(node.required_tools, requests)
                self._phase(engine_id, node, "REST", workers)
                yield from self.worker_pool.execute_rest(workers, self.config.rest_duration_time)
                self._close(engine_id, node)
                requests, critical = yield from self._equipment(engine_id, node)
            for name in critical:
                self.equipment_mgr.log_usage_start(name)
            start = self.env.now
            duration = self._calculate_duration(node.std_duration, node.time_variance)
            self._phase(engine_id, node, "NORMAL", workers, critical, planned_end=start+duration)
            yield self.env.timeout(duration)
            self.worker_pool.add_work_time_to_workers(workers, duration, node.work_load_score, start)
            failed = node.op_type == OpType.M and self._check_rework(node.rework_prob)
            if failed:
                rework_count += 1
            self._close(engine_id, node, kind="REWORK" if failed else "NORMAL", rework=rework_count)
            for name in critical:
                self.equipment_mgr.log_usage_end(name)
            # Release the complete team before resource-release events can wake waiters.
            if failed or node.work_load_score <= self.config.rest_load_threshold:
                self.worker_pool.release_workers(workers)
            self.equipment_mgr.release_equipment(node.required_tools, requests)
            if failed:
                continue
            if node.work_load_score > self.config.rest_load_threshold:
                self._phase(engine_id, node, "REST", workers)
                yield from self.worker_pool.execute_rest(workers, self.config.rest_duration_load, "load-triggered")
                self._close(engine_id, node)
                self.worker_pool.release_workers(workers)
            self.worker_pool.increment_tasks_completed(workers)
            self.event_collector.add_task_completion(engine_id, node, self.env.now)
            return True, rework_count

    def _calculate_duration(self, std_duration: float, std_dev: float) -> float:
        """
        计算实际工时（正态分布抽样）

        Args:
            std_duration: 标准工时（均值μ，分钟）
            std_dev: 工时波动标准差σ（分钟）。注意 np.random.normal 第二参数即标准差，
                     故此处按标准差使用，与 ProcessNode.time_variance 字段语义一致。

        Returns:
            实际工时（下限钳制为1分钟，避免负值）
        """
        if std_dev <= 0:
            return std_duration
        actual = np.random.normal(std_duration, std_dev)
        return max(1.0, actual)
    
    def _check_rework(self, rework_prob: float) -> bool:
        """
        判断是否需要返工
        
        Args:
            rework_prob: 返工概率
            
        Returns:
            是否需要返工
        """
        return random.random() < rework_prob


def execute_task_simple(
    env: simpy.Environment,
    engine_id: int,
    node: ProcessNode,
    config: GlobalConfig,
    worker_pool: WorkerPool,
    equipment_mgr: EquipmentManager,
    event_collector: EventCollector
) -> Generator[Any, Any, Tuple[bool, int]]:
    """
    简化的任务执行函数（无需创建TaskExecutor实例）
    
    Args:
        env: SimPy环境
        engine_id: 发动机编号
        node: 工艺节点
        config: 全局配置
        worker_pool: 工人池
        equipment_mgr: 设备管理器
        event_collector: 事件收集器
        
    Yields:
        SimPy事件
        
    Returns:
        (是否成功完成, 返工次数)
    """
    executor = TaskExecutor(
        env, config, worker_pool, equipment_mgr, event_collector
    )
    return (yield from executor.execute_task(engine_id, node))
