// Derived from actual work intervals, including incomplete work at the horizon.
function getLaborMetrics(result) {
 const context=result.evaluation_context||{};
 if(Number.isFinite(context.labor_minutes)&&Number.isFinite(context.peak_working_workers))return context;
 let labor_minutes=0,current=0,peak_working_workers=0;const changes=[];
 for(const e of result.gantt_events||[])if(['NORMAL','REWORK','IN_PROGRESS'].includes(e.event_type)){
  const count=(e.worker_ids||[]).length,duration=e.end_time-e.start_time;
  labor_minutes+=Math.max(0,duration)*count;if(duration>0)changes.push([e.start_time,count],[e.end_time,-count]);
 }
 changes.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);for(const [,delta]of changes){current+=delta;peak_working_workers=Math.max(peak_working_workers,current);}
 return {labor_minutes,peak_working_workers};
}
/**
 * 仿真模块
 */

// 运行仿真
function runSimulation(compare = false) {
    if (state.nodes.length === 0) {
        showToast('请先添加工艺节点', 'warning');
        return;
    }
    
    const config = getConfigFromUI();
    const process = buildProcessDefinition();
    if (typeof validateCapacityRun === 'function' && !validateCapacityRun({config, process}, compare)) return;
    
    showLoading(true);
    
    const stayInEditor = document.getElementById('tab-editor').classList.contains('active');
    const payload = { config, process };
    return (typeof requestSimulationRun === 'function' ? requestSimulationRun(payload) : fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config, process })
    }).then(res => res.json()))
    .then(data => {
        if (data.success) {
            state.simulationResult = data.data;
            updateResults(data.data);
            if (typeof acceptCapacityResult === 'function') acceptCapacityResult(data.data);
            if (!stayInEditor) switchTab('results');
            if (data.data.unity_sync && !data.data.unity_sync.success) {
                showToast('网页仿真已完成，但 Unity 同步失败：' + data.data.unity_sync.message, 'warning');
            } else if (data.data.unity_sync?.mode === 'station_progress_only') {
                showToast('仿真已完成，工位进度数据就绪', 'success');
            } else {
                showToast(data.message, 'success');
            }
        } else {
            if (typeof rejectCapacityResult === 'function') rejectCapacityResult(data.message);
            showToast(data.message || '仿真失败', 'error');
        }
        showLoading(false);
    })
    .catch(err => {
        if (typeof rejectCapacityResult === 'function') rejectCapacityResult(err.message);
        showLoading(false);
        console.error(err);
        showToast('仿真请求失败', 'error');
    });
}

// 更新结果显示
function updateResults(result) {
    const unityNotice = document.getElementById('unitySyncNotice');
    const syncFailed = result.unity_sync && !result.unity_sync.success;
    const stationProgressOnly = result.unity_sync?.mode === 'station_progress_only';
    unityNotice.hidden = !syncFailed && !stationProgressOnly;
    unityNotice.textContent = syncFailed
        ? '网页仿真已完成，但 Unity 同步失败。Unity 保留上一次有效结果。原因：' + result.unity_sync.message
        : stationProgressOnly ? '工位进度数据就绪，可供 Unity 后续接入。' : '';
    if (typeof initStationProgress === 'function') initStationProgress(result);
    // KPI指标
    document.getElementById('kpiEngines').textContent = result.engines_completed;
    const labor=getLaborMetrics(result);
    document.getElementById('kpiLaborMinutes').textContent=labor.labor_minutes.toFixed(1);
    document.getElementById('kpiPeakWorkers').textContent=labor.peak_working_workers;
    document.getElementById('kpiCycleTime').textContent = (result.avg_cycle_time / 60).toFixed(1);
    document.getElementById('kpiPassRate').textContent = Number.isFinite(result.quality_stats.first_pass_rate) ? (result.quality_stats.first_pass_rate * 100).toFixed(1) : '暂无数据';
    
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
    // Gantt is initialized once by the shared result adapter.
}

