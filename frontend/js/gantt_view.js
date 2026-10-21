/** One virtualized Canvas for all scheduling perspectives. Events stay referenced. */
const ganttView={model:null,view:'product',area:'',type:'',search:'',start:0,end:1,zoom:1,rows:[],hits:[],selected:null,frame:0};
const ganttColors={NORMAL:'#367bea',WAITING:'#d99129',REST:'#919aaa',REWORK:'#9466cf',IN_PROGRESS:'#367bea'};
const ganttNames={NORMAL:'工作',WAITING:'等待',REST:'休息',REWORK:'返工',IN_PROGRESS:'未完成'};
function ganttElement(id){return document.getElementById(id);}
function initGanttControls(result){
 if(ganttView.model?.result===result)return;
 const start=performance.now();ganttView.model=ResultView.create(result);ganttView.start=0;ganttView.end=Math.max(1,ganttView.model.duration);ganttView.zoom=1;ganttView.selected=null;
 const select=ganttElement('ganttArea');select.innerHTML='<option value="">全部工区</option>'+[...ganttView.model.areas].map(([id,label])=>`<option value="${capacityEscape(id)}">${capacityEscape(label)}</option>`).join('');ganttView.area='';
 ganttElement('ganttFrom').value=0;ganttElement('ganttTo').value=ganttView.end;ganttElement('ganttDetails').innerHTML='<div class="detail-empty">选择一项任务<br><small>查看人员、资源与执行记录</small></div>';
 ganttView.adaptMs=performance.now()-start;ganttElement('ganttScroll').dataset.adaptMs=ganttView.adaptMs.toFixed(2);updateGantt();
}
function updateGantt(){
 const g=ganttView,m=g.model;if(!m)return;const begin=performance.now();
 g.area=ganttElement('ganttArea').value;g.type=ganttElement('ganttType').value;g.search=ganttElement('ganttSearch').value.trim().toLowerCase();
 let top=0;g.filteredEvents=new Set();g.rows=[];
 for(const row of m.views[g.view].values()){
  const nameMatch=!g.search||row.id.toLowerCase().includes(g.search)||row.label?.toLowerCase().includes(g.search);
  if(!nameMatch)continue;
  const events=row.events.filter(e=>(!g.area||m.eventArea(e)===g.area)&&(!g.type||e.event_type===g.type));
  if((g.area||g.type)&&!events.length)continue;
  // Lane identities remain stable while filtering or changing the time window.
  const shown={row,top,height:Math.max(50,row.height),index:!g.area&&!g.type?row.index:ResultView.intervalIndex(events)};g.rows.push(shown);top+=shown.height;for(const e of events)g.filteredEvents.add(e);
 }
 ganttElement('ganttSpacer').style.height=Math.max(top+42,100)+'px';ganttElement('ganttSpacer').style.width=Math.max(1,(ganttElement('ganttScroll').clientWidth-200)*g.zoom+200)+'px';
 ganttElement('ganttFooter').textContent=`${g.rows.length} 个对象 · ${g.filteredEvents.size.toLocaleString()} 条筛选事件 · 原始时间单位：分钟 · Ctrl＋滚轮缩放`;
 g.filterMs=performance.now()-begin;ganttElement('ganttScroll').dataset.filterMs=g.filterMs.toFixed(2);requestGanttDraw();
}
function requestGanttDraw(){if(!ganttView.frame)ganttView.frame=requestAnimationFrame(()=>{ganttView.frame=0;drawGantt();});}
function drawGantt(target,exporting=false){
 const drawStart=performance.now();const g=ganttView,m=g.model;if(!m)return;const viewport=ganttElement('ganttScroll'),c=target||ganttElement('scheduleCanvas'),w=viewport.clientWidth,h=viewport.clientHeight;if(w<1||h<1)return;
 const dpr=exporting?1:window.devicePixelRatio||1;if(c.width!==Math.round(w*dpr))c.width=Math.round(w*dpr);if(c.height!==Math.round(h*dpr))c.height=Math.round(h*dpr);if(!exporting){c.style.width=w+'px';c.style.height=h+'px';}
 const ctx=c.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h);
 const labelWidth=200,header=42,pixels=(w-labelWidth)*g.zoom/(g.end-g.start),left=viewport.scrollLeft,scroll=viewport.scrollTop;
 const timeX=t=>labelWidth+(t-g.start)*pixels-left;g.hits=[];
 const step=Math.pow(10,Math.floor(Math.log10(Math.max(1,(g.end-g.start)/g.zoom/6))));const tick=step*([1,2,5,10].find(v=>v*step>=(g.end-g.start)/g.zoom/8)||10);
 const first=g.start+left/pixels,last=first+(w-labelWidth)/pixels;
 ctx.font='12px "Microsoft YaHei",sans-serif';
 for(let t=Math.ceil(first/tick)*tick;t<=last;t+=tick){const x=timeX(t);ctx.strokeStyle='#edf0f5';ctx.beginPath();ctx.moveTo(x,header);ctx.lineTo(x,h);ctx.stroke();}
 ctx.save();ctx.beginPath();ctx.rect(labelWidth,header,w-labelWidth,h-header);ctx.clip();
 for(const r of g.rows){const y=header+r.top-scroll;if(y+r.height<header||y>h)continue;
  ctx.strokeStyle='#edf0f5';ctx.beginPath();ctx.moveTo(labelWidth,y+r.height);ctx.lineTo(w,y+r.height);ctx.stroke();
  for(const e of r.index.query(first,last)){
   const x=Math.max(labelWidth,timeX(e.start_time)),right=Math.min(w,timeX(e.end_time)),width=right-x;if(width<=0)continue;
   const ey=y+24+(r.row.lanes.get(e)||0)*20;ctx.fillStyle=ganttColors[e.event_type]||'#367bea';ctx.fillRect(x,ey,width,16);
   if(e.event_type==='IN_PROGRESS'||e.is_complete===false&&e.event_type!=='WAITING'){
    ctx.save();ctx.beginPath();ctx.rect(x,ey,width,16);ctx.clip();ctx.strokeStyle='#ffffffaa';for(let k=x-16;k<right;k+=8){ctx.beginPath();ctx.moveTo(k,ey+16);ctx.lineTo(k+16,ey);ctx.stroke();}ctx.restore();
   }
   if(g.selected===e){ctx.strokeStyle='#162e50';ctx.lineWidth=2;ctx.strokeRect(x,ey,width,16);ctx.lineWidth=1;}
   if(width>48){ctx.fillStyle='#fff';ctx.fillText((e.step_id||ganttNames[e.event_type]||'').slice(0,Math.floor(width/9)),x+4,ey+12);}
   g.hits.push({x,y:ey,w:width,h:16,event:e});
  }
 }
 ctx.restore();ctx.fillStyle='#f8fafc';ctx.fillRect(0,header,labelWidth,h-header);
 for(const r of g.rows){const y=header+r.top-scroll;if(y+r.height<header||y>h)continue;
  ctx.save();ctx.beginPath();ctx.rect(8,header,labelWidth-16,h-header);ctx.clip();ctx.fillStyle='#24354b';ctx.font='12px "Microsoft YaHei",sans-serif';ctx.fillText((r.row.id.length>27?r.row.id.slice(0,12)+'…'+r.row.id.slice(-13):r.row.id),12,y+18);
  ctx.fillStyle='#78869a';ctx.font='11px "Microsoft YaHei",sans-serif';const visible=r.index.query(g.start,g.end).length;
  ctx.fillText(r.row.capacity!=null?`有效容量 ${r.row.capacity} · ${r.row.laneCount} 占用轨道`:r.row.events.length?(visible?'任务分轨展示':'本时窗无任务'):'整期无作业',12,y+35);ctx.restore();
 }
 ctx.fillStyle='#f1f5f9';ctx.fillRect(0,0,w,header);ctx.fillStyle='#596b81';ctx.font='12px "Microsoft YaHei",sans-serif';ctx.fillText({product:'产品 / 发动机',worker:'实际人员',resource:'设备与工位'}[g.view],12,26);
 ctx.save();ctx.beginPath();ctx.rect(labelWidth,0,w-labelWidth,header);ctx.clip();for(let t=Math.ceil(first/tick)*tick;t<=last;t+=tick)ctx.fillText(m.formatTime(t),timeX(t)+5,26);ctx.restore();
 if(!g.rows.length){ctx.fillStyle='#78869a';ctx.fillText('暂无符合条件的任务，请调整筛选或载入结果',labelWidth+24,100);}
 g.lastDrawAt=performance.now();viewport.dataset.drawMs=(g.lastDrawAt-drawStart).toFixed(2);viewport.dataset.visibleEvents=g.hits.length;c.dataset.dpr=dpr;viewport.dataset.browser=navigator.userAgent;
}
function ganttSetView(view){ganttView.view=view;document.querySelectorAll('[data-gantt-view]').forEach(b=>b.classList.toggle('active',b.dataset.ganttView===view));ganttElement('ganttScroll').scrollTop=0;updateGantt();}
function ganttRange(kind){const g=ganttView;if(!g.model)return;const from=Number(ganttElement('ganttFrom').value)||0,start=kind==='full'?0:Math.max(0,from),end=kind==='day'?Math.min(g.model.duration,start+g.model.minutesPerDay):kind==='week'?Math.min(g.model.duration,start+g.model.minutesPerDay*5):kind==='full'?Math.max(1,g.model.duration):Number(ganttElement('ganttTo').value);if(!Number.isFinite(end)||end<=start){showToast('结束时间需要晚于开始时间','warning');return;}g.start=start;g.end=end;g.zoom=1;ganttElement('ganttFrom').value=start;ganttElement('ganttTo').value=end;ganttElement('ganttScroll').scrollLeft=0;updateGantt();}
function ganttZoom(factor,anchor=.5){const g=ganttView,scroll=ganttElement('ganttScroll'),width=Math.max(1,scroll.clientWidth-200),old=g.zoom,next=Math.max(1,Math.min(100,old*factor));g.zoom=next;ganttElement('ganttSpacer').style.width=(width*next+200)+'px';scroll.scrollLeft=(scroll.scrollLeft+width*anchor)*next/old-width*anchor;requestGanttDraw();}
function showGanttDetail(e){
 ganttView.selected=e;const m=ganttView.model,entry=(label,value)=>`<dt>${label}</dt><dd>${capacityEscape(value??'历史结果未记录')}</dd>`;
 const complete=e.event_type!=='IN_PROGRESS'&&e.is_complete!==false;
 ganttElement('ganttDetails').innerHTML=`<div class="eyebrow">任务详情</div><h3>${capacityEscape(e.task_name||e.step_id||ganttNames[e.event_type])}</h3><dl>${entry('产品',e.engine_id)}${entry('工序',e.step_id)}${entry('所属工区',m.eventArea(e)||null)}${entry('事件',ganttNames[e.event_type]||e.event_type)}${entry('开始',m.formatTime(e.start_time)+' / '+Number(e.start_time).toFixed(2)+' 分钟')}${entry('结束',m.formatTime(e.end_time)+' / '+Number(e.end_time).toFixed(2)+' 分钟')}${entry('已发生时长',(e.end_time-e.start_time).toFixed(2)+' 分钟')}${entry('人员',(e.worker_ids||[]).join('、')||'未记录')}${entry('实际设备',(e.equipment_used||[]).join('、')||'无占用记录')}${entry('工位',e.workstation_id)}${entry('返工次数',e.rework_count)}${entry('等待原因',({area:'同一工区工序串行等待',equipment:'等待设备',workstation:'等待工位',workers:'等待人员'}[e.wait_reason]||e.wait_reason||'无'))}${entry('受阻资源',(e.wait_resource_ids||[]).join('、')||'无')}${entry('完成状态',complete?'该事件已结束':'未完成；不计入完成量')}</dl><button class="btn btn-secondary" id="locateProcess">定位到流程</button><p id="locateHint" class="muted"></p>`;
 const b=ganttElement('locateProcess');const compatible=workbenchProcessMatches();b.disabled=!compatible||!e.step_id;ganttElement('locateHint').textContent=compatible?'':'当前流程与结果快照不一致，无法定位。';b.onclick=()=>{if(!workbenchProcessMatches())return;switchTab('editor');state.selectedNode=state.nodes.find(n=>n.stepId===e.step_id);state.stationFilter=null;ganttElement('stationFilter').value='';if(state.selectedNode){const container=stationContainers[state.selectedNode.station];if(container)container.collapsed=false;resizeCanvas();const center=getCanvasContentCenter();canvasOffset.x=center.x-(state.selectedNode.x+60)*scale;canvasOffset.y=center.y-(state.selectedNode.y+25)*scale;renderCanvas();}};requestGanttDraw();
}
function downloadWorkbench(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function exportGanttCSV(filtered=false){const g=ganttView;if(!g.model)return;const keys=['engine_id','step_id','task_name','area_id','workstation_id','event_type','start_time','end_time','worker_ids','equipment_used','wait_reason','wait_resource_ids','is_complete'];const quote=v=>'"'+String(Array.isArray(v)?v.join(';'):v??'').replaceAll('"','""')+'"';const events=filtered?[...g.filteredEvents].filter(e=>e.end_time>=g.start&&e.start_time<=g.end):g.model.events;downloadWorkbench(new Blob(['\ufeff'+[keys.join(','),...events.map(e=>keys.map(k=>quote(e[k])).join(','))].join('\r\n')],{type:'text/csv;charset=utf-8'}),filtered?'当前筛选事件.csv':'全部仿真事件.csv');}
function exportGanttPNG(){const g=ganttView;if(!g.model)return;const source=ganttElement('scheduleCanvas'),c=document.createElement('canvas'),dpr=devicePixelRatio||1;c.width=source.width/dpr;c.height=source.height/dpr+112;const ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);ctx.fillStyle='#1e3048';ctx.font='bold 20px Microsoft YaHei';ctx.fillText('装配排产 · '+{product:'产品',worker:'人员',resource:'设备与工位'}[g.view]+'视角',20,30);ctx.font='12px Microsoft YaHei';ctx.fillText(`${workbenchContextText()} · ${g.start}—${g.end} 分钟`,20,53);ctx.fillText(`工区：${g.area||'全部'} · 对象：${g.search||'全部'} · 类型：${g.type||'全部'} · 导出当前可见窗口`,20,74);ctx.drawImage(source,0,90,c.width,source.height/dpr);ctx.fillText('蓝 工作 / 斜纹 未完成　橙 等待　灰 休息　紫 返工',20,c.height-5);let dialog=document.getElementById('ganttExportPreview');if(!dialog){dialog=document.createElement('dialog');dialog.id='ganttExportPreview';dialog.className='export-preview';dialog.innerHTML='<header><h3>排产甘特 PNG</h3><button class="btn btn-secondary" onclick="this.closest(\'dialog\').close()">关闭</button></header><img alt="当前甘特图导出预览"><footer><a class="btn btn-primary" download="排产甘特.png">下载 PNG</a></footer>';document.body.appendChild(dialog);}const url=c.toDataURL('image/png');dialog.querySelector('img').src=url;dialog.querySelector('a').href=url;dialog.showModal();}
document.addEventListener('DOMContentLoaded',()=>{
 const scroll=ganttElement('ganttScroll'),canvas=ganttElement('scheduleCanvas');scroll.addEventListener('scroll',requestGanttDraw,{passive:true});new ResizeObserver(requestGanttDraw).observe(scroll);
 scroll.addEventListener('wheel',e=>{if(!e.ctrlKey)return;e.preventDefault();ganttZoom(e.deltaY<0?1.2:1/1.2,Math.max(0,(e.clientX-scroll.getBoundingClientRect().left-200)/(scroll.clientWidth-200)));},{passive:false});
 scroll.addEventListener('mousemove',e=>{const r=canvas.getBoundingClientRect(),hit=ganttView.hits.findLast(h=>e.clientX-r.left>=h.x&&e.clientX-r.left<=h.x+h.w&&e.clientY-r.top>=h.y&&e.clientY-r.top<=h.y+h.h);scroll.style.cursor=hit?'pointer':'default';scroll.title=hit?`${hit.event.engine_id} · ${hit.event.task_name||hit.event.step_id} · ${ganttNames[hit.event.event_type]} · ${hit.event.start_time}—${hit.event.end_time} 分钟`:(e.clientX-r.left<200?(ganttView.rows.find(row=>e.clientY-r.top+scroll.scrollTop-42>=row.top&&e.clientY-r.top+scroll.scrollTop-42<row.top+row.height)?.row.id||''):'');});
 scroll.addEventListener('click',e=>{const pickStart=performance.now();const r=canvas.getBoundingClientRect(),hit=ganttView.hits.findLast(h=>e.clientX-r.left>=h.x&&e.clientX-r.left<=h.x+h.w&&e.clientY-r.top>=h.y&&e.clientY-r.top<=h.y+h.h);if(hit)showGanttDetail(hit.event);else if(e.clientX-r.left<200){const row=ganttView.rows.find(row=>e.clientY-r.top+scroll.scrollTop-42>=row.top&&e.clientY-r.top+scroll.scrollTop-42<row.top+row.height);if(row){const resource=row.row;ganttElement('ganttDetails').innerHTML=`<div class="eyebrow">对象详情</div><h3>${capacityEscape(resource.label||resource.id)}</h3><dl><dt>真实编号</dt><dd>${capacityEscape(resource.id)}</dd><dt>有效容量</dt><dd>${resource.capacity??(ganttView.view==='worker'?1:'历史结果未记录')}</dd><dt>整期事件数</dt><dd>${resource.events.length}</dd><dt>当前时窗事件数</dt><dd>${row.index.query(ganttView.start,ganttView.end).length}</dd><dt>状态</dt><dd>${resource.events.length?(row.index.query(ganttView.start,ganttView.end).length?'有任务记录':'本时窗无任务'):'整期无作业'}</dd></dl>`;}}scroll.dataset.pickMs=(performance.now()-pickStart).toFixed(2);});
 for(const id of ['ganttArea','ganttType'])ganttElement(id).onchange=updateGantt;let timer;ganttElement('ganttSearch').oninput=()=>{clearTimeout(timer);timer=setTimeout(updateGantt,100);};
});
