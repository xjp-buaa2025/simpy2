const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const ratios=[1,1.25,1.5,2,3];
const source=fs.readFileSync('frontend/js/canvas.js','utf8');
const identity=()=>[1,0,0,1,0,0];
const nearly=(actual,expected,message)=>assert.ok(Math.abs(actual-expected)<1e-8,`${message||'coordinate'}: ${actual} ≠ ${expected}`);

function setup(dpr=1){
  const calls=[],stack=[];
  let matrix=identity();
  const drawing={
    setTransform(...args){matrix=args.slice();calls.push({name:'setTransform',args:args.slice()});},
    getTransform(){const [a,b,c,d,e,f]=matrix;return {a,b,c,d,e,f};},
    reset(){matrix=identity();stack.length=0;},
    save(){stack.push(matrix.slice());},
    restore(){if(stack.length)matrix=stack.pop();},
    translate(x,y){matrix[4]+=matrix[0]*x+matrix[2]*y;matrix[5]+=matrix[1]*x+matrix[3]*y;},
    scale(x,y){matrix[0]*=x;matrix[1]*=x;matrix[2]*=y;matrix[3]*=y;},
    clearRect(...args){calls.push({name:'clearRect',args,transform:matrix.slice()});},
    fillText(...args){calls.push({name:'fillText',args,transform:matrix.slice()});},
    moveTo(...args){calls.push({name:'moveTo',args,transform:matrix.slice()});},
    lineTo(...args){calls.push({name:'lineTo',args,transform:matrix.slice()});},
    measureText(text){return {width:String(text).length*7};}
  };
  const ctx=new Proxy(drawing,{get(target,key){return key in target?target[key]:()=>{};}});
  const toolbar={offsetHeight:50,offsetTop:16};
  const parent={clientWidth:900,clientHeight:600,querySelector:selector=>selector==='.canvas-toolbar'?toolbar:null};
  let bitmapWidth=0,bitmapHeight=0;
  const canvas={
    style:{},dataset:{},parentElement:parent,
    get width(){return bitmapWidth;},set width(value){bitmapWidth=value;drawing.reset();},
    get height(){return bitmapHeight;},set height(value){bitmapHeight=value;drawing.reset();},
    get clientWidth(){return parent.clientWidth;},get clientHeight(){return parent.clientHeight;},
    getBoundingClientRect(){return {left:80,top:100,width:parent.clientWidth,height:parent.clientHeight};},
    getContext:()=>ctx,addEventListener(){}
  };
  const elements={processCanvas:canvas,canvasZoomLabel:{textContent:''},canvasZoomOut:{disabled:false},canvasZoomIn:{disabled:false},stationFilter:{value:''}};
  const node={id:'one',stepId:'S001',taskName:'装配测试',opType:'A',station:'A',x:80,y:120};
  const c=vm.createContext({
    console,performance,canvas,ctx,canvasOffset:{x:41,y:67},scale:1,
    state:{nodes:[node],edges:[],selectedNode:null,stationFilter:null,showStationContainers:true,layoutMode:'normal'},
    stationContainers:{A:{x:50,y:50,width:600,height:350,collapsed:false,name:'测试工区',color:'#367bea'}},
    isDragging:false,isConnecting:false,connectStart:null,dragNode:null,dragStationContainer:null,dragOffset:{x:0,y:0},lastMouseEvent:null,
    window:{devicePixelRatio:dpr,addEventListener(){},matchMedia:()=>({addEventListener(){},removeEventListener(){}})},
    document:{addEventListener(){},getElementById:id=>elements[id],querySelector:()=>null},
    ResizeObserver:class{observe(){}},updateStats(){},showToast(){},hexToRgba:()=> '#367bea22'
  });
  vm.runInContext(source,c);
  return {c,canvas,ctx,calls,parent,toolbar,node,elements,run:code=>vm.runInContext(code,c)};
}

