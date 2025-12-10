"""
时间转换工具
提供仿真时间与日历时间的相互转换

功能:
- 仿真分钟 ↔ Day-Hour格式
- 时间格式化
- 时间解析
"""

from typing import Tuple, Dict, Any, Optional
import re


def minutes_to_day_hour(
    minutes: float, 
    work_hours_per_day: int = 8
) -> str:
    """
    将仿真分钟转换为 Day-Hour 格式字符串
    
    Args:
        minutes: 仿真时间（分钟）
        work_hours_per_day: 每日工作小时数
        
    Returns:
        格式化字符串，如 "D1 2.5h"
        
    Example:
        >>> minutes_to_day_hour(150, 8)
        'D1 2.5h'
        >>> minutes_to_day_hour(600, 8)
        'D2 2.0h'
    """
    minutes_per_day = work_hours_per_day * 60
    day = int(minutes // minutes_per_day) + 1
    hour_in_day = (minutes % minutes_per_day) / 60
    return f"D{day} {hour_in_day:.1f}h"


def minutes_to_day_hour_dict(
    minutes: float, 
    work_hours_per_day: int = 8
) -> Dict[str, Any]:
    """
    将仿真分钟转换为字典格式
    
    Args:
        minutes: 仿真时间（分钟）
        work_hours_per_day: 每日工作小时数
        
    Returns:
        包含day, hour, formatted的字典
    """
    minutes_per_day = work_hours_per_day * 60
    day = int(minutes // minutes_per_day) + 1
    hour_in_day = (minutes % minutes_per_day) / 60
    
    return {
        "day": day,
        "hour": round(hour_in_day, 2),
        "formatted": f"D{day} {hour_in_day:.1f}h",
        "total_minutes": minutes
    }


def day_hour_to_minutes(
    day: int, 
    hour: float, 
    work_hours_per_day: int = 8
) -> float:
    """
    将 Day-Hour 格式转换为仿真分钟
    
    Args:
        day: 天数（从1开始）
        hour: 当天小时数
        work_hours_per_day: 每日工作小时数
        
    Returns:
        仿真时间（分钟）
        
    Example:
        >>> day_hour_to_minutes(1, 2.5, 8)
        150.0
        >>> day_hour_to_minutes(2, 2.0, 8)
        600.0
    """
    minutes_per_day = work_hours_per_day * 60
    return (day - 1) * minutes_per_day + hour * 60


def parse_day_hour_string(
    s: str, 
    work_hours_per_day: int = 8
) -> Optional[float]:
    """
    解析 Day-Hour 格式字符串
    
    支持格式:
    - "D1 2.5h"
    - "D1 2.5"
    - "1-2.5"
    
    Args:
        s: 时间字符串
        work_hours_per_day: 每日工作小时数
        
    Returns:
        仿真分钟数，解析失败返回None
    """
    # 尝试匹配 "D1 2.5h" 格式
    match = re.match(r'D(\d+)\s+(\d+\.?\d*)h?', s, re.IGNORECASE)
    if match:
        day = int(match.group(1))
        hour = float(match.group(2))
        return day_hour_to_minutes(day, hour, work_hours_per_day)
    
    # 尝试匹配 "1-2.5" 格式
    match = re.match(r'(\d+)-(\d+\.?\d*)', s)
    if match:
        day = int(match.group(1))
        hour = float(match.group(2))
        return day_hour_to_minutes(day, hour, work_hours_per_day)
    
    return None


def format_duration(minutes: float) -> str:
    """
    格式化时长为易读字符串
    
    Args:
        minutes: 时长（分钟）
        
    Returns:
        格式化字符串，如 "2小时30分钟" 或 "45分钟"
    """
    if minutes < 60:
        return f"{minutes:.0f}分钟"
    
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    
    if mins == 0:
        return f"{hours}小时"
    return f"{hours}小时{mins}分钟"


def format_duration_short(minutes: float) -> str:
    """
    格式化时长为短格式
    
    Args:
        minutes: 时长（分钟）
        
    Returns:
        格式化字符串，如 "2.5h" 或 "45m"
    """
    if minutes < 60:
        return f"{minutes:.0f}m"
    
    hours = minutes / 60
    return f"{hours:.1f}h"


def get_time_range(
    start_day: int,
    start_hour: float,
    end_day: int,
    end_hour: float,
    work_hours_per_day: int = 8
) -> Tuple[float, float]:
    """
    获取时间范围（分钟）
    
    Args:
        start_day: 开始天数
        start_hour: 开始小时
        end_day: 结束天数
        end_hour: 结束小时
        work_hours_per_day: 每日工作小时数
        
    Returns:
        (开始分钟, 结束分钟)
    """
    start_minutes = day_hour_to_minutes(start_day, start_hour, work_hours_per_day)
    end_minutes = day_hour_to_minutes(end_day, end_hour, work_hours_per_day)
    return start_minutes, end_minutes


def calculate_calendar_info(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据配置计算日历信息
    
    Args:
        config_dict: 配置字典，需包含work_hours_per_day和work_days_per_month
        
    Returns:
        日历信息字典
    """
    work_hours = config_dict.get('work_hours_per_day', 8)
    work_days = config_dict.get('work_days_per_month', 22)
    
    minutes_per_day = work_hours * 60
    total_minutes = minutes_per_day * work_days
    total_hours = work_hours * work_days
    
    return {
        "work_hours_per_day": work_hours,
        "work_days_per_month": work_days,
        "minutes_per_day": minutes_per_day,
        "total_minutes": total_minutes,
        "total_hours": total_hours,
        "total_days": work_days
    }


def split_time_into_days(
    start_minutes: float,
    end_minutes: float,
    work_hours_per_day: int = 8
) -> list:
    """
    将跨天时间段分割为每天的片段
    
    用于甘特图渲染时处理跨天任务
    
    Args:
        start_minutes: 开始时间（分钟）
        end_minutes: 结束时间（分钟）
        work_hours_per_day: 每日工作小时数
        
    Returns:
        时间片段列表 [(start, end, day), ...]
    """
    segments = []
    minutes_per_day = work_hours_per_day * 60
    
    current = start_minutes
    while current < end_minutes:
        day = int(current // minutes_per_day) + 1
        day_start = (day - 1) * minutes_per_day
        day_end = day * minutes_per_day
        
        segment_end = min(end_minutes, day_end)
        segments.append({
            "start": current,
            "end": segment_end,
            "day": day,
            "start_hour": (current - day_start) / 60,
            "end_hour": (segment_end - day_start) / 60
        })
        
        current = segment_end
    
    return segments
