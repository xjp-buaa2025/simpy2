const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function setup({empty=false,edited=false,invalid=false}={}){
 const elements={},calls=[];
 const result={sim_id:'current',gantt_events:[],sim_duration:480,input_snapshot:{process:{name:'current',nodes:[{step_id:'S1'}]},config:{critical_equipment:{old:2},work_hours_per_day:8,capacity_model:{enabled:false,areas:{},workstations:{}},evaluation:{mode:'plan'}}}};
 const state={nodes:[],stations:[],config:{criticalEquipment:{}}};
 const context=vm.createContext({console,JSON,encodeURIComponent,state,workbenchBusy:false,
  document:{addEventListener(){},getElementById:id=>elements[id]??={}},
  buildProcessDefinition:()=>({nodes:state.nodes}),getConfigFromUI:()=>({equipment:state.config.criticalEquipment}),
  areaDraftDirty:()=>false,nodeInspectorDirty:()=>false,capacityClone:v=>JSON.parse(JSON.stringify(v)),
  fetch:async url=>{calls.push(url);if(url.includes('/list/'))return {ok:true,json:async()=>({success:true,data:empty?[]:[{sim_id:'current'}]})};if(edited)state.nodes.push({step_id:'user-edit'});return {ok:true,json:async()=>({success:true,data:result})};},
  ResultView:{validate(){if(invalid)throw Error('invalid');}},
  loadProcessData:p=>{calls.push('load');state.nodes=p.nodes;state.stations=[{id:'WS1'}];},
  renderEquipmentList:()=>calls.push('equipment'),updateStats:()=>calls.push('stats'),
  acceptCapacityResult:r=>calls.push(['accept',r.sim_id]),updateResults:r=>calls.push(['display',r.sim_id]),
  refreshCapacitySignals(){},refreshHome(){},processImportMessage(){},showToast:()=>calls.push('error')});
 vm.runInContext(fs.readFileSync('frontend/js/main.js','utf8'),context);
 return {context,state,calls,run:()=>vm.runInContext('loadCurrentScenario()',context)};
}
test('startup loads current process and real results with no critical equipment',async()=>{
 const {run,state,calls}=setup();await run();assert.equal(state.nodes[0].step_id,'S1');
 assert.deepEqual(Object.keys(state.config.criticalEquipment),[]);assert.equal(state.simulationResult.sim_id,'current');
 assert.ok(calls.some(c=>Array.isArray(c)&&c[0]==='display'&&c[1]==='current'));
 assert.ok(calls.every(c=>typeof c!=='string'||!c.includes('/run')));
});
test('empty history leaves the editor and result state untouched',async()=>{
 const {run,state,calls}=setup({empty:true});await run();assert.equal(state.nodes.length,0);assert.equal(state.simulationResult,undefined);assert.ok(!calls.includes('load'));
});
test('an edit during startup is never overwritten by the fetched snapshot',async()=>{
 const {run,state,calls}=setup({edited:true});await run();assert.equal(state.nodes[0].step_id,'user-edit');assert.equal(state.simulationResult,undefined);assert.ok(!calls.includes('load'));
});
test('invalid results cannot replace the current editor',async()=>{
 const {run,state,calls,context}=setup({invalid:true});context.console={error(){}};await run();assert.equal(state.nodes.length,0);assert.ok(calls.includes('error'));assert.ok(!calls.includes('load'));
});
