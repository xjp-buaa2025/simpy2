/**
 * 画布模块 - 流程图编辑器
 */

const PROCESS_CANVAS_FONT = '"Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif';
const CANVAS_MIN_SCALE = 0.08;
const CANVAS_MAX_SCALE = 3;
let canvasPixelRatioQuery = null;

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
    canvas.addEventListener('wheel', handleCanvasWheel, { passive: false });
    canvas.addEventListener('dragover', e => e.preventDefault());
    canvas.addEventListener('drop', handleCanvasDrop);
    document.addEventListener('keydown', handleKeyDown);
    window.addEventListener('mouseup',e=>{if(e.target!==canvas&&(isDragging||isConnecting||dragNode||dragStationContainer))handleCanvasMouseUp(e);});
    if(typeof ResizeObserver!=='undefined')new ResizeObserver(resizeCanvas).observe(canvas.parentElement);
    watchCanvasPixelRatio();
}

// All layout and pointer coordinates stay in CSS pixels; only the bitmap uses DPR.
function getCanvasViewport() {
    const rect = canvas.getBoundingClientRect();
    return { width: rect.width, height: rect.height };
}

function getCanvasContentTop() {
    const { height } = getCanvasViewport();
    const toolbar = canvas.parentElement.querySelector('.canvas-toolbar');
    return Math.min(height, toolbar ? toolbar.offsetTop + toolbar.offsetHeight + 16 : 0);
}

function getCanvasContentCenter() {
    const { width, height } = getCanvasViewport();
    const top = getCanvasContentTop();
    return { x: width / 2, y: top + (height - top) / 2 };
}

function watchCanvasPixelRatio() {
    if (!window.matchMedia) return;
    if (canvasPixelRatioQuery) canvasPixelRatioQuery.removeEventListener('change', handleCanvasPixelRatioChange);
    canvasPixelRatioQuery = window.matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
    canvasPixelRatioQuery.addEventListener('change', handleCanvasPixelRatioChange);
}

function handleCanvasPixelRatioChange() {
    resizeCanvas();
    watchCanvasPixelRatio();
}

function updateCanvasZoomControls() {
    const label = document.getElementById('canvasZoomLabel');
    if (label) label.textContent = `${Math.round(scale * 100)}%`;
    const zoomOut = document.getElementById('canvasZoomOut');
    const zoomIn = document.getElementById('canvasZoomIn');
    if (zoomOut) zoomOut.disabled = scale <= CANVAS_MIN_SCALE;
    if (zoomIn) zoomIn.disabled = scale >= CANVAS_MAX_SCALE;
}

function setCanvasZoom(nextScale, anchor = getCanvasContentCenter()) {
    const { width, height } = getCanvasViewport();
    if (width <= 0 || height <= 0 || !Number.isFinite(nextScale)) return;
    const next = Math.min(CANVAS_MAX_SCALE, Math.max(CANVAS_MIN_SCALE, nextScale));
    canvasOffset.x = anchor.x - (anchor.x - canvasOffset.x) * next / scale;
    canvasOffset.y = anchor.y - (anchor.y - canvasOffset.y) * next / scale;
    scale = next;
    renderCanvas();
}

function zoomCanvas(factor) {
    setCanvasZoom(scale * factor);
}

function resetCanvasZoom() {
    setCanvasZoom(1);
}

