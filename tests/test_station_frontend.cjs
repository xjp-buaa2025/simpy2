const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const plain = value => JSON.parse(JSON.stringify(value));

function context() {
    const elements = new Map();
    function element(id) {
        if (!elements.has(id)) elements.set(id, {value:'', textContent:'', innerHTML:'', hidden:false,
            classList:{toggle(){}}, appendChild(){}, dataset:{}, style:{}});
        return elements.get(id);
    }
    const c = vm.createContext({console, URLSearchParams,
        FormData:class {append(){}},
        document:{getElementById:element, createElement:()=>({})},
        DEFAULT_STATIONS:[{id:'ST01', name:'旧工区', color:'#123456'}],
        state:{nodes:[], stations:[], config:{}, capacityAutomaticWip:7, capacitySamplingScheme:'paired_v1'},
        showToast(){}, refreshCapacitySignals(){}});
    for (const name of ['layout','csv','station_progress_view']) vm.runInContext(fs.readFileSync(`frontend/js/${name}.js`,'utf8'),c);
    c.initStationFilter=()=>{};c.rebuildEdges=()=>{};c.autoLayoutByStation=()=>{};
    return {c, element};
}

function definition() {
    return {name:'新流程', description:'说明', station_catalog:[
        {station_id:'WS-B',area_id:'WS-B',label:'第二工位'},
        {station_id:'WS-A',area_id:'WS-A',label:'第一工位'}],
        nodes:[{step_id:'a',task_name:'装配',op_type:'A',std_duration:10,
            station:'WS-A',area_id:'WS-A',workstation_id:'WS-A'},
        {step_id:'b',task_name:'移动',op_type:'S-Move',std_duration:2,
            station:'WS-B',area_id:'WS-B',workstation_id:'WS-B'}]};
}

function configuration(enabled=false) {
    return {critical_equipment:{tool:3}, evaluation:{mode:'plan',sampling_scheme:'paired_v1',max_wip:7},
        station_constraint_mode:true,
        capacity_model:{enabled,areas:{old:{label:'保留分配',equipment:{tool:1}},
            'WS-A':{label:'自定义工区',equipment:{tool:1},efficiency_multiplier:1.5,resource_sets:2}},
        workstations:{'WS-A':{area_id:'WS-A',label:'现有工位',capacity:4},other:{area_id:'old',capacity:2}}}};
}

test('file import merges a private candidate without enabling or reallocating saved resources',()=>{
    const {c}=context(), process=definition(), config=configuration();
    const before=JSON.stringify({process,config});
    const input=c.prepareProcessFileInput(process,config);
    assert.equal(JSON.stringify({process,config}),before);
    assert.equal(input.config.capacity_model.enabled,false);
    assert.deepEqual(plain(input.config.capacity_model.areas.old),config.capacity_model.areas.old);
    assert.deepEqual(plain(input.config.capacity_model.workstations['WS-A']),config.capacity_model.workstations['WS-A']);
    assert.equal(input.config.capacity_model.workstations['WS-B'].capacity,1);
    assert.deepEqual(plain(input.config.critical_equipment),{tool:3});
    assert.equal(input.config.station_constraint_mode,true);
    assert.equal(c.prepareProcessFileInput(process,configuration(true)).config.capacity_model.enabled,true);
});

test('conflicting physical ownership fails before any existing configuration can change',()=>{
    const {c}=context(), config=configuration();config.capacity_model.workstations['WS-A'].area_id='old';
    const before=JSON.stringify(config);
    assert.throws(()=>c.prepareProcessFileInput(definition(),config),/冲突/);
    assert.equal(JSON.stringify(config),before);
});

test('loading another process replaces visible areas and preserves JSON names, bindings and sampling settings',()=>{
    const {c}=context();c.state.stations=[{id:'old',name:'旧工区'}];
    const model=configuration().capacity_model;
    c.loadProcessData(definition(),{capacityModel:model,automaticWip:7,samplingScheme:'paired_v1'});
    assert.deepEqual(plain(c.state.stations.map(s=>s.id)),['WS-B','WS-A']);
    assert.equal(c.state.stations[1].name,'自定义工区');
    assert.equal(c.state.capacityAutomaticWip,7);assert.equal(c.state.capacitySamplingScheme,'paired_v1');
    const restored=c.buildProcessDefinition();
    assert.equal(restored.name,'新流程');assert.equal(restored.description,'说明');
    assert.equal(restored.nodes[0].workstation_id,'WS-A');
    assert.equal(restored.station_catalog[1].label,'自定义工区');
    c.loadProcessData({name:'再次切换',nodes:[{step_id:'x',station:'NEW',std_duration:1}]});
    assert.deepEqual(plain(c.state.stations.map(s=>s.id)),['NEW']);
});