for(const dpr of ratios){
  test(`process Canvas DPR ${dpr} renders sharp pixels and preserves logical hit coordinates`,()=>{
    const {run,canvas,calls,c,node}=setup(dpr);
    run('resizeCanvas()');
    assert.equal(canvas.width,Math.round(900*dpr));
    assert.equal(canvas.height,Math.round(600*dpr));
    assert.equal(run('getCanvasViewport().width'),900);
    assert.equal(run('getCanvasViewport().height'),600);
    const clear=calls.find(call=>call.name==='clearRect');
    assert.deepEqual(clear.args,[0,0,canvas.width,canvas.height]);
    assert.deepEqual(clear.transform,identity());
    const title=calls.find(call=>call.name==='fillText'&&call.args[0]==='A · S001');
    assert.ok(title,'the actual node renderer ran');
    nearly(title.transform[0],dpr,'horizontal backing scale');
    nearly(title.transform[3],dpr,'vertical backing scale');
    c.pointer={clientX:80+41+(node.x+20),clientY:100+67+(node.y+15)};
    assert.equal(run('findNodeAt(getMousePos(pointer)).id'),'one');
    nearly(run('getMousePos(pointer).x'),node.x+20);
    nearly(run('getMousePos(pointer).y'),node.y+15);
  });
}

test('repeated resize and DPR changes preserve zoom, offset and a single backing transform',()=>{
  const {run,c,canvas,calls}=setup(1.25);
  run('scale=1.6;canvasOffset={x:-91,y:38};resizeCanvas()');
  for(const dpr of [1.25,1.5,2,3,1]){
    c.window.devicePixelRatio=dpr;
    calls.length=0;
    run('resizeCanvas();resizeCanvas();renderCanvas()');
    assert.equal(canvas.width,Math.round(900*dpr));
    assert.equal(canvas.height,Math.round(600*dpr));
    assert.equal(run('scale'),1.6);
    assert.equal(run('canvasOffset.x'),-91);
    assert.equal(run('canvasOffset.y'),38);
    for(const title of calls.filter(call=>call.name==='fillText'&&call.args[0]==='A · S001')){
      nearly(title.transform[0],dpr*1.6,'repeated horizontal backing scale');
      nearly(title.transform[3],dpr*1.6,'repeated vertical backing scale');
      nearly(title.transform[4],dpr*-91,'backing translation x');
      nearly(title.transform[5],dpr*38,'backing translation y');
    }
    for(const clear of calls.filter(call=>call.name==='clearRect'))assert.deepEqual(clear.transform,identity());
  }
});

test('fitCanvas uses the CSS viewport consistently at every DPR and contains visible content',()=>{
  let expected;
  for(const dpr of ratios){
    const {run}=setup(dpr);
    run('resizeCanvas();fitCanvas()');
    const view=JSON.parse(run('JSON.stringify({scale,offset:canvasOffset})'));
    if(!expected)expected=view;else assert.deepEqual(view,expected);
    assert.ok(view.offset.x+50*view.scale>=0);
    assert.ok(view.offset.x+650*view.scale<=900);
    assert.ok(view.offset.y+50*view.scale>=82,'content clears the toolbar');
    assert.ok(view.offset.y+400*view.scale<=600);
  }
});

test('grid drawing remains bounded by the logical viewport at high DPR',()=>{
  const {run,calls}=setup(3);
  run('resizeCanvas();canvasOffset={x:0,y:0};scale=1');
  calls.length=0;
  run('drawGrid()');
  const points=calls.filter(call=>call.name==='moveTo'||call.name==='lineTo');
  assert.ok(points.length>0);
  assert.ok(points.every(call=>call.args[0]>=0&&call.args[0]<=900&&call.args[1]>=0&&call.args[1]<=600));
});

test('zoom keeps its anchor stationary, clamps its range and updates the visible percentage',()=>{
  const {run,elements}=setup(2);
  run('resizeCanvas();scale=.75;canvasOffset={x:-120,y:83}');
  const before=JSON.parse(run('JSON.stringify({x:(310-canvasOffset.x)/scale,y:(290-canvasOffset.y)/scale})'));
  run('setCanvasZoom(1.5,{x:310,y:290})');
  nearly(run('(310-canvasOffset.x)/scale'),before.x);
  nearly(run('(290-canvasOffset.y)/scale'),before.y);
  assert.equal(elements.canvasZoomLabel.textContent,'150%');
  run('setCanvasZoom(100,{x:310,y:290})');
  assert.equal(run('scale'),3);
  assert.equal(elements.canvasZoomIn.disabled,true);
  assert.equal(elements.canvasZoomOut.disabled,false);
  run('setCanvasZoom(.0001,{x:310,y:290})');
  assert.equal(run('scale'),.08);
  assert.equal(elements.canvasZoomLabel.textContent,'8%');
  assert.equal(elements.canvasZoomOut.disabled,true);
  assert.equal(elements.canvasZoomIn.disabled,false);
});

