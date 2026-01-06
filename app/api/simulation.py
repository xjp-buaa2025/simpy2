"""
仿真控制接口
提供仿真的启动、停止、状态查询等功能

API端点:
- POST /api/simulation/run: 运行仿真
- GET /api/simulation/test: 运行测试仿真
- GET /api/simulation/status/{sim_id}: 获取仿真状态
- POST /api/simulation/stop/{sim_id}: 停止仿真
"""

import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

router = APIRouter()


# ============ 枚举和常量 ============

class SimulationStatus(str, Enum):
    """仿真状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OpType(str, Enum):
    """操作类型枚举"""
    H = "H"
    A = "A"
    M = "M"
    T = "T"
    D = "D"


# ============ 数据模型 ============

from app.models.config_model import GlobalConfig

class ProcessNode(BaseModel):
    """工艺节点模型"""
    step_id: str
    task_name: str
    op_type: OpType
    predecessors: str = ""
    std_duration: float
    time_variance: float = 0.0
    work_load_score: int = Field(default=5, ge=1, le=10)
    rework_prob: float = Field(default=0.0, ge=0, le=1)
    required_workers: int = Field(default=1, ge=1)
    required_tools: List[str] = []
    station: str = ""  # 工位ID
    x: float = 0
    y: float = 0


class ProcessDefinition(BaseModel):
    """工艺流程定义"""
    name: str = "未命名流程"
    description: str = ""
    nodes: List[ProcessNode] = []


class SimulationRequest(BaseModel):
    """仿真请求"""
    config: GlobalConfig
    process: ProcessDefinition


class GanttEvent(BaseModel):
    """甘特图事件"""
    engine_id: int = Field(description="发动机编号")
    step_id: str = Field(description="步骤ID")
    task_name: str = Field(description="任务名称")
    op_type: str = Field(description="操作类型")
    start_time: float = Field(description="开始时间（分钟）")
    end_time: float = Field(description="结束时间（分钟）")
    event_type: str = Field(description="事件类型（NORMAL/REST/REWORK/WAITING）")
    worker_ids: List[str] = Field(default=[], description="执行工人列表")
    equipment_used: List[str] = Field(default=[], description="使用的关键设备")
    rework_count: int = Field(default=0, description="返工次数")


class ResourceUtilization(BaseModel):
    """资源利用率统计"""
    resource_id: str = Field(description="资源ID")
    resource_type: str = Field(description="资源类型")
    total_time: float = Field(description="总时间")
    work_time: float = Field(description="工作时间")
    rest_time: float = Field(default=0, description="休息时间")
    idle_time: float = Field(default=0, description="空闲时间")
    utilization_rate: float = Field(description="利用率")
    tasks_completed: int = Field(default=0, description="完成任务数")


class QualityStats(BaseModel):
    """质量统计"""
    total_inspections: int = Field(default=0, description="总检测次数")
    total_reworks: int = Field(default=0, description="总返工次数")
    first_pass_rate: float = Field(default=1.0, description="一次通过率")
    rework_time_total: float = Field(default=0, description="返工总耗时")


class SimulationResult(BaseModel):
    """仿真结果"""
    sim_id: str = Field(description="仿真ID")
    status: SimulationStatus = Field(description="仿真状态")
    config: GlobalConfig = Field(description="使用的配置")
    sim_duration: float = Field(description="实际仿真时长（分钟）")
    engines_completed: int = Field(description="完成发动机数量")
    target_achievement_rate: float = Field(description="计划达成率")
    avg_cycle_time: float = Field(description="平均单台周期时间（分钟）")
    worker_stats: List[ResourceUtilization] = Field(default=[], description="工人统计")
    equipment_stats: List[ResourceUtilization] = Field(default=[], description="设备统计")
    quality_stats: QualityStats = Field(description="质量统计")
    gantt_events: List[GanttEvent] = Field(default=[], description="甘特图事件列表")
    time_mapping: Dict[str, Any] = Field(default={}, description="时间映射元数据")
    created_at: str = Field(description="创建时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")


class APIResponse(BaseModel):
    """统一API响应格式"""
    success: bool
    message: str
    data: Optional[Any] = None


# ============ 仿真结果存储 ============

# 内存存储（生产环境应使用数据库）
simulation_results: Dict[str, SimulationResult] = {}
running_simulations: Dict[str, bool] = {}


# ============ 辅助函数 ============

def to_calendar_time(minutes: float, work_hours_per_day: int) -> str:
    """将仿真分钟转换为 Day-Hour 格式"""
    minutes_per_day = work_hours_per_day * 60
    day = int(minutes // minutes_per_day) + 1
    hour_in_day = (minutes % minutes_per_day) / 60
    return f"D{day} {hour_in_day:.1f}h"


def generate_mock_simulation_result(
    sim_id: str,
    config: GlobalConfig,
    process: ProcessDefinition
) -> SimulationResult:
    """
    生成模拟仿真结果（用于测试）
    实际应用中应使用SimPy仿真引擎
    """
    import random
    
    # 计算基本参数
    total_std_time = sum(node.std_duration for node in process.nodes)
    sim_time = config.sim_time_minutes
    
    # 估算产能
    estimated_engines = max(1, int(sim_time / (total_std_time * 1.2)))
    engines_completed = min(estimated_engines, config.target_output + 1)
    
    # 生成甘特图事件
    gantt_events = []
    current_time = 0
    
    for engine_id in range(1, engines_completed + 1):
        completed_nodes = set()
        node_map = {n.step_id: n for n in process.nodes}
        
        while len(completed_nodes) < len(process.nodes):
            # 找到可执行的节点
            for node in process.nodes:
                if node.step_id in completed_nodes:
                    continue
                
                # 检查前置依赖
                preds = [p.strip() for p in node.predecessors.split(';') if p.strip()]
                if all(p in completed_nodes for p in preds):
                    # 计算实际耗时（加入方差）
                    variance = node.time_variance
                    actual_duration = max(1, node.std_duration + random.gauss(0, variance))
                    
                    # 创建事件
                    event = GanttEvent(
                        engine_id=engine_id,
                        step_id=node.step_id,
                        task_name=node.task_name,
                        op_type=node.op_type.value,
                        start_time=current_time,
                        end_time=current_time + actual_duration,
                        event_type="NORMAL",
                        worker_ids=[f"Worker_{i:02d}" for i in range(1, node.required_workers + 1)],
                        equipment_used=node.required_tools[:1] if node.required_tools else [],
                        rework_count=0
                    )
                    gantt_events.append(event)
                    
                    # 处理返工
                    if node.op_type == OpType.M and random.random() < node.rework_prob:
                        rework_event = GanttEvent(
                            engine_id=engine_id,
                            step_id=node.step_id,
                            task_name=f"{node.task_name}(返工)",
                            op_type=node.op_type.value,
                            start_time=current_time + actual_duration,
                            end_time=current_time + actual_duration * 2,
                            event_type="REWORK",
                            worker_ids=event.worker_ids,
                            equipment_used=event.equipment_used,
                            rework_count=1
                        )
                        gantt_events.append(rework_event)
                        current_time += actual_duration
                    
                    current_time += actual_duration
                    completed_nodes.add(node.step_id)
                    break
    
    # 计算统计数据
    total_work_time = sum(e.end_time - e.start_time for e in gantt_events if e.event_type == "NORMAL")
    total_rework_time = sum(e.end_time - e.start_time for e in gantt_events if e.event_type == "REWORK")
    
    # 工人统计
    worker_stats = []
    for i in range(1, config.num_workers + 1):
        worker_id = f"Worker_{i:02d}"
        worker_events = [e for e in gantt_events if worker_id in e.worker_ids]
        work_time = sum(e.end_time - e.start_time for e in worker_events)
        rest_time = work_time * 0.1  # 假设10%休息时间
        
        worker_stats.append(ResourceUtilization(
            resource_id=worker_id,
            resource_type="WORKER",
            total_time=sim_time,
            work_time=work_time,
            rest_time=rest_time,
            idle_time=sim_time - work_time - rest_time,
            utilization_rate=work_time / sim_time if sim_time > 0 else 0,
            tasks_completed=len(worker_events)
        ))
    
    # 设备统计
    equipment_stats = []
    for equip_name, capacity in config.critical_equipment.items():
        equip_events = [e for e in gantt_events if equip_name in e.equipment_used]
        work_time = sum(e.end_time - e.start_time for e in equip_events)
        
        equipment_stats.append(ResourceUtilization(
            resource_id=equip_name,
            resource_type="EQUIPMENT",
            total_time=sim_time * capacity,
            work_time=work_time,
            idle_time=sim_time * capacity - work_time,
            utilization_rate=work_time / (sim_time * capacity) if sim_time > 0 else 0,
            tasks_completed=len(equip_events)
        ))
    
    # 质量统计
    total_inspections = len([e for e in gantt_events if e.op_type == "M"])
    total_reworks = len([e for e in gantt_events if e.event_type == "REWORK"])
    
    quality_stats = QualityStats(
        total_inspections=total_inspections,
        total_reworks=total_reworks,
        first_pass_rate=(total_inspections - total_reworks) / total_inspections if total_inspections > 0 else 1.0,
        rework_time_total=total_rework_time
    )
    
    # 时间映射
    time_mapping = {
        "minutes_per_day": config.work_hours_per_day * 60,
        "total_days": config.work_days_per_month,
        "total_minutes": sim_time,
        "work_hours_per_day": config.work_hours_per_day
    }
    
    return SimulationResult(
        sim_id=sim_id,
        status=SimulationStatus.COMPLETED,
        config=config,
        sim_duration=current_time,
        engines_completed=engines_completed,
        target_achievement_rate=engines_completed / config.target_output if config.target_output > 0 else 0,
        avg_cycle_time=current_time / engines_completed if engines_completed > 0 else 0,
        worker_stats=worker_stats,
        equipment_stats=equipment_stats,
        quality_stats=quality_stats,
        gantt_events=gantt_events,
        time_mapping=time_mapping,
        created_at=datetime.now().isoformat(),
        completed_at=datetime.now().isoformat()
    )


# ============ API端点 ============

@router.post("/run", response_model=APIResponse)
async def run_simulation(request: SimulationRequest, background_tasks: BackgroundTasks):
    """
    运行仿真
    
    接收配置和工艺流程定义，启动仿真并返回结果
    同时运行无休息对比仿真
    
    请求体:
    - config: 全局配置（排班、设备、休息规则等）
    - process: 工艺流程定义（节点列表）
    
    响应:
    - success: 是否成功
    - message: 结果消息
    - data: 仿真结果（SimulationResult）包含人因对比数据
    """
    try:
        # 验证输入
        if not request.process.nodes:
            return APIResponse(
                success=False,
                message="工艺流程不能为空"
            )
        
        # 导入真实仿真引擎
        from app.core.simulation_engine import SimulationEngine, SimulationEngineNoRest
        from app.models.process_model import ProcessDefinition as CoreProcess, ProcessNode as CoreNode
        from app.models.enums import OpType as CoreOpType
        
        # 转换配置
        core_config = request.config
        core_config.random_seed = 42
        
        # 转换工艺流程
        core_nodes = []
        for node in request.process.nodes:
            core_nodes.append(CoreNode(
                step_id=node.step_id,
                task_name=node.task_name,
                op_type=CoreOpType(node.op_type.value),
                predecessors=node.predecessors,
                std_duration=node.std_duration,
                time_variance=node.time_variance,
                work_load_score=node.work_load_score,
                rework_prob=node.rework_prob,
                required_workers=node.required_workers,
                required_tools=node.required_tools,
                station=node.station or "ST01"
            ))
        
        core_process = CoreProcess(
            name=request.process.name,
            description=request.process.description,
            nodes=core_nodes
        )
        
        # 运行主仿真（考虑人因）
        engine = SimulationEngine(core_config, core_process)
        result = engine.run()
        
        # 运行对比仿真（不考虑人因）
        no_rest_engine = SimulationEngineNoRest(core_config, core_process)
        no_rest_result = no_rest_engine.run()
        
        # 转换结果为API格式
        api_gantt_events = []
        for evt in result.gantt_events:
            api_gantt_events.append(GanttEvent(
                engine_id=evt.engine_id,
                step_id=evt.step_id,
                task_name=evt.task_name,
                op_type=evt.op_type,
                start_time=evt.start_time,
                end_time=evt.end_time,
                event_type=evt.event_type.value,
                worker_ids=evt.worker_ids,
                equipment_used=evt.equipment_used,
                rework_count=evt.rework_count
            ))
        
        api_worker_stats = []
        for w in result.worker_stats:
            api_worker_stats.append(ResourceUtilization(
                resource_id=w.resource_id,
                resource_type=w.resource_type,
                total_time=w.total_time,
                work_time=w.work_time,
                rest_time=w.rest_time,
                idle_time=w.idle_time,
                utilization_rate=w.utilization_rate,
                tasks_completed=w.tasks_completed
            ))
        
        api_equipment_stats = []
        for e in result.equipment_stats:
            api_equipment_stats.append(ResourceUtilization(
                resource_id=e.resource_id,
                resource_type=e.resource_type,
                total_time=e.total_time,
                work_time=e.work_time,
                rest_time=e.rest_time,
                idle_time=e.idle_time,
                utilization_rate=e.utilization_rate,
                tasks_completed=e.tasks_completed
            ))
        
        # 构建响应数据
        response_data = {
            "sim_id": result.sim_id,
            "status": result.status.value,
            "config": request.config.model_dump(),
            "sim_duration": result.sim_duration,
            "engines_completed": result.engines_completed,
            "target_achievement_rate": result.target_achievement_rate,
            "avg_cycle_time": result.avg_cycle_time,
            "worker_stats": [w.model_dump() for w in api_worker_stats],
            "equipment_stats": [e.model_dump() for e in api_equipment_stats],
            "quality_stats": {
                "total_inspections": result.quality_stats.total_inspections,
                "total_reworks": result.quality_stats.total_reworks,
                "first_pass_rate": result.quality_stats.first_pass_rate,
                "rework_time_total": result.quality_stats.rework_time_total
            },
            "human_factors_stats": result.human_factors_stats.to_dict(),
            "gantt_events": [e.model_dump() for e in api_gantt_events],
            "time_mapping": result.time_mapping,
            "created_at": result.created_at,
            "completed_at": result.completed_at,
            # 人因对比数据
            "no_rest_comparison": no_rest_result,
            # 添加工人疲劳度历史数据
            "worker_fatigue_data": [
                {
                    "worker_id": w.resource_id,
                    "fatigue_level": w.fatigue_level,
                    "high_intensity_count": w.high_intensity_count,
                    "fatigue_history": w.fatigue_history,
                    "total_rest_time": w.rest_time
                }
                for w in result.worker_stats
            ]
        }
        
        # 存储结果到全局字典，供后续API（如瓶颈分析）使用
        api_result = SimulationResult(
            sim_id=result.sim_id,
            status=SimulationStatus.COMPLETED,
            config=request.config,
            sim_duration=result.sim_duration,
            engines_completed=result.engines_completed,
            target_achievement_rate=result.target_achievement_rate,
            avg_cycle_time=result.avg_cycle_time,
            worker_stats=api_worker_stats,
            equipment_stats=api_equipment_stats,
            quality_stats=QualityStats(
                total_inspections=result.quality_stats.total_inspections,
                total_reworks=result.quality_stats.total_reworks,
                first_pass_rate=result.quality_stats.first_pass_rate,
                rework_time_total=result.quality_stats.rework_time_total
            ),
            gantt_events=api_gantt_events,
            time_mapping=result.time_mapping,
            created_at=result.created_at,
            completed_at=result.completed_at
        )
        simulation_results[result.sim_id] = api_result
        
        return APIResponse(
            success=True,
            message=f"仿真完成，产出 {result.engines_completed} 台发动机",
            data=response_data
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return APIResponse(
            success=False,
            message=f"仿真失败: {str(e)}"
        )


@router.get("/test", response_model=APIResponse)
async def run_test_simulation():
    """
    运行测试仿真
    
    使用默认配置和示例工艺流程运行一次快速仿真
    用于验证系统功能
    """
    # 默认配置
    config = GlobalConfig()
    
    # 示例工艺流程
    process = ProcessDefinition(
        name="测试流程",
        nodes=[
            ProcessNode(step_id="T001", task_name="取零件", op_type=OpType.H, std_duration=5),
            ProcessNode(step_id="T002", task_name="装配", op_type=OpType.A, predecessors="T001", std_duration=15),
            ProcessNode(step_id="T003", task_name="检测", op_type=OpType.M, predecessors="T002", std_duration=10, rework_prob=0.1),
            ProcessNode(step_id="T004", task_name="记录", op_type=OpType.D, predecessors="T003", std_duration=5),
        ]
    )
    
    sim_id = str(uuid.uuid4())
    result = generate_mock_simulation_result(sim_id, config, process)
    simulation_results[sim_id] = result
    
    return APIResponse(
        success=True,
        message=f"测试仿真完成，产出 {result.engines_completed} 台",
        data=result.model_dump()
    )


@router.get("/status/{sim_id}", response_model=APIResponse)
async def get_simulation_status(sim_id: str):
    """
    获取仿真状态
    
    查询指定仿真任务的当前状态和进度
    """
    if sim_id not in simulation_results:
        return APIResponse(
            success=False,
            message=f"仿真 {sim_id} 不存在"
        )
    
    result = simulation_results[sim_id]
    is_running = running_simulations.get(sim_id, False)
    
    return APIResponse(
        success=True,
        message=f"仿真状态: {result.status.value}",
        data={
            "sim_id": sim_id,
            "status": result.status.value,
            "is_running": is_running,
            "engines_completed": result.engines_completed,
            "created_at": result.created_at,
            "completed_at": result.completed_at
        }
    )


@router.post("/stop/{sim_id}", response_model=APIResponse)
async def stop_simulation(sim_id: str):
    """
    停止仿真
    
    中止正在运行的仿真任务
    """
    if sim_id not in simulation_results:
        return APIResponse(
            success=False,
            message=f"仿真 {sim_id} 不存在"
        )
    
    if not running_simulations.get(sim_id, False):
        return APIResponse(
            success=False,
            message="仿真未在运行中"
        )
    
    # 标记停止
    running_simulations[sim_id] = False
    result = simulation_results[sim_id]
    result.status = SimulationStatus.CANCELLED
    result.completed_at = datetime.now().isoformat()
    
    return APIResponse(
        success=True,
        message="仿真已停止"
    )


@router.get("/list", response_model=APIResponse)
async def list_simulations():
    """
    列出所有仿真记录
    
    返回所有仿真任务的概要信息
    """
    summaries = []
    for sim_id, result in simulation_results.items():
        summaries.append({
            "sim_id": sim_id,
            "status": result.status.value,
            "engines_completed": result.engines_completed,
            "target_achievement_rate": result.target_achievement_rate,
            "created_at": result.created_at,
            "completed_at": result.completed_at
        })
    
    # 按创建时间倒序
    summaries.sort(key=lambda x: x["created_at"], reverse=True)
    
    return APIResponse(
        success=True,
        message=f"共 {len(summaries)} 条仿真记录",
        data=summaries
    )


@router.delete("/clear", response_model=APIResponse)
async def clear_simulations():
    """
    清除所有仿真记录
    
    删除所有历史仿真数据（谨慎使用）
    """
    count = len(simulation_results)
    simulation_results.clear()
    running_simulations.clear()
    
    return APIResponse(
        success=True,
        message=f"已清除 {count} 条仿真记录"
    )
