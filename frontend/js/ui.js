/**
 * UI模块 - 界面交互、Tab、工具箱、加载状态
 */

// 初始化Tab
function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
}

// 切换Tab
function switchTab(tabId, force = false) {
    if(!force&&tabId!=='editor'&&typeof guardAreaTransition==='function'){guardAreaTransition(()=>switchTab(tabId,true));return;}
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    const tab = document.querySelector(`.tab[data-tab="${tabId}"]`);
    const content = document.getElementById(`tab-${tabId}`);
    
    if (tab) tab.classList.add('active');
    if (content) content.classList.add('active');
    
    // 控制侧边栏显示：只在流程编辑页面显示
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        if (tabId === 'editor') {
            sidebar.classList.add('visible');
        } else {
            sidebar.classList.remove('visible');
        }
    }
    
    if (tabId === 'gantt' && state.simulationResult) {
        updateGantt();
    }
    if (tabId === 'fatigue' && state.simulationResult) {
        updateFatigueChart();
    }
}

// 初始化工具箱（拖拽）
function initToolbox() {
    loadBehaviorColors();
    const toolbox = document.getElementById('behaviorToolbox');
    toolbox.innerHTML = BEHAVIOR_UNITS.map(unit => `
        <div class="toolbox-item" draggable="true" data-type="${unit.type}">
            <div class="toolbox-icon" aria-hidden="true"></div>
            <div class="toolbox-info"><h4>${unit.name}</h4><span>${unit.type} · ${unit.english}</span></div>
            <input class="behavior-color" type="color" data-behavior-color="${unit.type}" aria-label="${unit.name}配色" title="${unit.name}配色：同步所有 ${unit.type} 节点">
        </div>`).join('');
    document.getElementById('nodeOpType').innerHTML = BEHAVIOR_UNITS.map(unit => `<option value="${unit.type}">${unit.type} - ${unit.name}</option>`).join('');
    document.querySelectorAll('.toolbox-item').forEach(item => {
        item.addEventListener('dragstart', e => {
            if (e.target.closest('input')) { e.preventDefault(); return; }
            e.dataTransfer.setData('opType', item.dataset.type);
        });
    });
    toolbox.querySelectorAll('[data-behavior-color]').forEach(input => {
        input.addEventListener('input', () => setBehaviorColor(input.dataset.behaviorColor, input.value));
        input.addEventListener('mousedown', e => e.stopPropagation());
        input.addEventListener('dragstart', e => { e.preventDefault(); e.stopPropagation(); });
    });
    updateBehaviorPalette();
}

function loadBehaviorColors() {
    Object.assign(OP_TYPE_COLORS, DEFAULT_OP_TYPE_COLORS);
    try {
        const saved = JSON.parse(localStorage.getItem('assembly.ui.behaviorColors') || '{}');
        if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return;
        for (const unit of BEHAVIOR_UNITS) {
            if (/^#[0-9a-f]{6}$/i.test(saved[unit.type])) OP_TYPE_COLORS[unit.type] = saved[unit.type];
        }
    } catch {}
}

function updateBehaviorPalette() {
    document.querySelectorAll('.toolbox-item').forEach(item => {
        const color = OP_TYPE_COLORS[item.dataset.type];
        item.style.setProperty('--behavior-color', color);
        item.style.setProperty('--behavior-tint', hexToRgba(color, 0.12));
        const input = item.querySelector('[data-behavior-color]');
        if (input) input.value = color;
    });
}

function setBehaviorColor(type, color) {
    if (!Object.hasOwn(DEFAULT_OP_TYPE_COLORS, type) || !/^#[0-9a-f]{6}$/i.test(color)) return;
    OP_TYPE_COLORS[type] = color;
    try { localStorage.setItem('assembly.ui.behaviorColors', JSON.stringify(OP_TYPE_COLORS)); } catch {}
    updateBehaviorPalette();
    renderCanvas();
}

function resetBehaviorColors() {
    Object.assign(OP_TYPE_COLORS, DEFAULT_OP_TYPE_COLORS);
    try { localStorage.removeItem('assembly.ui.behaviorColors'); } catch {}
    updateBehaviorPalette();
    renderCanvas();
}

// 更新统计信息
function updateStats() {
    document.getElementById('nodeCount').textContent = state.nodes.length;
    document.getElementById('edgeCount').textContent = state.edges.length;
    if(typeof refreshCapacityEditStatus==='function')refreshCapacityEditStatus();
}

// 显示/隐藏加载状态
function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'flex' : 'none';
}

// 初始化配置
function initConfig() {
    renderEquipmentList();
}

// 渲染设备列表
function renderEquipmentList() {
    const list = document.getElementById('equipmentList');
    const equipment = state.config.criticalEquipment;
    
    list.innerHTML = Object.entries(equipment).map(([name, count]) => `
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.5rem; background: var(--bg-secondary); border-radius: 4px; margin-bottom: 0.5rem;">
            <span>${name}</span>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <input type="number" value="${count}" min="1" style="width: 60px; padding: 0.25rem; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-primary);" onchange="state.config.criticalEquipment['${name}'] = parseInt(this.value)">
                <button class="btn btn-danger" style="padding: 0.25rem 0.5rem;" onclick="removeEquipment('${name}')">×</button>
            </div>
        </div>
    `).join('') || '<p class="muted">无</p>';
}

// 添加设备
function addEquipment() {
    const nameInput = document.getElementById('newEquipmentName');
    const countInput = document.getElementById('newEquipmentCount');
    const name = nameInput.value.trim();
    const count = parseInt(countInput.value) || 1;
    
    if (!name) {
        showToast('请输入设备名称', 'warning');
        return;
    }
    
    if (state.config.criticalEquipment[name]) {
        showToast('设备已存在', 'warning');
        return;
    }
    
    state.config.criticalEquipment[name] = count;
    nameInput.value = '';
    countInput.value = '1';
    renderEquipmentList();
    showToast('设备已添加', 'success');
}

// 删除设备
function removeEquipment(name) {
    delete state.config.criticalEquipment[name];
    renderEquipmentList();
    showToast('设备已删除', 'success');
}

// 入场动画初始化：为卡片与通用容器添加淡入与上浮效果
function initAnimations() { /* No hidden cards or entrance transforms in the workbench. */ }
