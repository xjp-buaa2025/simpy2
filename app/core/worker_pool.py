"""
工人池管理器
使用SimPy FilterStore管理工人资源

功能:
- 工人资源的获取与释放
- 按状态过滤获取空闲工人
- 休息逻辑实现（工人休息期间仍被任务持有）
- 工人状态跟踪与统计

设计要点:
- 休息期间工人仍被任务持有，休息结束后才归还Store
- 支持按数量请求工人
- 记录工人的工作时间、休息时间统计
"""

from typing import Dict, List, Generator, Optional
import simpy

from app.models.enums import WorkerState
from app.models.worker_model import WorkerAgent
from app.models.config_model import GlobalConfig


class WorkerPool:
    """
    工人池管理器
    
    使用SimPy FilterStore实现工人资源管理
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
        self.config = config
        self.store = simpy.FilterStore(env)
        self.workers: Dict[str, WorkerAgent] = {}
        
        # 初始化工人
        for i in range(config.num_workers):
            worker_id = f"Worker_{i+1:02d}"
            worker = WorkerAgent(id=worker_id)
            self.workers[worker_id] = worker
            self.store.put(worker)
    
    def request_workers(self, count: int) -> Generator:
        """
        请求指定数量的空闲工人（负载均衡分配）
        
        优先选择累计工作时间最少的工人，实现均衡分配
        
        Args:
            count: 需要的工人数量
            
        Yields:
            获取工人的SimPy事件
            
        Returns:
            获取到的工人列表
        """
        workers = []
        for _ in range(count):
            # 获取所有空闲工人并按工作时间排序
            idle_workers = [w for w in self.store.items if w.state == WorkerState.IDLE]
            
            if idle_workers:
                # 选择累计工作时间最少的工人（负载均衡）
                idle_workers.sort(key=lambda w: w.total_work_time)
                target_id = idle_workers[0].id
                
                # 从store中获取指定工人
                worker = yield self.store.get(lambda w: w.id == target_id)
            else:
                # 没有空闲工人，等待任意一个空闲工人
                worker = yield self.store.get(
                    lambda w: w.state == WorkerState.IDLE
                )
            
            worker.state = WorkerState.WORKING
            workers.append(worker)
        return workers
    
    def release_workers(self, workers: List[WorkerAgent]):
        """
        释放工人回池
        
        Args:
            workers: 要释放的工人列表
        """
        for worker in workers:
            worker.state = WorkerState.IDLE
            self.store.put(worker)
    
    def execute_rest(
        self, 
        workers: List[WorkerAgent], 
        duration: float, 
        reason: str = "time-triggered"
    ) -> Generator:
        """
        执行休息进程
        
        关键：工人在休息期间仍被当前任务"持有"，不归还Store
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
        """
        重置所有工人状态（用于新仿真）
        """
        for worker in self.workers.values():
            worker.reset()
            if worker not in self.store.items:
                self.store.put(worker)
