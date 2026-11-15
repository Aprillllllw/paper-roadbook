import * as T from 'three';
import {make} from '../components/registry.js';
import {theme} from '../theme.js';
import {SCENE,boardRho,KEEP,surfaceAt} from './layout.js';
import {swapInto} from './glbswap.js';
export function placeProps(scene,land,routes,texture){
 const items=[];
 function put(p){
  const component=make(p.type,p.opts||{},theme),g=new T.Group();g.add(component.group);const made={...component,group:g};
  g.position.set(p.x,p.y??surfaceAt(p.x,p.z,land.sample),p.z);g.scale.setScalar(p.s??1.8);g.rotation.y=p.rotY??0;
  g.userData.stickerAnchor=component.group.userData.stickerAnchor;scene.add(g);items.push(made);
  if(p.opts?.glb)swapInto(component.group,p.opts.glb,{keep:component.group.userData.stickerAnchor?[component.group.userData.stickerAnchor]:[]}).catch(e=>console.warn('GLB',e));
  return made;
 }
 SCENE.props.forEach(put);
 let seed=4242;const rnd=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
 for(const c of SCENE.clumps){
  if(c.type==='spruce')continue; // instanced by landscape
  for(let i=0;i<(c.n??1);i++){const a=rnd()*Math.PI*2,d=Math.sqrt(rnd())*(c.r??1),x=c.x+Math.cos(a)*d,z=c.z+Math.sin(a)*d;if(boardRho(x,z)<.94&&!KEEP.some(([kx,kz,kr])=>Math.hypot(x-kx,z-kz)<kr))put({...c,x,z,s:c.s??2.8});}
 }
 const vehicle=SCENE.vehicle?put({x:0,z:0,s:6,...SCENE.vehicle}):null;
 let sticker=null;
 if(vehicle&&texture&&vehicle.group.userData.stickerAnchor){sticker=new T.Sprite(new T.SpriteMaterial({map:texture,depthTest:false}));sticker.scale.setScalar(.95);vehicle.group.userData.stickerAnchor.add(sticker);}
 let last=null;
 return {reset(){last=null;},update(t,dt,progress,route){let speed=0;if(vehicle&&route){const p=route.at(progress),tg=route.tangent(progress);vehicle.group.position.copy(p).y-=.12;vehicle.group.rotation.y=Math.atan2(-tg.z,tg.x);speed=last&&dt?p.distanceTo(last)/dt/2:0;last=p.clone();}if(sticker)sticker.position.y=Math.sin(t*6)*.03;for(const item of items)item.update?.(t,dt,item===vehicle?speed:undefined);}};
}
export function avatarTexture(src) {
  const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d');
  const draw = (img) => {
    g.clearRect(0, 0, 128, 128); g.fillStyle = theme.shade43; g.beginPath(); g.arc(64, 64, 60, 0, Math.PI * 2); g.fill();
    if (img) { g.save(); g.beginPath(); g.arc(64, 64, 55, 0, Math.PI * 2); g.clip(); g.drawImage(img, 9, 9, 110, 110); g.restore(); }
    else { g.fillStyle = theme.shade25; g.font = '62px Georgia'; g.textAlign = 'center'; g.textBaseline = 'middle';  }
    g.lineWidth = 5; g.strokeStyle = theme.shade25; g.beginPath(); g.arc(64, 64, 59, 0, Math.PI * 2); g.stroke();
  };
  draw(null); const tex = new T.CanvasTexture(c);
  const img = new Image(); img.onload = () => { draw(img); tex.needsUpdate = true; }; img.src = src;
  return tex;
}
