/** Simulation progress is driven by server model time, never a timer percentage. */
const simulationProgress = { token: 0, visible: false, running: false, percent: null, total: 1, completed: 0,
    started: 0, context: '', timer: null, closeTimer: null, stopPolling: null, previousFocus: null };
const progressElement = id => document.getElementById(id);

function renderSimulationProgress(phase = '正在准备仿真', stage = 'prepare', snapshot = null) {
    const p = simulationProgress, known = Number.isFinite(p.percent);
    progressElement('simulationProgressPhase').textContent = phase;
    progressElement('simulationProgressContext').textContent = p.context || '工艺流程 · 资源调度 · 人因对比';
    progressElement('simulationProgressValue').textContent = known ? `${Math.floor(p.percent)}%` : stage === 'failed' ? '未完成' : '运行中';
    const bar = progressElement('simulationProgressBar');
    bar.classList.toggle('indeterminate', !known);
    bar.setAttribute('aria-valuetext', known ? `${Math.floor(p.percent)}%，${phase}` : phase);
    if (known) bar.setAttribute('aria-valuenow', Math.floor(p.percent));
    else bar.removeAttribute('aria-valuenow');
    progressElement('simulationProgressFill').style.width = known ? `${p.percent}%` : '36%';
    const active = { prepare: 0, main: 1, comparison: 1, results: 2, complete: 3, failed: -1 }[stage] ?? 1;
    document.querySelectorAll('[data-progress-step]').forEach((el, index) => {
        el.classList.toggle('active', index === active);
        el.classList.toggle('done', index < active);
    });
    if (snapshot?.total_minutes > 0) {
        progressElement('simulationProgressDetail').textContent = `当前阶段已推进 ${(snapshot.simulation_minute / 60).toFixed(1)} / ${(snapshot.total_minutes / 60).toFixed(1)} 工作小时`;
    }
}

function openSimulationProgress() {
    const p = simulationProgress;
    p.stopPolling?.(); clearInterval(p.timer); clearTimeout(p.closeTimer);
    Object.assign(p, { token: p.token + 1, visible: true, running: true, percent: null,
        total: 1, completed: 0, started: Date.now(), context: '', previousFocus: document.activeElement });
    const overlay = progressElement('loading');
    overlay.hidden = false; overlay.classList.remove('complete', 'failed');
    progressElement('simulationProgressTitle').textContent = '仿真正在进行';
    progressElement('simulationProgressBadge').textContent = '计算中';
    progressElement('simulationProgressClose').hidden = true;
    progressElement('simulationProgressCount').textContent = `${state.nodes.length} 道工序`;
    progressElement('simulationProgressDetail').textContent = '正在提交计算任务，请稍候';
    const tick = () => {
        const seconds = Math.floor((Date.now() - p.started) / 1000);
        progressElement('simulationProgressElapsed').textContent = `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`;
    };
    tick(); p.timer = setInterval(tick, 1000);
    renderSimulationProgress(); overlay.focus({ preventScroll: true });
}

function setSimulationProgressGroup(total) {
    simulationProgress.total = total;
}

function setSimulationProgressPhase(text) {
    simulationProgress.context = text;
    if (simulationProgress.visible) progressElement('simulationProgressContext').textContent = text;
}

function finishSimulationProgress(success, message = '') {
    const p = simulationProgress;
    if (!p.visible || !p.running) return;
    p.running = false; p.stopPolling?.(); clearInterval(p.timer);
    const overlay = progressElement('loading');
    overlay.classList.add(success ? 'complete' : 'failed');
    progressElement('simulationProgressTitle').textContent = success ? '仿真已完成' : '本次仿真未完成';
    progressElement('simulationProgressBadge').textContent = success ? '完成' : '请检查';
    progressElement('simulationProgressClose').hidden = false;
    progressElement('simulationProgressDetail').textContent = success ? '仿真结果已更新，可以查看产出与排产分析' : message || '请检查配置或网络连接后重试，上次有效结果仍然保留';
    if (success) p.percent = 100;
    renderSimulationProgress(success ? '计算与结果整理完成' : '运行失败', success ? 'complete' : 'failed');
    if (success) p.closeTimer = setTimeout(closeSimulationProgress, 1100);
    else progressElement('simulationProgressClose').focus();
}

function closeSimulationProgress() {
    const p = simulationProgress;
    if (p.running) return;
    clearTimeout(p.closeTimer); clearInterval(p.timer); p.stopPolling?.();
    p.visible = false; progressElement('loading').hidden = true;
    if (p.previousFocus?.isConnected) p.previousFocus.focus({ preventScroll: true });
}

async function requestSimulationRun(payload) {
    const p = simulationProgress, token = p.token, index = p.completed;
    const progressId = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `run_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const controller = new AbortController();
    let stopped = false, timer;
    const stop = () => { stopped = true; clearTimeout(timer); controller.abort(); };
    p.stopPolling = stop;
    const poll = async () => {
        let delay = 500;
        try {
            const response = await fetch(`/api/simulation/progress/${progressId}`, { signal: controller.signal, cache: 'no-store' });
            const data = await response.json();
            if (stopped || token !== p.token) return;
            // Older servers still run normally with an honest indeterminate bar.
            if (response.status === 404 && ['Not Found', 'NotFound'].includes(data.detail)) return;
            if (response.ok && data.success && Number.isFinite(data.data?.percent)) {
                const snapshot = data.data;
                const percent = Math.min(99, (index + snapshot.percent / 100) / p.total * 100);
                p.percent = Math.max(p.percent ?? 0, percent);
                const receiving = snapshot.status === 'completed';
                const stage = index < p.total - 1 && ['results', 'complete'].includes(snapshot.stage) ? 'comparison' : receiving ? 'results' : snapshot.stage;
                renderSimulationProgress(receiving ? '正在接收仿真结果' : snapshot.phase, stage, snapshot);
            }
        } catch (error) {
            if (stopped || token !== p.token) return;
            delay = 2000;
        }
        if (!stopped && token === p.token) timer = setTimeout(poll, delay);
    };
    timer = setTimeout(poll, 150);
    progressElement('simulationProgressDetail').textContent = '正在计算仿真时间与资源调度';
    try {
        const response = await fetch('/api/simulation/run', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, progress_id: progressId }) });
        const data = await response.json();
        if (!response.ok) throw Error(data.message || '仿真请求失败，请检查输入或服务连接');
        if (data.success && token === p.token) {
            p.completed = index + 1;
            p.percent = Math.max(p.percent ?? 0, Math.min(99, p.completed / p.total * 100));
            renderSimulationProgress(p.completed < p.total ? '基准计算完成，准备评估候选方案' : '正在更新结果视图', p.completed < p.total ? 'comparison' : 'results');
        }
        return data;
    } finally {
        stop();
        if (p.stopPolling === stop) p.stopPolling = null;
    }
}

document.addEventListener('keydown', event => {
    const p = simulationProgress;
    if (!p.visible) return;
    if (event.key === 'Escape' && !p.running) closeSimulationProgress();
    if (event.key === 'Tab') {
        event.preventDefault();
        (p.running ? progressElement('loading') : progressElement('simulationProgressClose')).focus();
    }
});
