const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');

function fixture(){
    const elements={},frames=new Map(),calls=[];let next=0;
    const get=id=>elements[id]??={hidden:false,textContent:'',classList:{add(){}},addEventListener(){},removeAttribute(){},getBoundingClientRect:()=>({width:900,height:500})};
    const c=vm.createContext({console,THREE:{},OrbitControls(){},GLTFLoader(){},RoomEnvironment(){},AbortController,
        document:{getElementById:get,readyState:'loading'},window:{addEventListener(){},removeEventListener(){}},
        ResizeObserver:class {observe(){}disconnect(){calls.push('disconnect')}},
        requestAnimationFrame:callback=>{frames.set(++next,callback);return next},cancelAnimationFrame:id=>frames.delete(id),
        fetch:async()=>{calls.push('fetch');return {ok:false,status:503}}});
    const source=fs.readFileSync('frontend/js/home_engine.js','utf8').replace(/^import .*;\r?\n/gm,'');
    vm.runInContext(source,c);const viewer=vm.runInContext('new HomeEngine()',c);
    return {c,viewer,get,frames,calls,tick(time=16){const pending=[...frames.values()];frames.clear();for(const f of pending)f(time)}};
}

test('viewer stays lazy when home is hidden and static frames do not form an animation loop',()=>{
    const {viewer,frames,tick}=fixture();let loads=0,renders=0;viewer.load=()=>loads++;
    viewer.setVisible(false,false);assert.equal(loads,0);assert.equal(frames.size,0);
    viewer.setVisible(true,false);assert.equal(loads,1);
    viewer.status='ready';viewer.controls={update(){}};viewer.render=()=>renders++;
    viewer.invalidate();viewer.invalidate();assert.equal(frames.size,1);tick();assert.equal(renders,1);assert.equal(frames.size,0);
});

test('auto rotation has one frame loop and switching away cancels it immediately',()=>{
    const {viewer,frames,tick}=fixture();let renders=0;
    Object.assign(viewer,{status:'ready',active:true,auto:true,controls:{update(){}},render:()=>renders++});
    viewer.invalidate();tick();assert.equal(renders,1);assert.equal(frames.size,1);
    viewer.setVisible(false,true);assert.equal(frames.size,0);tick();assert.equal(renders,1);
    viewer.setVisible(true,false);tick();assert.equal(renders,2);assert.equal(frames.size,0);
});

test('model HTTP failure retains the actual engine poster and offers retry',async()=>{
    const {viewer,get}=fixture();viewer.createScene=()=>{viewer.renderer={}};await viewer.load();
    assert.equal(viewer.status,'error');assert.equal(get('homeEnginePoster').hidden,false);
    assert.equal(get('homeEngineRetry').hidden,false);assert.equal(get('homeEngineProgress').hidden,true);
});

test('unsupported WebGL uses the same poster without starting a model download',async()=>{
    const {viewer,get,calls}=fixture();viewer.createScene=()=>{throw new Error('No WebGL')};await viewer.load();
    assert.equal(viewer.status,'error');assert.equal(get('homeEnginePoster').hidden,false);assert.equal(calls.includes('fetch'),false);
});

test('retry discards the old scene once and only downloads when the home is visible',()=>{
    const {viewer}=fixture();let disposed=0,loaded=0;viewer.releaseScene=()=>disposed++;viewer.load=()=>loaded++;
    viewer.status='error';viewer.retry();assert.equal(disposed,1);assert.equal(loaded,0);
    viewer.active=true;viewer.retry();assert.equal(disposed,2);assert.equal(loaded,1);
});

test('published engine remains a self-contained four-part GLB under 12 MiB',()=>{
    const file=fs.readFileSync('frontend/assets/home-engine.glb');assert.equal(file.readUInt32LE(0),0x46546c67);
    assert.ok(file.length<12*1024*1024);assert.equal(file.readUInt32LE(8),file.length);
    const doc=JSON.parse(file.subarray(20,20+file.readUInt32LE(12)).toString());
    assert.equal(doc.meshes.length,4);assert.equal(doc.images.length,1);assert.ok(doc.images[0].bufferView>=0);
    const triangles=doc.meshes.flatMap(m=>m.primitives).reduce((sum,p)=>sum+doc.accessors[p.indices].count/3,0);
    assert.ok(triangles>240000&&triangles<260000);assert.ok(doc.buffers.every(b=>!b.uri));
});
