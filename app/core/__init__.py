"""
核心仿真模块包
包含SimPy仿真引擎的核心组件

模块说明:
- simulation_engine.py: 仿真引擎主控（SimPy核心）
- worker_pool.py: 工人池管理器（FilterStore）
- equipment_manager.py: 设备管理器（PriorityResource）
- dag_scheduler.py: DAG拓扑调度器（NetworkX）
- task_executor.py: 任务执行器（含休息/返工逻辑）
- event_collector.py: 事件收集器（甘特图数据源）
"""

from app.core.simulation_engine import SimulationEngine
from app.core.worker_pool import WorkerPool
from app.core.equipment_manager import EquipmentManager
from app.core.dag_scheduler import DAGScheduler
from app.core.task_executor import TaskExecutor
from app.core.event_collector import EventCollector

__all__ = [
    "SimulationEngine",
    "WorkerPool",
    "EquipmentManager",
    "DAGScheduler",
    "TaskExecutor",
    "EventCollector",
]
