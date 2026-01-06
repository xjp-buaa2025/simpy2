/**
 * CSV导入导出和数据处理模块
 */

// 导入CSV
function importCSV() {
    document.getElementById('csvFileInput').click();
}

// 处理CSV导入
function handleCSVImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    fetch('/api/process/parse-csv', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            loadProcessData(data.data);
            showToast('CSV导入成功', 'success');
        } else {
            showToast(data.message || '导入失败', 'error');
        }
    })
    .catch(err => {
        showToast('导入失败', 'error');
    });
    
    event.target.value = '';
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
        name: '工艺流程',
        description: '',
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
            x: n.x,
            y: n.y
        }))
    };
}

// 获取UI配置
function getConfigFromUI() {
    return {
        work_hours_per_day: parseInt(document.getElementById('workHoursPerDay').value),
        work_days_per_month: parseInt(document.getElementById('workDaysPerMonth').value),
        num_workers: parseInt(document.getElementById('numWorkers').value),
        target_output: parseInt(document.getElementById('targetOutput').value),
        critical_equipment: state.config.criticalEquipment,
        rest_time_threshold: parseInt(document.getElementById('restTimeThreshold').value),
        rest_duration_time: parseInt(document.getElementById('restDurationTime').value),
        rest_load_threshold: parseInt(document.getElementById('restLoadThreshold').value),
        rest_duration_load: parseInt(document.getElementById('restDurationLoad').value),
        pipeline_mode: document.getElementById('pipelineMode').checked,
        station_constraint_mode: document.getElementById('stationConstraintMode').checked
    };
}
