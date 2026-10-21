const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs');

function setup(saved=new Map()){
    const elements={behaviorToolbox:{innerHTML:'',querySelectorAll:()=>[]},nodeOpType:{innerHTML:''}};
    const strokes=[],fills=[];
    const drawing={measureText:text=>({width:text.length*7}),stroke(){strokes.push(this.strokeStyle);},fill(){fills.push(this.fillStyle);}};
    const ctx=new Proxy(drawing,{get:(target,key)=>key in target?target[key]:()=>{}});
    const c=vm.createContext({console,ctx,canvas:{getBoundingClientRect:()=>({left:0,top:0,width:900,height:600})},
        state:{nodes:[],edges:[],stationFilter:null},scale:1,canvasOffset:{x:0,y:0},
        localStorage:{getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,value),removeItem:key=>saved.delete(key)},
        document:{getElementById:id=>elements[id],querySelectorAll:()=>[]},
        hexToRgba:(color,alpha)=>`rgba(${color},${alpha})`,showToast(){}});
    for(const name of ['config','ui','canvas','csv'])vm.runInContext(fs.readFileSync(`frontend/js/${name}.js`,'utf8'),c);
    c.redraws=0;c.renderCanvas=()=>c.redraws++;
    return {c,elements,strokes,fills,saved,run:source=>vm.runInContext(source,c)};
}

test('toolbox and node editor expose the same eight behavior types',()=>{
    const {run,elements}=setup();
    run('initToolbox()');
    for(const code of ['H','A','M','T','D','S-Move','S-Rest','Coop']){
        assert.ok(elements.behaviorToolbox.innerHTML.includes(`data-type="${code}"`));
        assert.ok(elements.behaviorToolbox.innerHTML.includes(`data-behavior-color="${code}"`));
        assert.ok(elements.nodeOpType.innerHTML.includes(`value="${code}"`));
    }
});

test('custom type colors persist across reload and reset without changing process data',()=>{
    const {run,c,saved}=setup();
    run("state.nodes=[{id:'one',opType:'A'}];setBehaviorColor('A','#7c3aed')");
    assert.equal(c.redraws,1);
    assert.equal(run('JSON.stringify(state.nodes)'),JSON.stringify([{id:'one',opType:'A'}]));
    const reopened=setup(saved);
    reopened.run('loadBehaviorColors()');
    assert.equal(reopened.run('OP_TYPE_COLORS.A'),'#7c3aed');
    reopened.run('resetBehaviorColors()');
    assert.equal(saved.has('assembly.ui.behaviorColors'),false);
    assert.equal(reopened.run('OP_TYPE_COLORS.A===DEFAULT_OP_TYPE_COLORS.A'),true);
});

test('a changed type recolors existing and future nodes while other types retain their color',()=>{
    const {run,strokes,fills}=setup();
    run("setBehaviorColor('H','#123456');const h={x:0,y:0,opType:'H',stepId:'B1',taskName:'Test'};drawNode(h,false);drawNode({...h,stepId:'B2'},false);drawNode({...h,opType:'A'},false)");
    assert.deepEqual(strokes,['#123456','#123456','#10b981']);
    assert.ok(fills.includes('rgba(#123456,0.12)'));
});

test('malformed stored colors and invalid color changes cannot corrupt the palette',()=>{
    const {run}=setup(new Map([['assembly.ui.behaviorColors','{"A":"red","Coop":"#123456","unknown":"#abcdef"}']]));
    run("loadBehaviorColors();setBehaviorColor('A','not-a-color');setBehaviorColor('unknown','#abcdef')");
    assert.equal(run('OP_TYPE_COLORS.A'),'#10b981');
    assert.equal(run('OP_TYPE_COLORS.Coop'),'#123456');
    assert.equal(run('Object.hasOwn(OP_TYPE_COLORS,"unknown")'),false);
});

test('new behavior nodes retain their exact codes when dropped and exported',()=>{
    const {run,c}=setup();
    for(const type of ['S-Move','S-Rest','Coop']){
        c.drop={clientX:200,clientY:200,preventDefault(){},dataTransfer:{getData:()=>type}};
        run('handleCanvasDrop(drop)');
    }
    assert.equal(run('JSON.stringify(buildProcessDefinition().nodes.map(n=>n.op_type))'),JSON.stringify(['S-Move','S-Rest','Coop']));
});
