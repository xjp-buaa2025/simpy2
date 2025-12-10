"""
仿真结果模型
定义仿真运行后的结果数据结构

模型:
- ResourceUtilization: 资源利用率统计
- QualityStats: 质量统计
- SimulationResult: 完整仿真结果
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from app.models.enums import SimulationStatus
from app.models.config_model import GlobalConfig
from app.models.gantt_model import GanttEvent


@dataclass
class ResourceUtilization:
    """
    资源利用率统计
    
    记录单个资源（工人或设备）的使用情况
    
    Attributes:
        resource_id: 资源ID
        resource_type: 资源类型（WORKER/EQUIPMENT）
        total_time: 总时间（分钟）
        work_time: 工作时间（分钟）
        rest_time: 休息时间（分钟）
        idle_time: 空闲时间（分钟）
        utilization_rate: 利用率（0-1）
        tasks_completed: 完成任务数
        fatigue_level: 最终疲劳度（0-100）
        high_intensity_count: 高强度任务暴露次数
        fatigue_history: 疲劳度历史 [(时间, 疲劳度), ...]
    """
    
    resource_id: str
    resource_type: str
    total_time: float
    work_time: float
    rest_time: float = 0
    idle_time: float = 0
    utilization_rate: float = 0
    tasks_completed: int = 0
    fatigue_level: float = 0
    high_intensity_count: int = 0
    fatigue_history: list = field(default_factory=list)
    
    def __post_init__(self):
        """计算利用率和空闲时间"""
        if self.total_time > 0:
            if self.utilization_rate == 0:
                self.utilization_rate = self.work_time / self.total_time
            if self.idle_time == 0:
                self.idle_time = self.total_time - self.work_time - self.rest_time
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "total_time": self.total_time,
            "work_time": self.work_time,
            "rest_time": self.rest_time,
            "idle_time": self.idle_time,
            "utilization_rate": self.utilization_rate,
            "tasks_completed": self.tasks_completed,
            "fatigue_level": self.fatigue_level,
            "high_intensity_count": self.high_intensity_count,
            "fatigue_history": self.fatigue_history
        }
    
    @property
    def work_time_hours(self) -> float:
        """工作时间（小时）"""
        return self.work_time / 60
    
    @property
    def rest_time_hours(self) -> float:
        """休息时间（小时）"""
        return self.rest_time / 60
    
    @property
    def idle_time_hours(self) -> float:
        """空闲时间（小时）"""
        return self.idle_time / 60
    
    @property
    def utilization_percent(self) -> float:
        """利用率百分比"""
        return self.utilization_rate * 100


@dataclass
class HumanFactorsStats:
    """
    人因工程统计
    
    记录人因相关的汇总数据
    
    Attributes:
        total_rest_time: 所有工人总休息时间（分钟）
        avg_fatigue_level: 平均最终疲劳度
        max_fatigue_level: 最高疲劳度
        total_high_intensity_exposure: 高强度任务总暴露次数
        rest_events_count: 休息事件总次数
    """
    
    total_rest_time: float = 0
    avg_fatigue_level: float = 0
    max_fatigue_level: float = 0
    total_high_intensity_exposure: int = 0
    rest_events_count: int = 0
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_rest_time": self.total_rest_time,
            "total_rest_time_hours": self.total_rest_time / 60,
            "avg_fatigue_level": self.avg_fatigue_level,
            "max_fatigue_level": self.max_fatigue_level,
            "total_high_intensity_exposure": self.total_high_intensity_exposure,
            "rest_events_count": self.rest_events_count
        }


@dataclass
class QualityStats:
    """
    质量统计
    
    记录仿真中的质量相关数据
    
    Attributes:
        total_inspections: 总检测次数
        total_reworks: 总返工次数
        first_pass_rate: 一次通过率
        rework_time_total: 返工总耗时（分钟）
    """
    
    total_inspections: int = 0
    total_reworks: int = 0
    first_pass_rate: float = 1.0
    rework_time_total: float = 0
    
    def __post_init__(self):
        """计算一次通过率"""
        if self.total_inspections > 0 and self.first_pass_rate == 1.0:
            passed = self.total_inspections - self.total_reworks
            self.first_pass_rate = max(0, passed / self.total_inspections)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_inspections": self.total_inspections,
            "total_reworks": self.total_reworks,
            "first_pass_rate": self.first_pass_rate,
            "first_pass_percent": self.first_pass_rate * 100,
            "rework_time_total": self.rework_time_total,
            "rework_time_hours": self.rework_time_total / 60
        }
    
    @property
    def rework_rate(self) -> float:
        """返工率"""
        if self.total_inspections == 0:
            return 0
        return self.total_reworks / self.total_inspections
    
    @property
    def rework_time_hours(self) -> float:
        """返工总耗时（小时）"""
        return self.rework_time_total / 60


@dataclass
class SimulationResult:
    """
    仿真结果
    
    包含仿真运行后的所有结果数据
    
    Attributes:
        sim_id: 仿真ID
        status: 仿真状态
        config: 使用的配置
        sim_duration: 实际仿真时长（分钟）
        engines_completed: 完成发动机数量
        target_achievement_rate: 计划达成率
        avg_cycle_time: 平均单台周期时间（分钟）
        worker_stats: 工人统计列表
        equipment_stats: 设备统计列表
        quality_stats: 质量统计
        human_factors_stats: 人因工程统计
        gantt_events: 甘特图事件列表
        time_mapping: 时间映射元数据
        created_at: 创建时间
        completed_at: 完成时间
        no_rest_comparison: 不考虑人因的对比结果
    """
    
    sim_id: str = ""
    status: SimulationStatus = SimulationStatus.COMPLETED
    config: Optional[GlobalConfig] = None
    sim_duration: float = 0
    engines_completed: int = 0
    target_achievement_rate: float = 0
    avg_cycle_time: float = 0
    worker_stats: List[ResourceUtilization] = field(default_factory=list)
    equipment_stats: List[ResourceUtilization] = field(default_factory=list)
    quality_stats: QualityStats = field(default_factory=QualityStats)
    human_factors_stats: HumanFactorsStats = field(default_factory=HumanFactorsStats)
    gantt_events: List[GanttEvent] = field(default_factory=list)
    time_mapping: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    completed_at: str = ""
    no_rest_comparison: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """计算达成率"""
        if self.config and self.target_achievement_rate == 0:
            if self.config.target_output > 0:
                self.target_achievement_rate = self.engines_completed / self.config.target_output
    
    @property
    def sim_duration_hours(self) -> float:
        """仿真时长（小时）"""
        return self.sim_duration / 60
    
    @property
    def avg_cycle_time_hours(self) -> float:
        """平均周期时间（小时）"""
        return self.avg_cycle_time / 60
    
    @property
    def target_achievement_percent(self) -> float:
        """达成率百分比"""
        return self.target_achievement_rate * 100
    
    @property
    def avg_worker_utilization(self) -> float:
        """平均工人利用率"""
        if not self.worker_stats:
            return 0
        return sum(w.utilization_rate for w in self.worker_stats) / len(self.worker_stats)
    
    @property
    def avg_equipment_utilization(self) -> float:
        """平均设备利用率"""
        if not self.equipment_stats:
            return 0
        return sum(e.utilization_rate for e in self.equipment_stats) / len(self.equipment_stats)
    
    def get_worker_stat(self, worker_id: str) -> Optional[ResourceUtilization]:
        """获取指定工人的统计数据"""
        for stat in self.worker_stats:
            if stat.resource_id == worker_id:
                return stat
        return None
    
    def get_equipment_stat(self, equip_name: str) -> Optional[ResourceUtilization]:
        """获取指定设备的统计数据"""
        for stat in self.equipment_stats:
            if stat.resource_id == equip_name:
                return stat
        return None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "sim_id": self.sim_id,
            "status": self.status.value if isinstance(self.status, SimulationStatus) else self.status,
            "config": self.config.model_dump() if self.config else None,
            "sim_duration": self.sim_duration,
            "sim_duration_hours": self.sim_duration_hours,
            "engines_completed": self.engines_completed,
            "target_achievement_rate": self.target_achievement_rate,
            "target_achievement_percent": self.target_achievement_percent,
            "avg_cycle_time": self.avg_cycle_time,
            "avg_cycle_time_hours": self.avg_cycle_time_hours,
            "avg_worker_utilization": self.avg_worker_utilization,
            "avg_equipment_utilization": self.avg_equipment_utilization,
            "worker_stats": [w.to_dict() for w in self.worker_stats],
            "equipment_stats": [e.to_dict() for e in self.equipment_stats],
            "quality_stats": self.quality_stats.to_dict(),
            "human_factors_stats": self.human_factors_stats.to_dict(),
            "gantt_events_count": len(self.gantt_events),
            "time_mapping": self.time_mapping,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "no_rest_comparison": self.no_rest_comparison
        }
    
    def get_kpi_summary(self) -> dict:
        """获取KPI摘要"""
        return {
            "production": {
                "engines_completed": self.engines_completed,
                "target_output": self.config.target_output if self.config else 0,
                "achievement_rate": f"{self.target_achievement_percent:.1f}%"
            },
            "time": {
                "total_sim_time_hours": self.sim_duration_hours,
                "avg_cycle_time_hours": self.avg_cycle_time_hours
            },
            "efficiency": {
                "avg_worker_utilization": f"{self.avg_worker_utilization * 100:.1f}%",
                "avg_equipment_utilization": f"{self.avg_equipment_utilization * 100:.1f}%"
            },
            "quality": {
                "first_pass_rate": f"{self.quality_stats.first_pass_rate * 100:.1f}%",
                "total_reworks": self.quality_stats.total_reworks
            }
        }


# Pydantic版本（用于API）
class ResourceUtilizationModel(BaseModel):
    """资源利用率模型（Pydantic）"""
    resource_id: str = Field(description="资源ID")
    resource_type: str = Field(description="资源类型")
    total_time: float = Field(description="总时间")
    work_time: float = Field(description="工作时间")
    rest_time: float = Field(default=0, description="休息时间")
    idle_time: float = Field(default=0, description="空闲时间")
    utilization_rate: float = Field(description="利用率")
    tasks_completed: int = Field(default=0, description="完成任务数")


class QualityStatsModel(BaseModel):
    """质量统计模型（Pydantic）"""
    total_inspections: int = Field(default=0, description="总检测次数")
    total_reworks: int = Field(default=0, description="总返工次数")
    first_pass_rate: float = Field(default=1.0, description="一次通过率")
    rework_time_total: float = Field(default=0, description="返工总耗时")


class SimulationResultModel(BaseModel):
    """仿真结果模型（Pydantic）"""
    sim_id: str = Field(description="仿真ID")
    status: str = Field(description="仿真状态")
    sim_duration: float = Field(description="仿真时长")
    engines_completed: int = Field(description="完成发动机数")
    target_achievement_rate: float = Field(description="计划达成率")
    avg_cycle_time: float = Field(description="平均周期时间")
    worker_stats: List[ResourceUtilizationModel] = Field(default=[], description="工人统计")
    equipment_stats: List[ResourceUtilizationModel] = Field(default=[], description="设备统计")
    quality_stats: QualityStatsModel = Field(description="质量统计")
    created_at: str = Field(description="创建时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
