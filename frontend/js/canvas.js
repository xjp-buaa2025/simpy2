/**
 * 画布模块 - 流程图编辑器
 */

// 初始化画布
function initCanvas() {
    canvas = document.getElementById('processCanvas');
    ctx = canvas.getContext('2d');
    
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    
    // 事件绑定
    canvas.addEventListener('mousedown', handleCanvasMouseDown);
    canvas.addEventListener('mousemove', handleCanvasMouseMove);
    canvas.addEventListener('mouseup', handleCanvasMouseUp);
    canvas.addEventListener('dblclick', handleCanvasDblClick);
    canvas.addEventListener('contextmenu', handleCanvasContextMenu);
    canvas.addEventListener('wheel', handleCanvasWheel);
    canvas.addEventListener('dragover', e => e.preventDefault());
    canvas.addEventListener('drop', handleCanvasDrop);
    document.addEventListener('keydown', handleKeyDown);
}

// 调整画布大小
function resizeCanvas() {
    const container = canvas.parentElement;
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    renderCanvas();
}

// 切换布局模式
function toggleLayoutMode() {
    state.layoutMode = state.layoutMode === 'normal' ? 'station-only' : 'normal';
    const button = document.getElementById('layoutModeToggle');
    if (state.layoutMode === 'station-only') {
        button.textContent = '📋 详细视图';
        button.classList.remove('btn-secondary');
        button.classList.add('btn-primary');
    } else {
        button.textContent = '🏢 工位层级视图';
        button.classList.remove('btn-primary');
        button.classList.add('btn-secondary');
    }
    renderCanvas();
    showToast(`已切换到${state.layoutMode === 'station-only' ? '工位层级' : '详细'}视图`, 'success');
}

// 渲染画布
function renderCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(canvasOffset.x, canvasOffset.y);
    ctx.scale(scale, scale);
    
    drawGrid();
    
    // 绘制工位容器
    if (state.showStationContainers) {
        drawStationContainers();
    }
    
    // 在工位层级视图下，绘制工位之间的连线
    if (state.layoutMode === 'station-only') {
        drawStationEdges();
    } else {
        // 绘制节点之间的连线
        state.edges.forEach(edge => {
            const fromNode = state.nodes.find(n => n.id === edge.from);
            const toNode = state.nodes.find(n => n.id === edge.to);
            if (fromNode && toNode) drawEdge(fromNode, toNode);
        });
    }
    
    // 绘制连线预览
    if (isConnecting && connectStart && lastMouseEvent) {
        const mousePos = getMousePos(lastMouseEvent);
        ctx.beginPath();
        ctx.moveTo(connectStart.x + 60, connectStart.y + 25);
        ctx.lineTo(mousePos.x, mousePos.y);
        ctx.strokeStyle = '#3b82f6';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.stroke();
        ctx.setLineDash([]);
    }
    
    // 绘制节点
    state.nodes.forEach(node => {
        // 在正常模式下，根据工位过滤
        if (state.layoutMode === 'normal' && state.stationFilter && node.station !== state.stationFilter) {
            return;
        }
        // 在工位层级视图下，只显示展开工位的节点
        if (state.layoutMode === 'station-only') {
            const container = stationContainers[node.station];
            if (!container || container.collapsed) {
                return;
            }
        }
        drawNode(node, node === state.selectedNode);
    });
    
    ctx.restore();
    updateStats();
}

