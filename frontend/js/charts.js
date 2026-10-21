/**
 * 图表模块 - 疲劳图表、甘特图
 */

// 全局主题优化：统一文字与边框颜色
const workerChartView={result:null,page:0,pageSize:40};
const fatigueView={page:0,pageSize:20};
const chartEscape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function renderChartPager(kind,page,size,total){
    const root=document.getElementById(kind+'ChartPager');if(!root)return;
    root.hidden=total<=size;
    document.getElementById(kind+'ChartPageLabel').textContent=total?`${page*size+1}–${Math.min(total,(page+1)*size)} / ${total} 人`:'暂无人员';
    document.getElementById(kind+'ChartPrevious').disabled=page===0;
    document.getElementById(kind+'ChartNext').disabled=(page+1)*size>=total;
}
function changeWorkerChartPage(delta){
    const v=workerChartView;if(!v.result)return;
    v.page=Math.max(0,Math.min(Math.ceil(v.result.worker_stats.length/v.pageSize)-1,v.page+delta));
    updateWorkerChart(v.result);
}
function changeFatigueWorker(){fatigueView.page=0;updateFatigueChart();}
function changeFatiguePage(delta){
    const data=state.simulationResult?.worker_fatigue_data||state.simulationResult?.worker_stats||[];
    fatigueView.page=Math.max(0,Math.min(Math.ceil(data.length/fatigueView.pageSize)-1,fatigueView.page+delta));
    updateFatigueChart();
}
if (window.Chart) {
    Chart.defaults.color = '#78889d';
    Chart.defaults.borderColor = '#e4eaf2';
}

function updateFatigueChart() {
    if (!state.simulationResult) return;

    const selectedWorker = document.getElementById('fatigueWorkerSelect').value;
    const fatigueData = state.simulationResult.worker_fatigue_data || state.simulationResult.worker_stats || [];

    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

    let datasets = [];

    if (selectedWorker === 'all') {
        const start=fatigueView.page*fatigueView.pageSize;
        datasets = fatigueData.slice(start,start+fatigueView.pageSize).map((worker, idx) => {
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
                    data: Number.isFinite(worker.fatigue_level)?[{ x: state.simulationResult.sim_duration, y: worker.fatigue_level }]:[],
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
                    data: Number.isFinite(worker.fatigue_level)?[{ x: state.simulationResult.sim_duration, y: worker.fatigue_level }]:[],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0,
                    pointRadius: 4
                }];
            }
        }
    }

    renderChartPager('fatigue',fatigueView.page,fatigueView.pageSize,selectedWorker==='all'?fatigueData.length:0);

    if (fatigueChart) fatigueChart.destroy();
    fatigueChart = new Chart(document.getElementById('fatigueChart'), {
        type: 'line',
        data: { datasets },
        options: {
            animation: false,
            responsive: true,
            scales: {
                x: {
                    type: 'linear',
                    title: { display: true, text: '时间（分钟）', color: '#78889d' },
                    ticks: { color: '#78889d' },
                    grid: { display: false }
                },
                y: {
                    min: 0,
                    max: 100,
                    title: { display: true, text: '疲劳度', color: '#78889d' },
                    ticks: { color: '#78889d' },
                    grid: { display: false }
                }
            },
            plugins: {
                legend: {
                    display: selectedWorker === 'all',
                    labels: { color: '#78889d' }
                }
            }
        }
    });
}
