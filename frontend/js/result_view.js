/* Historical results are read-only; this module never reads the editor or form. */
(function(root){
'use strict';
const number=(v,f=0)=>Number.isFinite(Number(v))?Number(v):f;
const list=v=>Array.isArray(v)?v:[];
function intervalIndex(events){
 const sorted=events.slice().sort((a,b)=>a.start_time-b.start_time||a.end_time-b.end_time),ends=[];let max=-Infinity;
 for(const e of sorted){max=Math.max(max,number(e.end_time));ends.push(max);}
 return {events:sorted,query(start,end){let lo=0,hi=ends.length;while(lo<hi){const m=(lo+hi)>>1;if(ends[m]<start)lo=m+1;else hi=m;}const out=[];for(let i=lo;i<sorted.length&&sorted[i].start_time<=end;i++)if(sorted[i].end_time>=start)out.push(sorted[i]);return out;}};
}
function validate(result){
 if(!result||!Array.isArray(result.gantt_events)||!Number.isFinite(result.sim_duration)||result.sim_duration<0)throw Error('结果格式无效：缺少事件或评估时长');
 for(const e of result.gantt_events)if(!e||!Number.isFinite(e.start_time)||!Number.isFinite(e.end_time)||e.end_time<e.start_time||['worker_ids','equipment_used','wait_resource_ids'].some(k=>e[k]!=null&&!Array.isArray(e[k])))throw Error('结果事件格式无效：请检查时间与资源记录');
 return true;
}
function create(result){
 const snapshot=result.input_snapshot||{},config=snapshot.config||result.config||{},process=snapshot.process||{},evaluation=result.evaluation_context||config.evaluation||{};
 const events=list(result.gantt_events),nodes=new Map(list(process.nodes).map(n=>[n.step_id,n]));
 const catalog=new Map(list(result.resource_snapshot?.resources).map(r=>[r.resource_id,r]));
 const stationLabels=new Map(list(process.station_catalog).map(s=>[s.area_id||s.station_id,s.label]));
 const views={product:new Map(),worker:new Map(),resource:new Map()},areas=new Map();
 const add=(view,id,e,meta={})=>{if(id==null||id==='')return;id=String(id);let row=views[view].get(id);if(!row){row={id,label:id,events:[],...meta};views[view].set(id,row);}if(e)row.events.push(e);};
 for(const w of list(result.worker_stats)){const id=w.worker_id||w.resource_id;add('worker',id,null,{stats:w});}
 for(const [id,r] of catalog)if(!id.startsWith('workers:'))add('resource',id,null,{label:r.label||id,capacity:r.capacity,owner:r.owner});
 for(const e of events){
  const n=nodes.get(e.step_id),aid=e.area_id||n?.area_id||n?.station;if(aid){const label=config.capacity_model?.areas?.[aid]?.label||stationLabels.get(aid)||aid;areas.set(aid,label===aid?aid:`${aid} ${label}`);}
  add('product',e.engine_id,e);
  for(const id of new Set(list(e.worker_ids)))add('worker',id,e);
  if(e.event_type==='WAITING'||e.event_type==='REST')continue;
  for(const id of new Set(list(e.equipment_used)))add('resource',id,e,catalog.get(id)?{label:catalog.get(id).label,capacity:catalog.get(id).capacity}:{});
  if(e.workstation_id&&!list(e.equipment_used).includes('workstation:'+e.workstation_id)){const id='workstation:'+e.workstation_id;add('resource',id,e,{capacity:result.resource_snapshot?.effective_workstations?.[e.workstation_id]?.capacity??catalog.get(id)?.capacity});}
 }
 const eventArea=e=>e.area_id||nodes.get(e.step_id)?.area_id||nodes.get(e.step_id)?.station||'';
 const lanes=new WeakMap();
 for(const [view,map] of Object.entries(views))for(const row of map.values()){
  row.index=intervalIndex(row.events);const ends=[];row.lanes=new WeakMap();
  for(const e of row.index.events){let lane=ends.findIndex(t=>t<=e.start_time);if(lane<0)lane=ends.length;ends[lane]=e.end_time;row.lanes.set(e,lane);}
  row.laneCount=Math.max(1,ends.length);row.height=30+row.laneCount*20;
 }
 const duration=number(result.sim_duration,Math.max(0,...events.slice(0,1000).map(e=>e.end_time)));
 const minutesPerDay=number(result.time_mapping?.minutes_per_day,number(config.work_hours_per_day,8)*60);
 return {result,config,evaluation,process,nodes,events,views,areas,eventArea,duration,minutesPerDay,
  formatTime(t){return `第${Math.floor(t/minutesPerDay)+1}工作日 ${Math.floor((t%minutesPerDay)/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;},
  matches(e,filter={}){return (!filter.area||eventArea(e)===filter.area)&&(!filter.type||e.event_type===filter.type)&&(!filter.object||String(e.engine_id).includes(filter.object)||list(e.worker_ids).some(id=>String(id).includes(filter.object))||list(e.equipment_used).some(id=>String(id).includes(filter.object))||String(e.workstation_id||'').includes(filter.object));}
 };
}
const api={create,intervalIndex,validate};root.ResultView=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
