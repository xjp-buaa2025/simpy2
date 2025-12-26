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
function autoLayoutByStation() {
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
            collapsed: false,
            color: station.color,
            name: station.name
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
    
    renderCanvas();
    showToast('按工位布局完成', 'success');
}

// 初始化工位筛选器
function initStationFilter() {
    const select = document.getElementById('stationFilter');
    select.innerHTML = '<option value="">全部工位</option>';
    state.stations.forEach(st => {
        const opt = document.createElement('option');
        opt.value = st.id;
        opt.textContent = st.name;
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
function clearCanvas() {
    if (!confirm('确定要清空所有节点吗？')) return;
    state.nodes = [];
    state.edges = [];
    state.selectedNode = null;
    Object.keys(stationContainers).forEach(k => delete stationContainers[k]);
    renderCanvas();
    showToast('画布已清空', 'success');
}

// 加载复杂示例
function loadComplexExample() {
    loadProcessData({ name: '压气机装配流程', nodes: COMPLEX_PROCESS_NODES });
    
    document.getElementById('numWorkers').value = 8;
    document.getElementById('targetOutput').value = 3;
    document.getElementById('workDaysPerMonth').value = 22;
    
    state.config.criticalEquipment = {
        '动平衡机': 2,
        '检测台': 2,
        '叶片安装夹具': 3,
        '液压拉伸器': 2,
        '感应加热器': 2,
        '起重设备': 1
    };
    renderEquipmentList();
    
    showToast(`复杂示例流程已加载（${COMPLEX_PROCESS_NODES.length}个节点）`, 'success');
}

// 加载流程数据
function loadProcessData(process) {
    state.nodes = process.nodes.map((n, idx) => ({
        id: 'node_' + idx,
        stepId: n.step_id,
        taskName: n.task_name,
        opType: n.op_type,
        predecessors: n.predecessors || '',
        stdDuration: n.std_duration,
        timeVariance: n.time_variance || 0,
        workLoadScore: n.work_load_score || 5,
        reworkProb: n.rework_prob || 0,
        requiredWorkers: n.required_workers || 1,
        requiredTools: Array.isArray(n.required_tools) ? n.required_tools.join(';') : (n.required_tools || ''),
        station: n.station || 'ST01',
        x: n.x || 50 + idx * 150,
        y: n.y || 100
    }));
    
    rebuildEdges();
    autoLayoutByStation();
}
