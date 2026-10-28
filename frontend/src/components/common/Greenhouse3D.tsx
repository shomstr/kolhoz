import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { ReactNode } from 'react';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export interface SceneMarker {id:string; position:[number,number,number]; content:ReactNode; color:string; onSelect?:()=>void}
export default function Greenhouse3D({rotating,lighting,heating,ventilation,screens,temperature,cutaway=false,markers=[],onUnavailable}:{rotating:boolean;lighting:number;temperature?:number|null;heating?:number|null;ventilation?:number|null;screens?:number|null;cutaway?:boolean;markers?:SceneMarker[];onUnavailable?:()=>void}) {
  const markerNodes=useRef<Record<string,HTMLDivElement|null>>({});
  const markerData=useRef(markers);markerData.current=markers;
  const zoneMaterial=useRef<THREE.MeshBasicMaterial|null>(null);
  useEffect(()=>{if(zoneMaterial.current)zoneMaterial.current.color.set(temperature==null?'#829399':temperature<22?'#258abd':temperature>24?'#dc8b32':'#179574');invalidate.current?.();},[temperature]);
  const glassRef=useRef<THREE.Material|null>(null);
  const ventsRef=useRef<THREE.Group[]>([]);
  const screensRef=useRef<THREE.Mesh[]>([]);
  const heatRef=useRef<THREE.MeshStandardMaterial|null>(null);
  useEffect(()=>{if(glassRef.current)glassRef.current.visible=!cutaway;invalidate.current?.();},[cutaway]);
  useEffect(()=>{ventsRef.current.forEach(vent=>vent.rotation.z=-(ventilation??0)/100*.9);screensRef.current.forEach(screen=>{screen.visible=screens!=null&&screens>0;screen.scale.x=Math.max(.01,(screens??0)/100);});if(heatRef.current){heatRef.current.emissiveIntensity=(heating??0)/100*.8;}invalidate.current?.();},[heating,ventilation,screens]);
  useEffect(()=>{invalidate.current?.();},[markers]);
  const host=useRef<HTMLDivElement>(null);
  const orbit=useRef<OrbitControls|null>(null);
  const invalidate=useRef<(()=>void)|null>(null);
  const lampMaterial=useRef<THREE.MeshStandardMaterial|null>(null);
  const [unavailable,setUnavailable]=useState(false);
  useEffect(()=>{if(orbit.current)orbit.current.autoRotate=rotating;},[rotating]);
  useEffect(()=>{if(lampMaterial.current)lampMaterial.current.emissiveIntensity=lighting/400;invalidate.current?.();},[lighting]);
  useEffect(()=>{
    const container=host.current;if(!container)return;
    let renderer:THREE.WebGLRenderer;
    try {renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});} catch {setUnavailable(true);onUnavailable?.();return;}
    renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.8;container.appendChild(renderer.domElement);
    renderer.domElement.tabIndex=0;renderer.domElement.setAttribute('role','img');renderer.domElement.setAttribute('aria-label','3D-модель теплицы. Стрелки поворачивают, плюс и минус меняют масштаб. Можно перетаскивать мышью.');
    const scene=new THREE.Scene();scene.background=new THREE.Color('#dbe6ed');scene.fog=new THREE.Fog('#dbe6ed',75,160);
    const camera=new THREE.PerspectiveCamera(40,1,.1,200);camera.position.set(14,12,17);
    const controls=new OrbitControls(camera,renderer.domElement);orbit.current=controls;controls.target.set(0,1.5,0);controls.enableDamping=true;controls.enablePan=false;controls.minDistance=17;controls.maxDistance=48;controls.minPolarAngle=.35;controls.maxPolarAngle=Math.PI*.48;controls.autoRotate=rotating;controls.autoRotateSpeed=.7;
    const pmrem=new THREE.PMREMGenerator(renderer);const room=new RoomEnvironment();const environment=pmrem.fromScene(room,.04);scene.environment=environment.texture;scene.environmentIntensity=.6;room.dispose();pmrem.dispose();
    scene.add(new THREE.HemisphereLight(0xe7f5ff,0x809067,1.1));
    const sunlight=new THREE.DirectionalLight(0xfff7e7,2.2);sunlight.position.set(-14,26,12);sunlight.castShadow=true;sunlight.shadow.mapSize.set(1024,1024);sunlight.shadow.camera.left=-24;sunlight.shadow.camera.right=24;sunlight.shadow.camera.top=24;sunlight.shadow.camera.bottom=-24;sunlight.shadow.normalBias=.05;scene.add(sunlight);
    const silver=new THREE.MeshStandardMaterial({color:0xc1cbd0,metalness:.65,roughness:.3});
    const glass=new THREE.MeshPhysicalMaterial({color:0xc8e5ef,metalness:.05,roughness:.08,transparent:true,opacity:.25,side:THREE.DoubleSide,depthWrite:false});
    glass.visible=!cutaway;glassRef.current=glass;
    const soil=new THREE.MeshStandardMaterial({color:0xb2a082,roughness:1});
    const concrete=new THREE.MeshStandardMaterial({color:0xb7bcba,roughness:.94});
    const leafCanvas=document.createElement('canvas');leafCanvas.width=128;leafCanvas.height=64;const ctx=leafCanvas.getContext('2d')!;
    const gradient=ctx.createLinearGradient(0,0,0,64);gradient.addColorStop(0,'#3b7431');gradient.addColorStop(.45,'#609741');gradient.addColorStop(1,'#27532b');ctx.fillStyle=gradient;ctx.beginPath();ctx.moveTo(5,32);ctx.bezierCurveTo(28,3,96,2,123,31);ctx.bezierCurveTo(85,61,35,60,5,32);ctx.fill();ctx.strokeStyle='#aac07c99';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(6,32);ctx.lineTo(121,31);for(let x=24;x<111;x+=17){ctx.moveTo(x,32);ctx.lineTo(x-7,14);ctx.moveTo(x,32);ctx.lineTo(x-7,50);}ctx.stroke();
    const leafTexture=new THREE.CanvasTexture(leafCanvas);leafTexture.colorSpace=THREE.SRGBColorSpace;
    const green=new THREE.MeshStandardMaterial({color:0xffffff,map:leafTexture,alphaTest:.45,side:THREE.DoubleSide,roughness:1});
    const red=new THREE.MeshStandardMaterial({color:0xce4729,roughness:.52});
    const pink=new THREE.MeshStandardMaterial({color:0xf3d9f6,emissive:0xd055ae,emissiveIntensity:lighting/400});lampMaterial.current=pink;
    const box=(w:number,h:number,d:number,x:number,y:number,z:number,material:THREE.Material)=>{const mesh=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);mesh.position.set(x,y,z);mesh.receiveShadow=true;scene.add(mesh);return mesh;};
    const beam=(a:THREE.Vector3,b:THREE.Vector3,r=.04,material:THREE.Material=silver)=>{const distance=a.distanceTo(b);const mesh=new THREE.Mesh(new THREE.CylinderGeometry(r,r,distance,6),material);mesh.position.copy(a).add(b).multiplyScalar(.5);mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),b.clone().sub(a).normalize());scene.add(mesh);return mesh;};
    const v=(x:number,y:number,z:number)=>new THREE.Vector3(x,y,z);
    const panel=(points:number[])=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(points,3));g.setIndex([0,1,2,0,2,3]);g.computeVertexNormals();scene.add(new THREE.Mesh(g,glass));};
    const lawn=new THREE.Mesh(new THREE.PlaneGeometry(180,180),new THREE.MeshStandardMaterial({color:0x819778,roughness:1}));lawn.rotation.x=-Math.PI/2;lawn.position.y=-.12;lawn.receiveShadow=true;scene.add(lawn);
    box(18,.13,27,0,-.07,0,concrete);box(12,.15,20,0,.05,0,soil);
    const zoneColor=temperature==null?'#829399':temperature<22?'#258abd':temperature>24?'#dc8b32':'#179574';
    const zone=new THREE.MeshBasicMaterial({color:zoneColor,transparent:true,opacity:.23,depthWrite:false});zoneMaterial.current=zone;box(12,.015,20,0,.14,0,zone);
    box(180,.01,4,0,-.03,-20,new THREE.MeshStandardMaterial({color:0x7a8386,roughness:1}));
    // Four connected glass bays, longitudinal roof ribs and structural trusses.
    for(let bay=0;bay<4;bay++){
      const x=-6+bay*3,mid=x+1.5;
      for(let z=-10;z<=10;z+=2){
        beam(v(x,.1,z),v(x,3.2,z));beam(v(x+3,.1,z),v(x+3,3.2,z));beam(v(x,3.2,z),v(mid,4.25,z));beam(v(mid,4.25,z),v(x+3,3.2,z));beam(v(x,3.15,z),v(x+3,3.15,z),.025);
        if(z<10){
          panel([x,3.2,z,mid,4.25,z,mid,4.25,z+2,x,3.2,z+2]);panel([mid,4.25,z,x+3,3.2,z,x+3,3.2,z+2,mid,4.25,z+2]);
          beam(v(mid,4.25,z),v(mid,4.25,z+2),.033);
          for(const edge of [x,x+3])beam(v(edge,3.2,z),v(edge,3.2,z+2),.04);
          for(const offset of [.5,1,2,2.5]){const roofY=3.2+1.05*(1-Math.abs(offset-1.5)/1.5);beam(v(x+offset,roofY,z),v(x+offset,roofY,z+2),.016);}
        }
      }
      for(const z of [-10,10]){
        panel([x,.2,z,x+3,.2,z,x+3,3.2,z,x,3.2,z]);
        for(let offset=.5;offset<3;offset+=.5)beam(v(x+offset,.15,z),v(x+offset,3.2,z),.025);
        beam(v(x,1.5,z),v(x+3,1.5,z),.025);
      }
    }
    for(const x of [-6,6])for(let z=-10;z<10;z+=2){panel([x,.2,z,x,.2,z+2,x,3.2,z+2,x,3.2,z]);beam(v(x,1.5,z),v(x,1.5,z+2),.025);}
    // Instanced foliage keeps the growing rows detailed without thousands of draw calls.
    const leafGeometry=new THREE.PlaneGeometry(.65,.3);const leaves=new THREE.InstancedMesh(leafGeometry,green,2520);
    const fruit=new THREE.InstancedMesh(new THREE.SphereGeometry(.075,7,5),red,504);
    const matrix=new THREE.Object3D();let leafIndex=0,fruitIndex=0;
    const noise=(n:number)=>{const x=Math.sin(n*127.1)*43758.5453;return x-Math.floor(x);};
    for(let row=0;row<12;row++){
      const x=-5.5+row;
      box(.48,.25,19,x,.23,0,new THREE.MeshStandardMaterial({color:0xe2dfcf,roughness:.7}));
      beam(v(x,.55,-9.4),v(x,.55,9.4),.02);
      for(let plant=0;plant<14;plant++){
        const z=-9.1+plant*1.35,id=row*14+plant;
        beam(v(x,.4,z),v(x,2.75,z),.012,new THREE.MeshStandardMaterial({color:0x507740,roughness:1}));
        for(let leaf=0;leaf<15;leaf++){
          const n=id*15+leaf;matrix.position.set(x+(noise(n)-.5)*.58,.6+leaf*.135,z+(noise(n+200)-.5)*.55);matrix.scale.set(1.2,.85,1);matrix.rotation.set(noise(n+55)*.6,noise(n+88)*Math.PI,noise(n+30)*.7);matrix.updateMatrix();leaves.setColorAt(leafIndex,new THREE.Color().setScalar(.75+noise(n+10)*.25));leaves.setMatrixAt(leafIndex++,matrix.matrix);
        }
        for(let tomato=0;tomato<3;tomato++){matrix.position.set(x+.12,.85+tomato*.47,z+.14);matrix.scale.setScalar(1);matrix.rotation.set(0,0,0);matrix.updateMatrix();fruit.setMatrixAt(fruitIndex++,matrix.matrix);}
      }
      for(const z of [-6,0,6])box(.8,.045,.11,x,2.95,z,pink);
    }
    leaves.castShadow=true;scene.add(leaves,fruit);
    // Equipment positions are shared with the projected labels; opening follows the journal.
    const heatMaterial=new THREE.MeshStandardMaterial({color:0xc77a36,emissive:0xd66a16,emissiveIntensity:(heating??0)/100*.8,roughness:.5});heatRef.current=heatMaterial;
    for(const x of [-5.8,5.8])beam(v(x,.38,-9.7),v(x,.38,9.7),.065,heatMaterial);
    const screenMaterial=new THREE.MeshStandardMaterial({color:0xd4d0ba,transparent:true,opacity:.7,side:THREE.DoubleSide});
    for(let bay=0;bay<4;bay++){
      const x=-6+bay*3;
      const curtain=box(2.8,.018,18,x+1.5,3.08,0,screenMaterial);curtain.scale.x=Math.max(.01,(screens??0)/100);curtain.visible=screens!=null&&screens>0;screensRef.current.push(curtain);
      for(const z of [-6,0,6]){const hinge=new THREE.Group();hinge.position.set(x+1.5,4.28,z);const flap=new THREE.Mesh(new THREE.BoxGeometry(1.3,.04,1.4),new THREE.MeshStandardMaterial({color:0x74a9bc,transparent:true,opacity:.65,side:THREE.DoubleSide}));flap.position.set(.65,0,0);hinge.add(flap);hinge.rotation.z=-(ventilation??0)/100*.9;scene.add(hinge);ventsRef.current.push(hinge);}
    }
    // Outdoor climate infrastructure: buffer tanks, pipes and a compact service cabinet.
    for(let i=0;i<3;i++){
      const tank=new THREE.Mesh(new THREE.CylinderGeometry(.65,.65,2.5,24),silver);tank.position.set(-7.3,1.3,-6+i*2.2);tank.castShadow=true;scene.add(tank);
      beam(v(-7.3,.5,-6+i*2.2),v(-6,.5,-6+i*2.2),.11);
    }
    box(.9,1.5,1.3,-7.4,.75,2,silver);beam(v(-7.4,.4,-7),v(-7.4,.4,4),.09);
    // Garden edges, nearby planting and distant agricultural buildings.
    for(let i=0;i<32;i++){
      const x=(noise(i+400)-.5)*85,z=(noise(i+500)-.5)*90;if(Math.abs(x)<14&&Math.abs(z)<18)continue;
      const crown=new THREE.Mesh(new THREE.IcosahedronGeometry(1.4,1),new THREE.MeshStandardMaterial({color:new THREE.Color().setHSL(.26+noise(i)*.06,.25,.3+noise(i+5)*.12),roughness:1}));crown.position.set(x,2,z);scene.add(crown);beam(v(x,0,z),v(x,1.5,z),.14,soil);
    }
    for(let i=0;i<4;i++)box(12,2,18,25+i*16,1,-22,new THREE.MeshStandardMaterial({color:0xc4d2d6,roughness:.45}));
    // Batch static frame members and panes; retain separate movable equipment.
    const batches=new Map<THREE.Material,THREE.Mesh[]>();
    for(const object of [...scene.children])if(object instanceof THREE.Mesh&&!(object instanceof THREE.InstancedMesh)&&!screensRef.current.includes(object)&&!Array.isArray(object.material)){
      const group=batches.get(object.material)||[];group.push(object);batches.set(object.material,group);
    }
    for(const [material,meshes] of batches){
      if(meshes.length<2)continue;
      const geometries=meshes.map(mesh=>{mesh.updateMatrix();const geometry=mesh.geometry.clone().applyMatrix4(mesh.matrix);if(geometry.index){const flat=geometry.toNonIndexed();geometry.dispose();return flat;}return geometry;});
      const merged=mergeGeometries(geometries);geometries.forEach(geometry=>geometry.dispose());if(!merged)continue;
      const combined=new THREE.Mesh(merged,material);combined.castShadow=meshes.some(mesh=>mesh.castShadow);combined.receiveShadow=meshes.some(mesh=>mesh.receiveShadow);scene.add(combined);
      meshes.forEach(mesh=>{scene.remove(mesh);mesh.geometry.dispose();});
    }
    const keyboard=(event:KeyboardEvent)=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','='].includes(event.key))return;event.preventDefault();const offset=camera.position.clone().sub(controls.target);const spherical=new THREE.Spherical().setFromVector3(offset);if(event.key==='ArrowLeft')spherical.theta+=.06;if(event.key==='ArrowRight')spherical.theta-=.06;if(event.key==='ArrowUp')spherical.phi=Math.max(controls.minPolarAngle,spherical.phi-.05);if(event.key==='ArrowDown')spherical.phi=Math.min(controls.maxPolarAngle,spherical.phi+.05);if(event.key==='+'||event.key==='=')spherical.radius=Math.max(controls.minDistance,spherical.radius*.94);if(event.key==='-')spherical.radius=Math.min(controls.maxDistance,spherical.radius*1.06);camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));controls.update();};renderer.domElement.addEventListener('keydown',keyboard);
    let needsRender=true;invalidate.current=()=>{needsRender=true;};controls.addEventListener('change',()=>{needsRender=true;});
    const resize=()=>{const w=container.clientWidth,h=container.clientHeight;if(!w||!h)return;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h);needsRender=true;};const observer=new ResizeObserver(resize);observer.observe(container);resize();
    let frame=0;let last=0;const animate=(time:number)=>{frame=requestAnimationFrame(animate);if(time-last<32)return;const delta=Math.min((time-last)/1000,.1);last=time;if(document.visibilityState==='hidden')return;controls.update(delta);if(!needsRender)return;renderer.render(scene,camera);
      const hostRect=container.getBoundingClientRect();
      const occupied:{x:number;y:number;width:number;height:number}[]=Array.from(container.parentElement?.querySelectorAll<HTMLElement>('.scene-toolbar,.view-controls,.scene-timeline,.hero-footer')||[]).map(element=>{const rect=element.getBoundingClientRect();return {x:rect.left-hostRect.left,y:rect.top-hostRect.top,width:rect.width,height:rect.height};});
      for(const marker of markerData.current){
        const node=markerNodes.current[marker.id];if(!node)continue;
        const projected=new THREE.Vector3(...marker.position).project(camera);
        const visible=projected.z>-1&&projected.z<1&&Math.abs(projected.x)<.96&&Math.abs(projected.y)<.96;
        node.style.visibility=visible?'visible':'hidden';if(!visible)continue;
        const px=(projected.x*.5+.5)*container.clientWidth,py=(-projected.y*.5+.5)*container.clientHeight;
        node.style.left=`${px}px`;node.style.top=`${py}px`;
        const callout=node.querySelector<HTMLButtonElement>('.scene-callout')!,leader=node.querySelector<HTMLSpanElement>('.scene-leader')!;
        const width=callout.offsetWidth,height=callout.offsetHeight;
        const clampX=(x:number)=>Math.max(8,Math.min(container.clientWidth-width-8,x));
        const clampY=(y:number)=>Math.max(52,Math.min(container.clientHeight-height-108,y));
        let x=clampX(px-width/2),y=clampY(py-height-32);
        const candidates=[[0,0],[-width-12,0],[width+12,0],[0,-height-14],[0,height+14],[-width-12,-height-14],[width+12,-height-14]];
        const fallback:number[][]=[];
        for(let gridY=52;gridY<=container.clientHeight-height-108;gridY+=height+10)for(let gridX=8;gridX<=container.clientWidth-width-8;gridX+=width+10)fallback.push([gridX-(px-width/2),gridY-(py-height-32)]);
        fallback.sort((a,b)=>Math.hypot(a[0],a[1])-Math.hypot(b[0],b[1]));
        for(const [dx,dy] of [...candidates,...fallback]){
          const nextX=clampX(px-width/2+dx),nextY=clampY(py-height-32+dy);
          if(!occupied.some(rect=>nextX<rect.x+rect.width+8&&nextX+width+8>rect.x&&nextY<rect.y+rect.height+8&&nextY+height+8>rect.y)){x=nextX;y=nextY;break;}
        }
        occupied.push({x,y,width,height});callout.style.transform='none';callout.style.bottom='auto';callout.style.left=`${x-px}px`;callout.style.top=`${y-py}px`;
        const dx=x+width/2-px,dy=py-(y+height);leader.style.height=`${Math.hypot(dx,dy)}px`;leader.style.transformOrigin='bottom center';leader.style.transform=`rotate(${Math.atan2(dx,dy)}rad)`;
      }
      needsRender=false;};frame=requestAnimationFrame(animate);
    return()=>{cancelAnimationFrame(frame);renderer.domElement.removeEventListener('keydown',keyboard);invalidate.current=null;observer.disconnect();controls.dispose();orbit.current=null;ventsRef.current=[];screensRef.current=[];glassRef.current=null;heatRef.current=null;zoneMaterial.current=null;scene.traverse(o=>{if(o instanceof THREE.Mesh){o.geometry.dispose();(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.dispose());}});leafTexture.dispose();environment.dispose();renderer.dispose();renderer.domElement.remove();};
  },[]);
  return unavailable?<img className="greenhouse-photo" src="/assets/greenhouse-aerial.png" alt="Стеклянная теплица с рядами томатов"/>:<><div className="greenhouse-webgl" ref={host}/><div className="scene-annotations">{markers.map(marker=><div key={marker.id} className="scene-anchor" data-anchor={marker.id} ref={node=>{markerNodes.current[marker.id]=node;}} style={{'--marker-color':marker.color} as React.CSSProperties}><button type="button" className="scene-callout" onClick={marker.onSelect}>{marker.content}</button><span className="scene-leader"/><span className="scene-pin"/></div>)}</div></>;
}
