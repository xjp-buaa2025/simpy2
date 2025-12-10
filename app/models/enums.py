"""
枚举定义
包含系统中使用的所有枚举类型

枚举类:
- OpType: 操作类型（H/A/M/T/D）
- WorkerState: 工人状态
- GanttEventType: 甘特图事件类型
- ResourceType: 资源类型
"""

from enum import Enum


class OpType(str, Enum):
    """
    操作类型枚举
    
    用于CSV属性和拖拽节点属性
    
    Values:
        H: 取/放 (Handling)
        A: 装配 (Assembly)
        M: 测量 (Measurement) - 可触发返工
        T: 工具操作 (Tooling)
        D: 数据记录 (Data Recording)
    """
    H = "H"  # 取/放
    A = "A"  # 装配
    M = "M"  # 测量 - 可触发返工
    T = "T"  # 工具操作
    D = "D"  # 数据记录


class WorkerState(str, Enum):
    """
    工人状态枚举
    
    Values:
        IDLE: 空闲
        WORKING: 工作中
        RESTING: 休息中
    """
    IDLE = "idle"
    WORKING = "working"
    RESTING = "resting"


class GanttEventType(str, Enum):
    """
    甘特图事件类型枚举
    
    Values:
        NORMAL: 正常工作
        REST: 休息
        REWORK: 返工
        WAITING: 等待资源
    """
    NORMAL = "NORMAL"
    REST = "REST"
    REWORK = "REWORK"
    WAITING = "WAITING"


class ResourceType(str, Enum):
    """
    资源类型枚举
    
    Values:
        WORKER: 工人
        CRITICAL_EQUIPMENT: 关键设备
        COMMON_TOOL: 普通工具
    """
    WORKER = "WORKER"
    CRITICAL_EQUIPMENT = "CRITICAL_EQUIPMENT"
    COMMON_TOOL = "COMMON_TOOL"


class SimulationStatus(str, Enum):
    """
    仿真状态枚举
    
    Values:
        PENDING: 等待中
        RUNNING: 运行中
        COMPLETED: 已完成
        FAILED: 失败
        CANCELLED: 已取消
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RestTriggerType(str, Enum):
    """
    休息触发类型枚举
    
    Values:
        TIME: 时间触发（规则A）
        LOAD: 负荷触发（规则B）
    """
    TIME = "time-triggered"
    LOAD = "load-triggered"


# ============ 操作类型元数据 ============

OP_TYPE_META = {
    OpType.H: {
        "zh": "取/放",
        "en": "Handling",
        "color": "#3B82F6",  # 蓝色
        "icon": "📦",
        "description": "物料搬运、取放操作"
    },
    OpType.A: {
        "zh": "装配",
        "en": "Assembly",
        "color": "#10B981",  # 绿色
        "icon": "🔧",
        "description": "零部件装配操作"
    },
    OpType.M: {
        "zh": "测量",
        "en": "Measurement",
        "color": "#F59E0B",  # 橙色
        "icon": "📏",
        "description": "质量检测、测量操作（可能触发返工）"
    },
    OpType.T: {
        "zh": "工具操作",
        "en": "Tooling",
        "color": "#8B5CF6",  # 紫色
        "icon": "🛠️",
        "description": "工具使用、调整操作"
    },
    OpType.D: {
        "zh": "数据记录",
        "en": "Data Recording",
        "color": "#6B7280",  # 灰色
        "icon": "📝",
        "description": "数据记录、文档操作"
    },
}


# ============ 甘特图事件类型元数据 ============

GANTT_EVENT_TYPE_META = {
    GanttEventType.NORMAL: {
        "zh": "正常工作",
        "en": "Normal Work",
        "color": "#3B82F6",  # 蓝色实心
        "pattern": "solid"
    },
    GanttEventType.REST: {
        "zh": "休息",
        "en": "Rest",
        "color": "#8B5CF6",  # 紫色半透明
        "pattern": "translucent"
    },
    GanttEventType.REWORK: {
        "zh": "返工",
        "en": "Rework",
        "color": "#EF4444",  # 红色斜线
        "pattern": "striped"
    },
    GanttEventType.WAITING: {
        "zh": "等待资源",
        "en": "Waiting",
        "color": "#9CA3AF",  # 灰色半透明
        "pattern": "translucent"
    },
}


def get_op_type_info(op_type: OpType) -> dict:
    """
    获取操作类型的详细信息
    
    Args:
        op_type: 操作类型枚举值
        
    Returns:
        包含中英文名称、颜色、图标的字典
    """
    return OP_TYPE_META.get(op_type, {
        "zh": "未知",
        "en": "Unknown",
        "color": "#000000",
        "icon": "❓",
        "description": ""
    })


def get_gantt_event_info(event_type: GanttEventType) -> dict:
    """
    获取甘特图事件类型的详细信息
    
    Args:
        event_type: 事件类型枚举值
        
    Returns:
        包含中英文名称、颜色、填充模式的字典
    """
    return GANTT_EVENT_TYPE_META.get(event_type, {
        "zh": "未知",
        "en": "Unknown",
        "color": "#000000",
        "pattern": "solid"
    })
