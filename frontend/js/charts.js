/**
 * 图表模块 - 疲劳图表、甘特图
 */

// 全局主题优化：统一文字与边框颜色
if (window.Chart) {
    Chart.defaults.color = '#9ca3af';
    Chart.defaults.borderColor = '#374151';
}

function updateFatigueChart() {
    if (!state.simulationResult) return;
    
    const selectedWorker = document.getElementById('fatigueWorkerSelect').value;
    const fatigueData = state.simulationResult.worker_fatigue_data || state.simulationResult.worker_stats || [];
    
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
    
    let datasets = [];
    
    if (selectedWorker === 'all') {
        datasets = fatigueData.map((worker, idx) => {
            const workerId = worker.worker_id || worker.resource_id;
            const history = worker.fatigue_history || [];
            
            if (history.length > 0) {
                return {
                    label: workerId,
                    data: history.map(h => ({ x: h[0], y: h[1] })),
                    borderColor: colors[idx % colors.length],
                    backgroundColor: 'transparent',
                    tension: 0.3,
                    pointRadius: 0
                };
            } else {
                return {
                    label: workerId,
                    data: [{ x: 0, y: 0 }, { x: state.simulationResult.sim_duration, y: worker.fatigue_level || 0 }],
                    borderColor: colors[idx % colors.length],
                    backgroundColor: 'transparent',
                    tension: 0,
                    pointRadius: 2
                };
            }
        });
    } else {
        const worker = fatigueData.find(w => (w.worker_id || w.resource_id) === selectedWorker);
        if (worker) {
            const history = worker.fatigue_history || [];
            if (history.length > 0) {
                datasets = [{
                    label: selectedWorker,
                    data: history.map(h => ({ x: h[0], y: h[1] })),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2
                }];
            } else {
                datasets = [{
                    label: selectedWorker,
                    data: [{ x: 0, y: 0 }, { x: state.simulationResult.sim_duration, y: worker.fatigue_level || 0 }],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0,
                    pointRadius: 4
                }];
            }
        }
    }
    
    if (fatigueChart) fatigueChart.destroy();
    fatigueChart = new Chart(document.getElementById('fatigueChart'), {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            scales: {
                x: { 
                    type: 'linear',
                    title: { display: true, text: '时间（分钟）', color: '#9ca3af' },
                    ticks: { color: '#9ca3af' }, 
                    grid: { display: false } 
                },
                y: { 
                    min: 0, 
                    max: 100,
                    title: { display: true, text: '疲劳度', color: '#9ca3af' },
                    ticks: { color: '#9ca3af' }, 
                    grid: { display: false } 
                }
            },
            plugins: { 
                legend: { 
                    display: selectedWorker === 'all',
                    labels: { color: '#9ca3af' } 
                } 
            }
        }
    });
}

// ============================================================
// Gantt Chart - 优化版：自适应宽度 + 增大行高
// ============================================================
function initGanttControls(result) {
    const config = getConfigFromUI();
    const totalDays = config.work_days_per_month;
    const hoursPerDay = config.work_hours_per_day;
    
    const startDaySelect = document.getElementById('ganttStartDay');
    const endDaySelect = document.getElementById('ganttEndDay');
    const startHourSelect = document.getElementById('ganttStartHour');
    const endHourSelect = document.getElementById('ganttEndHour');
    
    startDaySelect.innerHTML = '';
    endDaySelect.innerHTML = '';
    for (let d = 1; d <= totalDays; d++) {
        startDaySelect.innerHTML += `<option value="${d}">第${d}天</option>`;
        endDaySelect.innerHTML += `<option value="${d}">第${d}天</option>`;
    }
    
    const actualDays = Math.ceil(result.sim_duration / (hoursPerDay * 60));
    endDaySelect.value = Math.min(Math.max(actualDays, 3), totalDays);
    
    startHourSelect.innerHTML = '';
    endHourSelect.innerHTML = '';
    for (let h = 0; h < hoursPerDay; h++) {
        startHourSelect.innerHTML += `<option value="${h}">${h}:00</option>`;
        endHourSelect.innerHTML += `<option value="${h+1}">${h+1}:00</option>`;
    }
    endHourSelect.value = hoursPerDay;
    
    updateGantt();
}