test('mouse-wheel zoom retains the world point beneath the cursor',()=>{
  const {run,c}=setup(1.5);
  run('resizeCanvas();scale=.6;canvasOffset={x:-75,y:22}');
  let prevented=false;
  c.pointer={clientX:80+330,clientY:100+270,deltaY:-120,preventDefault(){prevented=true;}};
  const before=JSON.parse(run('JSON.stringify(getMousePos(pointer))'));
  run('handleCanvasWheel(pointer)');
  const after=JSON.parse(run('JSON.stringify(getMousePos(pointer))'));
  assert.ok(prevented);
  assert.ok(run('scale')>.6);
  nearly(after.x,before.x);
  nearly(after.y,before.y);
});

test('toolbar zoom and 100% reset preserve the drawable content center',()=>{
  const {run,elements}=setup(2);
  run('resizeCanvas();scale=.5;canvasOffset={x:-120,y:35}');
  assert.equal(run('getCanvasContentCenter().x'),450);
  assert.equal(run('getCanvasContentCenter().y'),341);
  const before=JSON.parse(run('JSON.stringify({x:(450-canvasOffset.x)/scale,y:(341-canvasOffset.y)/scale})'));
  run('zoomCanvas(1.2)');
  nearly(run('scale'),.6);
  nearly(run('(450-canvasOffset.x)/scale'),before.x);
  nearly(run('(341-canvasOffset.y)/scale'),before.y);
  run('resetCanvasZoom()');
  assert.equal(run('scale'),1);
  assert.equal(elements.canvasZoomLabel.textContent,'100%');
  nearly(run('(450-canvasOffset.x)/scale'),before.x);
  nearly(run('(341-canvasOffset.y)/scale'),before.y);
});

test('zero-delta wheel events leave the view unchanged',()=>{
  const {run,c}=setup();
  run('resizeCanvas();scale=.7;canvasOffset={x:-21,y:44}');
  c.pointer={clientX:300,clientY:300,deltaY:0,preventDefault(){}};
  run('handleCanvasWheel(pointer)');
  assert.equal(run('scale'),.7);
  assert.equal(run('canvasOffset.x'),-21);
  assert.equal(run('canvasOffset.y'),44);
});

test('fractional CSS dimensions use the actual displayed viewport for fitting and hits',()=>{
  const {run,c,parent,canvas,node}=setup(1.25);
  parent.clientWidth=899;parent.clientHeight=599;
  canvas.getBoundingClientRect=()=>({left:80,top:100,width:899.5,height:599.5});
  run('resizeCanvas()');
  assert.equal(canvas.width,Math.round(899.5*1.25));
  assert.equal(canvas.height,Math.round(599.5*1.25));
  assert.equal(run('getCanvasViewport().width'),899.5);
  assert.equal(run('getCanvasViewport().height'),599.5);
  run('scale=.8;canvasOffset={x:-40,y:20}');
  c.pointer={clientX:80-40+(node.x+20)*.8,clientY:100+20+(node.y+15)*.8};
  assert.equal(run('findNodeAt(getMousePos(pointer)).id'),'one');
});

test('hidden editor dimensions do not destroy the view and restore at the current DPR',()=>{
  const {run,c,parent,canvas}=setup(2);
  run('resizeCanvas();scale=1.25;canvasOffset={x:-40,y:70}');
  parent.clientWidth=0;parent.clientHeight=0;
  assert.doesNotThrow(()=>run('resizeCanvas();fitCanvas()'));
  assert.equal(canvas.width,1800);
  assert.equal(canvas.height,1200);
  assert.equal(run('scale'),1.25);
  assert.equal(run('canvasOffset.x'),-40);
  assert.equal(run('canvasOffset.y'),70);
  parent.clientWidth=1100;parent.clientHeight=650;c.window.devicePixelRatio=1.5;
  run('resizeCanvas()');
  assert.equal(canvas.width,1650);
  assert.equal(canvas.height,975);
  assert.equal(run('getCanvasViewport().width'),1100);
  assert.equal(run('getCanvasViewport().height'),650);
  assert.equal(run('scale'),1.25);
  assert.equal(run('canvasOffset.x'),-40);
  assert.equal(run('canvasOffset.y'),70);
});

