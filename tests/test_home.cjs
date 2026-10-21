const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function setup(){
    const elements={},calls=[],listeners={},storage=new Map();
    function element(){const classes=new Set();return {classes,textContent:'',innerHTML:'',hidden:false,disabled:false,style:{},dataset:{},attrs:{},
        classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),contains:x=>classes.has(x),toggle:(x,on)=>on?classes.add(x):classes.delete(x)},
        setAttribute(k,v){this.attrs[k]=v},focus(){calls.push('focus')},addEventListener(){},querySelector(){return this.child??=element()}};}
    const get=id=>elements[id]??=element(),actions=['editor','config','run','overview','resources','human','gantt','files'].map(action=>Object.assign(element(),{dataset:{homeAction:action}}));
    const areas=['ST01','ST03','ST04','ST05','ST11','ST13'].map(id=>Object.assign(element(),{dataset:{homeArea:id}}));
    get('tab-home').classes.add('active');get('homeResultPrompt').hidden=true;get('homeFilesPanel').hidden=true;
    get('homeSceneGraphic').pauseAnimations=()=>calls.push('pause');get('homeSceneGraphic').unpauseAnimations=()=>calls.push('play');
    const media={matches:false,addEventListener(){}};
    const c=vm.createContext({console,state:{nodes:[],edges:[],stations:[],config:{}},ganttView:{model:null},workbenchBusy:false,workbenchFailure:'',
        document:{getElementById:get,querySelectorAll:s=>s==='[data-home-action]'?actions:s==='[data-home-area]'?areas:[],body:element(),hidden:false,
            addEventListener:(name,callback)=>listeners[name]=callback,documentElement:{requestFullscreen:async()=>calls.push('fullscreen')},exitFullscreen:async()=>calls.push('exit-fullscreen')},
        window:{matchMedia:()=>media,HomeEngineViewer:{setVisible:(visible,playing)=>calls.push(visible&&playing?'play':'pause')}},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
        isCapacityStale:()=>false,showToast:()=>calls.push('toast'),fetch(){throw Error('home must not write or fetch business data')},
        guardAreaTransition:action=>action(),switchTab:(name,force)=>calls.push(['tab',name,force]),resultGroup:name=>calls.push(['group',name]),
        runSimulation:()=>calls.push('run'),loadComplexExample:force=>calls.push(['example',force]),resizeCanvas:()=>calls.push('resize'),fitCanvas:()=>calls.push('fit'),filterByStation:()=>calls.push('filter')});
    for(const name of ['importCSV','requestCapacityImport','exportCSV','exportCapacityScenario'])c[name]=()=>calls.push(name);
    vm.runInContext(fs.readFileSync('frontend/js/home.js','utf8'),c);
    return {c,elements,get,calls,actions,areas,media,listeners,run:code=>vm.runInContext(code,c)};
}
const model=()=>({result:{engines_completed:5,avg_cycle_time:120,worker_stats:[{utilization_rate:0},{utilization_rate:.8}],
    equipment_stats:[{resource_id:'workstation:W',resource_type:'WORKSTATION',utilization_rate:.1},{resource_id:'equipment:test',utilization_rate:.75}],
    quality_stats:{total_inspections:1,first_pass_rate:0},completed_at:'2026-10-20'},config:{work_hours_per_day:8},evaluation:{mode:'capacity'},duration:480,
    process:{nodes:[{step_id:'one',station:'A'},{step_id:'two',area_id:'A'}]}});

test('initial home is an isolated demo and has all eight working navigation categories',()=>{
    const {run,c,get}=setup(),before=JSON.stringify(c.state);
    run('initHome()');assert.equal(JSON.stringify(c.state),before);assert.equal(c.ganttView.model,null);
    assert.equal(get('homeMetric-output').textContent,'12');assert.equal(get('homeMetricsNote').hidden,true);
    for(const action of ['editor','config','run','overview','resources','human','gantt','files'])assert.ok(get('homeFunctions').innerHTML.includes(`data-home-action="${action}"`));
    assert.equal(get('homeMetricsNote').textContent,'');
});

test('real home metrics preserve zeros, use the result snapshot and exclude workstation utilization',()=>{
    const {run,c,get}=setup();c.ganttView.model=model();run('initHome()');
    assert.equal(get('homeMetric-output').textContent,'5');assert.equal(get('homeMetric-cycle').textContent,'2.0');
    assert.equal(get('homeMetric-worker').textContent,'—');assert.equal(get('homeMetric-equipment').textContent,'75.0');
    assert.equal(get('homeMetric-pass').textContent,'0.0');assert.equal(get('homeModelSummary').textContent,'1 个工区 / 2 道工序');
    c.state.nodes.push({id:'new',station:'different'});c.isCapacityStale=()=>true;run('refreshHome()');
    assert.equal(get('homeMetric-output').textContent,'5');assert.ok(get('homeRunStatus').textContent.includes('待重算'));
});