// 更新工人图表
function updateWorkerChart(result) {
    if(workerChartView.result!==result){workerChartView.result=result;workerChartView.page=0;}
    const start=workerChartView.page*workerChartView.pageSize;
    const workers=result.worker_stats.slice(start,start+workerChartView.pageSize);
    renderChartPager('worker',workerChartView.page,workerChartView.pageSize,result.worker_stats.length);
    const workerLabels = workers.map(w => w.resource_id);
    const workerWork = workers.map(w => w.work_time || 0);
    const workerRest = workers.map(w => w.rest_time || 0);
    const workerIdle = workers.map(w => Math.max(0, result.sim_duration - (w.work_time || 0) - (w.rest_time || 0)));
    
    if (workerChart) workerChart.destroy();
    workerChart = new Chart(document.getElementById('workerChart'), {
        type: 'bar',
        data: {
            labels: workerLabels,
            datasets: [
                { label: '工作', data: workerWork, backgroundColor: '#3b82f6', borderRadius: 4 },
                { label: '休息', data: workerRest, backgroundColor: '#a855f7', borderRadius: 4 },
                { label: '空闲', data: workerIdle, backgroundColor: '#e4eaf2', borderRadius: 4 }
            ]
        },
        options: {
            animation: false,
            responsive: true,
            scales: {
                x: { stacked: true, ticks: { color: '#78889d' }, grid: { color: '#e4eaf2' } },
                y: { stacked: true, ticks: { color: '#78889d' }, grid: { color: '#e4eaf2' } }
            },
            plugins: { legend: { labels: { color: '#78889d' } } }
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
                { label: '空闲', data: equipIdle, backgroundColor: '#e4eaf2', borderRadius: 4 }
            ]
        },
        options: {
            responsive: true,
            scales: {
                x: { stacked: true, ticks: { color: '#78889d' }, grid: { color: '#e4eaf2' } },
                y: { stacked: true, ticks: { color: '#78889d' }, grid: { color: '#e4eaf2' } }
            },
            plugins: { legend: { labels: { color: '#78889d' } } }
        }
    });
}

// 初始化疲劳图表选择器
function initFatigueSelect(result) {
    const fatigueSelect = document.getElementById('fatigueWorkerSelect');
    const fatigueData = result.worker_fatigue_data || result.worker_stats || [];
    // Reassigning innerHTML in a loop reparses every preceding option. A run
    // with thousands of worker records used to block the browser here.
    fatigueSelect.innerHTML = '<option value="all">全部工人</option>'+fatigueData.map(w => {
        const workerId = w.worker_id || w.resource_id;
        return `<option value="${chartEscape(workerId)}">${chartEscape(workerId)}</option>`;
    }).join('');
    fatigueView.page=0;
}

// 更新对比表格
function updateComparisonTable(result) {
 const comparison=result.no_rest_comparison,body=document.getElementById('comparisonBody');
 if(!comparison){body.innerHTML='<tr><td colspan="4">历史结果未记录人因对比</td></tr>';return;}
 const rows=[['完成产出',result.engines_completed,comparison.engines_completed,'台'],['平均周期',result.engines_completed?result.avg_cycle_time/60:null,comparison.engines_completed?comparison.avg_cycle_time/60:null,'小时'],['返工次数',result.quality_stats?.total_reworks,comparison.quality_stats?.total_reworks,'次']];
 const fmt=v=>Number.isFinite(v)?v.toFixed(1):'暂无数据';
 body.innerHTML=rows.map(([label,a,b,unit])=>`<tr><td>${label}</td><td>${fmt(a)} ${unit}</td><td>${fmt(b)} ${unit}</td><td>${!Number.isFinite(a)||!Number.isFinite(b)?'暂无数据':b===0?(a===0?'无变化':'基准为 0'):(100*(a-b)/b).toFixed(1)+'%'}</td></tr>`).join('');
}
