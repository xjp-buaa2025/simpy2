"""
结果查询接口
提供仿真结果的查询、导出和分析功能

API端点:
- GET /api/results/{sim_id}: 获取仿真结果
- GET /api/results/list: 列出所有结果
- POST /api/results/export/gantt: 导出甘特图CSV
- POST /api/results/export/report: 导出完整报告
- GET /api/results/{sim_id}/gantt: 获取甘特图数据（支持时间筛选）
- GET /api/results/{sim_id}/kpi: 获取KPI指标
- GET /api/results/{sim_id}/bottleneck: 获取瓶颈分析
"""

import os
import io
import csv
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()


# ============ 数据模型 ============

class APIResponse(BaseModel):
    """统一API响应格式"""
    success: bool
    message: str
    data: Optional[Any] = None


class GanttTimeRange(BaseModel):
    """甘特图时间范围"""
    start_day: int = Field(default=1, ge=1, description="开始天数")
    start_hour: float = Field(default=0, ge=0, description="开始小时")
    end_day: int = Field(default=22, ge=1, description="结束天数")
    end_hour: float = Field(default=8, ge=0, description="结束小时")
    work_hours_per_day: int = Field(default=8, ge=1, le=24, description="每日工作小时数")


class GanttExportRequest(BaseModel):
    """甘特图导出请求"""
    sim_id: str = Field(description="仿真ID")
    time_range: Optional[GanttTimeRange] = Field(default=None, description="时间范围")
    include_rest: bool = Field(default=True, description="包含休息事件")
    include_rework: bool = Field(default=True, description="包含返工事件")


class KPIData(BaseModel):
    """KPI数据"""
    # 产量指标
    engines_completed: int = Field(description="完成发动机数量")
    target_output: int = Field(description="目标产量")
    target_achievement_rate: float = Field(description="计划达成率")
    
    # 时间指标
    total_sim_time: float = Field(description="总仿真时间（分钟）")
    avg_cycle_time: float = Field(description="平均单台周期时间（分钟）")
    avg_cycle_time_hours: float = Field(description="平均单台周期时间（小时）")
    
    # 效率指标
    avg_worker_utilization: float = Field(description="平均工人利用率")
    avg_equipment_utilization: float = Field(description="平均设备利用率")
    
    # 质量指标
    first_pass_rate: float = Field(description="一次通过率")
    total_reworks: int = Field(description="总返工次数")
    rework_time_ratio: float = Field(description="返工时间占比")


# ============ 模拟数据存储（与simulation.py共享） ============

# 导入simulation模块的存储
from app.api.simulation import simulation_results, SimulationResult, SimulationStatus


# ============ 辅助函数 ============

