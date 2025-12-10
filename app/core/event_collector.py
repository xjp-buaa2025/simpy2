"""
事件收集器
收集仿真过程中的所有事件，用于甘特图生成

功能:
- 收集甘特图事件
- 时间格式转换
- 事件筛选和查询
- 统计计算
"""

from typing import List, Dict, Any, Optional
from app.models.gantt_model import GanttEvent, minutes_to_calendar_time
from app.models.enums import GanttEventType


class EventCollector:
    """
    事件收集器
    
    收集仿真过程中的所有甘特图事件
    提供事件查询和统计功能
    """
    
    def __init__(self, work_hours_per_day: int = 8):
        """
        初始化事件收集器
        
        Args:
            work_hours_per_day: 每日工作小时数（用于时间转换）
        """
        self.events: List[GanttEvent] = []
        self.work_hours_per_day = work_hours_per_day
        
        # 统计计数器
        self.total_inspections = 0
        self.total_reworks = 0
        self.rework_time_total = 0.0
    
    def add_event(self, event: GanttEvent):
        """
        添加事件
        
        Args:
            event: 甘特图事件
        """
        self.events.append(event)
        
        # 更新统计
        if event.op_type == "M":
            self.total_inspections += 1
        if event.event_type == GanttEventType.REWORK:
            self.total_reworks += 1
            self.rework_time_total += (event.end_time - event.start_time)
    
    def get_all_events(self) -> List[GanttEvent]:
        """获取所有事件"""
        return self.events
    
    def get_events_in_range(
        self, 
        start_minute: float, 
        end_minute: float
    ) -> List[GanttEvent]:
        """
        获取指定时间范围内的事件
        
        Args:
            start_minute: 开始时间（分钟）
            end_minute: 结束时间（分钟）
            
        Returns:
            范围内的事件列表
        """
        return [
            e for e in self.events
            if e.end_time > start_minute and e.start_time < end_minute
        ]
    
    def get_events_by_engine(self, engine_id: int) -> List[GanttEvent]:
        """
        获取指定发动机的事件
        
        Args:
            engine_id: 发动机编号
            
        Returns:
            该发动机的所有事件
        """
        return [e for e in self.events if e.engine_id == engine_id]
    
    def get_events_by_type(self, event_type: GanttEventType) -> List[GanttEvent]:
        """
        获取指定类型的事件
        
        Args:
            event_type: 事件类型
            
        Returns:
            该类型的所有事件
        """
        return [e for e in self.events if e.event_type == event_type]
    
    def get_events_by_worker(self, worker_id: str) -> List[GanttEvent]:
        """
        获取指定工人参与的事件
        
        Args:
            worker_id: 工人ID
            
        Returns:
            该工人参与的所有事件
        """
        return [e for e in self.events if worker_id in e.worker_ids]
    
    def get_events_by_equipment(self, equipment_name: str) -> List[GanttEvent]:
        """
        获取使用指定设备的事件
        
        Args:
            equipment_name: 设备名称
            
        Returns:
            使用该设备的所有事件
        """
        return [e for e in self.events if equipment_name in e.equipment_used]
    
    def get_engine_ids(self) -> List[int]:
        """获取所有发动机ID"""
        return sorted(set(e.engine_id for e in self.events))
    
    def get_event_count(self) -> int:
        """获取事件总数"""
        return len(self.events)
    
    def get_event_type_counts(self) -> Dict[str, int]:
        """
        获取各类型事件数量统计
        
        Returns:
            事件类型 -> 数量 映射
        """
        counts = {}
        for event_type in GanttEventType:
            counts[event_type.value] = len(
                [e for e in self.events if e.event_type == event_type]
            )
        return counts
    
    def get_total_work_time(self) -> float:
        """获取总工作时间（正常工作事件）"""
        return sum(
            e.end_time - e.start_time
            for e in self.events
            if e.event_type == GanttEventType.NORMAL
        )
    
    def get_total_rest_time(self) -> float:
        """获取总休息时间"""
        return sum(
            e.end_time - e.start_time
            for e in self.events
            if e.event_type == GanttEventType.REST
        )
    
    def get_total_wait_time(self) -> float:
        """获取总等待时间"""
        return sum(
            e.end_time - e.start_time
            for e in self.events
            if e.event_type == GanttEventType.WAITING
        )
    
    def get_total_rework_time(self) -> float:
        """获取总返工时间"""
        return self.rework_time_total
    
    def get_quality_stats(self) -> Dict[str, Any]:
        """
        获取质量统计
        
        Returns:
            质量统计字典
        """
        first_pass_rate = (
            (self.total_inspections - self.total_reworks) / self.total_inspections
            if self.total_inspections > 0 else 1.0
        )
        
        return {
            "total_inspections": self.total_inspections,
            "total_reworks": self.total_reworks,
            "first_pass_rate": first_pass_rate,
            "rework_time_total": self.rework_time_total
        }
    
    def get_engine_completion_times(self) -> Dict[int, float]:
        """
        获取各发动机的完成时间
        
        Returns:
            发动机ID -> 完成时间 映射
        """
        completion_times = {}
        for engine_id in self.get_engine_ids():
            engine_events = self.get_events_by_engine(engine_id)
            if engine_events:
                completion_times[engine_id] = max(e.end_time for e in engine_events)
        return completion_times
    
    def get_events_for_display(
        self,
        start_minute: Optional[float] = None,
        end_minute: Optional[float] = None,
        engine_id: Optional[int] = None,
        event_type: Optional[GanttEventType] = None
    ) -> List[Dict[str, Any]]:
        """
        获取用于显示的事件数据
        
        Args:
            start_minute: 开始时间筛选
            end_minute: 结束时间筛选
            engine_id: 发动机ID筛选
            event_type: 事件类型筛选
            
        Returns:
            格式化的事件列表
        """
        filtered = self.events
        
        if start_minute is not None and end_minute is not None:
            filtered = [
                e for e in filtered
                if e.end_time > start_minute and e.start_time < end_minute
            ]
        
        if engine_id is not None:
            filtered = [e for e in filtered if e.engine_id == engine_id]
        
        if event_type is not None:
            filtered = [e for e in filtered if e.event_type == event_type]
        
        return [e.to_display_dict(self.work_hours_per_day) for e in filtered]
    
    def clear(self):
        """清空所有事件"""
        self.events = []
        self.total_inspections = 0
        self.total_reworks = 0
        self.rework_time_total = 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取事件汇总
        
        Returns:
            汇总信息字典
        """
        return {
            "total_events": len(self.events),
            "event_type_counts": self.get_event_type_counts(),
            "engine_count": len(self.get_engine_ids()),
            "total_work_time": self.get_total_work_time(),
            "total_rest_time": self.get_total_rest_time(),
            "total_wait_time": self.get_total_wait_time(),
            "quality_stats": self.get_quality_stats()
        }
