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
from app.models.enums import OpType
from app.core.run_progress import run_progress
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
    area_id: str = ""
    workstation_id: str = ""
    x: float = 0
    y: float = 0


class ProcessDefinition(BaseModel):
    """工艺流程定义"""
    name: str = "未命名流程"
    description: str = ""
    nodes: List[ProcessNode] = []
    station_catalog: List[Dict[str, str]] = Field(default_factory=list)


class SimulationRequest(BaseModel):
    """仿真请求"""
    config: GlobalConfig
    process: ProcessDefinition
    publish_to_clients: bool = True
    progress_id: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{8,80}$")


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
    area_id: str = ""
    workstation_id: str = ""
    wait_reason: str = ""
    is_complete: bool = True
    planned_end_time: Optional[float] = None
    wait_resource_ids: List[str] = Field(default_factory=list)


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
    target_achievement_rate: Optional[float] = Field(default=None, description="已停用")
    avg_cycle_time: float = Field(description="平均单台周期时间（分钟）")
    worker_stats: List[ResourceUtilization] = Field(default=[], description="工人统计")
    equipment_stats: List[ResourceUtilization] = Field(default=[], description="设备统计")
    quality_stats: QualityStats = Field(description="质量统计")
    gantt_events: List[GanttEvent] = Field(default=[], description="甘特图事件列表")
    time_mapping: Dict[str, Any] = Field(default={}, description="时间映射元数据")
    created_at: str = Field(description="创建时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
    area_stats: List[Dict[str, Any]] = Field(default_factory=list)
    area_completion_events: List[Dict[str, Any]] = Field(default_factory=list)
    engine_completion_events: List[Dict[str, Any]] = Field(default_factory=list)
    resource_snapshot: Dict[str, Any] = Field(default_factory=dict)
    evaluation_context: Dict[str, Any] = Field(default_factory=dict)
    input_snapshot: Dict[str, Any] = Field(default_factory=dict)
    station_progress: Optional[Dict[str, Any]] = Field(default=None, description="按工位和发动机保存的放行进度及完成时间线")


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
    """Run the same production rules for the test endpoint, without publishing."""
    from app.core.simulation_engine import SimulationEngine
    from app.models.process_model import ProcessDefinition as CoreProcess
    core_process = CoreProcess.model_validate(process.model_dump())
    result = SimulationEngine(config.model_copy(deep=True), core_process).run()
    data = result.to_dict()
    data["sim_id"] = sim_id
    if data.get("station_progress") is not None:
        data["station_progress"]["sim_id"] = sim_id
    data["gantt_events"] = [e.to_dict() for e in result.gantt_events]
    return SimulationResult.model_validate(data)


@router.get("/capacity/catalog")
def capacity_catalog():
    from app.core.area_capacity import verified_catalog
    return {"success": True, "message": "已核验实体工位目录", "data": verified_catalog()}


@router.post("/capacity/validate", response_model=APIResponse)
def validate_capacity(request: SimulationRequest):
    try:
        if request.config.capacity_model.enabled:
            from app.core.area_capacity import prepare_model, expansion_packages
            from app.models.process_model import ProcessDefinition as CoreProcess
            config, process, _ = prepare_model(request.config, CoreProcess.model_validate(request.process.model_dump()))
            return APIResponse(success=True, message="方案验证通过", data={"expansions": expansion_packages(config, process),
                "effective_station_slots": sum(config.capacity_model.workstations[s].capacity * config.capacity_model.areas[config.capacity_model.workstations[s].area_id].resource_sets for s in {n.workstation_id for n in process.nodes})})
        return APIResponse(success=True, message="方案验证通过")
    except ValueError as error:
        return APIResponse(success=False, message=str(error))

def _unity_snapshot(filename: str):
    from pathlib import Path
    from fastapi.responses import Response
    path = Path(__file__).resolve().parents[2] / "results" / "unity_validation" / filename
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="请先完成一次网页仿真以生成 Unity 回放")
    return Response(content, media_type="application/json", headers={"Cache-Control": "no-store"})


@router.get("/unity/replay.json")
def unity_replay():
    return _unity_snapshot("replay.json")


@router.get("/unity/station-progress.json")
def unity_station_progress():
    """Latest published station timeline; independent of the legacy replay."""
    try:
        return _unity_snapshot("station_progress.json")
    except HTTPException as error:
        if error.status_code == 404:
            raise HTTPException(status_code=404, detail="请先运行并发布一次仿真以生成工位进度数据") from error
        raise


@router.get("/unity/sync_status.json")
async def unity_sync_status():
    from pathlib import Path
    from app.core.factory_layout import load_json
    from app.api.factory_layout import store
    path = Path(__file__).resolve().parents[2] / "results/unity_validation/sync_status.json"
    data = load_json(path) if path.exists() else {"success": False}
    try:
        data.update(layout_revision=store.current['revision'], catalog_version=store.current['catalog_version'])
    except (OSError, ValueError):
        data['layout_revision'] = -1
    return data


@router.get("/progress/{progress_id}", response_model=APIResponse)
def simulation_progress(progress_id: str):
    snapshot = run_progress.snapshot(progress_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="尚未开始或进度已过期")
    return APIResponse(success=True, message="仿真进度", data=snapshot)


