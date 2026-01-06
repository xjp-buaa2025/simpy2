"""
全局配置模型
定义仿真系统的全局配置参数

配置项:
- 排班配置（工时/天数/工人数）
- 关键设备配置
- 休息规则参数
- 生产目标
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field, computed_field


class GlobalConfig(BaseModel):
    """
    全局配置模型
    
    包含仿真系统的所有可配置参数
    
    Attributes:
        work_hours_per_day: 每日工作小时数（1-24）
        work_days_per_month: 每月工作天数（1-31）
        num_workers: 工人数量（≥1）
        critical_equipment: 关键设备配置（设备名 -> 数量）
        rest_time_threshold: 连续工作触发休息阈值（分钟）
        rest_duration_time: 时间触发休息时长（分钟）
        rest_load_threshold: 负荷触发休息阈值（REBA 1-10）
        rest_duration_load: 负荷触发休息时长（分钟）
        target_output: 目标月产量（台）
    """
    
    # 排班配置
    work_hours_per_day: int = Field(
        default=8,
        ge=1,
        le=24,
        description="每日工作小时数"
    )
    work_days_per_month: int = Field(
        default=22,
        ge=1,
        le=31,
        description="每月工作天数"
    )
    num_workers: int = Field(
        default=6,
        ge=1,
        description="工人数量"
    )
    
    # 关键设备配置（前端自定义）
    critical_equipment: Dict[str, int] = Field(
        default={
            "动平衡机": 2,
            "试车台": 1,
            "装配台": 3,
            "检测台": 2
        },
        description="关键设备及数量"
    )
    
    # 休息规则参数
    # 规则A: 连续工作时间 ≥ 阈值 → 强制休息
    rest_time_threshold: float = Field(
        default=50.0,
        ge=0,
        description="连续工作触发休息阈值（分钟）"
    )
    rest_duration_time: float = Field(
        default=5.0,
        ge=0,
        description="时间触发休息时长（分钟）"
    )
    
    # 规则B: 任务负荷 > 阈值 → 任务后休息
    rest_load_threshold: int = Field(
        default=7,
        ge=1,
        le=10,
        description="负荷触发休息阈值（REBA 1-10）"
    )
    rest_duration_load: float = Field(
        default=3.0,
        ge=0,
        description="负荷触发休息时长（分钟）"
    )
    
    # 生产目标
    target_output: int = Field(
        default=3,
        ge=1,
        description="目标月产量（台）"
    )
    
    # 高级配置
    pipeline_mode: bool = Field(
        default=True,
        description="是否启用流水线模式（多台并行）"
    )
    station_constraint_mode: bool = Field(
        default=False,
        description="是否启用工位资源限制（工位内强制串行）"
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="随机种子（用于复现结果，None为随机）"
    )
    
    @computed_field
    @property
    def sim_time_minutes(self) -> float:
        """
        计算仿真总时长（分钟）
        
        Returns:
            仿真时长 = 每日工作小时数 × 60 × 每月工作天数
        """
        return self.work_hours_per_day * 60 * self.work_days_per_month
    
    @computed_field
    @property
    def sim_time_hours(self) -> float:
        """
        计算仿真总时长（小时）
        
        Returns:
            仿真时长（小时）
        """
        return self.work_hours_per_day * self.work_days_per_month
    
    @computed_field
    @property
    def minutes_per_day(self) -> int:
        """
        每日工作分钟数
        
        Returns:
            每日分钟数
        """
        return self.work_hours_per_day * 60
    
    def get_equipment_names(self) -> list:
        """
        获取所有关键设备名称
        
        Returns:
            设备名称列表
        """
        return list(self.critical_equipment.keys())
    
    def get_equipment_capacity(self, name: str) -> int:
        """
        获取指定设备的容量
        
        Args:
            name: 设备名称
            
        Returns:
            设备数量，不存在返回0
        """
        return self.critical_equipment.get(name, 0)
    
    def add_equipment(self, name: str, quantity: int):
        """
        添加关键设备
        
        Args:
            name: 设备名称
            quantity: 设备数量
        """
        self.critical_equipment[name] = quantity
    
    def remove_equipment(self, name: str) -> bool:
        """
        移除关键设备
        
        Args:
            name: 设备名称
            
        Returns:
            是否成功移除
        """
        if name in self.critical_equipment:
            del self.critical_equipment[name]
            return True
        return False
    
    def validate_config(self) -> tuple:
        """
        验证配置有效性
        
        Returns:
            (是否有效, 错误列表, 警告列表)
        """
        errors = []
        warnings = []
        
        # 检查工作时间
        if self.work_hours_per_day > 12:
            warnings.append(f"每日工作时间 {self.work_hours_per_day} 小时可能过长")
        
        # 检查工人数量
        if self.num_workers < 2:
            warnings.append("工人数量过少，可能导致流水线效率低下")
        
        # 检查设备配置
        if not self.critical_equipment:
            errors.append("至少需要配置一种关键设备")
        
        for name, qty in self.critical_equipment.items():
            if qty < 1:
                errors.append(f"设备 '{name}' 数量必须大于0")
        
        # 检查休息规则
        if self.rest_time_threshold < self.rest_duration_time:
            warnings.append("休息触发阈值小于休息时长")
        
        return len(errors) == 0, errors, warnings
    
    class Config:
        json_schema_extra = {
            "example": {
                "work_hours_per_day": 8,
                "work_days_per_month": 22,
                "num_workers": 6,
                "critical_equipment": {
                    "动平衡机": 2,
                    "试车台": 1,
                    "装配台": 3,
                    "检测台": 2
                },
                "rest_time_threshold": 50.0,
                "rest_duration_time": 5.0,
                "rest_load_threshold": 7,
                "rest_duration_load": 3.0,
                "target_output": 3
            }
        }
