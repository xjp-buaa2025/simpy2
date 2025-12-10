"""
KPI统计计算工具
提供仿真结果的统计分析功能

功能:
- 利用率计算（工人/设备）
- 一次通过率计算
- 周期时间统计
- 综合KPI汇总
"""

from typing import List, Dict, Any, Optional
from app.models.result_model import SimulationResult, ResourceUtilization, QualityStats
from app.models.gantt_model import GanttEvent
from app.models.enums import GanttEventType


def calculate_utilization_rate(
    work_time: float,
    total_time: float
) -> float:
    """
    计算利用率
    
    Args:
        work_time: 工作时间
        total_time: 总时间
        
    Returns:
        利用率（0-1）
    """
    if total_time <= 0:
        return 0.0
    return min(1.0, work_time / total_time)


def calculate_first_pass_rate(
    total_inspections: int,
    total_reworks: int
) -> float:
    """
    计算一次通过率
    
    Args:
        total_inspections: 总检测次数
        total_reworks: 返工次数
        
    Returns:
        一次通过率（0-1）
    """
    if total_inspections <= 0:
        return 1.0
    return (total_inspections - total_reworks) / total_inspections


def calculate_avg_cycle_time(
    engine_start_times: Dict[int, float],
    engine_end_times: Dict[int, float]
) -> float:
    """
    计算平均周期时间
    
    Args:
        engine_start_times: 发动机ID -> 开始时间
        engine_end_times: 发动机ID -> 结束时间
        
    Returns:
        平均周期时间（分钟）
    """
    cycle_times = []
    for engine_id in engine_end_times:
        if engine_id in engine_start_times:
            cycle_time = engine_end_times[engine_id] - engine_start_times[engine_id]
            if cycle_time > 0:
                cycle_times.append(cycle_time)
    
    if not cycle_times:
        return 0.0
    return sum(cycle_times) / len(cycle_times)


def calculate_kpi(result: SimulationResult) -> Dict[str, Any]:
    """
    计算完整的KPI指标
    
    Args:
        result: 仿真结果
        
    Returns:
        KPI指标字典
    """
    # 基本产出指标
    output_kpi = {
        "engines_completed": result.engines_completed,
        "target_output": result.config.target_output,
        "target_achievement_rate": result.target_achievement_rate,
        "target_achievement_percentage": f"{result.target_achievement_rate * 100:.1f}%"
    }
    
    # 时间效率指标
    time_kpi = {
        "avg_cycle_time_minutes": result.avg_cycle_time,
        "avg_cycle_time_hours": result.avg_cycle_time / 60 if result.avg_cycle_time > 0 else 0,
        "sim_duration_minutes": result.sim_duration,
        "sim_duration_hours": result.sim_duration / 60 if result.sim_duration > 0 else 0
    }
    
    # 工人利用率指标
    worker_utilizations = [w.utilization_rate for w in result.worker_stats]
    worker_kpi = {
        "avg_worker_utilization": (
            sum(worker_utilizations) / len(worker_utilizations)
            if worker_utilizations else 0
        ),
        "max_worker_utilization": max(worker_utilizations) if worker_utilizations else 0,
        "min_worker_utilization": min(worker_utilizations) if worker_utilizations else 0,
        "worker_count": len(result.worker_stats)
    }
    
    # 设备利用率指标
    equip_utilizations = [e.utilization_rate for e in result.equipment_stats]
    equipment_kpi = {
        "avg_equipment_utilization": (
            sum(equip_utilizations) / len(equip_utilizations)
            if equip_utilizations else 0
        ),
        "max_equipment_utilization": max(equip_utilizations) if equip_utilizations else 0,
        "min_equipment_utilization": min(equip_utilizations) if equip_utilizations else 0,
        "equipment_count": len(result.equipment_stats)
    }
    
    # 质量指标
    quality_kpi = {
        "total_inspections": result.quality_stats.total_inspections,
        "total_reworks": result.quality_stats.total_reworks,
        "first_pass_rate": result.quality_stats.first_pass_rate,
        "first_pass_percentage": f"{result.quality_stats.first_pass_rate * 100:.1f}%",
        "rework_time_total_minutes": result.quality_stats.rework_time_total,
        "rework_time_total_hours": result.quality_stats.rework_time_total / 60
    }
    
    return {
        "output": output_kpi,
        "time_efficiency": time_kpi,
        "worker_utilization": worker_kpi,
        "equipment_utilization": equipment_kpi,
        "quality": quality_kpi
    }


