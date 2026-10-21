"""On-demand worker identities with atomic reservations and persistent fatigue.

An empty roster grows only when no idle team is available. Worker identities are
reused deterministically; no configured headcount limits production.
"""

from typing import Dict, List, Generator, Optional
import simpy

from app.models.enums import WorkerState
from app.models.worker_model import WorkerAgent
from app.models.config_model import GlobalConfig


class WorkerPool:
    """
    工人池管理器
    
    按实际并发需求扩充工人记录，不设置人数上限
    支持按状态过滤获取空闲工人
    """
    
    def __init__(self, env: simpy.Environment, config: GlobalConfig):
        """
        初始化工人池
        
        Args:
            env: SimPy环境
            config: 全局配置
        """
        self.env = env
        # Shared across every product executor in this simulation run.
        self.area_locks = {}
        self.config = config
        self.workers: Dict[str, WorkerAgent] = {}
        self.sequence = 0

    def reserve_now(self, count: int) -> List[WorkerAgent]:
        """Atomically reserve an entire team; capacity never blocks production."""
        if not isinstance(count, int) or count < 1:
            raise ValueError("作业人数必须为正整数")
        idle = sorted((w for w in self.workers.values() if w.state == WorkerState.IDLE),
                      key=lambda w: (w.total_work_time, int(w.id.rsplit('_', 1)[1])))
        selected = idle[:count]
        while len(selected) < count:
            self.sequence += 1
            worker = WorkerAgent(id=f"Worker_{self.sequence:02d}")
            self.workers[worker.id] = worker
            selected.append(worker)
        for worker in selected:
            worker.state = WorkerState.WORKING
        return selected

    def request_workers(self, count: int) -> Generator:
        workers = self.reserve_now(count)
        yield self.env.event().succeed()
        return workers

    def release_workers(self, workers: List[WorkerAgent]):
        for worker in workers:
            worker.state = WorkerState.IDLE
            worker.current_task_id = None

    def execute_rest(
        self, 
        workers: List[WorkerAgent], 
        duration: float, 
        reason: str = "time-triggered"
    ) -> Generator:
        """
        执行休息进程
        
        关键：工人在休息期间仍被当前任务"持有"，不释放给其他任务
        休息结束后恢复为工作状态（而非空闲）
        
        Args:
            workers: 休息的工人列表
            duration: 休息时长（分钟）
            reason: 休息原因（time-triggered/load-triggered）
            
        Yields:
            休息超时事件
        """
        # 标记工人为休息状态
        for worker in workers:
            worker.state = WorkerState.RESTING
        
        rest_start_time = self.env.now
        
        # 等待休息时间
        yield self.env.timeout(duration)
        
        # 休息结束，恢复为工作状态（注意不是IDLE，因为还在任务中）
        for worker in workers:
            worker.apply_rest(duration, rest_start_time)
            worker.state = WorkerState.WORKING
    
    def get_available_count(self) -> int:
        """
        获取当前可用（空闲）工人数量
        
        Returns:
            空闲工人数量
        """
        return sum(1 for w in self.workers.values() if w.state == WorkerState.IDLE)
    
    def get_working_count(self) -> int:
        """
        获取当前工作中的工人数量
        
        Returns:
            工作中的工人数量
        """
        return sum(1 for w in self.workers.values() if w.state == WorkerState.WORKING)
    
    def get_resting_count(self) -> int:
        """
        获取当前休息中的工人数量
        
        Returns:
            休息中的工人数量
        """
        return sum(1 for w in self.workers.values() if w.state == WorkerState.RESTING)
    
    def get_worker(self, worker_id: str) -> Optional[WorkerAgent]:
        """
        获取指定工人
        
        Args:
            worker_id: 工人ID
            
        Returns:
            工人对象，不存在返回None
        """
        return self.workers.get(worker_id)
    
    def get_all_workers(self) -> List[WorkerAgent]:
        """
        获取所有工人
        
        Returns:
            所有工人列表
        """
        return list(self.workers.values())
    
    def get_worker_stats(self) -> List[Dict]:
        """
        获取所有工人的统计数据
        
        Returns:
            工人统计列表
        """
        stats = []
        for worker in self.workers.values():
            stats.append({
                "worker_id": worker.id,
                "state": worker.state.value,
                "total_work_time": worker.total_work_time,
                "total_rest_time": worker.total_rest_time,
                "consecutive_work_time": worker.consecutive_work_time,
                "tasks_completed": worker.tasks_completed
            })
        return stats
    
    def check_workers_need_rest(
        self, 
        workers: List[WorkerAgent], 
        time_threshold: float
    ) -> bool:
        """
        检查工人是否需要时间触发休息
        
        Args:
            workers: 工人列表
            time_threshold: 连续工作时间阈值
            
        Returns:
            是否需要休息
        """
        return any(w.needs_time_rest(time_threshold) for w in workers)
    
    def add_work_time_to_workers(
        self, 
        workers: List[WorkerAgent], 
        duration: float,
        work_load_score: int = 5,
        current_time: float = 0
    ):
        """
        为工人添加工作时间
        
        Args:
            workers: 工人列表
            duration: 工作时长
            work_load_score: 任务负荷评分
            current_time: 当前仿真时间
        """
        for worker in workers:
            worker.add_work_time(duration, work_load_score, current_time)
    
    def increment_tasks_completed(self, workers: List[WorkerAgent]):
        """
        增加工人完成任务计数
        
        Args:
            workers: 工人列表
        """
        for worker in workers:
            worker.tasks_completed += 1
    
    def reset_all_workers(self):
        self.workers.clear()
        self.sequence = 0