function updateGantt() {
    if (!state.simulationResult) {
        showToast('请先运行仿真', 'warning');
        return;
    }
    
    const config = getConfigFromUI();
    const hoursPerDay = config.work_hours_per_day;
    const minutesPerDay = hoursPerDay * 60;
    
    const startDay = parseInt(document.getElementById('ganttStartDay').value);
    const startHour = parseInt(document.getElementById('ganttStartHour').value);
    const endDay = parseInt(document.getElementById('ganttEndDay').value);
    const endHour = parseInt(document.getElementById('ganttEndHour').value);
    
    const startMinute = (startDay - 1) * minutesPerDay + startHour * 60;
    const endMinute = (endDay - 1) * minutesPerDay + endHour * 60;
    const totalMinutes = endMinute - startMinute;
    
    // ===== 计算hourWidth =====
    const engineRight = document.getElementById('engineGanttRight');
    const availableWidth = engineRight ? (engineRight.clientWidth - 20) : 800;
    
    const totalHours = totalMinutes / 60;
    // 最小30px保证可读性，无上限让其自适应
    const hourWidth = Math.max(30, availableWidth / totalHours);
    
    renderTimeline('ganttTimeline', startDay, startHour, endDay, endHour, hoursPerDay, hourWidth);
    renderTimeline('workerGanttTimeline', startDay, startHour, endDay, endHour, hoursPerDay, hourWidth);
    
    renderEngineGantt(startMinute, endMinute, hoursPerDay, hourWidth);
    renderWorkerGantt(startMinute, endMinute, hoursPerDay, hourWidth);
    
    // 设置滚动同步
    setupScrollSync();
}

// 设置左右、上下滚动同步
function setupScrollSync() {
    // 发动机甘特图滚动同步
    const engineLabels = document.getElementById('engineGanttLabels');
    const engineBody = document.getElementById('ganttBody');
    
    if (engineLabels && engineBody) {
        engineBody.onscroll = function() {
            engineLabels.scrollTop = engineBody.scrollTop;
        };
        engineLabels.onscroll = function() {
            engineBody.scrollTop = engineLabels.scrollTop;
        };
    }
    
    // 工人甘特图滚动同步
    const workerLabels = document.getElementById('workerGanttLabels');
    const workerBody = document.getElementById('workerGanttBody');
    
    if (workerLabels && workerBody) {
        workerBody.onscroll = function() {
            workerLabels.scrollTop = workerBody.scrollTop;
        };
        workerLabels.onscroll = function() {
            workerBody.scrollTop = workerLabels.scrollTop;
        };
    }
}

function renderTimeline(containerId, startDay, startHour, endDay, endHour, hoursPerDay, hourWidth) {
    const timeline = document.getElementById(containerId);
    timeline.innerHTML = '';
    
    for (let d = startDay; d <= endDay; d++) {
        const dayStartHour = d === startDay ? startHour : 0;
        const dayEndHour = d === endDay ? endHour : hoursPerDay;
        
        for (let h = dayStartHour; h < dayEndHour; h++) {
            const cell = document.createElement('div');
            cell.className = 'gantt-time-cell' + (h === 0 ? ' day-start' : '');
            cell.style.width = hourWidth + 'px';
            cell.style.minWidth = hourWidth + 'px';
            cell.textContent = `D${d} ${h}h`;
            timeline.appendChild(cell);
        }
    }
}

function renderEngineGantt(startMinute, endMinute, hoursPerDay, hourWidth) {
    const events = state.simulationResult.gantt_events.filter(e => 
        e.end_time > startMinute && e.start_time < endMinute
    );
    
    const totalWidth = (endMinute - startMinute) / 60 * hourWidth;
    
    const engineGroups = {};
    events.forEach(e => {
        const key = `Engine ${e.engine_id}`;
        if (!engineGroups[key]) engineGroups[key] = [];
        engineGroups[key].push(e);
    });
    
    const labels = document.getElementById('engineGanttLabels');
    const body = document.getElementById('ganttBody');
    labels.innerHTML = '';
    body.innerHTML = '';
    
    const sortedEngines = Object.entries(engineGroups).sort((a, b) => {
        return parseInt(a[0].split(' ')[1]) - parseInt(b[0].split(' ')[1]);
    });
    
    sortedEngines.forEach(([label, evts]) => {
        // 左侧标签
        const labelRow = document.createElement('div');
        labelRow.className = 'gantt-left-row';
        labelRow.textContent = label;
        labels.appendChild(labelRow);
        
        // 右侧内容
        const row = document.createElement('div');
        row.className = 'gantt-row';
        
        const rowContent = document.createElement('div');
        rowContent.className = 'gantt-row-content';
        rowContent.style.width = totalWidth + 'px';
        
        evts.forEach(evt => {
            const bar = createGanttBar(evt, startMinute, endMinute, hourWidth);
            rowContent.appendChild(bar);
        });
        
        row.appendChild(rowContent);
        body.appendChild(row);
    });
}

