/* Home is a read-only overview. Demonstration values never enter simulation state. */
const HOME_DEMO = Object.freeze({output:12,cycle:16.4,worker:12,equipment:74.2,pass:96.8,nodes:79,areas:11});
const homeView = {ready:false,model:null,overview:null,motion:true};
const HOME_AREAS = [
    {id:'ST01',name:'物料入库',x:105,y:175}, {id:'ST03',name:'压气机装配',x:418,y:126},
    {id:'ST04',name:'燃烧室装配',x:763,y:51}, {id:'ST05',name:'涡轮装配',x:1160,y:104},
    {id:'ST11',name:'总装集成',x:827,y:397}, {id:'ST13',name:'包装发运',x:1138,y:802}
];
const HOME_ICONS = {
    editor:'<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/><path d="M9 6h9v9M6 9v9h9"/>',
    config:'<path d="M6 3v18M12 3v18M18 3v18"/><path d="M3 8h6m0 8h6m0-10h6"/>',
    run:'<circle cx="12" cy="12" r="9"/><path d="m10 8 6 4-6 4z"/>',
    overview:'<path d="M4 3v17h17M8 15v-4m5 4V6m5 9v-6"/>',
    resources:'<path d="m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/>',
    human:'<circle cx="12" cy="7" r="3"/><path d="M5 21v-4a7 7 0 0 1 14 0v4M8 17h8"/>',
    gantt:'<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M7 2v4m10-4v4M7 10h5m-2 4h7m-9 4h5"/>',
    files:'<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 10h18"/>',
    output:'<path d="m12 3 8 4v10l-8 4-8-4V7zM4 7l8 4 8-4m-8 4v10"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    check:'<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6zM8 12l3 3 5-6"/>',
    equipment:'<rect x="3" y="5" width="18" height="13" rx="2"/><path d="M8 21h8m-4-3v3M6 9h4m-4 4h7m4-4v4"/>',
    fullscreen:'<path d="M3 9V3h6m6 0h6v6M3 15v6h6m6 0h6v-6"/>'
};
const homeIcon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${HOME_ICONS[name]||HOME_ICONS.overview}</svg>`;
const homeElement = id => document.getElementById(id);

function homeUtilization(stats, explicit, equipment=false) {
    const rows = (Array.isArray(stats)?stats:[]).filter(row=>!equipment||
        (row.resource_type!=='WORKSTATION'&&!String(row.resource_id||'').startsWith('workstation:')));
    const rates=rows.map(row=>row.utilization_rate).filter(Number.isFinite);
    if(rates.length)return rates.reduce((sum,value)=>sum+value,0)/rates.length*100;
    return (!Array.isArray(stats)||stats.length===0)&&Number.isFinite(explicit)?explicit*100:null;
}

function buildHomeOverview(model) {
    const r=model.result,process=model.process||{},nodes=(Array.isArray(process.nodes)?process.nodes:[]).filter(Boolean),quality=r.quality_stats||{};
    return {output:Number.isFinite(r.engines_completed)?r.engines_completed:null,
        cycle:r.engines_completed>0&&Number.isFinite(r.avg_cycle_time)?r.avg_cycle_time/60:null,
        worker:Number.isFinite(r.evaluation_context?.peak_working_workers)?r.evaluation_context.peak_working_workers:(typeof getLaborMetrics==='function'?getLaborMetrics(r).peak_working_workers:null),
        equipment:homeUtilization(r.equipment_stats,r.avg_equipment_utilization,true),
        pass:quality.total_inspections>0&&Number.isFinite(quality.first_pass_rate)?quality.first_pass_rate*100:null,
        nodes:nodes.length||null,areas:new Set(nodes.map(n=>n.area_id||n.station).filter(Boolean)).size||null};
}

function initHome() {
    const entries=[['editor','工艺建模','流程 · 行为 · 工区'],['config','仿真设置','日历 · 人员 · 设备'],
        ['run','运行仿真','计划排产 · 能力评估'],['overview','产出分析','产出概览 · 工区改善'],
        ['resources','资源与瓶颈','人员 · 设备 · 等待'],['human','人因与质量','疲劳 · 休息 · 返工'],
        ['gantt','排产甘特','产品 · 人员 · 工位'],['files','方案管理','CSV / XLSX / JSON 导入导出']];
    homeElement('homeFunctions').innerHTML=entries.map(([action,label])=>`<button class="home-function" data-home-action="${action}"><span class="home-function-icon">${homeIcon(action)}</span><span class="home-function-copy"><b>${label}</b></span><span class="home-function-arrow" aria-hidden="true">›</span></button>`).join('');
    const metrics=[['output','评估期产出','台','output'],['cycle','平均周期','小时','clock'],
        ['worker','峰值同时作业人数','人','human'],['equipment','设备利用率','%','equipment'],['pass','一次通过率','%','check']];
    homeElement('homeMetrics').innerHTML=metrics.map(([key,label,unit,icon])=>`<div class="home-metric"><div class="home-metric-label"><span>${label}</span>${homeIcon(icon)}</div><div class="home-metric-number"><strong id="homeMetric-${key}">—</strong><span id="homeUnit-${key}">${unit}</span></div>${['equipment','pass'].includes(key)?`<div class="home-metric-track" aria-hidden="true"><i id="homeTrack-${key}"></i></div>`:''}</div>`).join('');
    document.querySelectorAll('[data-home-action]').forEach(button=>button.addEventListener('click',()=>homeNavigate(button.dataset.homeAction)));
    document.querySelectorAll('[data-home-area]').forEach(button=>{
        button.addEventListener('click',()=>homeOpenArea(button.dataset.homeArea));
        button.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();homeOpenArea(button.dataset.homeArea);}});
    });
    try{homeView.motion=localStorage.getItem('assembly.ui.homeMotion')!=='off';}catch{}
    document.addEventListener('visibilitychange',syncHomeMotion);
    document.addEventListener('fullscreenchange',()=>{
        const button=homeElement('homeFullscreen');
        button.setAttribute('aria-pressed',String(!!document.fullscreenElement));
        button.querySelector('span').textContent=document.fullscreenElement?'退出全屏':'全屏';
    });
    const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if(reduced)reduced.addEventListener('change',syncHomeMotion);
    homeView.ready=true;refreshHome();
}

function refreshHome() {
    if(!homeView.ready||!homeElement('tab-home'))return;
    const model=typeof ganttView!=='undefined'?ganttView.model:null;
    if(model!==homeView.model){homeView.model=model;homeView.overview=model?buildHomeOverview(model):null;}
    const active=homeElement('tab-home').classList.contains('active');
    document.body.classList.toggle('home-active',active);
    if(!active){syncHomeMotion();return;}
    const real=!!model,values=real?homeView.overview:HOME_DEMO;
    homeElement('homeMetricsNote').textContent=real?'基于同一次仿真的结果快照':'';
    homeElement('homeMetricsNote').hidden=!real;
    for(const key of ['output','cycle','worker','equipment','pass']){
        const value=values[key],valid=Number.isFinite(value);
        homeElement(`homeMetric-${key}`).textContent=valid?(key==='output'?String(value):value.toFixed(1)):'—';
        homeElement(`homeUnit-${key}`).hidden=!valid;
        const track=homeElement(`homeTrack-${key}`);if(track)track.style.width=valid?`${Math.max(0,Math.min(100,value))}%`:'0%';
    }
    const evaluation=real?model.evaluation:null;
    homeElement('homeScenario').textContent=real?`${evaluation.mode==='capacity'?'能力评估':'计划仿真'} · ${Number.isFinite(model.duration)?(model.duration/60).toFixed(1)+' 工作小时':'评估时长未记录'}`:'22 工作日 × 8 小时';
    homeElement('homeModelSummary').textContent=`${values.areas??'—'} 个工区 / ${values.nodes??'—'} 道工序`;
    homeElement('homeResultTime').textContent=real?(model.result.completed_at||model.result.created_at||'未记录'):'—';
    const busy=typeof workbenchBusy!=='undefined'&&workbenchBusy;
    const stale=real&&typeof isCapacityStale==='function'&&isCapacityStale();
    const failed=typeof workbenchFailure!=='undefined'&&workbenchFailure;
    homeElement('homeRunStatus').textContent=busy?'正在运行仿真':failed?'运行失败 · 保留上次结果':stale?'配置已修改 · 结果待重算':real?'结果已就绪':'就绪';
    homeElement('homeRunStatus').classList.toggle('attention',!!stale||!!failed);
    document.querySelectorAll('[data-home-action]').forEach(button=>button.disabled=busy);
    homeElement('homePromptExample').disabled=busy;
    homeElement('homeExportCSV').disabled=busy||!state.nodes.length;
    homeElement('homeExportJSON').disabled=busy||!state.nodes.length;
    document.querySelectorAll('[data-home-area]').forEach(button=>{
        const available=state.nodes.some(node=>node.station===button.dataset.homeArea);
        button.classList.toggle('available',available);
        button.setAttribute('aria-disabled',String(!available||busy));
        const name=state.stations?.find(area=>area.id===button.dataset.homeArea)?.name||HOME_AREAS.find(area=>area.id===button.dataset.homeArea).name;
        button.querySelector('title').textContent=available?`${name}：点击查看当前工艺流程`:`${name}：当前流程尚无对应工区`;
    });
    syncHomeMotion();
}


function homeNavigate(action) {
    if(typeof workbenchBusy!=='undefined'&&workbenchBusy)return;
    homeElement('homeResultPrompt').hidden=true;
    homeElement('homeFilesPanel').hidden=action!=='files'||!homeElement('homeFilesPanel').hidden;
    if(action==='files')return;
    if(['overview','resources','human','gantt'].includes(action)&&!homeView.model){showHomePrompt('先运行仿真，或载入带结果的方案，即可查看分析与排产。');return;}
    if(action==='run'){
        if(!state.nodes.length){showHomePrompt('先载入示例流程或导入自己的流程，再开始仿真。');return;}
        return runSimulation();
    }
    if(action==='editor'||action==='config')return switchTab(action);
    if(action==='gantt')return switchTab('gantt');
    guardAreaTransition(()=>{switchTab('results',true);resultGroup(action);});
}

function showHomePrompt(message){homeElement('homePromptText').textContent=message;homeElement('homeResultPrompt').hidden=false;homeElement('homeResultPrompt').focus({preventScroll:true});}
function loadHomeExample(){guardAreaTransition(()=>{homeElement('homeResultPrompt').hidden=true;loadComplexExample(true);switchTab('editor',true);resizeCanvas();fitCanvas();});}
function homeOpenArea(aid){
    if(typeof workbenchBusy!=='undefined'&&workbenchBusy)return;
    if(!state.nodes.some(node=>node.station===aid)){showHomePrompt('当前流程没有对应工区，可以先载入示例流程或导入方案。');return;}
    guardAreaTransition(()=>{switchTab('editor',true);homeElement('stationFilter').value=aid;filterByStation();resizeCanvas();fitCanvas();});
}
function homeFileAction(action){if(typeof workbenchBusy!=='undefined'&&workbenchBusy)return;return ({importCSV,requestCapacityImport,exportCSV,exportCapacityScenario})[action]?.();}

function syncHomeMotion(){
    const scene=homeElement('homeScene');if(!scene)return;
    const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const playing=homeView.motion&&!document.hidden&&!reduced&&homeElement('tab-home').classList.contains('active');
    scene.classList.toggle('motion-paused',!playing);
    const visible=!document.hidden&&homeElement('tab-home').classList.contains('active');
    window.HomeEngineViewer?.setVisible(visible,playing);
    homeElement('homeMotion').setAttribute('aria-pressed',String(homeView.motion));
    homeElement('homeMotion').title=homeView.motion?'暂停自动旋转':'开启自动旋转';
}
function toggleHomeMotion(){homeView.motion=!homeView.motion;try{localStorage.setItem('assembly.ui.homeMotion',homeView.motion?'on':'off');}catch{}syncHomeMotion();}
function pauseHomeRotation(){if(homeView.motion)toggleHomeMotion();}
function toggleHomeDetails(open){const panel=homeElement('homeResultDetails');panel.hidden=typeof open==='boolean'?!open:!panel.hidden;homeElement('homeDetailsToggle').setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)homeElement('homeDetailsToggle').focus();}
async function toggleHomeFullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{showToast('当前浏览器不支持全屏展示','warning');}}

document.addEventListener('DOMContentLoaded',initHome);
