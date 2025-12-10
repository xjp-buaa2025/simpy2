"""
任务执行器
实现单个任务的完整执行流程

功能:
- 双层资源获取（工人 + 关键设备）
- 休息规则实现（规则A: 时间触发，规则B: 负荷触发）
- 返工逻辑（释放资源，重新排队）
- 事件记录（甘特图数据）

执行流程:
1. 获取工人（FilterStore.get）
2. 获取关键设备（PriorityResource.request）
3. 检查时间触发休息（规则A）
4. 执行任务（正态分布工时）
5. 质量检查（M类型）
   - 通过 → 继续
   - 失败 → 释放所有资源，返回需要重新排队
6. 检查负荷触发休息（规则B）
7. 释放资源
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
    
    def execute_task(
        self,
        engine_id: int,
        node: ProcessNode
    ) -> Generator[Any, Any, Tuple[bool, int]]:
        """
        执行单个任务
        
        Args:
            engine_id: 发动机编号
            node: 工艺节点
            
        Yields:
            SimPy事件
            
        Returns:
            (是否成功完成, 返工次数)
        """
        rework_count = 0
        task_completed = False
        
        while not task_completed:
            # ========== 阶段1: 等待并获取资源 ==========
            wait_start = self.env.now
            
            # 获取工人
            workers = yield from self.worker_pool.request_workers(node.required_workers)
            
            # 获取关键设备
            equip_requests, critical_equips = self.equipment_mgr.request_equipment(
                node.required_tools
            )
            if equip_requests:
                yield self.env.all_of(equip_requests)
            
            # 记录等待事件（如果有等待）
            wait_end = self.env.now
            if wait_end > wait_start:
                self.event_collector.add_event(GanttEvent(
                    engine_id=engine_id,
                    step_id=node.step_id,
                    task_name=f"{node.task_name}(等待)",
                    op_type=node.op_type.value,
                    start_time=wait_start,
                    end_time=wait_end,
                    event_type=GanttEventType.WAITING,
                    worker_ids=[],
                    equipment_used=[]
                ))
            
            # 记录设备使用开始
            for equip in critical_equips:
                self.equipment_mgr.log_usage_start(equip)
            
            # ========== 阶段2: 检查时间触发休息（规则A） ==========
            if self.worker_pool.check_workers_need_rest(
                workers, 
                self.config.rest_time_threshold
            ):
                rest_start = self.env.now
                yield from self.worker_pool.execute_rest(
                    workers,
                    self.config.rest_duration_time,
                    "time-triggered"
                )
                # 记录休息事件
                self.event_collector.add_event(GanttEvent(
                    engine_id=engine_id,
                    step_id=node.step_id,
                    task_name=f"{node.task_name}(休息-时间)",
                    op_type=node.op_type.value,
                    start_time=rest_start,
                    end_time=self.env.now,
                    event_type=GanttEventType.REST,
                    worker_ids=[w.id for w in workers],
                    equipment_used=critical_equips
                ))
            
            # ========== 阶段3: 执行任务 ==========
            task_start = self.env.now
            
            # 计算实际工时（正态分布）
            actual_duration = self._calculate_duration(
                node.std_duration,
                node.time_variance
            )
            
            # 等待任务完成
            yield self.env.timeout(actual_duration)
            
            # 更新工人工作时间（传递负荷评分用于疲劳计算）
            self.worker_pool.add_work_time_to_workers(
                workers, 
                actual_duration,
                node.work_load_score,
                task_start
            )
            
            task_end = self.env.now
            
            # ========== 阶段4: 质量检查（仅M类型） ==========
            if node.op_type == OpType.M and node.rework_prob > 0:
                if self._check_rework(node.rework_prob):
                    # 返工！
                    rework_count += 1
                    
                    # 记录返工事件
                    self.event_collector.add_event(GanttEvent(
                        engine_id=engine_id,
                        step_id=node.step_id,
                        task_name=f"{node.task_name}(返工#{rework_count})",
                        op_type=node.op_type.value,
                        start_time=task_start,
                        end_time=task_end,
                        event_type=GanttEventType.REWORK,
                        worker_ids=[w.id for w in workers],
                        equipment_used=critical_equips,
                        rework_count=rework_count
                    ))
                    
                    # 释放所有资源
                    for equip in critical_equips:
                        self.equipment_mgr.log_usage_end(equip)
                    self.equipment_mgr.release_equipment(
                        node.required_tools, 
                        equip_requests
                    )
                    self.worker_pool.release_workers(workers)
                    
                    # 重新排队（继续while循环）
                    continue
            
            # ========== 阶段5: 检查负荷触发休息（规则B） ==========
            if node.work_load_score > self.config.rest_load_threshold:
                rest_start = self.env.now
                yield from self.worker_pool.execute_rest(
                    workers,
                    self.config.rest_duration_load,
                    "load-triggered"
                )
                # 记录休息事件
                self.event_collector.add_event(GanttEvent(
                    engine_id=engine_id,
                    step_id=node.step_id,
                    task_name=f"{node.task_name}(休息-负荷)",
                    op_type=node.op_type.value,
                    start_time=rest_start,
                    end_time=self.env.now,
                    event_type=GanttEventType.REST,
                    worker_ids=[w.id for w in workers],
                    equipment_used=critical_equips
                ))
            
            # ========== 阶段6: 释放资源 ==========
            for equip in critical_equips:
                self.equipment_mgr.log_usage_end(equip)
            self.equipment_mgr.release_equipment(
                node.required_tools, 
                equip_requests
            )
            
            # 更新工人统计
            self.worker_pool.increment_tasks_completed(workers)
            self.worker_pool.release_workers(workers)
            
            # 记录正常完成事件
            self.event_collector.add_event(GanttEvent(
                engine_id=engine_id,
                step_id=node.step_id,
                task_name=node.task_name,
                op_type=node.op_type.value,
                start_time=task_start,
                end_time=task_end,
                event_type=GanttEventType.NORMAL,
                worker_ids=[w.id for w in workers],
                equipment_used=critical_equips,
                rework_count=rework_count
            ))
            
            # 任务完成
            task_completed = True
        
        return True, rework_count
    
    def _calculate_duration(self, std_duration: float, variance: float) -> float:
        """
        计算实际工时（正态分布）
        
        Args:
            std_duration: 标准工时
            variance: 方差
            
        Returns:
            实际工时（最小为1分钟）
        """
        if variance <= 0:
            return std_duration
        actual = np.random.normal(std_duration, variance)
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