function renderWorkerGantt(startMinute, endMinute, hoursPerDay, hourWidth) {
    const events = state.simulationResult.gantt_events.filter(e => 
        e.end_time > startMinute && e.start_time < endMinute
    );
    
    const totalWidth = (endMinute - startMinute) / 60 * hourWidth;
    
    const workerGroups = {};
    events.forEach(e => {
        if (e.worker_ids && e.worker_ids.length > 0) {
            e.worker_ids.forEach(workerId => {
                if (!workerGroups[workerId]) workerGroups[workerId] = [];
                workerGroups[workerId].push({ ...e, displayWorker: workerId });
            });
        }
    });
    
    const labels = document.getElementById('workerGanttLabels');
    const body = document.getElementById('workerGanttBody');
    labels.innerHTML = '';
    body.innerHTML = '';
    
    const sortedWorkers = Object.keys(workerGroups).sort((a, b) => {
        return parseInt(a.replace(/\D/g, '')) - parseInt(b.replace(/\D/g, ''));
    });
    
    const config = getConfigFromUI();
    
    // 先渲染有任务的工人
    sortedWorkers.forEach(workerId => {
        // 左侧标签
        const labelRow = document.createElement('div');
        labelRow.className = 'gantt-left-row';
        labelRow.textContent = workerId;
        labels.appendChild(labelRow);
        
        // 右侧内容
        const row = document.createElement('div');
        row.className = 'gantt-row';
        
        const rowContent = document.createElement('div');
        rowContent.className = 'gantt-row-content';
        rowContent.style.width = totalWidth + 'px';
        
        workerGroups[workerId].forEach(evt => {
            const bar = createGanttBar(evt, startMinute, endMinute, hourWidth, true);
            rowContent.appendChild(bar);
        });
        
        row.appendChild(rowContent);
        body.appendChild(row);
    });
    
    // 渲染没有任务的工人
    for (let i = 1; i <= config.num_workers; i++) {
        const workerId = `Worker_${String(i).padStart(2, '0')}`;
        if (!workerGroups[workerId]) {
            // 左侧标签
            const labelRow = document.createElement('div');
            labelRow.className = 'gantt-left-row';
            labelRow.textContent = workerId;
            labelRow.style.color = '#6b7280';
            labels.appendChild(labelRow);
            
            // 右侧内容
            const row = document.createElement('div');
            row.className = 'gantt-row';
            
            const rowContent = document.createElement('div');
            rowContent.className = 'gantt-row-content';
            rowContent.style.width = totalWidth + 'px';
            rowContent.innerHTML = '<span style="color: #6b7280; font-size: 0.75rem; padding-left: 10px;">（本时段无任务）</span>';
            
            row.appendChild(rowContent);
            body.appendChild(row);
        }
    }
}

function createWorkerGanttRow(workerId, events, startMinute, endMinute, hourWidth, totalWidth) {
    // 此函数已废弃，逻辑已合并到renderWorkerGantt中
    return null;
}

function createGanttBar(evt, startMinute, endMinute, hourWidth, isWorkerView = false) {
    const bar = document.createElement('div');
    const eventType = evt.event_type.toLowerCase();
    bar.className = 'gantt-bar ' + eventType;
    
    const evtStart = Math.max(evt.start_time, startMinute);
    const evtEnd = Math.min(evt.end_time, endMinute);
    
    const left = (evtStart - startMinute) / 60 * hourWidth;
    const width = Math.max((evtEnd - evtStart) / 60 * hourWidth, 6);
    
    bar.style.left = left + 'px';
    bar.style.width = width + 'px';
    
    const duration = (evt.end_time - evt.start_time).toFixed(0);
    let tooltipText = `${evt.task_name}\n时间: ${evt.start_time.toFixed(0)}-${evt.end_time.toFixed(0)}分钟 (${duration}分钟)\n类型: ${evt.event_type}`;
    if (evt.rework_count > 0) tooltipText += `\n返工次数: ${evt.rework_count}`;
    if (!isWorkerView && evt.worker_ids && evt.worker_ids.length > 0) {
        tooltipText += `\n工人: ${evt.worker_ids.join(', ')}`;
    }
    if (isWorkerView) tooltipText += `\n发动机: Engine ${evt.engine_id}`;
    bar.title = tooltipText;
    
    // 根据宽度决定显示内容
    if (width > 50) {
        bar.textContent = isWorkerView ? `E${evt.engine_id}` : evt.step_id;
    } else if (width > 30) {
        bar.textContent = isWorkerView ? evt.engine_id : evt.step_id.slice(-3);
    }
    
    return bar;
}

function exportGanttCSV() {
    if (!state.simulationResult) {
        showToast('请先运行仿真', 'warning');
        return;
    }
    
    let csv = 'engine_id,step_id,task_name,event_type,start_time,end_time,duration,workers\n';
    state.simulationResult.gantt_events.forEach(e => {
        csv += `${e.engine_id},${e.step_id},"${e.task_name}",${e.event_type},${e.start_time},${e.end_time},${e.end_time - e.start_time},"${(e.worker_ids || []).join(';')}"\n`;
    });
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'gantt_chart.csv';
    a.click();
    URL.revokeObjectURL(url);
    showToast('甘特图CSV已导出', 'success');
}
