"""
工人模型
定义工人实体及其状态管理

功能:
- 工人属性管理
- 工作时间和休息时间统计
- 休息规则判断逻辑
"""

from typing import Optional
from dataclasses import dataclass, field

from app.models.enums import WorkerState


@dataclass
class WorkerAgent:
    """
    工人代理模型
    
    用于仿真中的工人实体，追踪工作状态和统计数据
    
    Attributes:
        id: 工人唯一ID（如 Worker_01）
        state: 当前状态（IDLE/WORKING/RESTING）
        consecutive_work_time: 当前连续工作时间（分钟）
        total_work_time: 累计工作时间（分钟）
        total_rest_time: 累计休息时间（分钟）
        tasks_completed: 完成任务数
        current_task_id: 当前执行的任务ID
        fatigue_level: 当前疲劳度（0-100）
        high_intensity_count: 高强度任务暴露次数
        fatigue_history: 疲劳度历史记录 [(时间, 疲劳度), ...]
    """
    
    id: str
    state: WorkerState = field(default=WorkerState.IDLE)
    consecutive_work_time: float = field(default=0.0)
    total_work_time: float = field(default=0.0)
    total_rest_time: float = field(default=0.0)
    tasks_completed: int = field(default=0)
    current_task_id: Optional[str] = field(default=None)
    fatigue_level: float = field(default=0.0)
    high_intensity_count: int = field(default=0)
    fatigue_history: list = field(default_factory=list)
    
    def needs_time_rest(self, threshold: float) -> bool:
        """
        规则A: 检查是否需要时间触发的休息
        
        Args:
            threshold: 连续工作时间阈值（分钟）
            
        Returns:
            是否需要休息（连续工作时间 ≥ 阈值）
        """
        return self.consecutive_work_time >= threshold
    
    def apply_rest(self, duration: float, current_time: float = 0):
        """
        应用休息
        
        累加休息时间并重置连续工作时间，降低疲劳度
        
        Args:
            duration: 休息时长（分钟）
            current_time: 当前仿真时间
        """
        self.total_rest_time += duration
        self.consecutive_work_time = 0.0
        # 休息恢复疲劳度（每分钟休息恢复2点疲劳）
        fatigue_recovery = min(duration * 2, self.fatigue_level)
        self.fatigue_level = max(0, self.fatigue_level - fatigue_recovery)
        # 记录疲劳度
        self.fatigue_history.append((current_time + duration, self.fatigue_level))
    
    def add_work_time(self, duration: float, work_load_score: int = 5, current_time: float = 0):
        """
        累加工作时间并更新疲劳度
        
        同时累加连续工作时间和总工作时间，根据负荷增加疲劳度
        
        Args:
            duration: 工作时长（分钟）
            work_load_score: 任务负荷评分（1-10）
            current_time: 当前仿真时间
        """
        self.consecutive_work_time += duration
        self.total_work_time += duration
        
        # 根据负荷和时长计算疲劳增加
        # 基础疲劳增加 = 时长 * 负荷系数
        fatigue_factor = work_load_score / 10.0  # 0.1 - 1.0
        fatigue_increase = duration * fatigue_factor * 0.5  # 每分钟最多增加0.5点
        self.fatigue_level = min(100, self.fatigue_level + fatigue_increase)
        
        # 高强度任务统计（REBA >= 7）
        if work_load_score >= 7:
            self.high_intensity_count += 1
        
        # 记录疲劳度历史
        self.fatigue_history.append((current_time + duration, self.fatigue_level))
    
    def start_working(self, task_id: Optional[str] = None):
        """
        开始工作
        
        Args:
            task_id: 任务ID
        """
        self.state = WorkerState.WORKING
        self.current_task_id = task_id
    
    def start_resting(self):
        """
        开始休息
        """
        self.state = WorkerState.RESTING
    
    def finish_working(self):
        """
        完成工作
        """
        self.state = WorkerState.IDLE
        self.current_task_id = None
        self.tasks_completed += 1
    
    def set_idle(self):
        """
        设置为空闲状态
        """
        self.state = WorkerState.IDLE
        self.current_task_id = None
    
    def reset(self):
        """
        重置工人状态（用于新仿真）
        """
        self.state = WorkerState.IDLE
        self.consecutive_work_time = 0.0
        self.total_work_time = 0.0
        self.total_rest_time = 0.0
        self.tasks_completed = 0
        self.current_task_id = None
        self.fatigue_level = 0.0
        self.high_intensity_count = 0
        self.fatigue_history = []
    
    def get_utilization(self, total_sim_time: float) -> float:
        """
        计算利用率
        
        Args:
            total_sim_time: 总仿真时间（分钟）
            
        Returns:
            利用率（0-1）
        """
        if total_sim_time <= 0:
            return 0.0
        return min(self.total_work_time / total_sim_time, 1.0)
    
    def get_rest_ratio(self, total_sim_time: float) -> float:
        """
        计算休息时间占比
        
        Args:
            total_sim_time: 总仿真时间（分钟）
            
        Returns:
            休息占比（0-1）
        """
        if total_sim_time <= 0:
            return 0.0
        return min(self.total_rest_time / total_sim_time, 1.0)
    
    def get_idle_time(self, total_sim_time: float) -> float:
        """
        计算空闲时间
        
        Args:
            total_sim_time: 总仿真时间（分钟）
            
        Returns:
            空闲时间（分钟）
        """
        return max(0, total_sim_time - self.total_work_time - self.total_rest_time)
    
    def to_dict(self) -> dict:
        """
        转换为字典
        
        Returns:
            属性字典
        """
        return {
            "id": self.id,
            "state": self.state.value,
            "consecutive_work_time": self.consecutive_work_time,
            "total_work_time": self.total_work_time,
            "total_rest_time": self.total_rest_time,
            "tasks_completed": self.tasks_completed,
            "current_task_id": self.current_task_id,
            "fatigue_level": self.fatigue_level,
            "high_intensity_count": self.high_intensity_count,
            "fatigue_history": self.fatigue_history
        }
    
    def __str__(self) -> str:
        return f"Worker({self.id}, state={self.state.value}, tasks={self.tasks_completed})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other):
        if isinstance(other, WorkerAgent):
            return self.id == other.id
        return False
    
    def __hash__(self):
        return hash(self.id)


def create_workers(count: int, prefix: str = "Worker") -> list:
    """
    批量创建工人
    
    Args:
        count: 工人数量
        prefix: ID前缀
        
    Returns:
        工人列表
    """
    return [
        WorkerAgent(id=f"{prefix}_{i+1:02d}")
        for i in range(count)
    ]
