"""
KPI统计计算工具
提供仿真结果的统计分析功能

功能:
- 利用率计算（工人/设备）
- 一次通过率计算
- 周期时间统计
- 综合KPI汇总
- 瓶颈识别与分析
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
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


# ============ 瓶颈分析功能 ============

@dataclass
class BottleneckInfo:
    """瓶颈信息"""
    resource_type: str  # "worker" 或 "equipment" 或 "task"
    resource_id: str
    bottleneck_type: str  # "high_utilization", "long_wait", "frequent_queue", "critical_path"
    severity: str  # "high", "medium", "low"
    utilization_rate: float = 0
    wait_time: float = 0
    queue_time: float = 0
    impact_description: str = ""
    suggestion: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "bottleneck_type": self.bottleneck_type,
            "severity": self.severity,
            "utilization_rate": self.utilization_rate,
            "wait_time": self.wait_time,
            "queue_time": self.queue_time,
            "impact_description": self.impact_description,
            "suggestion": self.suggestion
        }


@dataclass
class BottleneckAnalysis:
    """瓶颈分析结果"""
    bottlenecks: List[BottleneckInfo] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "summary": self.summary,
            "recommendations": self.recommendations
        }


def analyze_bottlenecks(result: SimulationResult) -> BottleneckAnalysis:
    """
    分析生产瓶颈
    
    分析维度：
    1. 设备利用率瓶颈（高利用率设备）
    2. 工人利用率瓶颈（高利用率工人）
    3. 等待时间瓶颈（长等待的任务）
    4. 返工瓶颈（高返工率任务）
    5. 资源竞争瓶颈
    
    Args:
        result: 仿真结果
        
    Returns:
        瓶颈分析结果
    """
    analysis = BottleneckAnalysis()
    bottlenecks = []
    recommendations = []
    
    # 1. 分析设备瓶颈
    equipment_bottlenecks = _analyze_equipment_bottlenecks(result)
    bottlenecks.extend(equipment_bottlenecks)
    
    # 2. 分析工人瓶颈
    worker_bottlenecks = _analyze_worker_bottlenecks(result)
    bottlenecks.extend(worker_bottlenecks)
    
    # 3. 分析等待时间瓶颈
    wait_bottlenecks = _analyze_wait_time_bottlenecks(result)
    bottlenecks.extend(wait_bottlenecks)
    
    # 4. 分析返工瓶颈
    rework_bottlenecks = _analyze_rework_bottlenecks(result)
    bottlenecks.extend(rework_bottlenecks)
    
    # 按严重程度排序
    severity_order = {"high": 0, "medium": 1, "low": 2}
    bottlenecks.sort(key=lambda x: severity_order.get(x.severity, 3))
    
    analysis.bottlenecks = bottlenecks
    
    # 生成汇总
    analysis.summary = _generate_bottleneck_summary(bottlenecks, result)
    
    # 生成建议
    analysis.recommendations = _generate_recommendations(bottlenecks, result)
    
    return analysis


def _analyze_equipment_bottlenecks(result: SimulationResult) -> List[BottleneckInfo]:
    """分析设备瓶颈"""
    bottlenecks = []
    
    for equip in result.equipment_stats:
        # 跳过无限制设备
        if hasattr(equip, 'is_unlimited') and equip.is_unlimited:
            continue
            
        util_rate = equip.utilization_rate
        
        if util_rate >= 0.9:
            severity = "high"
            impact = f"设备 {equip.resource_id} 利用率高达 {util_rate*100:.1f}%，严重制约产能"
            suggestion = f"建议增加 {equip.resource_id} 数量或优化使用该设备的工序"
        elif util_rate >= 0.8:
            severity = "medium"
            impact = f"设备 {equip.resource_id} 利用率 {util_rate*100:.1f}%，接近满负荷"
            suggestion = f"关注 {equip.resource_id} 使用情况，必要时考虑增加设备"
        elif util_rate >= 0.7:
            severity = "low"
            impact = f"设备 {equip.resource_id} 利用率 {util_rate*100:.1f}%，负荷较高"
            suggestion = f"可考虑优化 {equip.resource_id} 的使用调度"
        else:
            continue
        
        bottlenecks.append(BottleneckInfo(
            resource_type="equipment",
            resource_id=equip.resource_id,
            bottleneck_type="high_utilization",
            severity=severity,
            utilization_rate=util_rate,
            impact_description=impact,
            suggestion=suggestion
        ))
    
    return bottlenecks


def _analyze_worker_bottlenecks(result: SimulationResult) -> List[BottleneckInfo]:
    """分析工人瓶颈"""
    bottlenecks = []
    
    utilizations = [w.utilization_rate for w in result.worker_stats]
    if not utilizations:
        return bottlenecks
    
    avg_util = sum(utilizations) / len(utilizations)
    max_util = max(utilizations)
    
    # 检查整体工人负荷
    if avg_util >= 0.85:
        bottlenecks.append(BottleneckInfo(
            resource_type="worker",
            resource_id="全体工人",
            bottleneck_type="high_utilization",
            severity="high",
            utilization_rate=avg_util,
            impact_description=f"工人平均利用率高达 {avg_util*100:.1f}%，整体负荷过重",
            suggestion="建议增加工人数量以提高产能和降低疲劳风险"
        ))
    elif avg_util >= 0.75:
        bottlenecks.append(BottleneckInfo(
            resource_type="worker",
            resource_id="全体工人",
            bottleneck_type="high_utilization",
            severity="medium",
            utilization_rate=avg_util,
            impact_description=f"工人平均利用率 {avg_util*100:.1f}%，负荷较高",
            suggestion="关注工人疲劳情况，考虑优化排班或增加人员"
        ))
    
    # 检查个别工人负荷不均
    for worker in result.worker_stats:
        if worker.utilization_rate >= 0.9:
            bottlenecks.append(BottleneckInfo(
                resource_type="worker",
                resource_id=worker.resource_id,
                bottleneck_type="high_utilization",
                severity="medium",
                utilization_rate=worker.utilization_rate,
                impact_description=f"工人 {worker.resource_id} 利用率 {worker.utilization_rate*100:.1f}%，负荷过重",
                suggestion=f"优化任务分配，减轻 {worker.resource_id} 的工作负担"
            ))
    
    return bottlenecks


def _analyze_wait_time_bottlenecks(result: SimulationResult) -> List[BottleneckInfo]:
    """分析等待时间瓶颈"""
    bottlenecks = []
    
    # 统计各任务的等待时间
    wait_events = [e for e in result.gantt_events if e.event_type == GanttEventType.WAITING]
    
    if not wait_events:
        return bottlenecks
    
    # 按任务步骤统计等待时间
    step_wait_times: Dict[str, List[float]] = {}
    for event in wait_events:
        step_id = event.step_id
        wait_time = event.end_time - event.start_time
        if step_id not in step_wait_times:
            step_wait_times[step_id] = []
        step_wait_times[step_id].append(wait_time)
    
    # 找出等待时间长的任务
    total_sim_time = result.sim_duration
    for step_id, wait_times in step_wait_times.items():
        avg_wait = sum(wait_times) / len(wait_times)
        total_wait = sum(wait_times)
        
        # 如果平均等待时间超过30分钟或总等待占总时长5%以上
        if avg_wait >= 30 or total_wait / total_sim_time >= 0.05:
            severity = "high" if avg_wait >= 60 else "medium"
            
            # 找出对应的任务名
            task_name = step_id
            for event in result.gantt_events:
                if event.step_id == step_id:
                    task_name = event.task_name.replace("(等待)", "").strip()
                    break
            
            bottlenecks.append(BottleneckInfo(
                resource_type="task",
                resource_id=step_id,
                bottleneck_type="long_wait",
                severity=severity,
                wait_time=avg_wait,
                impact_description=f"任务 '{task_name}' 平均等待时间 {avg_wait:.1f} 分钟，总等待 {total_wait:.1f} 分钟",
                suggestion=f"检查任务 '{task_name}' 所需资源是否充足，优化前置任务调度"
            ))
    
    return bottlenecks


def _analyze_rework_bottlenecks(result: SimulationResult) -> List[BottleneckInfo]:
    """分析返工瓶颈"""
    bottlenecks = []
    
    rework_events = [e for e in result.gantt_events if e.event_type == GanttEventType.REWORK]
    
    if not rework_events:
        return bottlenecks
    
    # 按任务统计返工次数和时间
    step_rework_info: Dict[str, Dict] = {}
    for event in rework_events:
        step_id = event.step_id
        if step_id not in step_rework_info:
            step_rework_info[step_id] = {
                "count": 0,
                "total_time": 0,
                "task_name": event.task_name.replace("(返工", "").replace(")", "").strip()
            }
        step_rework_info[step_id]["count"] += 1
        step_rework_info[step_id]["total_time"] += (event.end_time - event.start_time)
    
    # 找出返工严重的任务
    for step_id, info in step_rework_info.items():
        if info["count"] >= 3 or info["total_time"] >= 60:
            severity = "high" if info["count"] >= 5 else "medium"
            
            bottlenecks.append(BottleneckInfo(
                resource_type="task",
                resource_id=step_id,
                bottleneck_type="frequent_rework",
                severity=severity,
                wait_time=info["total_time"],
                impact_description=f"任务 '{info['task_name']}' 返工 {info['count']} 次，耗时 {info['total_time']:.1f} 分钟",
                suggestion=f"检查任务 '{info['task_name']}' 的质量控制流程，考虑增加前置检验或改进工艺"
            ))
    
    return bottlenecks


def _generate_bottleneck_summary(
    bottlenecks: List[BottleneckInfo], 
    result: SimulationResult
) -> Dict[str, Any]:
    """生成瓶颈汇总"""
    
    high_count = len([b for b in bottlenecks if b.severity == "high"])
    medium_count = len([b for b in bottlenecks if b.severity == "medium"])
    low_count = len([b for b in bottlenecks if b.severity == "low"])
    
    # 按类型统计
    equipment_bottlenecks = [b for b in bottlenecks if b.resource_type == "equipment"]
    worker_bottlenecks = [b for b in bottlenecks if b.resource_type == "worker"]
    task_bottlenecks = [b for b in bottlenecks if b.resource_type == "task"]
    
    # 主要瓶颈类型
    main_bottleneck_type = "none"
    if high_count > 0:
        high_bottlenecks = [b for b in bottlenecks if b.severity == "high"]
        if any(b.resource_type == "equipment" for b in high_bottlenecks):
            main_bottleneck_type = "equipment"
        elif any(b.resource_type == "worker" for b in high_bottlenecks):
            main_bottleneck_type = "worker"
        else:
            main_bottleneck_type = "task"
    
    return {
        "total_bottlenecks": len(bottlenecks),
        "by_severity": {
            "high": high_count,
            "medium": medium_count,
            "low": low_count
        },
        "by_type": {
            "equipment": len(equipment_bottlenecks),
            "worker": len(worker_bottlenecks),
            "task": len(task_bottlenecks)
        },
        "main_bottleneck_type": main_bottleneck_type,
        "production_status": _get_production_status(result),
        "efficiency_score": _calculate_efficiency_score(result, bottlenecks)
    }


def _get_production_status(result: SimulationResult) -> str:
    """获取生产状态描述"""
    rate = result.target_achievement_rate
    if rate >= 1.0:
        return "超额完成"
    elif rate >= 0.9:
        return "基本完成"
    elif rate >= 0.7:
        return "未达标"
    else:
        return "严重不足"


def _calculate_efficiency_score(
    result: SimulationResult, 
    bottlenecks: List[BottleneckInfo]
) -> float:
    """计算效率评分（0-100）"""
    score = 100.0
    
    # 根据达成率扣分
    if result.target_achievement_rate < 1.0:
        score -= (1.0 - result.target_achievement_rate) * 30
    
    # 根据瓶颈数量扣分
    high_count = len([b for b in bottlenecks if b.severity == "high"])
    medium_count = len([b for b in bottlenecks if b.severity == "medium"])
    score -= high_count * 10
    score -= medium_count * 5
    
    # 根据返工率扣分
    if result.quality_stats.first_pass_rate < 0.9:
        score -= (0.9 - result.quality_stats.first_pass_rate) * 20
    
    return max(0, min(100, score))


def _generate_recommendations(
    bottlenecks: List[BottleneckInfo], 
    result: SimulationResult
) -> List[str]:
    """生成改进建议"""
    recommendations = []
    
    # 高优先级瓶颈的建议
    high_bottlenecks = [b for b in bottlenecks if b.severity == "high"]
    
    # 设备瓶颈建议
    equip_bottlenecks = [b for b in high_bottlenecks if b.resource_type == "equipment"]
    if equip_bottlenecks:
        equip_names = [b.resource_id for b in equip_bottlenecks]
        recommendations.append(
            f"【优先】增加关键设备容量：{', '.join(equip_names)}。"
            f"这些设备利用率过高，是当前主要产能瓶颈。"
        )
    
    # 工人瓶颈建议
    worker_bottlenecks = [b for b in high_bottlenecks if b.resource_type == "worker"]
    if worker_bottlenecks:
        recommendations.append(
            "【优先】增加工人数量或优化排班。"
            "当前工人负荷过重，可能影响产能和质量。"
        )
    
    # 返工瓶颈建议
    rework_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == "frequent_rework"]
    if rework_bottlenecks:
        task_names = [b.resource_id for b in rework_bottlenecks[:3]]
        recommendations.append(
            f"【质量】关注高返工率任务：{', '.join(task_names)}。"
            f"建议加强质量控制或改进工艺流程。"
        )
    
    # 等待时间瓶颈建议
    wait_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == "long_wait"]
    if wait_bottlenecks:
        recommendations.append(
            "【调度】存在较长等待时间的任务，建议优化生产调度或增加相关资源。"
        )
    
    # 达成率建议
    if result.target_achievement_rate < 0.9:
        gap = result.config.target_output - result.engines_completed
        recommendations.append(
            f"【产量】当前产量缺口 {gap} 台，建议综合以上措施提升产能。"
        )
    
    # 如果没有明显瓶颈
    if not bottlenecks:
        if result.target_achievement_rate >= 1.0:
            recommendations.append(
                "【良好】当前生产状态良好，无明显瓶颈。"
                "可考虑提高目标产量或进一步优化资源配置。"
            )
        else:
            recommendations.append(
                "【分析】未检测到明显瓶颈，但产量未达标。"
                "建议检查工艺流程设计或增加仿真时长。"
            )
    
    return recommendations


def generate_kpi_report(result: SimulationResult) -> Dict[str, Any]:
    """
    生成完整的KPI报告（包含瓶颈分析）
    
    Args:
        result: 仿真结果
        
    Returns:
        完整KPI报告
    """
    kpi = calculate_kpi(result)
    bottleneck_analysis = analyze_bottlenecks(result)
    
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
        "events": calculate_event_statistics(result.gantt_events),
        "bottleneck_analysis": bottleneck_analysis.to_dict()
    }
