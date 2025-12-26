/**
 * 节点编辑器模块
 */

// 打开节点编辑模态框
function openNodeModal(node) {
    state.editingNode = node;
    
    document.getElementById('nodeStepId').value = node.stepId;
    document.getElementById('nodeTaskName').value = node.taskName;
    document.getElementById('nodeOpType').value = node.opType;
    document.getElementById('nodeStdDuration').value = node.stdDuration;
    document.getElementById('nodeTimeVariance').value = node.timeVariance;
    document.getElementById('nodeWorkLoad').value = node.workLoadScore;
    document.getElementById('nodeReworkProb').value = node.reworkProb;
    document.getElementById('nodeWorkers').value = node.requiredWorkers;
    document.getElementById('nodeTools').value = node.requiredTools;
    document.getElementById('nodePredecessors').value = node.predecessors;
    
    // 填充工位选项
    const stationSelect = document.getElementById('nodeStation');
    stationSelect.innerHTML = '<option value="">-- 请选择工位 --</option>';
    state.stations.forEach(st => {
        const opt = document.createElement('option');
        opt.value = st.id;
        opt.textContent = `${st.id} - ${st.name}`;
        opt.style.color = st.color;
        stationSelect.appendChild(opt);
    });
    stationSelect.value = node.station || '';
    
    document.getElementById('nodeModal').classList.add('active');
}

// 关闭节点编辑模态框
function closeNodeModal() {
    document.getElementById('nodeModal').classList.remove('active');
    state.editingNode = null;
}

// 保存节点
function saveNode() {
    if (!state.editingNode) return;
    
    const node = state.editingNode;
    const oldStepId = node.stepId;
    const newStepId = document.getElementById('nodeStepId').value;
    
    // 验证工位（必填）
    const station = document.getElementById('nodeStation').value;
    if (!station) {
        showToast('请选择工位', 'warning');
        return;
    }
    
    node.stepId = newStepId;
    node.taskName = document.getElementById('nodeTaskName').value;
    node.opType = document.getElementById('nodeOpType').value;
    node.stdDuration = parseFloat(document.getElementById('nodeStdDuration').value) || 30;
    node.timeVariance = parseFloat(document.getElementById('nodeTimeVariance').value) || 0;
    node.workLoadScore = parseInt(document.getElementById('nodeWorkLoad').value) || 5;
    node.reworkProb = parseFloat(document.getElementById('nodeReworkProb').value) || 0;
    node.requiredWorkers = parseInt(document.getElementById('nodeWorkers').value) || 1;
    node.requiredTools = document.getElementById('nodeTools').value;
    node.predecessors = document.getElementById('nodePredecessors').value;
    node.station = station;
    
    // 更新引用
    if (oldStepId !== newStepId) {
        state.nodes.forEach(n => {
            if (n.predecessors) {
                n.predecessors = n.predecessors.split(';')
                    .map(p => p.trim() === oldStepId ? newStepId : p)
                    .join(';');
            }
        });
    }
    
    rebuildEdges();
    closeNodeModal();
    renderCanvas();
    showToast('节点已保存', 'success');
}

// 删除节点
function deleteNode() {
    if (!state.editingNode) return;
    
    const nodeId = state.editingNode.id;
    const stepId = state.editingNode.stepId;
    
    state.nodes = state.nodes.filter(n => n.id !== nodeId);
    state.edges = state.edges.filter(e => e.from !== nodeId && e.to !== nodeId);
    
    // 清理引用
    state.nodes.forEach(n => {
        if (n.predecessors) {
            n.predecessors = n.predecessors.split(';')
                .filter(p => p.trim() !== stepId)
                .join(';');
        }
    });
    
    state.selectedNode = null;
    closeNodeModal();
    renderCanvas();
    showToast('节点已删除', 'success');
}

// 删除选中节点
function deleteSelectedNode() {
    if (!state.selectedNode) return;
    state.editingNode = state.selectedNode;
    deleteNode();
}

// 重建边
function rebuildEdges() {
    state.edges = [];
    const nodeMap = {};
    state.nodes.forEach(n => nodeMap[n.stepId] = n);
    
    state.nodes.forEach(node => {
        if (node.predecessors) {
            node.predecessors.split(';').forEach(predId => {
                predId = predId.trim();
                if (predId && nodeMap[predId]) {
                    state.edges.push({
                        from: nodeMap[predId].id,
                        to: node.id
                    });
                }
            });
        }
    });
}