function isAreaVisible(aid) {return state.showStationContainers&&(!state.stationFilter||state.stationFilter===aid);}
function isNodeVisible(node) {
    if(state.stationFilter&&node.station!==state.stationFilter)return false;
    return !(state.showStationContainers&&stationContainers[node.station]?.collapsed);
}
function cancelCanvasGesture(){isConnecting=false;connectStart=null;isDragging=false;dragNode=null;dragStationContainer=null;}
function areaHeaderAction(pos,entry){
    if(!entry)return '';
    const c=entry.container,w=c.collapsed?200:c.width;
    if(pos.y<c.y||pos.y>c.y+36)return '';
    if(pos.x>=c.x+w-36&&pos.x<=c.x+w-8)return 'fold';
    if(pos.x>=c.x+w-72&&pos.x<c.x+w-40)return 'properties';
    return '';
}
function fitCanvas(){
    const { width, height } = getCanvasViewport();
    if (width <= 0 || height <= 0) return;
    const boxes=[];
    for(const [aid,c] of Object.entries(stationContainers))if(isAreaVisible(aid))boxes.push({x:c.x,y:c.y,w:c.collapsed?200:c.width,h:c.collapsed?80:c.height});
    for(const n of state.nodes)if(isNodeVisible(n))boxes.push({x:n.x,y:n.y,w:120,h:50});
    if(!boxes.length)return;
    const left=Math.min(...boxes.map(b=>b.x)),top=Math.min(...boxes.map(b=>b.y)),right=Math.max(...boxes.map(b=>b.x+b.w)),bottom=Math.max(...boxes.map(b=>b.y+b.h));
    const marginTop=getCanvasContentTop(),availableHeight=Math.max(1,height-marginTop-32);
    scale=Math.min(2,Math.max(CANVAS_MIN_SCALE,Math.min(Math.max(1,width-64)/Math.max(1,right-left),availableHeight/Math.max(1,bottom-top))));
    canvasOffset={x:(width-(right-left)*scale)/2-left*scale,y:marginTop+(availableHeight-(bottom-top)*scale)/2-top*scale};renderCanvas();
}