test('missing result metrics show dashes rather than invented values',()=>{
    const {run,c,get}=setup();const result=model();Object.assign(result.result,{engines_completed:0,worker_stats:[],equipment_stats:[],quality_stats:{}});
    c.ganttView.model=result;run('initHome()');
    assert.equal(get('homeMetric-output').textContent,'0');
    for(const key of ['cycle','worker','equipment','pass']){assert.equal(get(`homeMetric-${key}`).textContent,'—');assert.equal(get(`homeUnit-${key}`).hidden,true);}
});

test('valid results automatically replace fallback data and survive failed reruns',()=>{
    const {run,c,get}=setup();run('initHome()');c.ganttView.model=model();run('refreshHome()');
    assert.equal(get('homeMetric-output').textContent,'5');
    assert.equal(get('homeMetricsNote').hidden,false);
    const before=JSON.stringify(c.ganttView.model);run('refreshHome()');
    assert.equal(JSON.stringify(c.ganttView.model),before);
    c.ganttView.model=model();c.ganttView.model.result.engines_completed=8;run('refreshHome()');
    assert.equal(get('homeMetric-output').textContent,'8');c.workbenchFailure='failed';run('refreshHome()');
    assert.equal(get('homeMetric-output').textContent,'8');assert.ok(get('homeRunStatus').textContent.includes('保留上次结果'));
});

test('empty result navigation prompts for explicit input without running or loading data',()=>{
    const {run,c,get,calls}=setup();run("initHome();homeNavigate('overview');homeNavigate('gantt');homeNavigate('run')");
    assert.equal(get('homeResultPrompt').hidden,false);assert.equal(c.state.nodes.length,0);
    assert.equal(calls.includes('run'),false);assert.equal(calls.some(call=>Array.isArray(call)&&call[0]==='example'),false);
});

test('all business navigation reuses the existing transition guards and functions',()=>{
    const {run,c,get,calls}=setup();c.ganttView.model=model();c.state.nodes=[{station:'ST03'}];run('initHome()');
    c.guardAreaTransition=()=>calls.push('guard-blocked');run("homeNavigate('resources');homeOpenArea('ST03');loadHomeExample()");
    assert.equal(calls.some(call=>Array.isArray(call)&&['tab','example','group'].includes(call[0])),false);
    c.guardAreaTransition=action=>action();run("homeNavigate('resources');homeOpenArea('ST03');homeFileAction('requestCapacityImport')");
    assert.ok(calls.some(call=>Array.isArray(call)&&call[0]==='group'&&call[1]==='resources'));
    assert.equal(get('stationFilter').value,'ST03');assert.ok(calls.includes('requestCapacityImport'));
    run("homeNavigate('run')");assert.ok(calls.includes('run'));
});

test('scene animation pauses when hidden, on another page, or with reduced motion',()=>{
    const {run,c,calls,get,media}=setup();run('initHome()');assert.equal(calls.at(-1),'play');
    c.document.hidden=true;run('syncHomeMotion()');assert.equal(calls.at(-1),'pause');
    c.document.hidden=false;get('tab-home').classes.delete('active');run('refreshHome()');assert.equal(calls.at(-1),'pause');
    get('tab-home').classes.add('active');media.matches=true;run('syncHomeMotion()');assert.equal(calls.at(-1),'pause');
    media.matches=false;run('toggleHomeMotion()');assert.equal(calls.at(-1),'pause');
    run('toggleHomeMotion()');assert.equal(calls.at(-1),'play');
});

test('busy state prevents duplicate starts and disables home actions',()=>{
    const {run,c,actions,calls}=setup();run('initHome()');c.workbenchBusy=true;run("refreshHome();homeNavigate('run');homeFileAction('importCSV')");
    assert.ok(actions.every(button=>button.disabled));assert.equal(calls.includes('run'),false);assert.equal(calls.includes('importCSV'),false);
});

test('home fullscreen is independent from the existing presentation state',async()=>{
    const {run,c,calls}=setup();c.presentationState={saved:'unchanged'};run('initHome()');
    await run('toggleHomeFullscreen()');assert.ok(calls.includes('fullscreen'));
    assert.equal(c.presentationState.saved,'unchanged');c.document.fullscreenElement={};
    await run('toggleHomeFullscreen()');assert.ok(calls.includes('exit-fullscreen'));
});

test('on-demand home shows peak workers rather than finite-roster utilization',()=>{
 const {run,c,get}=setup();const snapshot=model();snapshot.result.evaluation_context={worker_supply_mode:'on_demand',labor_minutes:240,peak_working_workers:3};c.ganttView.model=snapshot;run('initHome()');
 assert.equal(get('homeMetric-worker').textContent,'3.0');assert.equal(get('homeUnit-worker').textContent,'');assert.ok(get('homeMetrics').innerHTML.includes('峰值同时作业人数'));
});
