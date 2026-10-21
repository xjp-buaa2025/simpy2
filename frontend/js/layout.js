/**
 * 布局模块 - 自动布局和工位相关功能
 */

// 自动布局（按依赖层级）
function autoLayout() {
    const levels = {};
    const nodeMap = {};
    state.nodes.forEach(n => {
        nodeMap[n.stepId] = n;
        levels[n.stepId] = 0;
    });
    
    let changed = true;
    while (changed) {
        changed = false;
        state.nodes.forEach(node => {
            if (node.predecessors) {
                node.predecessors.split(';').forEach(pred => {
                    pred = pred.trim();
                    if (pred && levels[pred] !== undefined) {
                        const newLevel = levels[pred] + 1;
                        if (newLevel > levels[node.stepId]) {
                            levels[node.stepId] = newLevel;
                            changed = true;
                        }
                    }
                });
            }
        });
    }
    
    const levelGroups = {};
    Object.entries(levels).forEach(([stepId, level]) => {
        if (!levelGroups[level]) levelGroups[level] = [];
        levelGroups[level].push(stepId);
    });
    
    const startX = 50;
    const startY = 50;
    const xGap = 160;
    const yGap = 70;
    
    Object.entries(levelGroups).forEach(([level, stepIds]) => {
        stepIds.forEach((stepId, idx) => {
            const node = nodeMap[stepId];
            if (node) {
                node.x = startX + parseInt(level) * xGap;
                node.y = startY + idx * yGap;
            }
        });
    });
    
    renderCanvas();
    showToast('自动布局完成', 'success');
}

// 按工位自动布局（UE蓝图风格）
function autoLayoutByStation(collapseAll = true) {
    Object.keys(stationContainers).forEach(k=>delete stationContainers[k]);
    // 按工位分组节点
    const stationGroups = {};
    state.nodes.forEach(node => {
        const stId = node.station || 'UNASSIGNED';
        if (!stationGroups[stId]) stationGroups[stId] = [];
        stationGroups[stId].push(node);
    });
    
    // 获取工位顺序
    const stationOrder = state.stations.map(s => s.id);
    stationOrder.push('UNASSIGNED');
    
    // 布局参数
    const containerPadding = 30;
    const containerTitleHeight = 40;
    const nodeWidth = 120;
    const nodeHeight = 50;
    const nodeGapX = 20;
    const nodeGapY = 20;
    const containerGapX = 50;
    const containerGapY = 30;
    const maxNodesPerRow = 4;
    
    let currentX = 50;
    let currentY = 50;
    let maxRowHeight = 0;
    let containersPerRow = 0;
    const maxContainersPerRow = 3;
    
    stationOrder.forEach(stationId => {
        const nodes = stationGroups[stationId] || [];
        if (nodes.length === 0) return;
        
        const station = state.stations.find(s => s.id === stationId) || { 
            id: 'UNASSIGNED', 
            name: '未分配工位', 
            color: '#6b7280' 
        };
        
        // 计算容器尺寸
        const cols = Math.min(nodes.length, maxNodesPerRow);
        const rows = Math.ceil(nodes.length / maxNodesPerRow);
        const containerWidth = cols * (nodeWidth + nodeGapX) + containerPadding * 2 - nodeGapX;
        const containerHeight = rows * (nodeHeight + nodeGapY) + containerPadding * 2 + containerTitleHeight - nodeGapY;
        
        // 换行检查
        if (containersPerRow >= maxContainersPerRow) {
            currentX = 50;
            currentY += maxRowHeight + containerGapY;
            maxRowHeight = 0;
            containersPerRow = 0;
        }
        
        // 保存容器信息
        stationContainers[stationId] = {
            x: currentX,
            y: currentY,
            width: containerWidth,
            height: containerHeight,
            collapsed: collapseAll,
            color: station.color,
            name: stationDisplayLabel(station.id, station.name)
        };
        
        // 布局节点
        nodes.forEach((node, idx) => {
            const col = idx % maxNodesPerRow;
            const row = Math.floor(idx / maxNodesPerRow);
            node.x = currentX + containerPadding + col * (nodeWidth + nodeGapX);
            node.y = currentY + containerTitleHeight + containerPadding + row * (nodeHeight + nodeGapY);
        });
        
        currentX += containerWidth + containerGapX;
        maxRowHeight = Math.max(maxRowHeight, containerHeight);
        containersPerRow++;
    });
    
    if (collapseAll) {
        state.showStationContainers = true;
        document.getElementById('showContainers').checked = true;
        setCanvasLayoutMode('station-only');
    }
    renderCanvas();
    showToast('按工区布局完成', 'success');
}

// 初始化工位筛选器
function initStationFilter() {
    const select = document.getElementById('stationFilter');
    select.innerHTML = '<option value="">全部工区</option>';
    state.stations.forEach(st => {
        const opt = document.createElement('option');
        opt.value = st.id;
        opt.textContent = stationDisplayLabel(st.id, st.name);
        select.appendChild(opt);
    });
}