// 绘制工位之间的连线
function drawStationEdges() {
    // 收集工位之间的连接关系
    const stationConnections = new Map();
    
    // 分析节点之间的依赖，构建工位连接
    state.nodes.forEach(node => {
        if (!node.predecessors) return;
        
        const predStepIds = node.predecessors.split(';').map(p => p.trim()).filter(p => p);
        predStepIds.forEach(predStepId => {
            const predNode = state.nodes.find(n => n.stepId === predStepId);
            if (predNode && predNode.station !== node.station) {
                const fromStation = predNode.station;
                const toStation = node.station;
                
                // 只添加唯一的工位连接
                const key = `${fromStation}->${toStation}`;
                stationConnections.set(key, { fromStation, toStation });
            }
        });
    });
    
    // 绘制工位连线
    stationConnections.forEach(conn => {
        const fromContainer = stationContainers[conn.fromStation];
        const toContainer = stationContainers[conn.toStation];
        
        if (fromContainer && toContainer) {
            // 无论工位是否展开，都绘制连线
            const fromX = fromContainer.x + (fromContainer.collapsed ? 200 : fromContainer.width);
            const fromY = fromContainer.y + (fromContainer.collapsed ? 40 : fromContainer.height / 2);
            const toX = toContainer.x;
            const toY = toContainer.y + (toContainer.collapsed ? 40 : toContainer.height / 2);
            
            // 绘制带箭头的连线
            ctx.beginPath();
            ctx.moveTo(fromX, fromY);
            ctx.lineTo(toX, toY);
            ctx.strokeStyle = '#3b82f6';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            // 绘制箭头
            const angle = Math.atan2(toY - fromY, toX - fromX);
            ctx.beginPath();
            ctx.moveTo(toX, toY);
            ctx.lineTo(toX - 15 * Math.cos(angle - Math.PI/6), toY - 15 * Math.sin(angle - Math.PI/6));
            ctx.lineTo(toX - 15 * Math.cos(angle + Math.PI/6), toY - 15 * Math.sin(angle + Math.PI/6));
            ctx.closePath();
            ctx.fillStyle = '#3b82f6';
            ctx.fill();
        }
    });
}

// 绘制工位容器
function drawStationContainers() {
    Object.entries(stationContainers).forEach(([stationId, container]) => {
        const { x, y, width, height, color, name } = container;
        const isCollapsed = container.collapsed;
        
        // 在工位层级视图下，始终绘制工位容器（包括折叠状态）
        if (state.layoutMode === 'normal' && isCollapsed) return;
        
        // 容器背景
        ctx.fillStyle = hexToRgba(color, isCollapsed ? 0.2 : 0.1);
        ctx.beginPath();
        ctx.roundRect(x, y, isCollapsed ? 200 : width, isCollapsed ? 80 : height, 12);
        ctx.fill();
        
        // 容器边框
        ctx.strokeStyle = hexToRgba(color, isCollapsed ? 0.8 : 0.5);
        ctx.lineWidth = isCollapsed ? 3 : 2;
        ctx.stroke();
        
        // 标题栏背景
        ctx.fillStyle = hexToRgba(color, 0.3);
        ctx.beginPath();
        ctx.roundRect(x, y, isCollapsed ? 200 : width, 36, [12, 12, 0, 0]);
        ctx.fill();
        
        // 标题文字
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`📍 ${name}`, x + 12, y + 24);
        
        // 节点数量
        const nodeCount = state.nodes.filter(n => n.station === stationId).length;
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillStyle = hexToRgba('#fff', 0.7);
        ctx.fillText(`${nodeCount} 节点`, x + (isCollapsed ? 200 : width) - 12, y + 24);
        
        // 折叠状态的展开提示
        if (isCollapsed) {
            ctx.font = '16px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillStyle = hexToRgba(color, 0.8);
            ctx.fillText('▶️ 点击展开', x + 100, y + 55);
        }
    });
}

// 绘制网格
function drawGrid() {
    const gridSize = 20;
    ctx.strokeStyle = '#1f2937';
    ctx.lineWidth = 0.5;
    
    const startX = -canvasOffset.x / scale;
    const startY = -canvasOffset.y / scale;
    const endX = (canvas.width - canvasOffset.x) / scale;
    const endY = (canvas.height - canvasOffset.y) / scale;
    
    for (let x = Math.floor(startX / gridSize) * gridSize; x < endX; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, startY);
        ctx.lineTo(x, endY);
        ctx.stroke();
    }
    
    for (let y = Math.floor(startY / gridSize) * gridSize; y < endY; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(startX, y);
        ctx.lineTo(endX, y);
        ctx.stroke();
    }
}