@router.post("/run", response_model=APIResponse)
def run_simulation(request: SimulationRequest, background_tasks: BackgroundTasks):
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
    # SimPy runs synchronously. A sync endpoint lets FastAPI run it in a worker
    # thread while PC/VR replay and clock requests remain responsive.
    progress_id = None
    try:
        # 验证输入
        if not request.process.nodes:
            return APIResponse(
                success=False,
                message="工艺流程不能为空"
            )

        if request.progress_id:
            run_progress.start(request.progress_id)
            progress_id = request.progress_id

        # 导入真实仿真引擎
        from app.core.simulation_engine import SimulationEngine, SimulationEngineNoRest
        from app.models.process_model import ProcessDefinition as CoreProcess, ProcessNode as CoreNode
        from app.models.enums import OpType as CoreOpType

        # 转换配置
        core_config = request.config.model_copy(deep=True)
        if core_config.random_seed is None:
            core_config.random_seed = 42
        if core_config.evaluation.mode == "capacity" and not core_config.capacity_model.enabled:
            run_progress.finish(progress_id, False, "能力评估需要先启用工区资源模型")
            return APIResponse(success=False, message="能力评估需要先启用工区资源模型")

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
                station=node.station or "ST01",
                area_id=node.area_id,
                workstation_id=node.workstation_id,
                x=node.x, y=node.y
            ))

        core_process = CoreProcess(
            name=request.process.name,
            description=request.process.description,
            nodes=core_nodes,
            station_catalog=request.process.station_catalog
        )

        # 运行主仿真（考虑人因）
        if core_config.capacity_model.enabled:
            from app.core.area_capacity import AreaSimulationEngine
            engine = AreaSimulationEngine(core_config, core_process)
        else:
            engine = SimulationEngine(core_config.model_copy(deep=True), core_process.model_copy(deep=True))
        from app.core.dag_scheduler import DAGScheduler
        valid, validation_message = DAGScheduler(core_process).validate()
        if not valid:
            run_progress.finish(progress_id, False, validation_message)
            return APIResponse(success=False, message=validation_message)
        if progress_id:
            engine.progress_callback = lambda fraction, minute, total: run_progress.update(
                progress_id, 4 + fraction * 44, "正在计算主仿真", "main",
                simulation_minute=minute, total_minutes=total)
        result = engine.run()
        if result.status.value != "completed":
            run_progress.finish(progress_id, False, "仿真未成功完成，请检查工艺流程")
            return APIResponse(success=False, message="仿真未成功完成，请检查工艺流程")

        # 运行对比仿真（不考虑人因）
        if core_config.capacity_model.enabled:
            no_rest_engine = AreaSimulationEngine(core_config, core_process, no_rest=True)
        else:
            no_rest_engine = SimulationEngineNoRest(core_config.model_copy(deep=True), core_process.model_copy(deep=True))
        run_progress.update(progress_id, 50, "正在计算人因对比", "comparison", simulation_minute=0)
        if progress_id:
            no_rest_engine.progress_callback = lambda fraction, minute, total: run_progress.update(
                progress_id, 50 + fraction * 38, "正在计算人因对比", "comparison",
                simulation_minute=minute, total_minutes=total)
        comparison_result = no_rest_engine.run()
        no_rest_result = comparison_result.to_dict() if core_config.capacity_model.enabled else comparison_result
        run_progress.update(progress_id, 90, "正在整理仿真结果", "results")

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
                rework_count=evt.rework_count,
                area_id=evt.area_id, workstation_id=evt.workstation_id,
                wait_reason=evt.wait_reason, is_complete=evt.is_complete,
                planned_end_time=evt.planned_end_time,
                wait_resource_ids=evt.wait_resource_ids
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
            "config": result.config.model_dump(),
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
            "area_stats": result.area_stats,
            "area_completion_events": result.area_completion_events,
            "engine_completion_events": result.engine_completion_events,
            "resource_snapshot": result.resource_snapshot,
            "evaluation_context": result.evaluation_context,
            "input_snapshot": {"config": result.config.model_dump() if core_config.capacity_model.enabled else core_config.model_dump(),
                               "process": engine.process.model_dump() if core_config.capacity_model.enabled else core_process.model_dump()},
            "station_progress": result.station_progress,
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
            completed_at=result.completed_at,
            area_stats=result.area_stats, area_completion_events=result.area_completion_events,
            engine_completion_events=result.engine_completion_events,
            resource_snapshot=result.resource_snapshot, evaluation_context=result.evaluation_context,
            input_snapshot=response_data["input_snapshot"],
            station_progress=result.station_progress
        )
        simulation_results[result.sim_id] = api_result
        run_progress.update(progress_id, 96, "正在同步仿真结果" if request.publish_to_clients else "正在完成结果处理", "results")
        if request.publish_to_clients:
            # Publish the same run the webpage receives, including its work calendar.
            from tools.unity_validation import publication_lock
            with publication_lock:
                try:
                    from tools.unity_validation import publish_result
                    response_data["unity_sync"] = publish_result(response_data, engine.process if core_config.capacity_model.enabled else request.process)
                except Exception as sync_error:
                    response_data["unity_sync"] = {"success": False, "message": str(sync_error)}
                    import logging
                    logging.getLogger(__name__).warning("Unity replay publication failed: %s", sync_error)
                    try:
                        from tools.unity_validation import OUTPUT, atomic_write, supports_legacy_replay
                        import json
                        OUTPUT.mkdir(parents=True, exist_ok=True)
                        publication_process = engine.process if core_config.capacity_model.enabled else request.process
                        status_file = "sync_status.json" if supports_legacy_replay(publication_process) else "station_progress_status.json"
                        atomic_write(OUTPUT / status_file, json.dumps(
                            {"success": False, "sim_id": result.sim_id, "message": str(sync_error)},
                            ensure_ascii=False).encode("utf-8"))
                    except Exception:
                        logging.getLogger(__name__).exception("Could not record Unity synchronization failure")

        else:
            response_data["unity_sync"] = {"success": True, "skipped": True}

        run_progress.finish(progress_id, True)
        return APIResponse(
            success=True,
            message=f"仿真完成，产出 {result.engines_completed} 台发动机",
            data=response_data
        )

    except Exception as e:
        run_progress.finish(progress_id, False, str(e))
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
