/**
 * 主入口模块 - 初始化
 */

document.addEventListener('DOMContentLoaded', () => {
    // 初始化各模块
    initCanvas();
    initTabs();
    initToolbox();
    initConfig();
    initStationFilter();
    initAnimations();
    loadCurrentScenario();
    
    // 窗口大小变化时重新计算甘特图
    window.addEventListener('resize', () => {
        if (state.simulationResult && document.getElementById('tab-gantt').classList.contains('active')) {
            updateGantt();
        }
    });
    
    console.log('航空发动机装配排产仿真系统 - 已加载');
});

// Restore the newest completed run and its exact process without starting a run.
async function loadCurrentScenario() {
    const initial = JSON.stringify({process:buildProcessDefinition(),config:getConfigFromUI()});
    const untouched = () => !workbenchBusy && !state.simulationResult &&
        !areaDraftDirty() && !nodeInspectorDirty() &&
        initial === JSON.stringify({process:buildProcessDefinition(),config:getConfigFromUI()});
    const read = async url => {
        const response = await fetch(url, {cache:'no-store'});
        const body = await response.json();
        if (!response.ok || !body.success) throw Error(body.message || '读取当前方案失败');
        return body.data;
    };
    try {
        const runs = await read('/api/results/list/all?status=completed&limit=1');
        if (!runs.length) return;
        const result = await read('/api/results/' + encodeURIComponent(runs[0].sim_id));
        const input = result.input_snapshot;
        if (!input?.process?.nodes?.length || !input.config) throw Error('当前结果缺少方案快照');
        ResultView.validate(result);
        if (!untouched()) return;
        const c = input.config;
        loadProcessData(input.process, {capacityModel:capacityClone(c.capacity_model || {enabled:false,areas:{},workstations:{}}),
            automaticWip:c.evaluation?.max_wip ?? null, samplingScheme:c.evaluation?.sampling_scheme || 'legacy'});
        const fields = {workHoursPerDay:'work_hours_per_day',workDaysPerMonth:'work_days_per_month',
            restTimeThreshold:'rest_time_threshold',restDurationTime:'rest_duration_time',
            restLoadThreshold:'rest_load_threshold',restDurationLoad:'rest_duration_load'};
        for (const [id,key] of Object.entries(fields)) if (c[key] != null) document.getElementById(id).value = c[key];
        document.getElementById('pipelineMode').checked = c.pipeline_mode !== false;
        document.getElementById('stationConstraintMode').checked = true;
        document.getElementById('capacityMode').value = c.evaluation?.mode || 'plan';
        document.getElementById('capacityWip').value = '';
        document.getElementById('capacitySeed').value = c.random_seed ?? 42;
        state.config.criticalEquipment = {};
        renderEquipmentList();
        updateStats();
        state.simulationResult = result;
        acceptCapacityResult(result);
        updateResults(result);
        refreshCapacitySignals();
        processImportMessage(`已加载当前方案：${state.nodes.length} 道工序，${state.stations.length} 个工区`);
        refreshHome();
    } catch (error) {
        console.error(error);
        showToast('当前方案自动加载失败：' + error.message, 'warning');
    }
}
