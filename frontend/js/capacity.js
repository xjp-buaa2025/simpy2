/* Viewing an area is read-only. Only a validated save commits its local draft. */
let capacityCatalog = {}, capacityBaseline = null, capacityCandidate = null, capacityLastResult = null;
let areaDraft = null, areaSaving = false, areaEvaluating = false, areaPendingAction = null, areaRunError = '';
let capacityLastCapabilityResult = null;
const capacityClone = value => JSON.parse(JSON.stringify(value));
const capacityEscape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const capacityNumber = value => value == null ? '暂无数据' : Number(value).toFixed(1);
const capacityCanonical = value => JSON.stringify(value, function(key, item) {
    return item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.keys(item).sort().map(k => [k,item[k]])) : item;
});

function capacityModelSnapshot() {
    const model=capacityClone(state.capacityModel || {enabled:false,areas:{},workstations:{}}), bindings={};
    model.areas ||= {}; model.workstations ||= {};
    for(const area of Object.values(model.areas))delete area.dedicated_workers;
    for(const n of state.nodes) {
        const aid=n.station||'ST01';
        model.areas[aid] ||= {label:state.stations.find(s=>s.id===aid)?.name||aid,equipment:{}};
        model.areas[aid].efficiency_multiplier ??= 1;model.areas[aid].resource_sets ??= 1;
        const sid=n.workstationId||(capacityCatalog[n.stepId]?n.stepId:'');bindings[n.id]=sid;
        if(sid&&!model.workstations[sid]&&capacityCatalog[sid])model.workstations[sid]={...capacityCatalog[sid],area_id:aid};
    }
    return {model,bindings};
}
function capacityNormalizedInput(input, fixed=false) {
    if(!input)return '';
    const c=capacityClone(input.config),p=capacityClone(input.process);
    for(const key of ['sim_time_minutes','sim_time_hours','minutes_per_day'])delete c[key];
    delete c.num_workers; delete c.target_output;
    c.random_seed ??= 42;
    c.evaluation={mode:c.evaluation?.mode||'plan',max_wip:c.evaluation?.max_wip??null,sampling_scheme:c.evaluation?.sampling_scheme||'legacy'};
    c.capacity_model ||= {enabled:false};
    c.capacity_model={enabled:!!c.capacity_model.enabled,areas:c.capacity_model.areas||{},workstations:c.capacity_model.workstations||{}};
    for(const a of Object.values(c.capacity_model.areas)){delete a.dedicated_workers;delete a.label;a.efficiency_multiplier??=1;a.resource_sets??=1;}
    for(const s of Object.values(c.capacity_model.workstations))delete s.label;
    for(const n of p.nodes){delete n.x;delete n.y;delete n.task_name;}
    if(fixed){delete c.num_workers;delete c.critical_equipment;c.capacity_model={enabled:c.capacity_model.enabled};}
    return capacityCanonical({config:c,process:p});
}
const capacityFixedSignature=input=>capacityNormalizedInput(input,true);
function isCapacityStale(){return !!capacityLastResult?.input_snapshot&&capacityNormalizedInput({config:getConfigFromUI(),process:buildProcessDefinition()})!==capacityNormalizedInput(capacityLastResult.input_snapshot);}
function areaEditableSignature(d){const area=capacityClone(d.model.areas[d.aid]);area.efficiency_multiplier??=1;area.resource_sets??=1;area.equipment=Object.fromEntries(Object.entries(area.equipment).filter(([,n])=>n!==0));return capacityCanonical({area,stations:Object.fromEntries(Object.entries(d.model.workstations).filter(([,s])=>s.area_id===d.aid)),bindings:d.bindings,tools:d.tools});}
function readAreaDraft() {
    if(!areaDraft)return;
    const root=document.getElementById('areaPanelBody'),d=areaDraft,area=d.model.areas[d.aid],name=root.querySelector('#areaName');
    if(!name)return;
    area.label=name.value;
    area.efficiency_multiplier=Number(root.querySelector('#areaEfficiency')?.value??(area.efficiency_multiplier||1)*100)/100;
    area.resource_sets=Number(root.querySelector('#areaResourceSets')?.value??area.resource_sets??1);
    for(const t of root.querySelectorAll('[data-equipment-count]')) {
        const mode=[...root.querySelectorAll('[data-equipment-mode]')].find(s=>s.dataset.equipmentMode===t.dataset.equipmentCount);
        area.equipment[t.dataset.equipmentCount]=mode.value==='fixed'?Number(t.value):0;
    }
    for(const t of root.querySelectorAll('[data-station]'))d.model.workstations[t.dataset.station].capacity=Number(t.value);
    for(const t of root.querySelectorAll('[data-binding]'))d.bindings[t.dataset.binding]=t.value;
    for(const t of root.querySelectorAll('[data-tools]'))d.tools[t.dataset.tools]=t.value;
}
function areaDraftDirty(){readAreaDraft();return !!areaDraft&&areaEditableSignature(areaDraft)!==areaDraft.initial;}
function syncCapacityEditor(){/* Reading run inputs must never commit a draft. */}
function guardAreaTransition(action) {
    if(areaSaving||areaEvaluating)return false;
    if(!areaDraftDirty()){action();return true;}
    areaPendingAction=action;document.getElementById('areaLeaveDialog').classList.add('active');document.getElementById('areaLeaveKeep').focus();return false;
}
function finishAreaTransition(discard) {
    const action=areaPendingAction;areaPendingAction=null;document.getElementById('areaLeaveDialog').classList.remove('active');
    if(discard){const aid=areaDraft?.aid;areaDraft=null;if(aid)openAreaInspector(aid);action?.();}
}
function openAreaInspector(aid) {
    if(!state.nodes.some(n=>(n.station||'ST01')===aid))return;
    if(areaDraft?.aid===aid){document.getElementById('areaInspector').hidden=false;return;}
    guardAreaTransition(()=>{
        if(typeof closeNodeModal==='function'&&state.editingNode)closeNodeModal(true);
        const snapshot=capacityModelSnapshot(),nodes=state.nodes.filter(n=>(n.station||'ST01')===aid);
        areaDraft={aid,model:snapshot.model,bindings:Object.fromEntries(nodes.map(n=>[n.id,snapshot.bindings[n.id]])),tools:Object.fromEntries(nodes.map(n=>[n.id,n.requiredTools||'']))};
        areaDraft.initial=areaEditableSignature(areaDraft);state.selectedArea=aid;
        document.getElementById('areaInspector').hidden=false;renderAreaInspector();resizeCanvas();
    });
}
function refreshCleanAreaInspector(){if(areaDraft&&!areaDraftDirty()){const aid=areaDraft.aid;resetAreaEditorForProcess();openAreaInspector(aid);}}
function openSelectedArea(){openAreaInspector(state.selectedNode?.station||state.stationFilter||state.selectedArea||state.nodes[0]?.station||'ST01');}
function closeAreaInspector(){guardAreaTransition(()=>{areaDraft=null;state.selectedArea=null;document.getElementById('areaInspector').hidden=true;resizeCanvas();});}
function resetAreaEditorForProcess(){areaDraft=null;state.selectedArea=null;document.getElementById('areaInspector').hidden=true;resizeCanvas();}

