/**
 * 状态管理模块
 */

const state = {
    nodes: [],
    edges: [],
    selectedNode: null,
    selectedArea: null,
    editingNode: null,
    simulationResult: null,
    stations: [...DEFAULT_STATIONS],
    stationFilter: null,
    showStationContainers: true,
    layoutMode: 'normal', // 'normal' 或 'station-only'
    config: { ...DEFAULT_CONFIG, criticalEquipment: {...DEFAULT_CONFIG.criticalEquipment} }
};

// 画布相关状态
let canvas, ctx;
let canvasOffset = { x: 0, y: 0 };
let scale = 1;
let isDragging = false;
let isConnecting = false;
let connectStart = null;
let dragNode = null;
let dragStationContainer = null;
let dragOffset = { x: 0, y: 0 };
let lastMouseEvent = null;

// 图表实例
let workerChart = null;
let equipmentChart = null;
let fatigueChart = null;
