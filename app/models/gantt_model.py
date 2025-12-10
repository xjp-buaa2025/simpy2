"""
甘特图事件模型
定义甘特图中的事件数据结构

功能:
- 事件属性定义
- 时间格式转换（分钟 ↔ Day-Hour）
- 事件类型标识
"""

from typing import List, Optional
from dataclasses import dataclass, field

from app.models.enums import GanttEventType, OpType


@dataclass
class GanttEvent:
    """
    甘特图事件模型
    
    记录仿真中的单个事件，用于生成甘特图
    
    Attributes:
        engine_id: 发动机编号
        step_id: 步骤ID
        task_name: 任务名称
        op_type: 操作类型
        start_time: 开始时间（分钟）
        end_time: 结束时间（分钟）
        event_type: 事件类型（NORMAL/REST/REWORK/WAITING）
        worker_ids: 执行工人列表
        equipment_used: 使用的关键设备
        rework_count: 返工次数
    """
    
    engine_id: int
    step_id: str
    task_name: str
    op_type: str
    start_time: float
    end_time: float
    event_type: str = field(default=GanttEventType.NORMAL.value)
    worker_ids: List[str] = field(default_factory=list)
    equipment_used: List[str] = field(default_factory=list)
    rework_count: int = field(default=0)
    
    @property
    def duration(self) -> float:
        """
        计算事件时长（分钟）
        
        Returns:
            时长
        """
        return self.end_time - self.start_time
    
    @property
    def duration_hours(self) -> float:
        """
        计算事件时长（小时）
        
        Returns:
            时长
        """
        return self.duration / 60
    
    def to_calendar_time(self, work_hours_per_day: int = 8) -> dict:
        """
        转换为日历时间格式
        
        Args:
            work_hours_per_day: 每日工作小时数
            
        Returns:
            包含开始和结束的Day-Hour格式时间
        """
        return {
            "start": minutes_to_calendar_time(self.start_time, work_hours_per_day),
            "end": minutes_to_calendar_time(self.end_time, work_hours_per_day)
        }
    
    def get_start_day_hour(self, work_hours_per_day: int = 8) -> tuple:
        """
        获取开始时间的Day和Hour
        
        Args:
            work_hours_per_day: 每日工作小时数
            
        Returns:
            (day, hour)元组
        """
        minutes_per_day = work_hours_per_day * 60
        day = int(self.start_time // minutes_per_day) + 1
        hour = (self.start_time % minutes_per_day) / 60
        return day, hour
    
    def get_end_day_hour(self, work_hours_per_day: int = 8) -> tuple:
        """
        获取结束时间的Day和Hour
        
        Args:
            work_hours_per_day: 每日工作小时数
            
        Returns:
            (day, hour)元组
        """
        minutes_per_day = work_hours_per_day * 60
        day = int(self.end_time // minutes_per_day) + 1
        hour = (self.end_time % minutes_per_day) / 60
        return day, hour
    
    def is_normal(self) -> bool:
        """判断是否为正常工作事件"""
        return self.event_type == GanttEventType.NORMAL.value
    
    def is_rest(self) -> bool:
        """判断是否为休息事件"""
        return self.event_type == GanttEventType.REST.value
    
    def is_rework(self) -> bool:
        """判断是否为返工事件"""
        return self.event_type == GanttEventType.REWORK.value
    
    def is_waiting(self) -> bool:
        """判断是否为等待事件"""
        return self.event_type == GanttEventType.WAITING.value
    
    def overlaps_with(self, start: float, end: float) -> bool:
        """
        判断是否与指定时间范围重叠
        
        Args:
            start: 范围开始时间
            end: 范围结束时间
            
        Returns:
            是否重叠
        """
        return self.end_time > start and self.start_time < end
    
    def to_dict(self) -> dict:
        """
        转换为字典
        
        Returns:
            属性字典
        """
        return {
            "engine_id": self.engine_id,
            "step_id": self.step_id,
            "task_name": self.task_name,
            "op_type": self.op_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "event_type": self.event_type,
            "worker_ids": self.worker_ids,
            "equipment_used": self.equipment_used,
            "rework_count": self.rework_count
        }
    
    def to_csv_row(self, work_hours_per_day: int = 8) -> List:
        """
        转换为CSV行数据
        
        Args:
            work_hours_per_day: 每日工作小时数
            
        Returns:
            CSV字段列表
        """
        start_day, start_hour = self.get_start_day_hour(work_hours_per_day)
        end_day, end_hour = self.get_end_day_hour(work_hours_per_day)
        
        return [
            self.engine_id,
            self.step_id,
            self.task_name,
            self.op_type,
            start_day,
            f"{start_hour:.2f}",
            end_day,
            f"{end_hour:.2f}",
            f"{self.duration:.2f}",
            self.event_type,
            ";".join(self.worker_ids),
            ";".join(self.equipment_used),
            self.rework_count
        ]


def minutes_to_calendar_time(minutes: float, work_hours_per_day: int = 8) -> str:
    """
    将仿真分钟转换为 Day-Hour 格式
    
    Args:
        minutes: 仿真时间（分钟）
        work_hours_per_day: 每日工作小时数
        
    Returns:
        格式化字符串，如 "D1 2.5h"
    
    Example:
        >>> minutes_to_calendar_time(150, 8)
        'D1 2.5h'
        >>> minutes_to_calendar_time(600, 8)
        'D2 2.0h'
    """
    minutes_per_day = work_hours_per_day * 60
    day = int(minutes // minutes_per_day) + 1
    hour_in_day = (minutes % minutes_per_day) / 60
    return f"D{day} {hour_in_day:.1f}h"


def calendar_time_to_minutes(day: int, hour: float, work_hours_per_day: int = 8) -> float:
    """
    将 Day-Hour 格式转换为仿真分钟
    
    Args:
        day: 天数（从1开始）
        hour: 当天小时数
        work_hours_per_day: 每日工作小时数
        
    Returns:
        仿真分钟数
    
    Example:
        >>> calendar_time_to_minutes(1, 2.5, 8)
        150.0
        >>> calendar_time_to_minutes(2, 2.0, 8)
        600.0
    """
    minutes_per_day = work_hours_per_day * 60
    return (day - 1) * minutes_per_day + hour * 60


def parse_calendar_time(time_str: str, work_hours_per_day: int = 8) -> float:
    """
    解析 Day-Hour 格式字符串为分钟
    
    Args:
        time_str: 时间字符串，如 "D1 2.5h" 或 "D1 2:30"
        work_hours_per_day: 每日工作小时数
        
    Returns:
        仿真分钟数
    """
    import re
    
    # 尝试匹配 "D1 2.5h" 格式
    match = re.match(r'D(\d+)\s+(\d+\.?\d*)h?', time_str)
    if match:
        day = int(match.group(1))
        hour = float(match.group(2))
        return calendar_time_to_minutes(day, hour, work_hours_per_day)
    
    # 尝试匹配 "D1 2:30" 格式
    match = re.match(r'D(\d+)\s+(\d+):(\d+)', time_str)
    if match:
        day = int(match.group(1))
        hour = int(match.group(2)) + int(match.group(3)) / 60
        return calendar_time_to_minutes(day, hour, work_hours_per_day)
    
    raise ValueError(f"无法解析时间格式: {time_str}")


# CSV表头
GANTT_CSV_HEADERS = [
    "engine_id",
    "step_id",
    "task_name",
    "op_type",
    "start_day",
    "start_hour",
    "end_day",
    "end_hour",
    "duration_minutes",
    "event_type",
    "workers",
    "equipment",
    "rework_count"
]