// 绘制节点
function drawNode(node, selected) {
    const x = node.x;
    const y = node.y;
    const width = 120;
    const height = 50;
    
    // 阴影
    ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
    ctx.shadowBlur = 10;
    ctx.shadowOffsetX = 2;
    ctx.shadowOffsetY = 2;
    
    // 节点背景
    ctx.fillStyle = OP_TYPE_COLORS[node.opType] || '#6b7280';
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, 8);
    ctx.fill();
    
    ctx.shadowColor = 'transparent';
    
    // 选中边框
    if (selected) {
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 3;
        ctx.stroke();
    }
    
    // 节点文字
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${OP_TYPE_ICONS[node.opType]} ${node.stepId}`, x + width/2, y + 20);
    
    ctx.font = '11px sans-serif';
    const displayName = node.taskName.length > 10 ? node.taskName.substring(0, 10) + '...' : node.taskName;
    ctx.fillText(displayName, x + width/2, y + 38);
}

// 绘制连线
function drawEdge(from, to) {
    const fromCenterX = from.x + 60;
    const fromCenterY = from.y + 25;
    const toCenterX = to.x + 60;
    const toCenterY = to.y + 25;
    
    let fromX, fromY, toX, toY;
    
    if (toCenterX > fromCenterX + 60) {
        fromX = from.x + 120;
        fromY = from.y + 25;
        toX = to.x;
        toY = to.y + 25;
    } else if (toCenterX < fromCenterX - 60) {
        fromX = from.x;
        fromY = from.y + 25;
        toX = to.x + 120;
        toY = to.y + 25;
    } else if (toCenterY > fromCenterY) {
        fromX = from.x + 60;
        fromY = from.y + 50;
        toX = to.x + 60;
        toY = to.y;
    } else {
        fromX = from.x + 60;
        fromY = from.y;
        toX = to.x + 60;
        toY = to.y + 50;
    }
    
    // 贝塞尔曲线
    ctx.beginPath();
    ctx.moveTo(fromX, fromY);
    const cpX = (fromX + toX) / 2;
    const cpY = (fromY + toY) / 2;
    ctx.bezierCurveTo(cpX, fromY, cpX, toY, toX, toY);
    ctx.strokeStyle = '#4b5563';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // 箭头
    const angle = Math.atan2(toY - cpY, toX - cpX);
    ctx.beginPath();
    ctx.moveTo(toX, toY);
    ctx.lineTo(toX - 10 * Math.cos(angle - Math.PI/6), toY - 10 * Math.sin(angle - Math.PI/6));
    ctx.lineTo(toX - 10 * Math.cos(angle + Math.PI/6), toY - 10 * Math.sin(angle + Math.PI/6));
    ctx.closePath();
    ctx.fillStyle = '#4b5563';
    ctx.fill();
}

// 获取鼠标位置
function getMousePos(e) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: (e.clientX - rect.left - canvasOffset.x) / scale,
        y: (e.clientY - rect.top - canvasOffset.y) / scale
    };
}

// 查找鼠标位置的节点
function findNodeAt(pos) {
    for (let i = state.nodes.length - 1; i >= 0; i--) {
        const n = state.nodes[i];
        if (pos.x >= n.x && pos.x <= n.x + 120 && pos.y >= n.y && pos.y <= n.y + 50) {
            return n;
        }
    }
    return null;
}

// 查找鼠标位置的工位容器
function findStationContainerAt(pos) {
    for (const [stationId, container] of Object.entries(stationContainers)) {
        // 在工位层级视图下，即使容器折叠也要检查点击
        if (state.layoutMode === 'normal' && container.collapsed) continue;
        
        const width = container.collapsed ? 200 : container.width;
        const height = container.collapsed ? 80 : container.height;
        
        if (pos.x >= container.x && pos.x <= container.x + width && 
            pos.y >= container.y && pos.y <= container.y + height) {
            return { stationId, container };
        }
    }
    return null;
}

// 鼠标按下事件
function handleCanvasMouseDown(e) {
    const pos = getMousePos(e);
    const node = findNodeAt(pos);
    const stationContainer = findStationContainerAt(pos);
    
    if (e.shiftKey && node) {
        isConnecting = true;
        connectStart = node;
        return;
    }
    
    if (node) {
        state.selectedNode = node;
        dragNode = node;
        dragOffset = { x: pos.x - node.x, y: pos.y - node.y };
    } else if (stationContainer) {
        state.selectedNode = null;
        
        // 无论在什么模式下，都允许拖动工位容器
        dragStationContainer = stationContainer;
        dragOffset = { x: pos.x - stationContainer.container.x, y: pos.y - stationContainer.container.y };
    } else {
        state.selectedNode = null;
        isDragging = true;
        dragOffset = { x: e.clientX - canvasOffset.x, y: e.clientY - canvasOffset.y };
    }
    
    renderCanvas();
}

// 切换工位容器的展开/收起状态
function toggleStationContainer(stationId) {
    const container = stationContainers[stationId];
    if (container) {
        container.collapsed = !container.collapsed;
        
        // 如果展开，调整容器大小以容纳所有节点
        if (!container.collapsed) {
            const stationNodes = state.nodes.filter(n => n.station === stationId);
            if (stationNodes.length > 0) {
                // 计算容纳所有节点所需的容器大小
                const containerPadding = 30;
                const containerTitleHeight = 40;
                const nodeWidth = 120;
                const nodeHeight = 50;
                const nodeGapX = 20;
                const nodeGapY = 20;
                const maxNodesPerRow = 4;
                
                const cols = Math.min(stationNodes.length, maxNodesPerRow);
                const rows = Math.ceil(stationNodes.length / maxNodesPerRow);
                container.width = cols * (nodeWidth + nodeGapX) + containerPadding * 2 - nodeGapX;
                container.height = rows * (nodeHeight + nodeGapY) + containerPadding * 2 + containerTitleHeight - nodeGapY;
            }
        } else {
            // 折叠时使用默认大小
            container.width = 200;
            container.height = 80;
        }
        
        renderCanvas();
        showToast(`${container.collapsed ? '已折叠' : '已展开'}工位: ${container.name}`, 'success');
    }
}

// 鼠标移动事件
function handleCanvasMouseMove(e) {
    lastMouseEvent = e;
    
    if (dragNode) {
        const pos = getMousePos(e);
        dragNode.x = pos.x - dragOffset.x;
        dragNode.y = pos.y - dragOffset.y;
        renderCanvas();
    } else if (dragStationContainer) {
        const pos = getMousePos(e);
        const container = dragStationContainer.container;
        const oldX = container.x;
        const oldY = container.y;
        
        // 更新容器位置
        container.x = pos.x - dragOffset.x;
        container.y = pos.y - dragOffset.y;
        
        // 计算位置偏移量
        const deltaX = container.x - oldX;
        const deltaY = container.y - oldY;
        
        // 更新该工位下所有节点的位置
        state.nodes.forEach(node => {
            if (node.station === dragStationContainer.stationId) {
                node.x += deltaX;
                node.y += deltaY;
            }
        });
        
        renderCanvas();
    } else if (isDragging) {
        canvasOffset.x = e.clientX - dragOffset.x;
        canvasOffset.y = e.clientY - dragOffset.y;
        renderCanvas();
    } else if (isConnecting) {
        renderCanvas();
    }
}

// 鼠标释放事件
function handleCanvasMouseUp(e) {
    if (isConnecting && connectStart) {
        const pos = getMousePos(e);
        const targetNode = findNodeAt(pos);
        
        if (targetNode && targetNode !== connectStart) {
            const existingPreds = targetNode.predecessors ? targetNode.predecessors.split(';').map(p => p.trim()) : [];
            if (!existingPreds.includes(connectStart.stepId)) {
                existingPreds.push(connectStart.stepId);
                targetNode.predecessors = existingPreds.filter(p => p).join(';');
                rebuildEdges();
                showToast(`已添加依赖: ${connectStart.stepId} → ${targetNode.stepId}`, 'success');
            }
        }
    }
    
    isConnecting = false;
    connectStart = null;
    isDragging = false;
    dragNode = null;
    dragStationContainer = null;
    renderCanvas();
}

// 双击事件
function handleCanvasDblClick(e) {
    const pos = getMousePos(e);
    const node = findNodeAt(pos);
    const stationContainer = findStationContainerAt(pos);
    
    if (node) {
        openNodeModal(node);
    } else if (stationContainer) {
        // 检查是否点击在标题栏区域（容器顶部36px高度）
        if (pos.y >= stationContainer.container.y && 
            pos.y <= stationContainer.container.y + 36) {
            // 如果按住了Ctrl键，或者在正常视图下，双击标题栏编辑名称
            if (e.ctrlKey || state.layoutMode === 'normal') {
                editStationName(stationContainer.stationId, stationContainer.container);
            } else {
                // 在工位层级视图下，双击标题栏展开/收起工位
                toggleStationContainer(stationContainer.stationId);
            }
        } else {
            // 双击工位容器其他区域展开/收起工位
            if (state.layoutMode === 'station-only') {
                toggleStationContainer(stationContainer.stationId);
            }
        }
    }
}

// 右键菜单
function handleCanvasContextMenu(e) { 
    e.preventDefault(); 
}

// 编辑工位名称
function editStationName(stationId, container) {
    // 创建临时输入框元素
    const input = document.createElement('input');
    const station = state.stations.find(s => s.id === stationId);
    
    if (!station) return;
    
    input.type = 'text';
    input.value = station.name;
    input.style.position = 'absolute';
    input.style.zIndex = 1000;
    input.style.backgroundColor = 'white';
    input.style.border = '2px solid #3b82f6';
    input.style.borderRadius = '4px';
    input.style.padding = '8px';
    input.style.fontSize = '14px';
    input.style.fontWeight = 'bold';
    input.style.color = '#374151';
    
    // 计算输入框位置（基于容器标题栏位置）
    const rect = canvas.getBoundingClientRect();
    const canvasScale = scale;
    const inputLeft = rect.left + (container.x + 12) * canvasScale + canvasOffset.x * canvasScale;
    const inputTop = rect.top + (container.y + 8) * canvasScale + canvasOffset.y * canvasScale;
    const inputWidth = (container.width - 24) * canvasScale;
    
    input.style.left = inputLeft + 'px';
    input.style.top = inputTop + 'px';
    input.style.width = inputWidth + 'px';
    
    // 添加到页面
    document.body.appendChild(input);
    
    // 自动聚焦并全选
    input.focus();
    input.select();
    
    // 处理确认修改
    function handleConfirm() {
        const newName = input.value.trim();
        if (newName && newName !== station.name) {
            // 更新工位名称
            station.name = newName;
            container.name = newName;
            
            // 更新所有相关显示
            renderCanvas();
            showToast(`工位名称已更新为: ${newName}`, 'success');
        }
        
        // 清理输入框
        document.body.removeChild(input);
    }
    
    // 处理取消修改
    function handleCancel() {
        document.body.removeChild(input);
    }
    
    // 事件绑定
    input.addEventListener('blur', handleConfirm);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleConfirm();
        }
    });
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            handleCancel();
        }
    });
}

// 滚轮缩放
function handleCanvasWheel(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    scale = Math.min(Math.max(scale * delta, 0.3), 3);
    renderCanvas();
}

// 拖放事件
function handleCanvasDrop(e) {
    e.preventDefault();
    const opType = e.dataTransfer.getData('opType');
    if (!opType) return;
    
    const pos = getMousePos(e);
    const newId = `node_${Date.now()}`;
    const stepId = `S${String(state.nodes.length + 1).padStart(3, '0')}`;
    
    state.nodes.push({
        id: newId,
        stepId: stepId,
        taskName: '新节点',
        opType: opType,
        predecessors: '',
        stdDuration: 30,
        timeVariance: 5,
        workLoadScore: 5,
        reworkProb: 0,
        requiredWorkers: 1,
        requiredTools: '',
        station: state.stationFilter || 'ST01',
        x: pos.x - 60,
        y: pos.y - 25
    });
    
    renderCanvas();
    showToast('节点已创建，双击编辑', 'success');
}

// 键盘事件
function handleKeyDown(e) {
    if (e.key === 'Delete' && state.selectedNode) {
        deleteSelectedNode();
    }
}