test('capacity validation failure leaves the current process and model intact',async()=>{
    const {c,element}=context(), config=configuration(), original={name:'original',nodes:[]};
    c.state.capacityModel=config.capacity_model;
    c.getConfigFromUI=()=>config;c.buildProcessDefinition=()=>original;
    let commits=0,calls=0;c.loadProcessData=()=>{commits++};
    c.fetch=async()=>({ok:true,json:async()=>++calls===1?{success:true,data:definition()}:{success:false,message:'设备库存不足'}});
    const before=JSON.stringify(c.state);
    await c.importProcessFile({name:'process.xlsx'});
    assert.equal(commits,0);assert.equal(JSON.stringify(c.state),before);
    assert.match(element('processImportNotice').textContent,/设备库存不足/);
});

test('a validated import commits once and retains automatic WIP and sampling scheme',async()=>{
    const {c}=context(), config=configuration();c.getConfigFromUI=()=>config;
    c.buildProcessDefinition=()=>({name:'unchanged',nodes:[]});
    let committed=null,calls=0;c.loadProcessData=(p,options)=>{committed={p,options}};
    c.fetch=async()=>({ok:true,json:async()=>++calls===1?{success:true,data:definition()}:{success:true}});
    await c.importProcessFile({name:'process.xlsx'});
    assert.equal(calls,2);assert.equal(committed.p.name,'新流程');
    assert.equal(committed.options.automaticWip,7);assert.equal(committed.options.samplingScheme,'paired_v1');
    assert.equal(committed.options.capacityModel.enabled,false);
});

function timeline(durations=[10,30], times=[10,40]) {
    return {schema_version:1,sim_id:'run',time_unit:'minute',time_minutes:60,stations:[{
        station_id:'WS-A',area_id:'WS-A',label:'第一工位',total_steps:durations.length,
        total_standard_minutes:durations.reduce((a,b)=>a+b,0), engines:[{
            engine_id:1,released_at:0,started_at:0,completed_at:40,
            completion_events:durations.map((std_duration,i)=>({step_id:String(i),std_duration,completed_at:times[i]}))},
        {engine_id:2,released_at:20,started_at:20,completion_events:[]}]}]};
}

test('offline sampling uses completed standard work, includes exact boundaries and is repeatable',()=>{
    const {c}=context(), source=timeline(), before=JSON.stringify(source);
    assert.equal(c.sampleStationProgress(source,9).stations[0].engines[0].progress,0);
    const at=c.sampleStationProgress(source,10);
    assert.equal(at.stations[0].engines.length,1);
    assert.equal(at.stations[0].engines[0].progress,.25);
    assert.equal(at.stations[0].engines[0].completed_steps,1);
    assert.equal('completion_events' in at.stations[0].engines[0],false);
    assert.equal(c.sampleStationProgress(source,40).stations[0].engines[0].completed,true);
    assert.deepEqual(plain(c.sampleStationProgress(source,10)),plain(at));
    assert.equal(JSON.stringify(source),before);
    assert.equal(c.sampleStationProgress(source,40,'2').stations[0].engines[0].engine_id,2);
    assert.throws(()=>c.sampleStationProgress(source,Infinity));assert.throws(()=>c.sampleStationProgress(source,61));
});

test('zero-time and duplicate releases never inflate completion or force 99 percent',()=>{
    const {c,element}=context(), mixed=timeline([10,0],[10,20]);
    mixed.stations[0].engines[0].completion_events.push({...mixed.stations[0].engines[0].completion_events[0]});
    const sampled=c.sampleStationProgress(mixed,10), row=sampled.stations[0].engines[0];
    assert.equal(row.progress,1);assert.equal(row.completed,false);assert.equal(row.completed_steps,1);
    c.renderStationProgress(sampled);
    assert.match(element('stationProgressRows').innerHTML,/100\.0%/);
    assert.match(element('stationProgressRows').innerHTML,/进行中/);
    const zero=timeline([0,0],[10,20]);
    assert.equal(c.sampleStationProgress(zero,10).stations[0].engines[0].progress,0);
    assert.equal(c.sampleStationProgress(zero,20).stations[0].engines[0].progress,1);
});

test('saved-result queries fall back on their full timeline when the backend no longer retains the run',async()=>{
    const {c,element}=context();c.fixture={sim_id:'run',station_progress:timeline()};
    vm.runInContext('stationProgressView.result=fixture',c);
    element('stationProgressTime').value='10';element('stationProgressEngine').value='1';
    c.fetch=async()=>({status:404});
    await c.queryStationProgress();
    assert.match(element('stationProgressRows').innerHTML,/25\.0%/);
    assert.match(element('stationProgressStatus').textContent,/保存的完成时间线/);
});

test('saved station labels and counts are rendered as text',()=>{
    const {c,element}=context(), sampled=c.sampleStationProgress(timeline(),10);
    sampled.stations[0].label='<img src=x onerror=alert(1)>';
    sampled.stations[0].engines[0].completed_steps='<script>bad()</script>';
    c.renderStationProgress(sampled);
    assert.doesNotMatch(element('stationProgressRows').innerHTML,/<img|<script/);
    assert.match(element('stationProgressRows').innerHTML,/&lt;img/);
});
