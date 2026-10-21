const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(){
  const elements={};
  const c=vm.createContext({console,document:{addEventListener(){},getElementById(id){return elements[id]}},window:{addEventListener(){}},state:{nodes:[{id:'1',stepId:'P',station:'A',stdDuration:5,requiredTools:''}],stations:[{id:'A',name:'Area'}],config:{criticalEquipment:{test:2}}},stationContainers:{A:{x:0,y:0,width:200,height:100,collapsed:false}},getConfigFromUI:()=>({}),buildProcessDefinition:()=>({nodes:[]})});
  vm.runInContext(fs.readFileSync('frontend/js/capacity.js','utf8'),c);
  return {c,elements,run:code=>vm.runInContext(code,c)};
}
test('opening a model snapshot never enables or mutates the saved model',()=>{
  const {run}=setup();
  run("capacityCatalog={P:{area_id:'A',label:'Station',capacity:1}}; const snapshot=capacityModelSnapshot(); snapshot.model.areas.A.dedicated_workers=4;");
  assert.equal(run('state.capacityModel'),undefined);
  assert.equal(run('state.nodes[0].workstationId'),undefined);
});
test('zero shared equipment fields do not mark a draft dirty',()=>{
  const {run}=setup();
  run("const d={aid:'A',model:{areas:{A:{equipment:{},dedicated_workers:0}},workstations:{}},bindings:{},tools:{}}; const initial=areaEditableSignature(d); d.model.areas.A.equipment.test=0;");
  assert.equal(run('initial===areaEditableSignature(d)'),true);
  assert.equal(run('d.model.areas.A.equipment.test=1; initial===areaEditableSignature(d)'),false);
});
test('save reads all current input values even before blur',()=>{
  const {run,elements}=setup();
  const fields={'#areaName':{value:'Edited'},'#areaWorkerMode':{value:'fixed'},'#areaWorkers':{value:'6'}};
  elements.areaPanelBody={querySelector:s=>fields[s],querySelectorAll:s=>s==='[data-station]'?[{dataset:{station:'W'},value:'2'}]:[]};
  run("areaDraft={aid:'A',model:{areas:{A:{equipment:{}}},workstations:{W:{capacity:1}}}};readAreaDraft();");
  assert.equal(run('areaDraft.model.areas.A.dedicated_workers'),undefined);
  assert.equal(run('areaDraft.model.workstations.W.capacity'),2);
  assert.equal(run('areaDraft.model.areas.A.label'),'Edited');
});
test('actual wait events identify a specific blocked device',()=>{
  const {run}=setup();
  run("capacityLastResult={gantt_events:[{area_id:'A',event_type:'WAITING',wait_reason:'equipment',wait_resource_ids:['equipment:A:test'],start_time:1,end_time:7},{area_id:'A',event_type:'WAITING',wait_reason:'workers',wait_resource_ids:['workers:A'],start_time:0,end_time:2}],resource_snapshot:{resources:[{resource_id:'equipment:A:test',label:'检测设备'}]}};");
  assert.equal(run("capacityMajorWait('A').label"),'检测设备');
  assert.equal(run("capacityMajorWait('A').minutes"),6);
});
test('comparison fixes process and evaluation conditions while permitting resource changes',()=>{
  const {run}=setup();
  run("const a={config:{num_workers:4,critical_equipment:{test:1},evaluation:{mode:'capacity',max_wip:8},capacity_model:{enabled:true,areas:{A:{dedicated_workers:1}},workstations:{W:{capacity:1}}}},process:{nodes:[{step_id:'p',x:10,std_duration:5}]}};const b=capacityClone(a);b.config.num_workers=6;b.config.capacity_model.workstations.W.capacity=2;b.process.nodes[0].x=20;");
  assert.equal(run('capacityFixedSignature(a)===capacityFixedSignature(b)'),true);
  assert.equal(run('capacityNormalizedInput(a)===capacityNormalizedInput(b)'),false);
  assert.equal(run('b.config.evaluation.max_wip=10;capacityFixedSignature(a)===capacityFixedSignature(b)'),false);
});
test('collapsed and filtered nodes share drawing and hit-testing visibility',()=>{
  const {c,run}=setup();
  vm.runInContext(fs.readFileSync('frontend/js/canvas.js','utf8'),c);
  run("state.nodes[0].x=10;state.nodes[0].y=40;state.showStationContainers=true;state.stationFilter=null;stationContainers.A.collapsed=true;");
  assert.equal(run('findNodeAt({x:20,y:50})'),null);
  run("stationContainers.A.collapsed=false;state.stationFilter='B';");
  assert.equal(run('findNodeAt({x:20,y:50})'),null);
  assert.equal(run('findStationContainerAt({x:20,y:50})'),null);
  assert.equal(run("state.stationFilter='A';findNodeAt({x:20,y:50}).id"),'1');
});
test('Delete in an input cannot delete a canvas node',()=>{
  const {c,run}=setup();
  vm.runInContext(fs.readFileSync('frontend/js/canvas.js','utf8'),c);
  run("let deleted=false;function deleteSelectedNode(){deleted=true;}handleKeyDown({key:'Delete',target:{tagName:'INPUT',isContentEditable:false,closest(){return this}}});");
  assert.equal(run('deleted'),false);
});
test('right mouse cannot start a drag or connection',()=>{
  const {c,run}=setup();
  vm.runInContext(fs.readFileSync('frontend/js/canvas.js','utf8'),c);
  run("let isConnecting=true,connectStart={},isDragging=true,dragNode={},dragStationContainer={};handleCanvasMouseDown({button:2});");
  assert.equal(run('isConnecting||isDragging||dragNode||dragStationContainer'),null);
});
const comparisonFixture="const input={config:{num_workers:2,random_seed:42,critical_equipment:{test:1},capacity_model:{enabled:true,areas:{A:{label:'Area',equipment:{},dedicated_workers:0,efficiency_multiplier:1.25,resource_sets:2}},workstations:{W:{area_id:'A',capacity:3}}},evaluation:{mode:'plan',max_wip:null}},process:{nodes:[{step_id:'p',workstation_id:'W',station:'A',std_duration:30}]}};";
test('first improvement pairs a default baseline with a common bounded WIP',()=>{
  const {run}=setup();run(comparisonFixture);
  assert.equal(run("const pair=buildAreaComparison(input,null,null);pair.baseline.config.capacity_model.areas.A.resource_sets"),1);
  assert.equal(run('pair.baseline.config.capacity_model.areas.A.efficiency_multiplier'),1);
  assert.equal(run('pair.baseline.config.evaluation.max_wip'),6);
  assert.equal(run('pair.candidate.config.evaluation.max_wip'),6);
  assert.equal(run('pair.candidate.config.evaluation.sampling_scheme'),'paired_v1');
  assert.equal(run('input.config.evaluation.mode'),'plan');
});
test('a prior capability result is reused only under identical evaluation inputs',()=>{
  const {run}=setup();run(comparisonFixture);
  run("const pair=buildAreaComparison(input,null,8);const previous={input_snapshot:pair.candidate};");
  assert.equal(run('buildAreaComparison(input,previous,8).reuse'),true);
  assert.equal(run('buildAreaComparison(input,previous,9).reuse'),false);
  assert.equal(run("previous.input_snapshot.config.evaluation.sampling_scheme='legacy';buildAreaComparison(input,previous,8).reuse"),false);
});
test('two-parameter preview computes added resources from unique stations',()=>{
  const {run}=setup();
  run("state.nodes=[{id:'p',station:'A',requiredWorkers:2},{id:'q',station:'A',requiredWorkers:3}];const d={aid:'A',bindings:{p:'W',q:'W'},tools:{p:'test;test',q:'test'},model:{areas:{A:{resource_sets:2}},workstations:{W:{capacity:2}}}};");
  assert.equal(run('estimateAreaExpansion(d).workers'),undefined);
  assert.equal(run('estimateAreaExpansion(d).equipment.test'),2);
  assert.equal(run('estimateAreaExpansion(d).slots'),2);
});
test('candidate failure preserves the previous displayed result and never publishes the baseline',async()=>{
  const {c,run,elements}=setup();run(comparisonFixture);
  elements.capacityWip={value:''};elements.areaPanelError={textContent:''};
  c.fetch=async(url,options)=>{const request=JSON.parse(options.body);c.calls.push(request);return {json:async()=>c.calls.length===1?{success:true,data:{input_snapshot:request}}:{success:false,message:'controlled failure'}}};
  c.calls=[];c.showLoading=()=>{};c.showToast=()=>{};
  run("getConfigFromUI=()=>input.config;buildProcessDefinition=()=>input.process;refreshCapacitySignals=()=>{};capacityLastResult={sim_id:'valid-old-result'};");
  await run('runAreaImprovement()');
  assert.equal(run('capacityLastResult.sim_id'),'valid-old-result');
  assert.equal(c.calls.length,2);
  assert.equal(c.calls[0].publish_to_clients,false);
  assert.equal(c.calls[1].publish_to_clients,true);
  assert.equal(run('areaEvaluating'),false);
  assert.equal(run('areaRunError'),'controlled failure');
});
