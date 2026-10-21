"""
配置管理接口
提供全局配置的获取、更新和验证功能

API端点:
- GET /api/config/default: 获取默认配置
- POST /api/config/validate: 验证配置有效性
- POST /api/config/update: 更新配置
- GET /api/config/equipment-types: 获取关键设备类型列表
"""

import os
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import yaml

router = APIRouter()


# ============ 请求/响应模型 ============

from app.models.config_model import GlobalConfig


class APIResponse(BaseModel):
    """统一API响应格式"""
    success: bool = Field(description="请求是否成功")
    message: str = Field(description="响应消息")
    data: Optional[Any] = Field(default=None, description="响应数据")


class ConfigValidationResult(BaseModel):
    """配置验证结果"""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class EquipmentUpdate(BaseModel):
    """设备更新请求"""
    name: str = Field(description="设备名称")
    quantity: int = Field(ge=1, description="设备数量")


# ============ API端点 ============

@router.get("/default", response_model=APIResponse)
async def get_default_config():
    """
    获取默认配置
    
    返回系统默认的全局配置参数，包括：
    - 排班配置（工时/天数/工人数）
    - 关键设备配置
    - 休息规则参数
    - 生产目标
    """
    # 尝试从配置文件加载
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config", "default_config.yaml"
    )
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
                config = GlobalConfig(**config_data)
        except Exception as e:
            config = GlobalConfig()
    else:
        config = GlobalConfig()
    
    return APIResponse(
        success=True,
        message="获取默认配置成功",
        data=config.model_dump()
    )


@router.post("/validate", response_model=APIResponse)
async def validate_config(config: GlobalConfig):
    """
    验证配置有效性
    
    检查配置参数的合理性，包括：
    - 参数范围检查
    - 设备数量检查
    - 逻辑一致性检查
    """
    errors = []
    warnings = []
    
    # 检查工作时间设置
    if config.work_hours_per_day > 12:
        warnings.append(f"每日工作时间 {config.work_hours_per_day} 小时可能过长")
    
    
    # 检查关键设备
    if not config.critical_equipment:
        errors.append("至少需要配置一种关键设备")
    
    for equip_name, quantity in config.critical_equipment.items():
        if quantity < 1:
            errors.append(f"设备 '{equip_name}' 数量必须大于0")
    
    # 检查休息规则
    if config.rest_time_threshold < config.rest_duration_time:
        warnings.append("休息触发阈值小于休息时长，可能导致频繁休息")
    
    # 检查仿真时间
    sim_time = config.sim_time_minutes
    if sim_time < 480:  # 少于8小时
        warnings.append(f"仿真总时长 {sim_time} 分钟较短，可能不足以观察稳定产出")
    
    result = ConfigValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
    
    return APIResponse(
        success=result.valid,
        message="配置验证通过" if result.valid else "配置存在错误",
        data=result.model_dump()
    )


@router.post("/update", response_model=APIResponse)
async def update_config(config: GlobalConfig):
    """
    更新配置
    
    保存配置到配置文件（可选）
    """
    # 先验证配置
    errors = []
    
    
    if not config.critical_equipment:
        errors.append("必须配置关键设备")
    
    if errors:
        return APIResponse(
            success=False,
            message="配置验证失败",
            data={"errors": errors}
        )
    
    # 可选：保存到文件
    # config_path = os.path.join(...)
    # with open(config_path, "w", encoding="utf-8") as f:
    #     yaml.dump(config.model_dump(), f, allow_unicode=True)
    
    return APIResponse(
        success=True,
        message="配置更新成功",
        data=config.model_dump()
    )


@router.get("/equipment-types", response_model=APIResponse)
async def get_equipment_types():
    """
    获取关键设备类型列表
    
    返回系统支持的关键设备类型，供前端下拉选择
    """
    equipment_types = [
        {"name": "动平衡机", "description": "用于转子动平衡检测", "default_quantity": 2},
        {"name": "试车台", "description": "发动机整机试车", "default_quantity": 1},
        {"name": "装配台", "description": "部件装配工作台", "default_quantity": 3},
        {"name": "检测台", "description": "质量检测工作台", "default_quantity": 2},
        {"name": "吊装设备", "description": "重型部件吊装", "default_quantity": 2},
        {"name": "清洗设备", "description": "零件清洗", "default_quantity": 1},
        {"name": "涂装设备", "description": "防护涂装", "default_quantity": 1},
    ]
    
    return APIResponse(
        success=True,
        message="获取设备类型成功",
        data=equipment_types
    )


@router.post("/equipment/add", response_model=APIResponse)
async def add_equipment(equipment: EquipmentUpdate, config: GlobalConfig):
    """
    添加关键设备
    """
    if equipment.name in config.critical_equipment:
        return APIResponse(
            success=False,
            message=f"设备 '{equipment.name}' 已存在"
        )
    
    config.critical_equipment[equipment.name] = equipment.quantity
    
    return APIResponse(
        success=True,
        message=f"成功添加设备 '{equipment.name}'",
        data=config.critical_equipment
    )


@router.delete("/equipment/{name}", response_model=APIResponse)
async def remove_equipment(name: str):
    """
    删除关键设备
    """
    # 这里需要从当前配置中删除
    # 实际应用中应该从持久化存储中操作
    return APIResponse(
        success=True,
        message=f"成功删除设备 '{name}'"
    )


@router.get("/sim-time-info", response_model=APIResponse)
async def get_sim_time_info(
    work_hours_per_day: int = 8,
    work_days_per_month: int = 22
):
    """
    获取仿真时间信息
    
    根据配置计算仿真时长相关信息
    """
    total_minutes = work_hours_per_day * 60 * work_days_per_month
    total_hours = total_minutes / 60
    
    return APIResponse(
        success=True,
        message="计算成功",
        data={
            "total_minutes": total_minutes,
            "total_hours": total_hours,
            "total_days": work_days_per_month,
            "minutes_per_day": work_hours_per_day * 60,
            "description": f"仿真周期：{work_days_per_month}天，每天{work_hours_per_day}小时，共{total_hours}小时"
        }
    )
