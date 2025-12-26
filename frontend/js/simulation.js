/**
 * 仿真模块
 */

// 运行仿真
function runSimulation() {
    if (state.nodes.length === 0) {
        showToast('请先添加工艺节点', 'warning');
        return;
    }
    
    const config = getConfigFromUI();
    const process = buildProcessDefinition();
    
    showLoading(true);
    
    fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config, process })
    })
    .then(res => res.json())
    .then(data => {
        showLoading(false);
        if (data.success) {
            state.simulationResult = data.data;
            updateResults(data.data);
            switchTab('results');
            showToast(data.message, 'success');
        } else {
            showToast(data.message || '仿真失败', 'error');
        }
    })
    .catch(err => {
        showLoading(false);
        console.error(err);
        showToast('仿真请求失败', 'error');
    });
}

// 更新结果显示
function updateResults(result) {
    // KPI指标
    document.getElementById('kpiEngines').textContent = result.engines_completed;
    document.getElementById('kpiAchievement').textContent = (result.target_achievement_rate * 100).toFixed(1);
    document.getElementById('kpiCycleTime').textContent = (result.avg_cycle_time / 60).toFixed(1);
    document.getElementById('kpiPassRate').textContent = (result.quality_stats.first_pass_rate * 100).toFixed(1);
    
    const hfStats = result.human_factors_stats || {};
    document.getElementById('kpiRestTime').textContent = (hfStats.total_rest_time || 0).toFixed(0);
    document.getElementById('kpiHighIntensity').textContent = hfStats.total_high_intensity_exposure || 0;
    
    // 统计数据
    document.getElementById('statInspections').textContent = result.quality_stats.total_inspections;
    document.getElementById('statReworks').textContent = result.quality_stats.total_reworks;
    document.getElementById('statReworkTime').textContent = (result.quality_stats.rework_time_total || 0).toFixed(1) + '分钟';
    document.getElementById('statDuration').textContent = (result.sim_duration / 60).toFixed(1) + '小时';
    
    // 对比表格
    updateComparisonTable(result);
    
    // 瓶颈分析
    analyzeBottlenecks(result);
    
    // 设备详情
    updateEquipmentDetails(result);
    
    // 工位分析
    analyzeStationStatistics(result);
    
    // 工人图表
    updateWorkerChart(result);
    
    // 设备图表
    updateEquipmentChart(result);
    
    // 疲劳图表
    initFatigueSelect(result);
    updateFatigueChart();
    
    // 甘特图
    initGanttControls(result);
}

// 更新工人图表
function updateWorkerChart(result) {
    const workerLabels = result.worker_stats.map(w => w.resource_id);
    const workerWork = result.worker_stats.map(w => w.work_time || 0);
    const workerRest = result.worker_stats.map(w => w.rest_time || 0);
    const workerIdle = result.worker_stats.map(w => Math.max(0, result.sim_duration - (w.work_time || 0) - (w.rest_time || 0)));
    
    if (workerChart) workerChart.destroy();
    workerChart = new Chart(document.getElementById('workerChart'), {
        type: 'bar',
        data: {
            labels: workerLabels,
            datasets: [
                { label: '工作', data: workerWork, backgroundColor: '#3b82f6', borderRadius: 4 },
                { label: '休息', data: workerRest, backgroundColor: '#a855f7', borderRadius: 4 },
                { label: '空闲', data: workerIdle, backgroundColor: '#374151', borderRadius: 4 }
            ]
        },
        options: {
            responsive: true,
            scales: {
                x: { stacked: true, ticks: { color: '#9ca3af' }, grid: { color: '#374151' } },
                y: { stacked: true, ticks: { color: '#9ca3af' }, grid: { color: '#374151' } }
            },
            plugins: { legend: { labels: { color: '#9ca3af' } } }
        }
    });
}

// 更新设备图表
function updateEquipmentChart(result) {
    const equipLabels = result.equipment_stats.map(e => e.resource_id);
    const equipWork = result.equipment_stats.map(e => e.work_time || 0);
    const equipIdle = result.equipment_stats.map(e => Math.max(0, result.sim_duration - (e.work_time || 0)));
    
    if (equipmentChart) equipmentChart.destroy();
    equipmentChart = new Chart(document.getElementById('equipmentChart'), {
        type: 'bar',
        data: {
            labels: equipLabels,
            datasets: [
                { label: '使用', data: equipWork, backgroundColor: '#10b981', borderRadius: 4 },
                { label: '空闲', data: equipIdle, backgroundColor: '#374151', borderRadius: 4 }
            ]
        },
        options: {
            responsive: true,
            scales: {
                x: { stacked: true, ticks: { color: '#9ca3af' }, grid: { color: '#374151' } },
                y: { stacked: true, ticks: { color: '#9ca3af' }, grid: { color: '#374151' } }
            },
            plugins: { legend: { labels: { color: '#9ca3af' } } }
        }
    });
}

// 初始化疲劳图表选择器
function initFatigueSelect(result) {
    const fatigueSelect = document.getElementById('fatigueWorkerSelect');
    fatigueSelect.innerHTML = '<option value="all">全部工人</option>';
    const fatigueData = result.worker_fatigue_data || result.worker_stats || [];
    fatigueData.forEach(w => {
        const workerId = w.worker_id || w.resource_id;
        fatigueSelect.innerHTML += `<option value="${workerId}">${workerId}</option>`;
    });
}

// 更新对比表格
function updateComparisonTable(result) {
    const comparison = result.no_rest_comparison || {};
    const tbody = document.getElementById('comparisonBody');
    
    if (!comparison.engines_completed) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-secondary);">对比数据不可用</td></tr>';
        return;
    }
    
    const rows = [
        {
            label: '完成产量',
            with: result.engines_completed,
            without: comparison.engines_completed,
            unit: '台'
        },
        {
            label: '平均周期时间',
            with: (result.avg_cycle_time / 60).toFixed(1),
            without: (comparison.avg_cycle_time / 60).toFixed(1),
            unit: '小时'
        },
        {
            label: '一次通过率',
            with: (result.quality_stats.first_pass_rate * 100).toFixed(1),
            without: (comparison.quality_stats?.first_pass_rate * 100 || 0).toFixed(1),
            unit: '%'
        },
        {
            label: '总返工次数',
            with: result.quality_stats.total_reworks,
            without: comparison.quality_stats?.total_reworks || 0,
            unit: '次'
        }
    ];
    
    tbody.innerHTML = rows.map(row => {
        const withVal = parseFloat(row.with);
        const withoutVal = parseFloat(row.without);
        let diff = ((withVal - withoutVal) / withoutVal * 100).toFixed(1);
        let diffClass = 'neutral';
        
        if (row.label === '完成产量' || row.label === '一次通过率') {
            diffClass = diff > 0 ? 'positive' : (diff < 0 ? 'negative' : 'neutral');
        } else {
            diffClass = diff < 0 ? 'positive' : (diff > 0 ? 'negative' : 'neutral');
        }
        
        const diffIcon = diff > 0 ? '↑' : (diff < 0 ? '↓' : '→');
        diff = Math.abs(diff);
        
        return `
            <tr>
                <td>${row.label}</td>
                <td>${row.with} ${row.unit}</td>
                <td>${row.without} ${row.unit}</td>
                <td class="${diffClass}">${diffIcon} ${diff}%</td>
            </tr>
        `;
    }).join('');
}
