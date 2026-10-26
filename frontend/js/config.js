/**
 * 配置模块 - 常量和默认配置
 */

// 默认工位配置
const DEFAULT_STATIONS = [
    { id: 'ST01', name: '原材料入库区', color: '#3b82f6', order: 1 },
    { id: 'ST02', name: '预处理工区', color: '#8b5cf6', order: 2 },
    { id: 'ST03', name: '压气机模块装配区', color: '#10b981', order: 3 },
    { id: 'ST04', name: '燃烧室模块装配区', color: '#f59e0b', order: 4 },
    { id: 'ST05', name: '涡轮模块装配区', color: '#ef4444', order: 5 },
    { id: 'ST06', name: '齿轮箱模块装配区', color: '#06b6d4', order: 6 },
    { id: 'ST07', name: '燃油系统模块装配区', color: '#ec4899', order: 7 },
    { id: 'ST08', name: '点火系统模块装配区', color: '#84cc16', order: 8 },
    { id: 'ST09', name: '润滑系统模块装配区', color: '#a855f7', order: 9 },
    { id: 'ST10', name: '进气系统模块装配区', color: '#14b8a6', order: 10 },
    { id: 'ST11', name: '总装集成工区', color: '#f97316', order: 11 },
    { id: 'ST12', name: '整机测试工区', color: '#6366f1', order: 12 },
    { id: 'ST13', name: '包装发运区', color: '#22c55e', order: 13 },
    { id: 'ST14', name: '返修工区', color: '#dc2626', order: 14 }
];

// 操作类型颜色
const DEFAULT_OP_TYPE_COLORS = {
    'H': '#3b82f6',  // 取/放 - 蓝色
    'A': '#10b981',  // 装配 - 绿色
    'M': '#f59e0b',  // 测量 - 橙色
    'T': '#8b5cf6',  // 工具操作 - 紫色
    'D': '#6b7280',  // 数据记录 - 灰色
    'S-Move': '#06b6d4',
    'S-Rest': '#84cc16',
    'Coop': '#ec4899'
};
const OP_TYPE_COLORS = { ...DEFAULT_OP_TYPE_COLORS };
const BEHAVIOR_UNITS = [
    { type: 'H', name: '取 / 放', english: 'Handle' },
    { type: 'A', name: '装配', english: 'Assemble' },
    { type: 'M', name: '测量 & 检验', english: 'Measure' },
    { type: 'T', name: '工具 & 工装操作', english: 'Tooling' },
    { type: 'D', name: '数据记录', english: 'Document' },
    { type: 'S-Move', name: '工间移动', english: 'Shift-Move' },
    { type: 'S-Rest', name: '工间休息', english: 'Shift-Rest' },
    { type: 'Coop', name: '作业协同沟通', english: 'Co-operation' }
];

// 操作类型图标
const OP_TYPE_ICONS = {
    'H': '📦',
    'A': '🔧',
    'M': '📏',
    'T': '🛠️',
    'D': '📝',
    'S-Move': '↔',
    'S-Rest': '☕',
    'Coop': '💬'
};

// 工位容器状态（位置、大小、折叠状态）
const stationContainers = {};

// 默认配置
const DEFAULT_CONFIG = {
    workHoursPerDay: 8,
    workDaysPerMonth: 22,
    criticalEquipment: {},
    restTimeThreshold: 50,
    restDurationTime: 5,
    restLoadThreshold: 7,
    restDurationLoad: 3,
    pipelineMode: true,
    stationConstraintMode: true
};
