"""
仿真引擎主控
SimPy离散事件仿真的核心控制器

功能:
- 流水线模式：支持多台发动机并行生产
- DAG调度：基于依赖关系调度任务
- 资源管理：协调工人和设备资源
- 结果收集：汇总仿真结果和统计数据

设计要点:
- 流水线模式下，当资源允许时启动新发动机
- 单台发动机按DAG拓扑顺序执行
- 支持并行任务的同时执行
"""

from typing import Dict, List, Set, Any, Generator, Optional
from datetime import datetime
import uuid
import simpy
import numpy as np

from app.models.config_model import GlobalConfig
from app.models.process_model import ProcessDefinition
from app.models.result_model import (
    SimulationResult, 
    ResourceUtilization, 
    QualityStats,
    HumanFactorsStats
)
from app.models.enums import SimulationStatus
from app.core.worker_pool import WorkerPool
from app.core.equipment_manager import EquipmentManager
from app.core.dag_scheduler import DAGScheduler
from app.core.task_executor import TaskExecutor
from app.core.event_collector import EventCollector


class SimulationEngine:
    """
    仿真引擎主控
    
    负责协调整个仿真过程，包括：
    - 初始化仿真环境和组件
    - 流水线控制（多台并行）
    - 单台发动机的DAG调度
    - 结果收集和统计
    """
    
    def __init__(self, config: GlobalConfig, process: ProcessDefinition):
        """
        初始化仿真引擎
        
        Args:
            config: 全局配置
            process: 工艺流程定义
        """
        self.config = config
        self.process = process
        self.sim_id = str(uuid.uuid4())
        
        # 设置随机种子（用于复现）
        if config.random_seed is not None:
            np.random.seed(config.random_seed)
        
        # 仿真组件（在run时初始化）
        self.env: Optional[simpy.Environment] = None
        self.worker_pool: Optional[WorkerPool] = None
        self.equipment_mgr: Optional[EquipmentManager] = None
        self.scheduler: Optional[DAGScheduler] = None
        self.event_collector: Optional[EventCollector] = None
        
        # 运行状态
        self.engines_completed = 0
        self.engine_start_times: Dict[int, float] = {}
        self.engine_end_times: Dict[int, float] = {}
    
    def run(self) -> SimulationResult:
        """
        运行仿真
        
        Returns:
            仿真结果
        """
        # 初始化SimPy环境
        self.env = simpy.Environment()
        
        # 初始化组件
        self.worker_pool = WorkerPool(self.env, self.config)
        self.equipment_mgr = EquipmentManager(self.env, self.config)
        self.scheduler = DAGScheduler(self.process)
        self.event_collector = EventCollector(self.config.work_hours_per_day)
        
        # 验证DAG
        valid, msg = self.scheduler.validate()
        if not valid:
            return self._create_failed_result(msg)
        
        # 处理工位资源限制模式
        if self.config.station_constraint_mode:
            self._apply_station_constraints()
        
        # 启动流水线控制器
        if self.config.pipeline_mode:
            self.env.process(self._pipeline_controller())
        else:
            # 单台模式
            self.env.process(self._single_engine_process(1))
        
        # 运行仿真
        self.env.run(until=self.config.sim_time_minutes)
        
        # 收集结果
        return self._collect_results()
    
    def _apply_station_constraints(self):
        """
        应用工位资源限制
        
        1. 将所有工位添加为关键设备（容量=1）
        2. 将工位名称添加到对应任务的required_tools中
        """
        # 收集所有工位
        all_stations = set()
        for node in self.process.nodes:
            if node.station:
                all_stations.add(node.station)
        
        # 将工位添加为关键设备（如果不存在）
        for station in all_stations:
            # 只有当设备管理器中不存在该设备时才添加
            # 这样用户可以在配置中手动覆盖工位容量（例如设置某个工位容量为2）
            if not self.equipment_mgr.has_equipment(station):
                # 这里的add_equipment是动态添加，需要确保EquipmentManager支持
                # EquipmentManager在初始化时已经读取了config，所以我们需要直接操作env中的资源
                # 但最好的方式是更新config并重新初始化EquipmentManager，或者直接在EquipmentManager中添加
                # 由于EquipmentManager已经初始化，我们调用其动态添加方法
                # 注意：config中的critical_equipment也需要同步更新，以便后续统计
                self.config.add_equipment(station, 1)
                self.equipment_mgr.add_dynamic_equipment(station, 1)
        
        # 将工位添加到任务所需工具
        for node in self.process.nodes:
            if node.station:
                if node.station not in node.required_tools:
                    node.required_tools.append(node.station)

    def _pipeline_controller(self) -> Generator:
        """
        流水线控制器
        
        当资源允许时启动新发动机生产
        """
        engine_id = 0
        max_engines = self.config.target_output + 2  # 多尝试几台
        
        # 获取第一个任务所需的最小工人数
        start_nodes = self.scheduler.get_start_nodes()
        if not start_nodes:
            return
        
        first_node = self.scheduler.get_node(start_nodes[0])
        min_workers_needed = first_node.required_workers if first_node else 1
        
        # 获取第一个任务的大致时长
        first_task_duration = first_node.std_duration if first_node else 30
        
        while engine_id < max_engines and self.env.now < self.config.sim_time_minutes:
            # 检查资源是否足够启动新发动机
            available_workers = self.worker_pool.get_available_count()
            
            if available_workers >= min_workers_needed:
                engine_id += 1
                self.engine_start_times[engine_id] = self.env.now
                
                # 启动新发动机生产进程
                self.env.process(self._engine_process(engine_id))
                
                # 间隔启动（等待第一个任务完成一半）
                yield self.env.timeout(first_task_duration * 0.5)
            else:
                # 等待资源
                yield self.env.timeout(10)
    
    def _single_engine_process(self, start_engine_id: int) -> Generator:
        """
        单台发动机模式（串行生产）
        
        一台接一台地生产，直到达到目标产量或时间耗尽
        
        Args:
            start_engine_id: 起始发动机编号
        """
        engine_id = start_engine_id
        max_engines = self.config.target_output + 1  # 目标产量
        
        while engine_id <= max_engines and self.env.now < self.config.sim_time_minutes:
            self.engine_start_times[engine_id] = self.env.now
            
            # 等待当前发动机完全生产结束
            yield from self._engine_process(engine_id)
            
            # 准备下一台
            engine_id += 1
    
    def _engine_process(self, engine_id: int) -> Generator:
        """
        单台发动机的完整生产流程
        
        使用DAG调度，支持并行任务执行
        
        Args:
            engine_id: 发动机编号
        """
        completed: Set[str] = set()
        running: Set[str] = set()
        total_tasks = self.scheduler.get_node_count()
        
        # 创建任务执行器
        executor = TaskExecutor(
            self.env,
            self.config,
            self.worker_pool,
            self.equipment_mgr,
            self.event_collector
        )
        
        # 任务完成回调
        def on_task_complete(step_id: str):
            running.discard(step_id)
            completed.add(step_id)
        
        while len(completed) < total_tasks:
            # 检查时间限制
            if self.env.now >= self.config.sim_time_minutes:
                break
            
            # 获取就绪任务（支持并行）
            ready_tasks = self.scheduler.get_ready_nodes(completed)
            ready_tasks = [t for t in ready_tasks if t not in running]
            
            # 启动所有就绪任务
            for step_id in ready_tasks:
                node = self.scheduler.get_node(step_id)
                if node:
                    running.add(step_id)
                    self.env.process(
                        self._execute_and_complete(
                            engine_id, node, executor, on_task_complete
                        )
                    )
            
            # 短暂等待，避免忙循环
            yield self.env.timeout(0.1)
        
        # 记录完成时间
        if len(completed) == total_tasks:
            self.engine_end_times[engine_id] = self.env.now
            self.engines_completed += 1
    
    def _execute_and_complete(
        self,
        engine_id: int,
        node: Any,
        executor: TaskExecutor,
        callback: Any
    ) -> Generator:
        """
        执行任务并触发完成回调
        
        Args:
            engine_id: 发动机编号
            node: 工艺节点
            executor: 任务执行器
            callback: 完成回调函数
        """
        yield from executor.execute_task(engine_id, node)
        callback(node.step_id)
    
    def _collect_results(self) -> SimulationResult:
        """
        收集仿真结果
        
        Returns:
            完整的仿真结果
        """
        # 计算仿真时长
        sim_duration = self.env.now
        
        # 计算平均周期时间
        cycle_times = []
        for engine_id in self.engine_end_times:
            if engine_id in self.engine_start_times:
                cycle_time = (
                    self.engine_end_times[engine_id] - 
                    self.engine_start_times[engine_id]
                )
                cycle_times.append(cycle_time)
        
        avg_cycle_time = (
            sum(cycle_times) / len(cycle_times) if cycle_times else 0
        )
        
        # 计划达成率
        target_achievement_rate = (
            self.engines_completed / self.config.target_output
            if self.config.target_output > 0 else 0
        )
        
        # 工人统计（包含人因数据）
        worker_stats = []
        total_rest_time = 0
        total_high_intensity = 0
        fatigue_levels = []
        
        for worker in self.worker_pool.get_all_workers():
            worker_stats.append(ResourceUtilization(
                resource_id=worker.id,
                resource_type="WORKER",
                total_time=sim_duration,
                work_time=worker.total_work_time,
                rest_time=worker.total_rest_time,
                idle_time=sim_duration - worker.total_work_time - worker.total_rest_time,
                utilization_rate=(
                    worker.total_work_time / sim_duration if sim_duration > 0 else 0
                ),
                tasks_completed=worker.tasks_completed,
                fatigue_level=worker.fatigue_level,
                high_intensity_count=worker.high_intensity_count,
                fatigue_history=worker.fatigue_history
            ))
            total_rest_time += worker.total_rest_time
            total_high_intensity += worker.high_intensity_count
            fatigue_levels.append(worker.fatigue_level)
        
        # 设备统计
        equipment_stats = []
        for stat in self.equipment_mgr.get_equipment_stats(sim_duration):
            equipment_stats.append(ResourceUtilization(
                resource_id=stat["equipment_name"],
                resource_type="EQUIPMENT",
                total_time=stat["total_time"],
                work_time=stat["work_time"],
                idle_time=stat["idle_time"],
                utilization_rate=stat["utilization_rate"],
                tasks_completed=stat["tasks_served"]
            ))
        
        # 质量统计
        quality_data = self.event_collector.get_quality_stats()
        quality_stats = QualityStats(
            total_inspections=quality_data["total_inspections"],
            total_reworks=quality_data["total_reworks"],
            first_pass_rate=quality_data["first_pass_rate"],
            rework_time_total=quality_data["rework_time_total"]
        )
        
        # 人因统计
        rest_events = [e for e in self.event_collector.get_all_events() 
                       if e.event_type.value == "REST"]
        human_factors_stats = HumanFactorsStats(
            total_rest_time=total_rest_time,
            avg_fatigue_level=sum(fatigue_levels) / len(fatigue_levels) if fatigue_levels else 0,
            max_fatigue_level=max(fatigue_levels) if fatigue_levels else 0,
            total_high_intensity_exposure=total_high_intensity,
            rest_events_count=len(rest_events)
        )
        
        # 时间映射
        time_mapping = {
            "minutes_per_day": self.config.work_hours_per_day * 60,
            "total_days": self.config.work_days_per_month,
            "total_minutes": self.config.sim_time_minutes,
            "work_hours_per_day": self.config.work_hours_per_day
        }
        
        return SimulationResult(
            sim_id=self.sim_id,
            status=SimulationStatus.COMPLETED,
            config=self.config,
            sim_duration=sim_duration,
            engines_completed=self.engines_completed,
            target_achievement_rate=target_achievement_rate,
            avg_cycle_time=avg_cycle_time,
            worker_stats=worker_stats,
            equipment_stats=equipment_stats,
            quality_stats=quality_stats,
            human_factors_stats=human_factors_stats,
            gantt_events=self.event_collector.get_all_events(),
            time_mapping=time_mapping,
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat()
        )
    
    def _create_failed_result(self, error_message: str) -> SimulationResult:
        """
        创建失败的仿真结果
        
        Args:
            error_message: 错误信息
            
        Returns:
            失败状态的仿真结果
        """
        return SimulationResult(
            sim_id=self.sim_id,
            status=SimulationStatus.FAILED,
            config=self.config,
            sim_duration=0,
            engines_completed=0,
            target_achievement_rate=0,
            avg_cycle_time=0,
            quality_stats=QualityStats(),
            human_factors_stats=HumanFactorsStats(),
            time_mapping={},
            created_at=datetime.now().isoformat()
        )


