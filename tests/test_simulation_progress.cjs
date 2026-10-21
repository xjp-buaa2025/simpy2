const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject};};
function setup(){
    const timers=new Map(),intervals=new Map(),elements={},steps=[];let serial=0;
    const element=()=>({hidden:true,textContent:'',style:{},attrs:{},classes:new Set(),focus(){},
        setAttribute(key,value){this.attrs[key]=value},removeAttribute(key){delete this.attrs[key]},
        get classList(){return {add:name=>this.classes.add(name),remove:(...names)=>names.forEach(n=>this.classes.delete(n)),
            toggle:(name,active)=>active?this.classes.add(name):this.classes.delete(name)}}});
    for(let i=0;i<4;i++)steps.push(element());
    const c=vm.createContext({console,AbortController,state:{nodes:[1,2,3,4]},crypto:{randomUUID:()=>`progress_${++serial}`},
        document:{activeElement:null,getElementById:id=>elements[id]??=element(),querySelectorAll:()=>steps,addEventListener(){}},
        setTimeout:(callback,delay)=>{const id=++serial;timers.set(id,{callback,delay});return id},clearTimeout:id=>timers.delete(id),
        setInterval:callback=>{const id=++serial;intervals.set(id,callback);return id},clearInterval:id=>intervals.delete(id)});
    vm.runInContext(fs.readFileSync('frontend/js/simulation_progress.js','utf8'),c);
    const run=code=>vm.runInContext(code,c);
    const tick=async()=>{const next=[...timers].sort((a,b)=>a[1].delay-b[1].delay)[0];if(next){timers.delete(next[0]);await next[1].callback();}};
    return {c,run,elements,steps,timers,intervals,tick};
}
const response=data=>({ok:true,status:200,json:async()=>data});
const snapshot=percent=>response({success:true,data:{status:'running',percent,phase:'正在计算主仿真',stage:'main',simulation_minute:60,total_minutes:480}});

test('large progress starts indeterminate and never invents timer percentages',()=>{
    const {run,elements,intervals}=setup();run('openSimulationProgress()');
    assert.equal(elements.loading.hidden,false);
    assert.equal(elements.simulationProgressValue.textContent,'运行中');
    for(const tick of intervals.values())tick();
    assert.equal(elements.simulationProgressBar.attrs['aria-valuenow'],undefined);
    assert.equal(elements.simulationProgressCount.textContent,'4 道工序');
    run('finishSimulationProgress(false,"网络断开")');
    assert.equal(elements.simulationProgressValue.textContent,'未完成');
    assert.equal(elements.simulationProgressDetail.textContent,'网络断开');
    assert.equal(intervals.size,0);
});

test('real server percentages are monotonic and 100 waits for result rendering',async()=>{
    const {c,run,elements,tick,timers,intervals}=setup(),post=deferred();let percent=64;
    c.fetch=async url=>url.includes('/progress/')?snapshot(percent):post.promise;
    run('openSimulationProgress()');const request=run('requestSimulationRun({config:{},process:{}})');
    await tick();assert.equal(elements.simulationProgressValue.textContent,'64%');
    percent=30;await tick();assert.equal(elements.simulationProgressValue.textContent,'64%');
    percent=100;await tick();assert.equal(elements.simulationProgressValue.textContent,'99%');
    post.resolve(response({success:true,data:{}}));await request;
    assert.equal(elements.simulationProgressValue.textContent,'99%');
    assert.equal(timers.size,0,'poll timers stop when the response arrives');
    run('finishSimulationProgress(true)');
    assert.equal(elements.simulationProgressValue.textContent,'100%');
    assert.equal(intervals.size,0);
    await tick();assert.equal(elements.loading.hidden,true);
});

test('two-request improvement evaluations share one bar without premature completion',async()=>{
    const {c,run,elements,tick}=setup();let post=deferred(),percent=100;
    c.fetch=async url=>url.includes('/progress/')?snapshot(percent):post.promise;
    run('openSimulationProgress();setSimulationProgressGroup(2)');
    let request=run('requestSimulationRun({publish_to_clients:false})');await tick();
    assert.equal(elements.simulationProgressValue.textContent,'50%');
    post.resolve(response({success:true,data:{}}));await request;
    post=deferred();percent=20;
    request=run('requestSimulationRun({publish_to_clients:true})');await tick();
    assert.equal(elements.simulationProgressValue.textContent,'60%');
    post.resolve(response({success:true,data:{}}));await request;
    assert.equal(elements.simulationProgressValue.textContent,'99%');
    run('finishSimulationProgress(true)');assert.equal(elements.simulationProgressValue.textContent,'100%');
});

test('older backend support stays indeterminate until the run response completes',async()=>{
    const {c,run,elements,tick,timers}=setup(),post=deferred();
    c.fetch=async url=>url.includes('/progress/')?{ok:false,status:404,json:async()=>({detail:'Not Found'})}:post.promise;
    run('openSimulationProgress()');const request=run('requestSimulationRun({})');await tick();
    assert.equal(elements.simulationProgressValue.textContent,'运行中');assert.equal(timers.size,0);
    post.resolve(response({success:true,data:{}}));await request;run('finishSimulationProgress(true)');
    assert.equal(elements.simulationProgressValue.textContent,'100%');
});

test('request errors stop polling and leave a readable failure panel',async()=>{
    const {c,run,elements,timers,intervals}=setup();c.fetch=async()=>{throw Error('disconnected')};
    run('openSimulationProgress()');await assert.rejects(run('requestSimulationRun({})'),/disconnected/);
    run('finishSimulationProgress(false,"请求失败，请重试")');
    assert.equal(timers.size,0);assert.equal(intervals.size,0);
    assert.equal(elements.simulationProgressClose.hidden,false);
    assert.equal(elements.loading.classes.has('failed'),true);
    run('closeSimulationProgress()');assert.equal(elements.loading.hidden,true);
});

test('a late poll from the previous run cannot overwrite a new run',async()=>{
    const {c,run,elements,tick}=setup(),poll=deferred(),post=deferred();
    c.fetch=async url=>url.includes('/progress/')?poll.promise:post.promise;
    run('openSimulationProgress()');const request=run('requestSimulationRun({})'),pending=tick();
    run('openSimulationProgress()');poll.resolve(snapshot(88));await pending;
    assert.equal(elements.simulationProgressValue.textContent,'运行中');
    post.resolve(response({success:true,data:{}}));await request;
    assert.equal(elements.simulationProgressValue.textContent,'运行中');
    run('finishSimulationProgress(false)');
});
