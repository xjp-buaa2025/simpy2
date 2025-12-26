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
    
    // 窗口大小变化时重新计算甘特图
    window.addEventListener('resize', () => {
        if (state.simulationResult && document.getElementById('tab-gantt').classList.contains('active')) {
            updateGantt();
        }
    });
    
    console.log('航空发动机装配排产仿真系统 - 已加载');
});