function capacityMajorWait(aid,result=capacityLastResult) {
    const totals=new Map();
    for(const e of result?.gantt_events||[]) {
        if(e.area_id!==aid||e.event_type!=='WAITING'||e.end_time<=e.start_time)continue;
        let ids=e.wait_resource_ids||[];
        if(!ids.length&&e.wait_reason==='workstation'&&e.workstation_id)ids=['workstation:'+e.workstation_id];
        const key=e.wait_reason+':'+ids.slice().sort().join('|'),row=totals.get(key)||{reason:e.wait_reason,ids,minutes:0};
        row.minutes+=e.end_time-e.start_time;totals.set(key,row);
    }
    const top=[...totals.values()].sort((a,b)=>b.minutes-a.minutes)[0];if(!top)return null;
    const resources=result.resource_snapshot?.resources||[];
    top.label=top.reason==='area'?'同一工区工序串行':top.reason==='workers'?'工区可用人员':top.ids.map(id=>resources.find(r=>r.resource_id===id)?.label||id.replace(/^workstation:/,'')).join('、')||(top.reason==='equipment'?'设备（历史记录未细分）':'工位');
    return top;
}
function estimateAreaExpansion(d) {
    const groups=new Map(),inventory=state.config.criticalEquipment;
    for(const node of state.nodes.filter(n=>(n.station||'ST01')===d.aid)) {
        const sid=d.bindings[node.id],station=d.model.workstations[sid];if(!station)continue;
        if(!groups.has(sid))groups.set(sid,{capacity:station.capacity,equipment:new Set()});
        const group=groups.get(sid);
        for(const tool of (d.tools[node.id]||'').split(';').map(t=>t.trim()))if(tool in inventory)group.equipment.add(tool);
    }
    let slots=0;const equipment={};
    const copies=d.model.areas[d.aid].resource_sets-1;
    for(const group of groups.values()){
        slots+=group.capacity*copies;
        for(const name of group.equipment)equipment[name]=(equipment[name]||0)+group.capacity*copies;
    }
    return {slots,equipment};
}
function refreshAreaImprovementPreview(){
    if(!areaDraft)return;
    const area=areaDraft.model.areas[areaDraft.aid],p=estimateAreaExpansion(areaDraft);
    const standard=state.nodes.filter(n=>(n.station||'ST01')===areaDraft.aid).reduce((sum,n)=>sum+n.stdDuration,0);
    const root=document.getElementById('areaImprovementPreview');if(!root)return;
    const devices=Object.entries(p.equipment).filter(([,n])=>n).map(([name,n])=>`${capacityEscape(name)} ${n} 台`).join('、');
    root.innerHTML=`<p>有效标准作业时间：${capacityNumber(standard)} → <strong>${capacityNumber(standard/area.efficiency_multiplier)} 分钟</strong></p><p>预计新增：<strong>${p.slots} 个工位并行名额</strong>${devices?`<br>设备：${devices}`:' · 无新增有限设备'}</p>`;
}
function renderAreaInspector() {
    if(!areaDraft)return;
    const d=areaDraft,aid=d.aid,area=d.model.areas[aid],esc=capacityEscape;
    const nodes=state.nodes.filter(n=>(n.station||'ST01')===aid),stations=Object.entries(d.model.workstations).filter(([,s])=>s.area_id===aid),inventory=state.config.criticalEquipment;
    const used=new Set(nodes.flatMap(n=>(d.tools[n.id]||'').split(';').map(t=>t.trim()).filter(t=>t in inventory)));
    for(const [name,count] of Object.entries(area.equipment))if(count)used.add(name);
    const sharedDevice=name=>Number(inventory[name]||0)-Object.values(d.model.areas).reduce((sum,a)=>sum+(a.equipment[name]||0),0);
    const major=capacityMajorWait(aid);
    document.getElementById('areaPanelTitle').textContent=stationDisplayLabel(aid,area.label);document.getElementById('areaPanelError').textContent='';
    document.getElementById('areaPanelBody').innerHTML=`<fieldset id="areaFormFields">
      <section class="area-section"><p class="area-muted">${esc(aid)} · ${nodes.length} 道工序 · ${new Set(Object.values(d.bindings).filter(Boolean)).size} 个绑定工位</p>
      <label class="form-group" for="areaEfficiency">作业效率（%）<input id="areaEfficiency" type="number" min="100" max="200" step="5" value="${(area.efficiency_multiplier||1)*100}"></label>
      <div class="area-efficiency-presets">${[100,125,150,200].map(n=>`<button type="button" class="btn btn-secondary" data-efficiency="${n}">${n}%</button>`).join('')}</div>
      <label class="form-group" for="areaResourceSets">并行工位套数<input id="areaResourceSets" type="number" min="1" max="4" step="1" value="${area.resource_sets||1}"></label>
      <div id="areaImprovementPreview" class="area-improvement-preview"></div><p class="area-muted">套数增加时，为新增工位配套设备；人员按需到岗，不限制产能。</p></section>
      <section class="area-section"><h4>改善效果</h4><div id="areaRunResult"></div></section>
      <details class="area-section" id="areaAdvancedResources"><summary>高级设置：基础资源与等待分析</summary>
      <label class="form-group">工区名称<input id="areaName" value="${esc(area.label)}" required maxlength="100"></label>
      <h4>上次主要等待</h4><div id="areaWaitSummary"></div><h4>基础资源配置</h4>
      <p class="area-muted">以下是原有基础资源；新增资源另行计算，不从公共池划拨。</p>
      <div class="area-resource-list">${[...used].map(name=>{const fixed=area.equipment[name]||0;return `<div class="area-resource-row"><div><strong>${esc(name)}</strong><span class="area-resource-type">设备</span></div>
      <label>使用方式<select data-equipment-mode="${esc(name)}"><option value="shared" ${fixed?'':'selected'}>公共共享（剩余 ${sharedDevice(name)} 台）</option><option value="fixed" ${fixed?'selected':''}>本工区专用</option></select></label>
      <label data-equipment-row="${esc(name)}" ${fixed?'':'hidden'}>设备数量（台）<input data-equipment-count="${esc(name)}" type="number" min="1" value="${fixed||Math.max(1,sharedDevice(name))}"></label><small>基础库存 ${inventory[name]||0} 台${nodes.some(n=>(d.tools[n.id]||'').split(';').map(t=>t.trim()).includes(name))?'':' · 未绑定本区工序，暂不影响产出'}</small></div>`;}).join('')||'<p class="area-muted">本区未绑定有限设备。</p>'}
      <details id="areaWorkstationDetails"><summary>基础工位并行数量（${stations.length} 个）</summary>
      ${stations.map(([sid,station])=>`<label class="area-resource-row ${major?.ids.includes('workstation:'+sid)?'area-recommended':''}"><span>${esc(station.label||sid)} <small>${esc(sid)}</small><span class="area-resource-type">工位</span></span><span>基础可同时加工（件）<input data-station="${esc(sid)}" type="number" min="1" max="1000" value="${station.capacity}"></span></label>`).join('')||'<p>请绑定实体工位。</p>'}</details></div>
      <details class="area-section"><summary>工序绑定</summary><p class="area-muted">设备名称须与全局库存一致，用分号分隔。</p>
      ${nodes.map(n=>`<div class="area-resource-row"><strong>${esc(n.stepId)} ${esc(n.taskName)}</strong><label>执行工位<select data-binding="${esc(n.id)}"><option value="">请选择实体工位</option>${stations.map(([sid,station])=>`<option value="${esc(sid)}" ${d.bindings[n.id]===sid?'selected':''}>${esc(sid)} ${esc(station.label||sid)}</option>`).join('')}</select></label><label>所需设备／工具<input data-tools="${esc(n.id)}" value="${esc(d.tools[n.id])}"></label></div>`).join('')}<button type="button" id="areaAddStation" class="btn btn-secondary">新增实体工位</button></details></details></fieldset>`;
    const body=document.getElementById('areaPanelBody');
    body.oninput=()=>{readAreaDraft();refreshAreaDraftState();refreshAreaImprovementPreview();};
    body.onchange=()=>{readAreaDraft();
        for(const row of body.querySelectorAll('[data-equipment-row]')){const mode=[...body.querySelectorAll('[data-equipment-mode]')].find(t=>t.dataset.equipmentMode===row.dataset.equipmentRow);row.hidden=mode.value!=='fixed';}refreshAreaDraftState();refreshAreaImprovementPreview();};
    for(const button of body.querySelectorAll('[data-efficiency]'))button.onclick=()=>{document.getElementById('areaEfficiency').value=button.dataset.efficiency;readAreaDraft();refreshAreaDraftState();refreshAreaImprovementPreview();};
    document.getElementById('areaAddStation').onclick=()=>{readAreaDraft();const sid=prompt('输入实体工位编号，例如 WS01');if(!sid?.trim())return;if(d.model.workstations[sid.trim()]){showToast('工位编号已存在','warning');return;}d.model.workstations[sid.trim()]={area_id:aid,label:sid.trim(),capacity:1};renderAreaInspector();};
    refreshAreaDraftState();refreshAreaResult();refreshAreaImprovementPreview();
}

