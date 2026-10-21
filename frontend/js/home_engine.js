import * as THREE from '/static/vendor/three/three.module.js';
import { OrbitControls } from '/static/vendor/three/OrbitControls.js';
import { GLTFLoader } from '/static/vendor/three/GLTFLoader.js';
import { RoomEnvironment } from '/static/vendor/three/RoomEnvironment.js';

// This viewer owns only presentation resources. It never reads or writes simulation state.
class HomeEngine {
    constructor() {
        this.active=false;this.auto=true;this.frame=0;this.status='idle';this.generation=0;
        this.host=document.getElementById('homeEngineHost');
        this.poster=document.getElementById('homeEnginePoster');
        this.loading=document.getElementById('homeEngineLoading');
        this.label=document.getElementById('homeEngineLoadText');
        this.progress=document.getElementById('homeEngineProgress');
        this.retryButton=document.getElementById('homeEngineRetry');
        this.retryButton.addEventListener('click',()=>this.retry());
        this.resizeObserver=new ResizeObserver(()=>this.resize());
        this.resizeObserver.observe(this.host);
        this.onPageHide=()=>this.dispose();
        window.addEventListener('pagehide',this.onPageHide);
    }
    setVisible(active,auto) {
        this.active=active;this.auto=auto;
        if(active&&this.status==='idle')this.load();
        if(!active){cancelAnimationFrame(this.frame);this.frame=0;this.lastTime=0;}
        else{this.resize();this.invalidate();}
    }
    async load() {
        const generation=++this.generation;
        this.status='loading';this.loading.hidden=false;this.retryButton.hidden=true;
        this.label.textContent='正在加载发动机';this.progress.removeAttribute('value');
        this.progress.hidden=false;this.poster.hidden=false;
        try {
            if(!this.renderer)this.createScene();
            this.abort=new AbortController();
            const response=await fetch('/static/assets/home-engine.glb',{signal:this.abort.signal});
            if(!response.ok)throw new Error(`Model HTTP ${response.status}`);
            const total=Number(response.headers.get('Content-Length'));
            const reader=response.body?.getReader();let data;
            if(reader){
                const chunks=[];let loaded=0;
                while(true){const {value,done}=await reader.read();if(done)break;chunks.push(value);loaded+=value.byteLength;
                    if(total>0){this.progress.value=Math.min(.99,loaded/total);this.label.textContent=`正在加载 ${Math.floor(loaded/total*100)}%`;}}
                data=new Uint8Array(loaded);let offset=0;for(const chunk of chunks){data.set(chunk,offset);offset+=chunk.length;}
            }else data=new Uint8Array(await response.arrayBuffer());
            this.label.textContent='正在准备模型';
            const gltf=await new GLTFLoader().parseAsync(data.buffer,'/static/assets/');
            if(generation!==this.generation){this.releaseModel(gltf.scene);return;}
            this.model=gltf.scene;this.scene.add(this.model);
            // Keep the Unity albedo detail but lift its near-black CAD texture for the white showroom.
            this.model.traverse(object=>{if(object.isMesh)for(const material of [object.material].flat()){
                material.color.setRGB(.32,.38,.46);material.roughness=.48;
                material.onBeforeCompile=shader=>{shader.fragmentShader=shader.fragmentShader.replace(
                    '#include <map_fragment>','#include <map_fragment>\n diffuseColor.rgb = mix(diffuse, diffuseColor.rgb, 0.18);');};
                material.customProgramCacheKey=()=> 'home-showroom-metal-v1';
            }});
            const bounds=new THREE.Box3().setFromObject(this.model),center=bounds.getCenter(new THREE.Vector3());
            this.model.position.sub(center);this.size=bounds.getSize(new THREE.Vector3());
            this.floor.position.y=-this.size.y/2-.025;
            this.status='ready';this.fit();this.render();this.progress.value=1;
            this.poster.hidden=true;this.loading.hidden=true;this.host.classList.add('engine-ready');
            this.invalidate();
        }catch(error){
            if(generation!==this.generation||error.name==='AbortError')return;
            this.status='error';this.poster.hidden=false;this.progress.hidden=true;
            this.label.textContent='三维展示暂不可用';this.retryButton.hidden=false;
            this.loading.hidden=false;cancelAnimationFrame(this.frame);this.frame=0;
        }
    }
    createScene() {
        this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.75));
        this.renderer.outputColorSpace=THREE.SRGBColorSpace;
        this.renderer.toneMapping=THREE.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.05;
        this.renderer.shadowMap.enabled=true;this.renderer.shadowMap.type=THREE.PCFSoftShadowMap;
        this.renderer.domElement.setAttribute('aria-label','Unity 发动机三维模型，拖拽旋转，滚轮缩放');
        this.renderer.domElement.setAttribute('role','img');this.renderer.domElement.tabIndex=0;
        this.host.prepend(this.renderer.domElement);
        this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera(30,1,.01,100);
        const environment=new RoomEnvironment();this.pmrem=new THREE.PMREMGenerator(this.renderer);
        this.environment=this.pmrem.fromScene(environment,.04);this.scene.environment=this.environment.texture;
        environment.dispose();
        this.scene.add(new THREE.HemisphereLight(0xe4efff,0x8492a2,.8));
        const key=new THREE.DirectionalLight(0xffffff,2.2);key.position.set(-1,3,3);key.castShadow=true;
        key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-2;key.shadow.camera.right=2;
        key.shadow.camera.top=2;key.shadow.camera.bottom=-2;key.shadow.bias=-.0001;
        key.shadow.normalBias=.015;key.shadow.radius=4;this.scene.add(key);
        const rim=new THREE.DirectionalLight(0xa4c7ff,1.4);rim.position.set(2,1,-2);this.scene.add(rim);
        this.floor=new THREE.Mesh(new THREE.PlaneGeometry(20,20),new THREE.ShadowMaterial({opacity:.075}));
        this.floor.rotation.x=-Math.PI/2;this.floor.receiveShadow=true;this.scene.add(this.floor);
        this.controls=new OrbitControls(this.camera,this.renderer.domElement);
        this.controls.enablePan=false;this.controls.enableDamping=false;this.controls.autoRotateSpeed=4/3;
        this.controls.minPolarAngle=Math.PI*.16;this.controls.maxPolarAngle=Math.PI*.66;
        this.controls.addEventListener('change',()=>this.invalidate());
        this.controls.addEventListener('start',()=>{
            if(this.auto){this.auto=false;window.pauseHomeRotation?.();}
        });
        this.renderer.domElement.addEventListener('keydown',event=>{
            const deltas={ArrowLeft:[.1,0],ArrowRight:[-.1,0],ArrowUp:[0,.1],ArrowDown:[0,-.1]};
            if(deltas[event.key]){event.preventDefault();window.pauseHomeRotation?.();
                this.controls.rotateLeft(deltas[event.key][0]);this.controls.rotateUp(deltas[event.key][1]);this.controls.update();}
            if(event.key==='Home'){event.preventDefault();this.reset();}
        });
        this.contextLost=event=>{event.preventDefault();this.status='error';this.poster.hidden=false;
            this.loading.hidden=false;this.progress.hidden=true;this.label.textContent='三维展示暂不可用';
            this.retryButton.hidden=false;cancelAnimationFrame(this.frame);this.frame=0;};
        this.renderer.domElement.addEventListener('webglcontextlost',this.contextLost);
        this.resize();
    }
    fit() {
        if(!this.model)return;
        const aspect=this.camera.aspect,fov=THREE.MathUtils.degToRad(this.camera.fov);
        const radius=this.size.length()/2;
        const direction=new THREE.Vector3(.85,.55,2.8).normalize();
        const right=new THREE.Vector3().crossVectors(new THREE.Vector3(0,1,0),direction).normalize();
        const up=new THREE.Vector3().crossVectors(direction,right).normalize();
        let distance=0;
        for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1]){
            const corner=new THREE.Vector3(x*this.size.x,y*this.size.y,z*this.size.z).multiplyScalar(.5);
            const depth=corner.dot(direction);
            distance=Math.max(distance,Math.abs(corner.dot(right))/(Math.tan(fov/2)*aspect)+depth,
                Math.abs(corner.dot(up))/Math.tan(fov/2)+depth);
        }
        distance*=1.12;
        this.fitDistance=distance;this.controls.minDistance=radius*1.5;this.controls.maxDistance=distance*2.2;
        this.camera.position.copy(direction.multiplyScalar(distance));
        this.controls.target.set(0,0,0);this.camera.lookAt(0,0,0);this.controls.update();this.controls.saveState();
        this.model.traverse(object=>{if(object.isMesh){object.castShadow=true;object.receiveShadow=true;}});
    }
    resize() {
        if(!this.renderer||!this.active)return;
        const {width,height}=this.host.getBoundingClientRect();if(!width||!height)return;
        const aspect=width/height,changed=this.width!==width||this.height!==height;
        if(changed){this.width=width;this.height=height;this.renderer.setSize(width,height,false);
            this.camera.aspect=aspect;this.camera.updateProjectionMatrix();
            if(this.status==='ready')this.fit();this.invalidate();}
    }
    render(){if(this.active&&this.renderer&&this.status==='ready')this.renderer.render(this.scene,this.camera);}
    invalidate() {
        if(!this.active||this.status!=='ready'||this.frame)return;
        this.frame=requestAnimationFrame(time=>{
            this.frame=0;const delta=this.lastTime?Math.min(.1,(time-this.lastTime)/1000):0;
            this.lastTime=time;this.controls.autoRotate=this.auto;
            if(this.auto)this.controls.update(delta);
            this.render();if(this.auto)this.invalidate();
        });
    }
    reset(){if(this.status==='ready'){this.fit();this.invalidate();}}
    releaseModel(model){model?.traverse(object=>{if(object.isMesh){object.geometry.dispose();
        for(const material of [object.material].flat()){for(const value of Object.values(material)){
            if(value?.isTexture){value.source?.data?.close?.();value.dispose();}}material.dispose();}}});}
    releaseScene(){
        cancelAnimationFrame(this.frame);this.frame=0;this.abort?.abort();
        this.controls?.dispose();this.releaseModel(this.model);this.model=null;
        this.floor?.geometry.dispose();this.floor?.material.dispose();this.environment?.dispose();this.pmrem?.dispose();
        this.scene?.traverse(object=>object.shadow?.dispose?.());
        if(this.renderer){this.renderer.domElement.removeEventListener('webglcontextlost',this.contextLost);
            this.renderer.dispose();this.renderer.domElement.remove();this.renderer=null;}
    }
    retry(){this.generation++;this.releaseScene();this.status='idle';if(this.active)this.load();}
    dispose(){this.generation++;this.releaseScene();this.resizeObserver.disconnect();window.removeEventListener('pagehide',this.onPageHide);}
}

let viewer;
window.HomeEngineViewer={
    setVisible(active,auto){viewer??=new HomeEngine();viewer.setVisible(active,auto);},
    reset(){viewer?.reset();},
    dispose(){viewer?.dispose();viewer=null;}
};
// The classic home script may initialize before this module on a warm cache.
if(document.readyState!=='loading')window.syncHomeMotion?.();
window.addEventListener('pageshow',event=>{if(event.persisted){window.HomeEngineViewer.dispose();window.syncHomeMotion?.();}});