class SimulationEngineNoRest:
    """
    无休息仿真引擎（用于对比）
    
    与主引擎相同，但禁用所有休息规则
    用于对比考虑人因与不考虑人因的差异
    """
    
    def __init__(self, config: GlobalConfig, process: ProcessDefinition):
        """初始化无休息仿真引擎"""
        # 复制配置并禁用休息
        # 使用极大的时间阈值和零休息时长来禁用休息
        self.config = GlobalConfig(
            work_hours_per_day=config.work_hours_per_day,
            work_days_per_month=config.work_days_per_month,
            num_workers=config.num_workers,
            target_output=config.target_output,
            critical_equipment=config.critical_equipment,
            rest_time_threshold=999999,  # 禁用时间触发休息（极大阈值）
            rest_duration_time=0,  # 休息时长为0
            rest_load_threshold=10,  # 使用最大合法值
            rest_duration_load=0,  # 休息时长为0
            pipeline_mode=config.pipeline_mode,
            station_constraint_mode=config.station_constraint_mode,
            random_seed=config.random_seed
        )
        self.process = process
        self.sim_id = str(uuid.uuid4())
        
        self.env: Optional[simpy.Environment] = None
        self.worker_pool: Optional[WorkerPool] = None
        self.equipment_mgr: Optional[EquipmentManager] = None
        self.scheduler: Optional[DAGScheduler] = None
        self.event_collector: Optional[EventCollector] = None
        
        self.engines_completed = 0
        self.engine_start_times: Dict[int, float] = {}
        self.engine_end_times: Dict[int, float] = {}
    
    def run(self) -> Dict[str, Any]:
        """
        运行无休息仿真
        
        Returns:
            简化的结果字典（用于对比）
        """
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed + 1000)  # 使用不同种子
        
        self.env = simpy.Environment()
        self.worker_pool = WorkerPool(self.env, self.config)
        self.equipment_mgr = EquipmentManager(self.env, self.config)
        self.scheduler = DAGScheduler(self.process)
        self.event_collector = EventCollector(self.config.work_hours_per_day)
        
        valid, msg = self.scheduler.validate()
        if not valid:
            return {"error": msg}
        
        # 处理工位资源限制模式
        if self.config.station_constraint_mode:
            self._apply_station_constraints()
        
        if self.config.pipeline_mode:
            self.env.process(self._pipeline_controller())
        else:
            self.env.process(self._single_engine_process(1))
        
        self.env.run(until=self.config.sim_time_minutes)
        
        return self._collect_simple_results()

    def _apply_station_constraints(self):
        """
        应用工位资源限制
        """
        all_stations = set()
        for node in self.process.nodes:
            if node.station:
                all_stations.add(node.station)
        
        for station in all_stations:
            if not self.equipment_mgr.has_equipment(station):
                self.config.add_equipment(station, 1)
                self.equipment_mgr.add_dynamic_equipment(station, 1)
        
        for node in self.process.nodes:
            if node.station:
                if node.station not in node.required_tools:
                    node.required_tools.append(node.station)
    
    def _pipeline_controller(self) -> Generator:
        """流水线控制器"""
        engine_id = 0
        max_engines = self.config.target_output + 2
        
        start_nodes = self.scheduler.get_start_nodes()
        if not start_nodes:
            return
        
        first_node = self.scheduler.get_node(start_nodes[0])
        min_workers_needed = first_node.required_workers if first_node else 1
        first_task_duration = first_node.std_duration if first_node else 30
        
        while engine_id < max_engines and self.env.now < self.config.sim_time_minutes:
            available_workers = self.worker_pool.get_available_count()
            
            if available_workers >= min_workers_needed:
                engine_id += 1
                self.engine_start_times[engine_id] = self.env.now
                self.env.process(self._engine_process(engine_id))
                yield self.env.timeout(first_task_duration * 0.5)
            else:
                yield self.env.timeout(10)
    
    def _single_engine_process(self, start_engine_id: int) -> Generator:
        """单台发动机模式（串行生产）"""
        engine_id = start_engine_id
        max_engines = self.config.target_output + 1
        
        while engine_id <= max_engines and self.env.now < self.config.sim_time_minutes:
            self.engine_start_times[engine_id] = self.env.now
            yield from self._engine_process(engine_id)
            engine_id += 1
    
    def _engine_process(self, engine_id: int) -> Generator:
        """单台发动机生产流程"""
        completed: Set[str] = set()
        running: Set[str] = set()
        total_tasks = self.scheduler.get_node_count()
        
        executor = TaskExecutor(
            self.env,
            self.config,
            self.worker_pool,
            self.equipment_mgr,
            self.event_collector
        )
        
        def on_task_complete(step_id: str):
            running.discard(step_id)
            completed.add(step_id)
        
        while len(completed) < total_tasks:
            if self.env.now >= self.config.sim_time_minutes:
                break
            
            ready_tasks = self.scheduler.get_ready_nodes(completed)
            ready_tasks = [t for t in ready_tasks if t not in running]
            
            for step_id in ready_tasks:
                node = self.scheduler.get_node(step_id)
                if node:
                    running.add(step_id)
                    self.env.process(
                        self._execute_and_complete(
                            engine_id, node, executor, on_task_complete
                        )
                    )
            
            yield self.env.timeout(0.1)
        
        if len(completed) == total_tasks:
            self.engine_end_times[engine_id] = self.env.now
            self.engines_completed += 1
    
    def _execute_and_complete(self, engine_id, node, executor, callback) -> Generator:
        """执行任务并触发回调"""
        yield from executor.execute_task(engine_id, node)
        callback(node.step_id)
    
    def _collect_simple_results(self) -> Dict[str, Any]:
        """收集简化结果"""
        sim_duration = self.env.now
        
        cycle_times = []
        for engine_id in self.engine_end_times:
            if engine_id in self.engine_start_times:
                cycle_time = self.engine_end_times[engine_id] - self.engine_start_times[engine_id]
                cycle_times.append(cycle_time)
        
        avg_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else 0
        
        worker_utilizations = []
        for worker in self.worker_pool.get_all_workers():
            if sim_duration > 0:
                worker_utilizations.append(worker.total_work_time / sim_duration)
        
        quality_data = self.event_collector.get_quality_stats()
        
        return {
            "engines_completed": self.engines_completed,
            "avg_cycle_time": avg_cycle_time,
            "sim_duration": sim_duration,
            "avg_worker_utilization": sum(worker_utilizations) / len(worker_utilizations) if worker_utilizations else 0,
            "total_rest_time": 0,  # 无休息
            "first_pass_rate": quality_data["first_pass_rate"]
        }