// 按工位筛选
function filterByStation() {
    const select = document.getElementById('stationFilter');
    state.stationFilter = select.value || null;
    renderCanvas();
}

// 切换工位容器显示
function toggleContainers() {
    state.showStationContainers = document.getElementById('showContainers').checked;
    renderCanvas();
}

// 清空画布
function clearCanvas(force = false) {
    if(!force&&typeof guardAreaTransition==='function'){guardAreaTransition(()=>clearCanvas(true));return;}
    if (!confirm('确定要清空所有节点吗？')) return;
    state.nodes = [];
    state.edges = [];
    state.selectedNode = null;
    if(typeof resetAreaEditorForProcess==='function')resetAreaEditorForProcess();
    Object.keys(stationContainers).forEach(k => delete stationContainers[k]);
    renderCanvas();
    showToast('画布已清空', 'success');
}

// 加载复杂示例（基础案例，源自 data/3.csv；参数对齐实验配置 9.1.1）
function loadComplexExample(force = false) {
    if(!force&&typeof guardAreaTransition==='function'){guardAreaTransition(()=>loadComplexExample(true));return;}
    loadProcessData({ name: '航空发动机整机装配流程', nodes: COMPLEX_PROCESS_NODES });

    // 全局参数（依据 9.1.1 实验配置说明）
    document.getElementById('workHoursPerDay').value = 8;     // 每日工作小时数
    document.getElementById('workDaysPerMonth').value = 22;   // 每月工作天数

    // 休息规则参数
    document.getElementById('restTimeThreshold').value = 40;  // 连续工作触发阈值(分钟)
    document.getElementById('restDurationTime').value = 10;   // 时间触发休息时长(分钟)
    document.getElementById('restLoadThreshold').value = 5;   // 负荷触发阈值(REBA)
    document.getElementById('restDurationLoad').value = 10;   // 负荷触发休息时长(分钟)

    // 关键设备：试车台 x1
    state.config.criticalEquipment = {
        '试车台': 1
    };
    renderEquipmentList();

    showToast(`基础案例已加载（${COMPLEX_PROCESS_NODES.length}个节点）`, 'success');
}

// The active process owns the visible area list. A previous process never adds areas here.
function stationDisplayLabel(id, label) {
    return !label || label === id ? id : `${id} ${label}`;
}
function processStationCatalog(process, capacityModel = null) {
    const used = new Set(process.nodes.map(n => n.area_id || n.station || 'ST01'));
    const catalog = Array.isArray(process.station_catalog) ? process.station_catalog : [];
    const entries = new Map();
    for (const row of [...catalog, ...DEFAULT_STATIONS.map(s => ({station_id:s.id, area_id:s.id, label:s.name, color:s.color}))]) {
        const id = row.area_id || row.station_id;
        if (used.has(id) && !entries.has(id)) entries.set(id, {id, name:row.label || id, color:row.color || DEFAULT_STATIONS[entries.size % DEFAULT_STATIONS.length].color});
    }
    for (const id of used) if (!entries.has(id)) entries.set(id, {id, name:id, color:DEFAULT_STATIONS[entries.size % DEFAULT_STATIONS.length].color});
    for (const station of entries.values()) if (capacityModel?.areas?.[station.id]?.label) station.name = capacityModel.areas[station.id].label;
    return [...entries.values()];
}

// 加载流程数据；调用者在提交前验证完整候选输入。
function loadProcessData(process, options = {}) {
    if(typeof resetAreaEditorForProcess==='function')resetAreaEditorForProcess();
    state.selectedNode=null;state.stationFilter=null;state.capacityModel=options.capacityModel || null;
    state.capacityAutomaticWip=options.automaticWip ?? null;state.capacitySamplingScheme=options.samplingScheme || 'legacy';
    state.processName=process.name || '工艺流程';state.processDescription=process.description || '';
    state.stations=processStationCatalog(process, state.capacityModel);
    initStationFilter();
    state.nodes = process.nodes.map((n, idx) => ({
        id: 'node_' + idx,
        stepId: n.step_id,
        taskName: n.task_name,
        opType: n.op_type,
        predecessors: n.predecessors || '',
        stdDuration: n.std_duration,
        timeVariance: n.time_variance ?? 0,
        workLoadScore: n.work_load_score ?? 5,
        reworkProb: n.rework_prob ?? 0,
        requiredWorkers: n.required_workers ?? 1,
        requiredTools: Array.isArray(n.required_tools) ? n.required_tools.join(';') : (n.required_tools || ''),
        station: n.area_id || n.station || 'ST01',
        workstationId: n.workstation_id || '',
        x: n.x ?? 50 + idx * 150,
        y: n.y ?? 100
    }));
    
    rebuildEdges();
    autoLayoutByStation(false);
}
