/* Station progress is sampled from release events, never inferred from Gantt durations. */
const stationProgressView = {result:null, token:0, rows:[], page:0, pageSize:100};
const stationProgressEscape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// Used when a saved JSON result is no longer available in the server's result store.
function sampleStationProgress(source, timeMinutes = source?.time_minutes, engineId = '') {
    if (!source || source.schema_version !== 1 || !Array.isArray(source.stations)) throw Error('该结果没有受支持的工位完成记录，请重新仿真');
    const time = Number(timeMinutes);
    if (!Number.isFinite(time) || time < 0 || time > source.time_minutes) throw Error(`仿真时间应在 0～${source.time_minutes} 分钟之间`);
    return {...source, time_minutes:time, stations:source.stations.map(station => ({...station, engines:(station.engines || [])
        .filter(engine => engine.released_at <= time && (!engineId || String(engine.engine_id) === String(engineId)))
        .map(engine => {
            if (!Array.isArray(engine.completion_events)) throw Error('该结果缺少完整工位完成时间线，请重新仿真');
            const seen = new Set(), events = engine.completion_events.filter(event => {
                if (event.completed_at > time || seen.has(event.step_id)) return false;
                seen.add(event.step_id);return true;
            });
            const completedSteps = events.length, minutes = events.reduce((sum,event) => sum + event.std_duration, 0);
            const completed = station.total_steps > 0 && completedSteps === station.total_steps;
            const startedAt = engine.started_at != null && engine.started_at <= time ? engine.started_at : null;
            const {completion_events, ...summary} = engine;
            return {...summary, started_at:startedAt, completed_at:completed ? Math.max(...events.map(e => e.completed_at)) : null,
                completed_steps:completedSteps, completed_standard_minutes:minutes,
                progress:station.total_standard_minutes > 0 ? Math.min(1, Math.max(0, minutes / station.total_standard_minutes)) : completed ? 1 : 0,
                completed, state:completed ? 'completed' : startedAt != null || events.length ? 'in_progress' : 'not_started'};
        })}))};
}
function renderStationProgress(snapshot) {
    stationProgressView.rows=[];stationProgressView.page=0;
    for (const station of snapshot.stations) for (const engine of station.engines) stationProgressView.rows.push({station,engine});
    renderStationProgressPage();
}
function changeStationProgressPage(delta){
    const v=stationProgressView;
    v.page=Math.max(0,Math.min(Math.ceil(v.rows.length/v.pageSize)-1,v.page+delta));
    renderStationProgressPage();
}
function renderStationProgressPage(){
    const root = document.getElementById('stationProgressRows');if (!root) return;
    const v=stationProgressView,start=v.page*v.pageSize,total=v.rows.length;
    const esc = stationProgressEscape, states = {not_started:'未开始',in_progress:'进行中',completed:'已完成'};
    const rows = [];
    for (const {station,engine} of v.rows.slice(start,start+v.pageSize)) {
        const label = station.label && station.label !== station.station_id ? `${station.station_id} ${station.label}` : station.station_id;
        const percent = engine.progress * 100;
        rows.push(`<tr><td>${esc(label)}</td><td>${esc(engine.engine_id)}</td><td><div class="station-progress-reading"><progress max="1" value="${Number(engine.progress)}" aria-label="${esc(label)} ${esc(engine.engine_id)} 进度"></progress><span>${percent.toFixed(1)}%</span></div></td><td>${esc(engine.completed_steps)} / ${esc(station.total_steps)}</td><td>${esc(states[engine.state] || engine.state)}</td></tr>`);
    }
    root.innerHTML = rows.join('') || '<tr><td colspan="5">此时刻没有符合条件的已投产发动机</td></tr>';
    const pager=document.getElementById('stationProgressPager');
    if(pager){
        pager.hidden=total<=v.pageSize;
        document.getElementById('stationProgressPageLabel').textContent=`${total?start+1:0}–${Math.min(total,start+v.pageSize)} / ${total} 条`;
        document.getElementById('stationProgressPrevious').disabled=v.page===0;
        document.getElementById('stationProgressNext').disabled=start+v.pageSize>=total;
    }
}
function initStationProgress(result) {
    stationProgressView.result = result;stationProgressView.token++;
    const select = document.getElementById('stationProgressEngine'), time = document.getElementById('stationProgressTime'), status = document.getElementById('stationProgressStatus'), button = document.getElementById('stationProgressQuery');
    if (!select || !time || !status || !button) return;
    const source = result.station_progress, available = Array.isArray(source?.stations);
    select.innerHTML = '<option value="">全部发动机</option>';
    for (const id of new Set((source?.stations || []).flatMap(s => (s.engines || []).map(e => String(e.engine_id))))) {
        const option = document.createElement('option');option.value = id;option.textContent = id;select.appendChild(option);
    }
    for (const control of [select,time,button]) control.disabled = !available;
    time.value = available ? source.time_minutes : '';time.max = available ? source.time_minutes : '';
    select.onchange = queryStationProgress;button.onclick = queryStationProgress;
    time.onkeydown = event => {if (event.key === 'Enter') {event.preventDefault();queryStationProgress();}};
    if (!available) {renderStationProgress({stations:[]});status.textContent = '此历史结果未记录工位放行事件，请重新仿真以生成工位进度。';document.getElementById('stationProgressRows').innerHTML = '<tr><td colspan="5">需要重新仿真</td></tr>';return;}
    // The run response already carries the final snapshot, avoiding an extra initial request.
    renderStationProgress(source);
    status.textContent = `仿真第 ${source.time_minutes} 分钟 · 按已放行工序的标准工时累计，完成状态以全部工序放行为准。`;
}
async function queryStationProgress() {
    const view = stationProgressView, result = view.result, source = result?.station_progress;
    if (!source) return;
    const token = ++view.token, status = document.getElementById('stationProgressStatus'), timeInput = document.getElementById('stationProgressTime'), engineId = document.getElementById('stationProgressEngine').value;
    const time = timeInput.value.trim() === '' ? source.time_minutes : Number(timeInput.value);
    if (!Number.isFinite(time) || time < 0 || time > source.time_minutes) {status.textContent = `请输入 0～${source.time_minutes} 之间的仿真分钟数。`;return;}
    status.textContent = '正在查询工位进度…';
    try {
        const params = new URLSearchParams({time_minutes:String(time)});if (engineId) params.set('engine_id',engineId);
        const response = await fetch(`/api/results/${encodeURIComponent(result.sim_id)}/station-progress?${params}`, {cache:'no-store'});
        let snapshot, local = false;
        if (response.status === 404) {snapshot = sampleStationProgress(source,time,engineId);local = true;}
        else {const data = await response.json();if (!response.ok || !data.success) throw Error(data.message || data.detail || '查询失败');snapshot = data.data;}
        if (token !== view.token) return;
        renderStationProgress(snapshot);
        status.textContent = `仿真第 ${snapshot.time_minutes} 分钟${local ? ' · 使用方案内保存的完成时间线' : ''} · 仅累计已放行工序。`;
    } catch (error) {if (token === view.token) status.textContent = '查询失败：' + error.message;}
}