def calculate_worker_statistics(
    worker_stats: List[ResourceUtilization],
    total_sim_time: float
) -> Dict[str, Any]:
    """
    计算工人统计数据
    
    Args:
        worker_stats: 工人统计列表
        total_sim_time: 总仿真时间
        
    Returns:
        工人统计摘要
    """
    if not worker_stats:
        return {
            "count": 0,
            "total_work_time": 0,
            "total_rest_time": 0,
            "avg_utilization": 0,
            "details": []
        }
    
    total_work = sum(w.work_time for w in worker_stats)
    total_rest = sum(w.rest_time for w in worker_stats)
    total_tasks = sum(w.tasks_completed for w in worker_stats)
    avg_util = sum(w.utilization_rate for w in worker_stats) / len(worker_stats)
    
    return {
        "count": len(worker_stats),
        "total_work_time_minutes": total_work,
        "total_work_time_hours": total_work / 60,
        "total_rest_time_minutes": total_rest,
        "total_rest_time_hours": total_rest / 60,
        "total_tasks_completed": total_tasks,
        "avg_tasks_per_worker": total_tasks / len(worker_stats),
        "avg_utilization": avg_util,
        "avg_utilization_percentage": f"{avg_util * 100:.1f}%",
        "details": [
            {
                "id": w.resource_id,
                "work_time": w.work_time,
                "rest_time": w.rest_time,
                "utilization": w.utilization_rate,
                "tasks": w.tasks_completed
            }
            for w in worker_stats
        ]
    }


def calculate_equipment_statistics(
    equipment_stats: List[ResourceUtilization],
    total_sim_time: float
) -> Dict[str, Any]:
    """
    计算设备统计数据
    
    Args:
        equipment_stats: 设备统计列表
        total_sim_time: 总仿真时间
        
    Returns:
        设备统计摘要
    """
    if not equipment_stats:
        return {
            "count": 0,
            "avg_utilization": 0,
            "bottlenecks": [],
            "details": []
        }
    
    avg_util = sum(e.utilization_rate for e in equipment_stats) / len(equipment_stats)
    
    # 找出瓶颈设备（利用率>80%）
    bottlenecks = [
        e.resource_id for e in equipment_stats 
        if e.utilization_rate > 0.8
    ]
    
    return {
        "count": len(equipment_stats),
        "avg_utilization": avg_util,
        "avg_utilization_percentage": f"{avg_util * 100:.1f}%",
        "bottlenecks": bottlenecks,
        "details": [
            {
                "id": e.resource_id,
                "work_time": e.work_time,
                "idle_time": e.idle_time,
                "utilization": e.utilization_rate,
                "tasks": e.tasks_completed
            }
            for e in equipment_stats
        ]
    }


def calculate_event_statistics(events: List[GanttEvent]) -> Dict[str, Any]:
    """
    计算事件统计数据
    
    Args:
        events: 甘特图事件列表
        
    Returns:
        事件统计摘要
    """
    if not events:
        return {
            "total_events": 0,
            "by_type": {},
            "time_breakdown": {}
        }
    
    # 按类型统计
    type_counts = {}
    type_times = {}
    for event_type in GanttEventType:
        type_events = [e for e in events if e.event_type == event_type]
        type_counts[event_type.value] = len(type_events)
        type_times[event_type.value] = sum(e.end_time - e.start_time for e in type_events)
    
    # 计算总时间
    total_time = sum(type_times.values())
    
    # 时间占比
    time_percentages = {}
    for event_type, time in type_times.items():
        time_percentages[event_type] = (
            f"{time / total_time * 100:.1f}%" if total_time > 0 else "0%"
        )
    
    return {
        "total_events": len(events),
        "by_type": type_counts,
        "time_by_type_minutes": type_times,
        "time_percentages": time_percentages,
        "engine_count": len(set(e.engine_id for e in events))
    }


def generate_kpi_report(result: SimulationResult) -> Dict[str, Any]:
    """
    生成完整的KPI报告
    
    Args:
        result: 仿真结果
        
    Returns:
        完整KPI报告
    """
    kpi = calculate_kpi(result)
    
    return {
        "summary": {
            "sim_id": result.sim_id,
            "status": result.status.value,
            "completed_at": result.completed_at,
            "engines_completed": result.engines_completed,
            "target_output": result.config.target_output,
            "achievement_rate": kpi["output"]["target_achievement_percentage"]
        },
        "production": kpi["output"],
        "efficiency": kpi["time_efficiency"],
        "workers": calculate_worker_statistics(
            result.worker_stats, 
            result.sim_duration
        ),
        "equipment": calculate_equipment_statistics(
            result.equipment_stats,
            result.sim_duration
        ),
        "quality": kpi["quality"],
        "events": calculate_event_statistics(result.gantt_events)
    }
