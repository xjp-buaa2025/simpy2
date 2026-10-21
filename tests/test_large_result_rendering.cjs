const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');

function setup(){
 const elements=new Map(),charts=[];
 function element(id){
  if(!elements.has(id)){
   let html='';const el={value:id==='fatigueWorkerSelect'?'all':'',hidden:false,disabled:false,writes:0,textContent:''};
   Object.defineProperty(el,'innerHTML',{get:()=>html,set:value=>{html=value;el.writes++;}});elements.set(id,el);
  }
  return elements.get(id);
 }
 class Chart{constructor(target,config){this.target=target;this.config=config;charts.push(this);}destroy(){}}
 const c=vm.createContext({console,Chart,workerChart:null,equipmentChart:null,fatigueChart:null,
  window:{},state:{simulationResult:null},document:{getElementById:element},charts});
 for(const name of ['charts','simulation','station_progress_view'])vm.runInContext(fs.readFileSync(`frontend/js/${name}.js`,'utf8'),c);
 return {c,element,charts,run:code=>vm.runInContext(code,c)};
}

test('5000 worker options are installed once and fatigue pages retain every exact curve',()=>{
 const {c,element,charts,run}=setup();
 const workers=Array.from({length:5000},(_,i)=>({resource_id:`worker-${i}`,fatigue_history:[[0,i%100],[100,10]],work_time:i,rest_time:0}));
 c.state.simulationResult={worker_stats:workers,sim_duration:10000};
 run('initFatigueSelect(state.simulationResult);updateFatigueChart()');
 assert.equal(element('fatigueWorkerSelect').writes,1);
 assert.equal((element('fatigueWorkerSelect').innerHTML.match(/<option /g)||[]).length,5001);
 const seen=[];
 for(let page=0;page<250;page++){
  const chart=charts.at(-1);assert.equal(chart.config.data.datasets.length,20);
  seen.push(...chart.config.data.datasets.map(d=>d.label));
  if(page<249)run('changeFatiguePage(1)');
 }
 assert.deepEqual(seen,workers.map(w=>w.resource_id));
 assert.equal(element('fatigueChartNext').disabled,true);
 element('fatigueWorkerSelect').value='worker-4999';run('changeFatigueWorker()');
 assert.equal(charts.at(-1).config.data.datasets.length,1);
 assert.equal(charts.at(-1).config.data.datasets[0].label,'worker-4999');
 assert.equal(element('fatigueChartPager').hidden,true);
 assert.equal(workers.length,5000);
});

test('worker utilization pages preserve exact work and rest values',()=>{
 const {c,element,charts,run}=setup();
 c.fixture={sim_duration:100,worker_stats:Array.from({length:81},(_,i)=>({resource_id:String(i),work_time:i,rest_time:2}))};
 run('updateWorkerChart(fixture)');assert.equal(charts.at(-1).config.data.labels.length,40);
 run('changeWorkerChartPage(1);changeWorkerChartPage(1)');
 assert.deepEqual(Array.from(charts.at(-1).config.data.labels),['80']);
 assert.deepEqual(Array.from(charts.at(-1).config.data.datasets[0].data),[80]);
 assert.equal(element('workerChartNext').disabled,true);
 c.fixture={sim_duration:100,worker_stats:[]};run('updateWorkerChart(fixture)');
 assert.equal(element('workerChartPager').hidden,true);
});

test('20001 station progress records remain reachable with bounded table size',()=>{
 const {c,element,run}=setup();
 c.fixture={stations:[{station_id:'A',label:'工位',total_steps:3,engines:Array.from({length:20001},(_,i)=>({engine_id:i,progress:.5,completed_steps:1,state:'in_progress'}))}]};
 run('renderStationProgress(fixture)');
 assert.equal((element('stationProgressRows').innerHTML.match(/<tr>/g)||[]).length,100);
 assert.match(element('stationProgressPageLabel').textContent,/20001/);
 run('changeStationProgressPage(200)');
 assert.equal((element('stationProgressRows').innerHTML.match(/<tr>/g)||[]).length,1);
 assert.match(element('stationProgressRows').innerHTML,/<td>20000<\/td>/);
 assert.equal(element('stationProgressNext').disabled,true);
 run('renderStationProgress({stations:[]})');
 assert.equal(element('stationProgressPager').hidden,true);
 assert.match(element('stationProgressRows').innerHTML,/没有符合条件/);
});

test('worker names remain text in the bulk option update',()=>{
 const {c,element,run}=setup();c.fixture={worker_stats:[{resource_id:'<img src=x onerror="bad">'}]};
 run('initFatigueSelect(fixture)');assert.ok(!element('fatigueWorkerSelect').innerHTML.includes('<img'));
 assert.match(element('fatigueWorkerSelect').innerHTML,/&lt;img/);
});