test('moving between display densities redraws immediately and keeps only one active DPR listener',()=>{
  const {c,run,canvas}=setup(1);
  const queries=[];
  c.window.matchMedia=media=>{
    const listeners=new Set();
    const query={media,listeners,
      addEventListener(type,listener){assert.equal(type,'change');listeners.add(listener);},
      removeEventListener(type,listener){assert.equal(type,'change');listeners.delete(listener);},
      dispatch(){for(const listener of [...listeners])listener({matches:false,media});}
    };
    queries.push(query);
    return query;
  };
  run('initCanvas();scale=.8;canvasOffset={x:-61,y:72}');
  assert.equal(queries.length,1);
  for(const ratio of [1.25,1.5,2,3,1]){
    c.window.devicePixelRatio=ratio;
    const previous=queries.at(-1);
    previous.dispatch();
    assert.equal(canvas.width,Math.round(900*ratio));
    assert.equal(canvas.height,Math.round(600*ratio));
    assert.equal(queries.at(-1).media,`(resolution: ${ratio}dppx)`);
    assert.equal(previous.listeners.size,0,'old display query is detached');
    assert.equal(queries.reduce((count,query)=>count+query.listeners.size,0),1);
    assert.equal(run('scale'),.8);
    assert.equal(run('canvasOffset.x'),-61);
    assert.equal(run('canvasOffset.y'),72);
  }
});

test('locating a Gantt event centers its process node in CSS coordinates at every DPR',()=>{
  for(const dpr of ratios){
    const {c,run,elements,node}=setup(dpr);
    Object.assign(elements,{ganttDetails:{innerHTML:''},locateProcess:{},locateHint:{textContent:''}});
    c.capacityEscape=String;c.workbenchProcessMatches=()=>true;c.switchTab=()=>{};
    c.requestAnimationFrame=()=>1;
    vm.runInContext(fs.readFileSync('frontend/js/gantt_view.js','utf8'),c);
    run('requestGanttDraw=()=>{};resizeCanvas();scale=.8;stationContainers.A.collapsed=true;ganttView.model={eventArea:()=>"A",formatTime:String};showGanttDetail({step_id:"S001",engine_id:1,event_type:"NORMAL",start_time:0,end_time:10});');
    elements.locateProcess.onclick();
    nearly(run('canvasOffset.x')+(node.x+60)*.8,450,'center x');
    nearly(run('canvasOffset.y')+(node.y+25)*.8,341,'drawable center y');
    assert.equal(run('stationContainers.A.collapsed'),false);
    assert.equal(run('state.selectedNode.id'),'one');
  }
});

test('area layout collapses every area and keeps individual areas expandable',()=>{
  const {c,run,elements}=setup(1.5);
  elements.showContainers={checked:false};
  elements.layoutModeToggle={textContent:'',classList:{add(){},remove(){}}};
  c.state.stations=[{id:'A',name:'Area A',color:'#367bea'},{id:'B',name:'Area B',color:'#33aa88'}];
  c.state.nodes.push({id:'two',stepId:'S002',taskName:'后续工序',opType:'A',station:'B',predecessors:'S001',x:0,y:0});
  c.state.showStationContainers=false;
  vm.runInContext(fs.readFileSync('frontend/js/layout.js','utf8'),c);
  run('autoLayoutByStation()');
  assert.equal(run('Object.values(stationContainers).every(area=>area.collapsed)'),true);
  assert.equal(run('state.showStationContainers'),true);
  assert.equal(elements.showContainers.checked,true);
  assert.equal(run('state.layoutMode'),'station-only');
  assert.equal(run('state.nodes.every(node=>!isNodeVisible(node))'),true);
  assert.equal(run('state.nodes[1].predecessors'),'S001');
  run("toggleStationContainer('A')");
  assert.equal(run('isNodeVisible(state.nodes[0])'),true);
  assert.equal(run('findNodeAt({x:90,y:130}).id'),'one');
  assert.equal(run('stationContainers.B.collapsed'),true);
  run('autoLayoutByStation()');
  assert.equal(run('Object.values(stationContainers).every(area=>area.collapsed)'),true);
});

test('initial process layout can retain the expanded detail view',()=>{
  const {c,run}=setup();
  c.state.stations=[{id:'A',name:'Area A',color:'#367bea'}];
  vm.runInContext(fs.readFileSync('frontend/js/layout.js','utf8'),c);
  run('autoLayoutByStation(false)');
  assert.equal(run('stationContainers.A.collapsed'),false);
  assert.equal(run('state.layoutMode'),'normal');
  assert.equal(run('isNodeVisible(state.nodes[0])'),true);
});