// 调整画布大小
function resizeCanvas() {
    const { width, height } = getCanvasViewport();
    if (width <= 0 || height <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    const pixelWidth = Math.max(1, Math.round(width * dpr));
    const pixelHeight = Math.max(1, Math.round(height * dpr));
    if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
    if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
    renderCanvas();
}

// 切换布局模式
function setCanvasLayoutMode(mode) {
    state.layoutMode = mode;
    const button = document.getElementById('layoutModeToggle');
    if (state.layoutMode === 'station-only') {
        button.textContent = '📋 详细视图';
        button.classList.remove('btn-secondary');
        button.classList.add('btn-primary');
    } else {
        button.textContent = '🏢 工区层级视图';
        button.classList.remove('btn-primary');
        button.classList.add('btn-secondary');
    }
}

function toggleLayoutMode() {
    setCanvasLayoutMode(state.layoutMode === 'normal' ? 'station-only' : 'normal');
    renderCanvas();
    showToast(`已切换到${state.layoutMode === 'station-only' ? '工区层级' : '详细'}视图`, 'success');
}

// 渲染画布
function renderCanvas() {
    const { width, height } = getCanvasViewport();
    if (width <= 0 || height <= 0) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(canvas.width / width, 0, 0, canvas.height / height, 0, 0);
    ctx.save();
    ctx.translate(canvasOffset.x, canvasOffset.y);
    ctx.scale(scale, scale);
    
    drawGrid();
    
    // 绘制工位容器
    if (state.showStationContainers) {
        drawStationContainers();
    }
    
    // 在工区层级视图下，绘制工位之间的连线
    if (state.layoutMode === 'station-only') {
        drawStationEdges();
    } else {
        // 绘制节点之间的连线
        state.edges.forEach(edge => {
            const fromNode = state.nodes.find(n => n.id === edge.from);
            const toNode = state.nodes.find(n => n.id === edge.to);
            if (fromNode && toNode && isNodeVisible(fromNode) && isNodeVisible(toNode)) drawEdge(fromNode, toNode);
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
    
    state.nodes.forEach(node=>{if(isNodeVisible(node))drawNode(node,node===state.selectedNode);});
    
    ctx.restore();
    updateCanvasZoomControls();
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
        
        if (fromContainer && toContainer && isAreaVisible(conn.fromStation) && isAreaVisible(conn.toStation)) {
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
    const stale=typeof isCapacityStale==='function'&&isCapacityStale();
    Object.entries(stationContainers).forEach(([stationId, container]) => {
        const { x, y, width, height, color, name } = container;
        const isCollapsed = container.collapsed;
        
        // 在工区层级视图下，始终绘制工位容器（包括折叠状态）
        if (!isAreaVisible(stationId)) return;
        
        // 容器背景
        ctx.fillStyle = hexToRgba(color, isCollapsed ? 0.1 : 0.045);
        ctx.beginPath();
        ctx.roundRect(x, y, isCollapsed ? 200 : width, isCollapsed ? 80 : height, 12);
        ctx.fill();
        
        // 容器边框
        ctx.strokeStyle = hexToRgba(color, isCollapsed ? 0.8 : 0.5);
        ctx.lineWidth = state.selectedArea===stationId ? 4 : isCollapsed ? 3 : 2;
        if(state.selectedArea===stationId)ctx.strokeStyle=color;
        ctx.stroke();
        
        // 标题栏背景
        ctx.fillStyle = hexToRgba(color, 0.09);
        ctx.beginPath();
        ctx.roundRect(x, y, isCollapsed ? 200 : width, 36, [12, 12, 0, 0]);
        ctx.fill();
        
        const w=isCollapsed?200:width;
        ctx.fillStyle='#253b56';ctx.font=`bold 14px ${PROCESS_CANVAS_FONT}`;ctx.textAlign='left';
        let title=name;while(title.length>1&&ctx.measureText(title).width>w-100)title=title.slice(0,-1);
        if(title!==name)title+='…';ctx.fillText(title,x+12,y+24);
        ctx.font=`16px ${PROCESS_CANVAS_FONT}`;ctx.textAlign='center';ctx.fillText('ⓘ',x+w-56,y+24);ctx.fillText(isCollapsed?'▸':'▾',x+w-22,y+24);
        const count=state.nodes.filter(n=>n.station===stationId).length;
        ctx.font=`11px ${PROCESS_CANVAS_FONT}`;ctx.textAlign='left';ctx.fillStyle=stale?'#946420':'#52677f';
        ctx.fillText(`${count} 道工序 · ${stale?'待重新仿真':'右键查看属性'}`,x+12,y+55);

    });
}

// 绘制网格
function drawGrid() {
    const { width, height } = getCanvasViewport();
    const gridSize = 20;
    ctx.strokeStyle = '#e8edf4';
    ctx.lineWidth = 0.5;
    
    const startX = -canvasOffset.x / scale;
    const startY = -canvasOffset.y / scale;
    const endX = (width - canvasOffset.x) / scale;
    const endY = (height - canvasOffset.y) / scale;
    
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
    const typeColor = typeof OP_TYPE_COLORS === 'undefined' ? '#64748b' : OP_TYPE_COLORS[node.opType] || '#64748b';
    
    // 阴影
    ctx.shadowColor = 'rgba(48, 73, 106, 0.06)';
    ctx.shadowBlur = 4;
    ctx.shadowOffsetX = 2;
    ctx.shadowOffsetY = 2;
    
    // 节点背景
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, 8);
    ctx.fill();
    
    ctx.shadowColor = 'transparent';
    ctx.fillStyle = hexToRgba(typeColor, 0.12);
    ctx.fill();
    
    ctx.strokeStyle=typeColor;ctx.lineWidth=1.5;ctx.stroke();
    // 选中边框
    if (selected) {
        ctx.strokeStyle = '#367bea';
        ctx.lineWidth = 3;
        ctx.stroke();
    }
    
    // 节点文字
    ctx.fillStyle = '#253b56';
    ctx.font = `bold 14px ${PROCESS_CANVAS_FONT}`;
    ctx.textAlign = 'center';
    const heading = `${node.opType} · ${node.stepId}`;
    if (ctx.measureText(heading).width > width - 12) ctx.font = `bold 11px ${PROCESS_CANVAS_FONT}`;
    ctx.fillText(heading, x + width/2, y + 20);
    
    ctx.font = `12px ${PROCESS_CANVAS_FONT}`;
    ctx.fillStyle = '#334155';
    let displayName = node.taskName;
    if (ctx.measureText(displayName).width > width - 16) {
        while (displayName.length && ctx.measureText(displayName + '…').width > width - 16) displayName = displayName.slice(0, -1);
        displayName += '…';
    }
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
        if (!isNodeVisible(n)) continue;
        if (pos.x >= n.x && pos.x <= n.x + 120 && pos.y >= n.y && pos.y <= n.y + 50) {
            return n;
        }
    }
    return null;
}

// 查找鼠标位置的工位容器
function findStationContainerAt(pos) {
    for (const [stationId, container] of Object.entries(stationContainers).reverse()) {
        // 在工区层级视图下，即使容器折叠也要检查点击
        if (!isAreaVisible(stationId)) continue;
        
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
    if(typeof workbenchBusy!=='undefined'&&workbenchBusy)return;
    if(typeof canvasPress!=='undefined')canvasPress={x:e.clientX,y:e.clientY};
    if(e.button!==0){cancelCanvasGesture();return;}
    const pos = getMousePos(e);
    const node = findNodeAt(pos);
    const stationContainer = findStationContainerAt(pos);
    const action=areaHeaderAction(pos,stationContainer);
    if(action){cancelCanvasGesture();if(action==='fold')toggleStationContainer(stationContainer.stationId);else openAreaInspector(stationContainer.stationId);return;}
    
    if ((e.shiftKey || (typeof canvasLinkTool!=='undefined'&&canvasLinkTool)) && node) {
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
        state.selectedArea = stationContainer.stationId;
        
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
        showToast(`${container.collapsed ? '已折叠' : '已展开'}工区: ${container.name}`, 'success');
    }
}

// 鼠标移动事件
function handleCanvasMouseMove(e) {
    lastMouseEvent = e;
    if(typeof canvasPress!=='undefined'&&canvasPress&&(dragNode||dragStationContainer)&&Math.hypot(e.clientX-canvasPress.x,e.clientY-canvasPress.y)<4)return;
    
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
    if(e.button!==0){cancelCanvasGesture();renderCanvas();return;}
    const clickedNode=dragNode;
    const simpleClick=typeof canvasPress!=='undefined'&&canvasPress&&Math.hypot(e.clientX-canvasPress.x,e.clientY-canvasPress.y)<4;
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
    if(simpleClick&&clickedNode)openNodeModal(clickedNode);
    if(typeof canvasPress!=='undefined')canvasPress=null;
}

// 双击事件
function handleCanvasDblClick(e) {
    if(e.button!==0)return;
    const pos = getMousePos(e);
    const node = findNodeAt(pos);
    const stationContainer = findStationContainerAt(pos);
    
    if(areaHeaderAction(pos,stationContainer))return;
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
                // 在工区层级视图下，双击标题栏展开/收起工位
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
    e.preventDefault();cancelCanvasGesture();
    const pos=getMousePos(e),node=findNodeAt(pos),container=findStationContainerAt(pos);
    const aid=node?.station||container?.stationId;
    if(aid)openAreaInspector(aid);
}

// All name edits share the inspector save path and update every displayed name.
function editStationName(stationId){openAreaInspector(stationId);document.getElementById('areaName')?.focus();}

// 滚轮缩放
function handleCanvasWheel(e) {
    e.preventDefault();
    if (!e.deltaY) return;
    const rect = canvas.getBoundingClientRect();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setCanvasZoom(scale * delta, { x: e.clientX - rect.left, y: e.clientY - rect.top });
}

// 拖放事件
function handleCanvasDrop(e) {
    if(typeof workbenchBusy!=='undefined'&&workbenchBusy)return;
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
    if(typeof workbenchBusy!=='undefined'&&workbenchBusy)return;
    if(e.target?.closest?.('input,textarea,select,[contenteditable=true]')||document.querySelector('.modal-overlay.active'))return;
    if(e.key==='Escape'){cancelCanvasGesture();if(typeof closeAreaInspector==='function')closeAreaInspector();return;}
    if (e.key === 'Delete' && state.selectedNode) {
        deleteSelectedNode();
    }
}
