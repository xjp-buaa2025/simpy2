/**
 * 工具函数模块
 */

// 显示提示消息
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 颜色转换：HEX to RGBA
function hexToRgba(hex, alpha) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!result) return `rgba(100, 100, 100, ${alpha})`;
    return `rgba(${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}, ${alpha})`;
}

// 格式化时间（分钟转小时）
function formatDuration(minutes) {
    if (minutes < 60) return `${minutes.toFixed(0)}分钟`;
    return `${(minutes / 60).toFixed(1)}小时`;
}

// 格式化百分比
function formatPercent(value) {
    return `${(value * 100).toFixed(1)}%`;
}