def minutes_to_day_hour(minutes: float, work_hours_per_day: int) -> Dict[str, Any]:
    """将仿真分钟转换为Day-Hour格式"""
    minutes_per_day = work_hours_per_day * 60
    day = int(minutes // minutes_per_day) + 1
    remaining_minutes = minutes % minutes_per_day
    hour = remaining_minutes / 60
    
    return {
        "day": day,
        "hour": round(hour, 2),
        "formatted": f"D{day} {hour:.1f}h",
        "total_minutes": minutes
    }


def day_hour_to_minutes(day: int, hour: float, work_hours_per_day: int) -> float:
    """将Day-Hour格式转换为仿真分钟"""
    minutes_per_day = work_hours_per_day * 60
    return (day - 1) * minutes_per_day + hour * 60


# ============ API端点 ============

@router.get("/{sim_id}", response_model=APIResponse)
async def get_simulation_result(sim_id: str):
    """
    获取仿真结果
    
    返回指定仿真ID的完整结果数据
    """
    if sim_id not in simulation_results:
        return APIResponse(
            success=False,
            message=f"仿真结果 {sim_id} 不存在"
        )
    
    result = simulation_results[sim_id]
    
    return APIResponse(
        success=True,
        message="获取结果成功",
        data=result.model_dump()
    )


@router.get("/list/all", response_model=APIResponse)
async def list_all_results(
    limit: int = Query(default=20, ge=1, le=100, description="返回数量限制"),
    status: Optional[str] = Query(default=None, description="筛选状态")
):
    """
    列出所有仿真结果
    
    返回仿真结果列表的概要信息
    """
    results_list = []
    
    for sim_id, result in simulation_results.items():
        # 状态筛选
        if status and result.status.value != status:
            continue
        
        results_list.append({
            "sim_id": sim_id,
            "status": result.status.value,
            "engines_completed": result.engines_completed,
            "target_achievement_rate": round(result.target_achievement_rate * 100, 1),
            "avg_cycle_time_hours": round(result.avg_cycle_time / 60, 2),
            "created_at": result.created_at,
            "completed_at": result.completed_at,
            "config_summary": {
                "num_workers": result.config.num_workers,
                "target_output": result.config.target_output,
                "work_days": result.config.work_days_per_month
            }
        })
    
    # 按创建时间倒序排列
    results_list.sort(key=lambda x: x["created_at"], reverse=True)
    
    # 限制返回数量
    results_list = results_list[:limit]
    
    return APIResponse(
        success=True,
        message=f"共 {len(results_list)} 条结果",
        data=results_list
    )


@router.get("/{sim_id}/gantt", response_model=APIResponse)
async def get_gantt_data(
    sim_id: str,
    start_day: int = Query(default=1, ge=1, description="开始天数"),
    start_hour: float = Query(default=0, ge=0, description="开始小时"),
    end_day: int = Query(default=22, ge=1, description="结束天数"),
    end_hour: float = Query(default=8, ge=0, description="结束小时"),
    engine_id: Optional[int] = Query(default=None, description="筛选发动机编号"),
    event_type: Optional[str] = Query(default=None, description="筛选事件类型")
):
    """
    获取甘特图数据
    
    支持按时间范围、发动机编号、事件类型筛选
    返回格式化的甘特图事件数据
    """
    if sim_id not in simulation_results:
        return APIResponse(
            success=False,
            message=f"仿真结果 {sim_id} 不存在"
        )
    
    result = simulation_results[sim_id]
    work_hours = result.config.work_hours_per_day
    
    # 计算时间范围（分钟）
    start_minutes = day_hour_to_minutes(start_day, start_hour, work_hours)
    end_minutes = day_hour_to_minutes(end_day, end_hour, work_hours)
    
    # 筛选事件
    filtered_events = []
    for event in result.gantt_events:
        # 时间范围筛选
        if event.end_time < start_minutes or event.start_time > end_minutes:
            continue
        
        # 发动机筛选
        if engine_id is not None and event.engine_id != engine_id:
            continue
        
        # 事件类型筛选
        if event_type and event.event_type != event_type:
            continue
        
        # 格式化时间
        event_data = event.model_dump()
        event_data["start_time_formatted"] = minutes_to_day_hour(event.start_time, work_hours)
        event_data["end_time_formatted"] = minutes_to_day_hour(event.end_time, work_hours)
        event_data["duration_minutes"] = event.end_time - event.start_time
        
        filtered_events.append(event_data)
    
    # 按发动机和开始时间排序
    filtered_events.sort(key=lambda x: (x["engine_id"], x["start_time"]))
    
    return APIResponse(
        success=True,
        message=f"获取 {len(filtered_events)} 个甘特图事件",
        data={
            "events": filtered_events,
            "time_range": {
                "start": minutes_to_day_hour(start_minutes, work_hours),
                "end": minutes_to_day_hour(end_minutes, work_hours)
            },
            "total_events": len(result.gantt_events),
            "filtered_events": len(filtered_events)
        }
    )


@router.get("/{sim_id}/kpi", response_model=APIResponse)
async def get_kpi_data(sim_id: str):
    """
    获取KPI指标
    
    返回仿真结果的关键性能指标
    """
    if sim_id not in simulation_results:
        return APIResponse(
            success=False,
            message=f"仿真结果 {sim_id} 不存在"
        )
    
    result = simulation_results[sim_id]
    
    # 计算工人平均利用率
    avg_worker_util = 0
    if result.worker_stats:
        avg_worker_util = sum(w.utilization_rate for w in result.worker_stats) / len(result.worker_stats)
    
    # 计算设备平均利用率
    avg_equip_util = 0
    if result.equipment_stats:
        avg_equip_util = sum(e.utilization_rate for e in result.equipment_stats) / len(result.equipment_stats)
    
    # 计算返工时间占比
    total_time = sum(e.end_time - e.start_time for e in result.gantt_events)
    rework_time = sum(e.end_time - e.start_time for e in result.gantt_events if e.event_type == "REWORK")
    rework_ratio = rework_time / total_time if total_time > 0 else 0
    
    kpi = KPIData(
        engines_completed=result.engines_completed,
        target_output=result.config.target_output,
        target_achievement_rate=result.target_achievement_rate,
        total_sim_time=result.sim_duration,
        avg_cycle_time=result.avg_cycle_time,
        avg_cycle_time_hours=result.avg_cycle_time / 60,
        avg_worker_utilization=avg_worker_util,
        avg_equipment_utilization=avg_equip_util,
        first_pass_rate=result.quality_stats.first_pass_rate,
        total_reworks=result.quality_stats.total_reworks,
        rework_time_ratio=rework_ratio
    )
    
    return APIResponse(
        success=True,
        message="获取KPI成功",
        data=kpi.model_dump()
    )


@router.get("/{sim_id}/bottleneck", response_model=APIResponse)
async def get_bottleneck_analysis(sim_id: str):
    """
    获取瓶颈分析
    
    分析生产过程中的瓶颈，包括：
    - 设备瓶颈（高利用率设备）
    - 工人瓶颈（高负荷工人）
    - 等待时间瓶颈（长等待任务）
    - 返工瓶颈（高返工率任务）
    
    返回瓶颈列表、汇总和改进建议
    """
    if sim_id not in simulation_results:
        return APIResponse(
            success=False,
            message=f"仿真结果 {sim_id} 不存在"
        )
    
    result = simulation_results[sim_id]
    
    # 使用统计模块的瓶颈分析
    from app.utils.statistics import analyze_bottlenecks
    
    analysis = analyze_bottlenecks(result)
    
    return APIResponse(
        success=True,
        message=f"识别到 {len(analysis.bottlenecks)} 个瓶颈",
        data=analysis.to_dict()
    )


@router.post("/export/gantt")
async def export_gantt_csv(request: GanttExportRequest):
    """
    导出甘特图CSV
    
    将甘特图数据导出为CSV文件
    """
    if request.sim_id not in simulation_results:
        raise HTTPException(status_code=404, detail=f"仿真结果 {request.sim_id} 不存在")
    
    result = simulation_results[request.sim_id]
    work_hours = result.config.work_hours_per_day
    
    # 筛选事件
    events = result.gantt_events
    if request.time_range:
        start_minutes = day_hour_to_minutes(
            request.time_range.start_day,
            request.time_range.start_hour,
            work_hours
        )
        end_minutes = day_hour_to_minutes(
            request.time_range.end_day,
            request.time_range.end_hour,
            work_hours
        )
        events = [e for e in events if e.start_time >= start_minutes and e.end_time <= end_minutes]
    
    if not request.include_rest:
        events = [e for e in events if e.event_type != "REST"]
    
    if not request.include_rework:
        events = [e for e in events if e.event_type != "REWORK"]
    
    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    headers = [
        "engine_id", "step_id", "task_name", "op_type",
        "start_day", "start_hour", "end_day", "end_hour",
        "duration_minutes", "event_type", "workers", "equipment", "rework_count"
    ]
    writer.writerow(headers)
    
    # 数据行
    for event in events:
        start_time = minutes_to_day_hour(event.start_time, work_hours)
        end_time = minutes_to_day_hour(event.end_time, work_hours)
        
        writer.writerow([
            event.engine_id,
            event.step_id,
            event.task_name,
            event.op_type,
            start_time["day"],
            start_time["hour"],
            end_time["day"],
            end_time["hour"],
            round(event.end_time - event.start_time, 2),
            event.event_type,
            ";".join(event.worker_ids),
            ";".join(event.equipment_used),
            event.rework_count
        ])
    
    output.seek(0)
    filename = f"gantt_{request.sim_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.post("/export/report")
async def export_report(sim_id: str):
    """
    导出完整报告
    
    生成包含配置、KPI、甘特图数据的JSON报告
    """
    if sim_id not in simulation_results:
        raise HTTPException(status_code=404, detail=f"仿真结果 {sim_id} 不存在")
    
    result = simulation_results[sim_id]
    work_hours = result.config.work_hours_per_day
    
    # 获取瓶颈分析
    from app.utils.statistics import analyze_bottlenecks
    bottleneck_analysis = analyze_bottlenecks(result)
    
    # 构建报告
    report = {
        "report_info": {
            "sim_id": sim_id,
            "generated_at": datetime.now().isoformat(),
            "system": "航空发动机装配排产仿真系统",
            "version": "1.0.0"
        },
        "config": result.config.model_dump(),
        "summary": {
            "status": result.status.value,
            "engines_completed": result.engines_completed,
            "target_achievement_rate": f"{result.target_achievement_rate * 100:.1f}%",
            "avg_cycle_time": f"{result.avg_cycle_time / 60:.2f} 小时",
            "total_sim_time": f"{result.sim_duration / 60:.2f} 小时"
        },
        "quality_stats": result.quality_stats.model_dump(),
        "worker_stats": [w.model_dump() for w in result.worker_stats],
        "equipment_stats": [e.model_dump() for e in result.equipment_stats],
        "bottleneck_analysis": bottleneck_analysis.to_dict(),
        "gantt_events_count": len(result.gantt_events)
    }
    
    # 生成JSON
    output = json.dumps(report, ensure_ascii=False, indent=2)
    filename = f"report_{sim_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    return StreamingResponse(
        io.BytesIO(output.encode('utf-8')),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/{sim_id}/worker-stats", response_model=APIResponse)
async def get_worker_stats(sim_id: str):
    """
    获取工人统计数据
    
    返回各工人的利用率、工作时间、休息时间等详细数据
    """
    if sim_id not in simulation_results:
        return APIResponse(
            success=False,
            message=f"仿真结果 {sim_id} 不存在"
        )
    
    result = simulation_results[sim_id]
    
    # 格式化工人统计
    worker_data = []
    for stat in result.worker_stats:
        worker_data.append({
            "worker_id": stat.resource_id,
            "work_time_hours": round(stat.work_time / 60, 2),
            "rest_time_hours": round(stat.rest_time / 60, 2),
            "idle_time_hours": round(stat.idle_time / 60, 2),
            "utilization_rate": round(stat.utilization_rate * 100, 1),
            "tasks_completed": stat.tasks_completed
        })
    
    return APIResponse(
        success=True,
        message="获取工人统计成功",
        data=worker_data
    )


@router.get("/{sim_id}/equipment-stats", response_model=APIResponse)
async def get_equipment_stats(sim_id: str):
    """
    获取设备统计数据
    
    返回各设备的利用率详细数据，包括关键设备和无限制设备
    """
    if sim_id not in simulation_results:
        return APIResponse(
            success=False,
            message=f"仿真结果 {sim_id} 不存在"
        )
    
    result = simulation_results[sim_id]
    
    # 格式化设备统计
    equipment_data = []
    critical_equipment = []
    unlimited_equipment = []
    
    for stat in result.equipment_stats:
        item = {
            "equipment_name": stat.resource_id,
            "work_time_hours": round(stat.work_time / 60, 2),
            "idle_time_hours": round(stat.idle_time / 60, 2),
            "utilization_rate": round(stat.utilization_rate * 100, 1),
            "tasks_served": stat.tasks_completed,
            "is_unlimited": getattr(stat, 'is_unlimited', False),
            "is_bottleneck": stat.utilization_rate > 0.8
        }
        equipment_data.append(item)
        
        if getattr(stat, 'is_unlimited', False):
            unlimited_equipment.append(item)
        else:
            critical_equipment.append(item)
    
    return APIResponse(
        success=True,
        message="获取设备统计成功",
        data={
            "all": equipment_data,
            "critical": critical_equipment,
            "unlimited": unlimited_equipment,
            "summary": {
                "total_count": len(equipment_data),
                "critical_count": len(critical_equipment),
                "unlimited_count": len(unlimited_equipment),
                "bottleneck_count": len([e for e in equipment_data if e["is_bottleneck"]])
            }
        }
    )


@router.delete("/{sim_id}", response_model=APIResponse)
async def delete_result(sim_id: str):
    """
    删除仿真结果
    
    从存储中删除指定的仿真结果
    """
    if sim_id not in simulation_results:
        return APIResponse(
            success=False,
            message=f"仿真结果 {sim_id} 不存在"
        )
    
    del simulation_results[sim_id]
    
    return APIResponse(
        success=True,
        message=f"仿真结果 {sim_id} 已删除"
    )