function refreshAreaDraftState() {
    if(!areaDraft)return;
    const dirty=areaEditableSignature(areaDraft)!==areaDraft.initial;
    document.getElementById('areaPanelState').textContent=dirty?'有未保存修改':isCapacityStale()?'待重新仿真':'已保存';
    document.getElementById('areaSave').textContent=state.capacityModel?.enabled?'保存':'启用并保存';
}
function refreshAreaResult() {
    if(!areaDraft)return;
    const aid=areaDraft.aid,stale=isCapacityStale(),r=capacityLastResult,stat=r?.area_stats?.find(s=>s.area_id===aid),major=capacityMajorWait(aid),wait=document.getElementById('areaWaitSummary');
    if(!stat)wait.textContent='运行后分析，不预设瓶颈。';
    else if(!major)wait.textContent='上次运行没有资源等待记录。';
    else {const suggestion=major.reason==='workers'?'这是旧版有限人员模型的等待记录，重新运行后采用按需供给。':major.reason==='equipment'?'可尝试增加对应设备数量。':'可尝试增加此工位的同时作业数量，并确认设备容量匹配。';wait.innerHTML=`<strong>${capacityEscape(major.label)}</strong><p>累计等待 ${capacityNumber(major.minutes)} 分钟${stale?'（上次配置）':''}</p><p>${suggestion}</p>`;}
    const root=document.getElementById('areaRunResult');
    if(!stat){root.textContent='点击“查看改善效果”，自动比较同条件下的工区和整线产出。'+(areaRunError?` 上次评估失败：${areaRunError}`:'');return;}
    const comparable=capacityBaseline?.input_snapshot&&r.input_snapshot&&capacityFixedSignature(capacityBaseline.input_snapshot)===capacityFixedSignature(r.input_snapshot);
    const previous=comparable?capacityBaseline.area_stats?.find(s=>s.area_id===aid):null,delta=previous?stat.completed_units-previous.completed_units:null;
    const effective=stat.effective_standard_minutes??stat.standard_minutes/(stat.efficiency_multiplier||1);
    const previousEffective=previous?(previous.effective_standard_minutes??previous.standard_minutes/(previous.efficiency_multiplier||1)):null;
    const lineBefore=comparable?capacityBaseline.engines_completed:null;
    const difference=(value,before,unit)=>before==null?`${value} ${unit}`:`${before} → ${value} ${unit}（${value-before>=0?'+':''}${value-before}）`;
    root.innerHTML=`<p>本区有效标准作业时间<br><strong>${previousEffective==null?'':capacityNumber(previousEffective)+' → '}${capacityNumber(effective)} 分钟</strong></p>
      <p>本区完成量<br><strong>${difference(stat.completed_units,previous?.completed_units,'套')}</strong></p>
      <p class="area-result-total">整线 ${difference(r.engines_completed,lineBefore,'台')}</p>
      ${lineBefore!=null&&r.engines_completed===lineBefore?'<p class="area-muted">本次整线产量未变化，可展开高级设置查看实际等待记录。</p>':''}
      <p class="area-muted">平均通过周期 ${capacityNumber(stat.avg_cycle_time)} 分钟 · 期末在制 ${stat.wip} 套<br>运行时间：${capacityEscape(r.completed_at||r.created_at||'—')}<br>${r.evaluation_context?.mode==='capacity'?`持续补投 · 在制上限 ${r.evaluation_context.max_wip} · 评估 ${capacityNumber(r.sim_duration)} 分钟`:'计划仿真结果'}<br>${stale?'配置已修改，以上为上次有效结果，待重新评估。':'以上为本评估条件下的产出。'}</p>${areaRunError?`<p class="area-panel-error">${capacityEscape(areaRunError)}，已保留上次有效结果。</p>`:''}`;
}
let capacityDisplayState = null;
function refreshCapacityEditStatus() {
    const stale=isCapacityStale(),key=String(stale)+areaRunError;
    if(capacityDisplayState===key)return;
    capacityDisplayState=key;
    const notice=document.getElementById('areaCanvasNotice');
    notice.textContent=areaRunError?'仿真失败 · 保留上次结果':stale?'配置已修改 · 待重新仿真':'右键工区查看与修改属性';
    notice.classList.toggle('is-stale',stale||!!areaRunError);
    refreshAreaDraftState();refreshAreaResult();
}
function refreshCapacitySignals() {
    capacityDisplayState=null;refreshCapacityEditStatus();
    const stale=isCapacityStale(),notice=document.getElementById('areaCanvasNotice');
    notice.textContent=areaRunError?'仿真失败 · 保留上次结果':stale?'配置已修改 · 待重新仿真':'右键工区查看与修改属性';notice.classList.toggle('is-stale',stale||!!areaRunError);
    document.getElementById('capacityModelState').textContent=state.capacityModel?.enabled?'工区资源约束已启用。常用配置在流程图右键工区修改。':'在流程图右键工区，保存资源配置后启用工区约束。';
    document.getElementById('stationConstraintMode').disabled=true;
    document.getElementById('stationConstraintMode').checked=true;
    refreshAreaDraftState();refreshAreaResult();renderCanvas();
}
const renderCapacityPanel=refreshCapacitySignals;
function setAreaName(aid,name) {
    const station=state.stations.find(s=>s.id===aid);if(station)station.name=name;else state.stations.push({id:aid,name,color:'#3b82f6'});
    if(stationContainers[aid])stationContainers[aid].name=stationDisplayLabel(aid,name);if(state.capacityModel?.areas[aid])state.capacityModel.areas[aid].label=name;
    const selected=state.stationFilter;initStationFilter();document.getElementById('stationFilter').value=selected||'';
}
async function saveAreaInspector(run=false) {
    if(!areaDraft||areaSaving||areaEvaluating)return false;readAreaDraft();const draft=areaDraft;
    const fail=message=>{document.getElementById('areaPanelError').textContent=message;return false;};
    if(!draft.model.areas[draft.aid].label.trim())return fail('请填写工区名称。');
    for(const input of document.getElementById('areaPanelBody').querySelectorAll('input[type=number]'))if(!input.closest('[hidden]')&&!input.checkValidity())return fail('人数、设备和工位数量必须是范围内的整数。');
    const snapshot=capacityModelSnapshot(),model=snapshot.model;model.enabled=true;model.areas[draft.aid]=capacityClone(draft.model.areas[draft.aid]);
    for(const [sid,s] of Object.entries(draft.model.workstations))if(s.area_id===draft.aid)model.workstations[sid]=capacityClone(s);
    const process=buildProcessDefinition();
    for(let i=0;i<state.nodes.length;i++){const node=state.nodes[i];process.nodes[i].workstation_id=draft.bindings[node.id]??snapshot.bindings[node.id];if(node.id in draft.tools)process.nodes[i].required_tools=draft.tools[node.id].split(';').map(t=>t.trim()).filter(Boolean);}
    const input={config:{...getConfigFromUI(),capacity_model:model},process};
    areaSaving=true;document.getElementById('areaFormFields').disabled=true;
    for(const id of ['areaSave','areaSaveRun','areaCancel','areaClose'])document.getElementById(id).disabled=true;
    document.getElementById('areaPanelError').textContent='正在校验配置…';
    try {
        const v=await fetch('/api/simulation/capacity/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)}).then(r=>r.json());
        if(!v.success)return fail(v.message||'配置验证失败。');if(areaDraft!==draft)return false;
        state.capacityModel=model;state.nodes.forEach((n,i)=>{n.workstationId=process.nodes[i].workstation_id;if(n.id in draft.tools)n.requiredTools=draft.tools[n.id];});
        setAreaName(draft.aid,model.areas[draft.aid].label.trim());draft.model=capacityClone(model);draft.initial=areaEditableSignature(draft);
        areaRunError='';renderAreaInspector();refreshCapacitySignals();document.getElementById('areaPanelError').textContent='';
    }catch(error){return fail('配置未保存：'+error.message);}
    finally{areaSaving=false;if(document.getElementById('areaFormFields'))document.getElementById('areaFormFields').disabled=false;for(const id of ['areaSave','areaSaveRun','areaCancel','areaClose'])document.getElementById(id).disabled=false;}
    if(run)await runAreaImprovement();return true;
}
function capacityProcessSignature(process){
    const p=capacityClone(process);delete p.name;delete p.description;
    for(const n of p.nodes){delete n.x;delete n.y;delete n.task_name;}
    return capacityCanonical(p);
}
function effectiveSlotCount(input){
    const model=input.config.capacity_model,used=new Set(input.process.nodes.map(n=>n.workstation_id||n.step_id));
    return [...used].reduce((sum,sid)=>{const station=model.workstations[sid];return sum+(station?station.capacity*(model.areas[station.area_id]?.resource_sets||1):0);},0);
}
function buildAreaComparison(candidate,previous,explicitWip){
    candidate=capacityClone(candidate);const baseline=capacityClone(candidate);
    if(previous?.input_snapshot&&capacityProcessSignature(previous.input_snapshot.process)===capacityProcessSignature(candidate.process)){
        for(const key of ['capacity_model','critical_equipment'])baseline.config[key]=capacityClone(previous.input_snapshot.config[key]);
    }else{
        for(const area of Object.values(baseline.config.capacity_model.areas)){area.efficiency_multiplier=1;area.resource_sets=1;}
    }
    const wip=explicitWip==null?Math.max(2,effectiveSlotCount(baseline),effectiveSlotCount(candidate)):Number(explicitWip);
    for(const input of [baseline,candidate]){
        input.config.evaluation={mode:'capacity',max_wip:wip,sampling_scheme:'paired_v1'};
        input.config.random_seed ??= 42;
    }
    return {baseline,candidate,reuse:!!previous&&capacityNormalizedInput(previous.input_snapshot)===capacityNormalizedInput(baseline)};
}
async function postCapacityRun(input,publish){
    if(typeof requestSimulationRun==='function'){
        const data=await requestSimulationRun({...input,publish_to_clients:publish});
        if(!data.success)throw Error(data.message||'仿真请求失败，请检查评估配置');return data.data;
    }
    const response=await fetch('/api/simulation/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...input,publish_to_clients:publish})});
    const data=await response.json();if(!data.success)throw Error(data.message||'仿真请求失败，请检查评估配置');return data.data;
}
async function runAreaImprovement(){
    if(areaSaving||areaEvaluating||areaDraftDirty())return;
    areaEvaluating=true;showLoading(true);areaRunError='';
    try{
        const explicit=document.getElementById('capacityWip').value;
        const pair=buildAreaComparison({config:getConfigFromUI(),process:buildProcessDefinition()},capacityLastCapabilityResult,explicit===''?null:Number(explicit));
        if(typeof setSimulationProgressGroup==='function')setSimulationProgressGroup(pair.reuse?1:2);
        if(typeof setWorkbenchPhase==='function')setWorkbenchPhase(pair.reuse?'正在评估候选方案':'正在计算同条件基准');
        document.getElementById('areaPanelError').textContent=pair.reuse?'正在评估改善方案…':'正在计算同条件基准…';
        const baseline=pair.reuse?capacityLastCapabilityResult:await postCapacityRun(pair.baseline,false);
        if(typeof setWorkbenchPhase==='function')setWorkbenchPhase('正在评估候选方案');
        document.getElementById('areaPanelError').textContent='正在评估改善方案…';
        const result=await postCapacityRun(pair.candidate,true);
        document.getElementById('capacityMode').value='capacity';
        state.capacityAutomaticWip=explicit===''?pair.candidate.config.evaluation.max_wip:null;
        state.simulationResult=result;acceptCapacityResult(result,baseline);updateResults(result);
        if(result.unity_sync&&!result.unity_sync.success)showToast('评估完成；PC/VR同步失败：'+result.unity_sync.message,'warning');
        else showToast(result.unity_sync?.mode==='station_progress_only'?'同条件改善评估完成，工位进度数据就绪':'同条件改善评估完成','success');
    }catch(error){rejectCapacityResult(error.message);showToast('改善评估失败：'+error.message,'error');}
    finally{areaEvaluating=false;showLoading(false);document.getElementById('areaPanelError').textContent='';}
}

function validateCapacityRun(input) {
    if(areaSaving||areaEvaluating){showToast('请等待工区配置保存完成','warning');return false;}
    if(areaDraftDirty()){showToast('请先保存或取消工区修改，也可点击“查看改善效果”','warning');return false;}
    if(input.config.evaluation.mode==='capacity'&&!input.config.capacity_model.enabled){showToast('请先在流程图右键工区，保存资源配置以启用能力评估','warning');return false;}return true;
}
function acceptCapacityResult(result,comparisonBaseline=null) {
    const prev=capacityLastResult;capacityBaseline=prev?.input_snapshot&&prev.area_stats?.length&&result.area_stats?.length&&capacityFixedSignature(prev.input_snapshot)===capacityFixedSignature(result.input_snapshot)?capacityClone(prev):null;
    if(comparisonBaseline?.input_snapshot)capacityBaseline=capacityClone(comparisonBaseline);
    if(result.evaluation_context?.mode==='capacity')capacityLastCapabilityResult=capacityClone(result);
    state.capacitySamplingScheme=result.evaluation_context?.sampling_scheme||'legacy';
    if(!document.getElementById('capacityWip').value)state.capacityAutomaticWip=result.evaluation_context?.max_wip??null;
    capacityLastResult=capacityClone(result);capacityCandidate=capacityLastResult;areaRunError='';

    if(areaDraft&&!areaDraftDirty())renderAreaInspector();refreshCapacitySignals();
}
function rejectCapacityResult(message){areaRunError=message||'仿真失败';refreshCapacitySignals();}
function capacityStatus(message){document.getElementById('capacityStatus').textContent=message;}
function exportCapacityScenario() {
    if(areaDraftDirty()){showToast('请先保存或取消工区草稿再导出','warning');return;}
    const data={schema_version:1,automatic_wip:document.getElementById('capacityWip').value==='',input:{config:getConfigFromUI(),process:buildProcessDefinition()},result:capacityLastResult,baseline:capacityBaseline,candidate:null,candidate_is_result:!!capacityLastResult};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='工区产能方案.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function requestCapacityImport(){guardAreaTransition(()=>document.getElementById('capacityScenarioFile').click());}
async function importCapacityScenario(event) {
    try {
        const file=event.target.files[0];if(!file)return;if(file.size>100*1024*1024)throw Error('方案文件超过100MB');
        const data=JSON.parse(await file.text()),input=data.input;
        if(data.schema_version!==1||!Array.isArray(input?.process?.nodes)||!input.config?.capacity_model?.areas||!input.config?.capacity_model?.workstations)throw Error('方案格式不完整');
        if(data.result&&typeof ResultView!=='undefined')ResultView.validate(data.result);
        const v=await fetch('/api/simulation/capacity/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)}).then(r=>r.json());if(!v.success)throw Error(v.message);
        guardAreaTransition(()=>{
            resetAreaEditorForProcess();loadProcessData(input.process,{capacityModel:capacityClone(input.config.capacity_model)});const c=input.config;
            const ids={workHoursPerDay:'work_hours_per_day',workDaysPerMonth:'work_days_per_month',restTimeThreshold:'rest_time_threshold',restDurationTime:'rest_duration_time',restLoadThreshold:'rest_load_threshold',restDurationLoad:'rest_duration_load'};
            for(const [id,key] of Object.entries(ids))document.getElementById(id).value=c[key];
            for(const [id,key] of [['pipelineMode','pipeline_mode'],['stationConstraintMode','station_constraint_mode']])document.getElementById(id).checked=id==='stationConstraintMode'||c[key];
            state.config.criticalEquipment=capacityClone(c.critical_equipment);state.capacityModel=capacityClone(c.capacity_model);
            for(const [aid,a] of Object.entries(state.capacityModel.areas))if(a.label)setAreaName(aid,a.label);
            document.getElementById('capacityMode').value=c.evaluation?.mode||'plan';document.getElementById('capacityWip').value=data.automatic_wip?'':c.evaluation?.max_wip??'';state.capacityAutomaticWip=data.automatic_wip?c.evaluation?.max_wip:null;document.getElementById('capacitySeed').value=c.random_seed??42;
            capacityLastResult=data.result?.input_snapshot?data.result:null;capacityBaseline=data.baseline?.input_snapshot?data.baseline:null;capacityCandidate=capacityLastResult;capacityLastCapabilityResult=capacityLastResult?.evaluation_context?.mode==='capacity'?capacityLastResult:null;state.capacitySamplingScheme=c.evaluation?.sampling_scheme||'legacy';areaRunError='';
            if(data.result&&Array.isArray(data.result.gantt_events)){state.simulationResult=data.result;updateResults(data.result);}
            renderEquipmentList();refreshCapacitySignals();capacityStatus('方案已载入。可查询保存的工位进度，重新运行后更新客户端数据。');
        });
    }catch(error){console.error(error);showToast('载入失败：'+error.message,'error');}finally{event.target.value='';}
}
document.addEventListener('DOMContentLoaded',async()=>{
    document.getElementById('areaClose').onclick=closeAreaInspector;
    document.getElementById('areaSave').onclick=()=>saveAreaInspector(false);document.getElementById('areaSaveRun').onclick=()=>saveAreaInspector(true);
    document.getElementById('areaCancel').onclick=()=>{if(areaSaving||areaEvaluating)return;const aid=areaDraft?.aid;areaDraft=null;if(aid)openAreaInspector(aid);};
    document.getElementById('areaLeaveKeep').onclick=()=>finishAreaTransition(false);document.getElementById('areaLeaveDiscard').onclick=()=>finishAreaTransition(true);
    document.getElementById('areaLeaveSave').onclick=async()=>{if(await saveAreaInspector())finishAreaTransition(true);};
    document.getElementById('capacityScenarioFile').onchange=importCapacityScenario;
    document.getElementById('tab-config').addEventListener('change',e=>{if(e.target.id==='capacityWip')state.capacityAutomaticWip=null;refreshCapacitySignals();});
    document.getElementById('areaLeaveDialog').addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();finishAreaTransition(false);}if(e.key==='Tab'){const buttons=[...document.querySelectorAll('#areaLeaveDialog button')],i=buttons.indexOf(document.activeElement);e.preventDefault();buttons[(i+(e.shiftKey?-1:1)+buttons.length)%buttons.length].focus();}});
    window.addEventListener('beforeunload',e=>{if(areaDraftDirty()){e.preventDefault();e.returnValue='';}});
    try{const r=await fetch('/api/simulation/capacity/catalog').then(r=>r.json());if(r.success)capacityCatalog=r.data;else throw Error(r.message);}catch(error){capacityStatus('实体工位目录暂不可用，可查看已有配置。保存前请检查工位绑定。');}
    refreshCapacitySignals();
});
