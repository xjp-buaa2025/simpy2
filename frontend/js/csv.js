/**
 * 工艺文件导入、CSV导出和数据处理模块
 */

// 导入CSV
function importCSV() {
    if(typeof guardAreaTransition==='function')guardAreaTransition(()=>document.getElementById('csvFileInput').click());
    else document.getElementById('csvFileInput').click();
}

let processFileImportBusy = false;
function processImportMessage(message, error = false) {
    const notice = document.getElementById('processImportNotice');
    if (notice) { notice.hidden = false; notice.textContent = message; notice.classList.toggle('error', error); }
}
function processResponseError(data) {
    if (Array.isArray(data.data?.errors) && data.data.errors.length) return data.data.errors.join('\n');
    if (Array.isArray(data.detail)) return data.detail.map(e => `${(e.loc || []).join('.')}：${e.msg}`).join('\n');
    return data.message || data.detail || '导入失败';
}
function prepareProcessFileInput(process, config) {
    const input = JSON.parse(JSON.stringify({process, config}));
    const model = input.config.capacity_model ||= {enabled:false};
    model.areas ||= {}; model.workstations ||= {};
    const catalog = processStationCatalog(input.process);
    for (const area of catalog) model.areas[area.id] ||= {label:area.name, equipment:{}, efficiency_multiplier:1, resource_sets:1};
    for (const node of input.process.nodes) {
        const aid = node.area_id || node.station || 'ST01', sid = node.workstation_id;
        if (!sid) continue; // Legacy CSV bindings remain optional when the model is disabled.
        const existing = model.workstations[sid];
        if (existing && existing.area_id !== aid) throw Error(`工序 ${node.step_id}：工位 ${sid} 已属于工区 ${existing.area_id}，与导入工区 ${aid} 冲突`);
        model.workstations[sid] ||= {area_id:aid, label:catalog.find(s => s.id === aid)?.name || sid, capacity:1};
    }
    return input;
}

// Parsing and capacity validation both finish before committing any editor data.
async function importProcessFile(file) {
    if (processFileImportBusy) return;
    processFileImportBusy = true;
    processImportMessage(`正在解析 ${file.name}…`);
    try {
        const formData = new FormData(); formData.append('file', file);
        const response = await fetch('/api/process/parse-file', {method:'POST', body:formData});
        const parsed = await response.json();
        if (!response.ok || !parsed.success) throw Error(processResponseError(parsed));
        const processBefore = JSON.stringify(buildProcessDefinition()), config = getConfigFromUI(), configBefore = JSON.stringify(config);
        const input = prepareProcessFileInput(parsed.data, config);
        processImportMessage('正在校验工位绑定和现有容量配置…');
        const validation = await fetch('/api/simulation/capacity/validate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(input)});
        const checked = await validation.json();
        if (!validation.ok || !checked.success) throw Error(processResponseError(checked));
        if (processBefore !== JSON.stringify(buildProcessDefinition()) || configBefore !== JSON.stringify(getConfigFromUI())) throw Error('校验期间流程或配置已变化，请重新导入');
        if ((typeof areaDraftDirty === 'function' && areaDraftDirty()) || (typeof nodeInspectorDirty === 'function' && nodeInspectorDirty())) throw Error('校验期间产生了未保存修改，请保存或取消修改后重新导入');
        loadProcessData(input.process, {capacityModel:input.config.capacity_model,
            automaticWip:state.capacityAutomaticWip, samplingScheme:state.capacitySamplingScheme});
        if (typeof refreshCapacitySignals === 'function') refreshCapacitySignals();
        const message = `已导入 ${file.name}：${state.nodes.length} 道工序，${state.stations.length} 个工区`;
        processImportMessage(message);showToast(message, 'success');
    } catch (error) {
        processImportMessage(`导入失败，当前流程与配置已保留。\n${error.message}`, true);
        showToast('导入失败：' + error.message, 'error');
    } finally { processFileImportBusy = false; }
}
function handleCSVImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    event.target.value = '';
    if (typeof guardAreaTransition === 'function') guardAreaTransition(() => importProcessFile(file));
    else return importProcessFile(file);
}

// 导出CSV
function exportCSV() {
    const process = buildProcessDefinition();
    
    fetch('/api/process/export-csv', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(process)
    })
    .then(res => res.blob())
    .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'process.csv';
        a.click();
        URL.revokeObjectURL(url);
        showToast('CSV已导出', 'success');
    })
    .catch(err => {
        showToast('导出失败', 'error');
    });
}

// 构建流程定义
function buildProcessDefinition() {
    return {
        name: state.processName || '工艺流程',
        description: state.processDescription || '',
        station_catalog: (state.stations || []).map(s => ({station_id:s.id, area_id:s.id, label:s.name})),
        nodes: state.nodes.map(n => ({
            step_id: n.stepId,
            task_name: n.taskName,
            op_type: n.opType,
            predecessors: n.predecessors,
            std_duration: n.stdDuration,
            time_variance: n.timeVariance,
            work_load_score: n.workLoadScore,
            rework_prob: n.reworkProb,
            required_workers: n.requiredWorkers,
            required_tools: n.requiredTools ? n.requiredTools.split(';').map(t => t.trim()).filter(t => t) : [],
            station: n.station || 'ST01',
            area_id: n.station || 'ST01',
            workstation_id: n.workstationId || '',
            x: n.x,
            y: n.y
        }))
    };
}

// 获取UI配置
function getConfigFromUI() {
    if (typeof syncCapacityEditor === 'function') syncCapacityEditor();
    return {
        work_hours_per_day: parseInt(document.getElementById('workHoursPerDay').value),
        work_days_per_month: parseInt(document.getElementById('workDaysPerMonth').value),
        critical_equipment: state.config.criticalEquipment,
        rest_time_threshold: parseInt(document.getElementById('restTimeThreshold').value),
        rest_duration_time: parseInt(document.getElementById('restDurationTime').value),
        rest_load_threshold: parseInt(document.getElementById('restLoadThreshold').value),
        rest_duration_load: parseInt(document.getElementById('restDurationLoad').value),
        pipeline_mode: document.getElementById('pipelineMode').checked,
        station_constraint_mode: document.getElementById('stationConstraintMode').checked,
        random_seed: Number(document.getElementById('capacitySeed')?.value ?? 42),
        capacity_model: (()=>{const m=JSON.parse(JSON.stringify(state.capacityModel||{enabled:false}));for(const a of Object.values(m.areas||{}))delete a.dedicated_workers;return m;})(),
        evaluation: {
            mode: document.getElementById('capacityMode')?.value || 'plan',
            sampling_scheme: state.capacitySamplingScheme || 'legacy',
            max_wip: document.getElementById('capacityWip')?.value ? Number(document.getElementById('capacityWip').value) : (state.capacityAutomaticWip??null)
        }
    };
}
