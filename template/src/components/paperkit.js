import * as T from 'three';
import { theme as C } from '../theme.js';
export { C };
export function material(color,extra={}){return new T.MeshLambertMaterial({color,flatShading:true,vertexColors:true,...extra});}
export function tint(geometry){const g=geometry.index?geometry.toNonIndexed():geometry.clone(),a=g.attributes.position,colors=[];for(let i=0;i<a.count;i++){const v=1+Math.sin(Math.floor(i/3)*12.9898)*.03;colors.push(v,v,v);}g.setAttribute('color',new T.Float32BufferAttribute(colors,3));return g;}
export function mesh(parent,geo,color,pos=[0,0,0],extra={}){const m=new T.Mesh(tint(geo),material(color,extra));m.userData.seasonalSnow=color===C.snow;m.position.set(...pos);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;}
export const box=(p,s,v,c,e)=>mesh(p,new T.BoxGeometry(...s),c,v,e);
export const cone=(p,r,h,v,c,n=8)=>mesh(p,new T.ConeGeometry(r,h,n),c,v);
export const ball=(p,s,v,c)=>{const m=mesh(p,new T.IcosahedronGeometry(1,0),c,v);m.scale.set(...s);return m;};
export function rod(p,a,b,r,c){const av=new T.Vector3(...a),bv=new T.Vector3(...b),d=bv.clone().sub(av);const m=mesh(p,new T.CylinderGeometry(r,r,d.length(),5),c,av.add(bv).multiplyScalar(.5).toArray());m.userData.outlined=true;m.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),d.normalize());return m;}
export function addOutline(group,thickness=.02){const originals=[];group.traverse(o=>{if(o.isMesh&&!o.userData.outline&&!o.userData.outlined) originals.push(o);});for(const m of originals){const g=m.geometry.clone(),p=g.attributes.position,n=g.attributes.normal;for(let i=0;i<p.count;i++)p.setXYZ(i,p.getX(i)+n.getX(i)*thickness/Math.max(.001,Math.abs(m.scale.x)),p.getY(i)+n.getY(i)*thickness/Math.max(.001,Math.abs(m.scale.y)),p.getZ(i)+n.getZ(i)*thickness/Math.max(.001,Math.abs(m.scale.z)));g.computeBoundingSphere();const hull=new T.Mesh(g,new T.MeshLambertMaterial({color:C.shade14,side:T.BackSide,flatShading:true}));hull.userData.outline=true;hull.castShadow=false;m.userData.outlined=true;m.add(hull);}return group;}
// 全局手工纸质感：纸纤维颗粒 + 暖调（向 #F4E1DA 混 6%）+ 压住纯黑纯白

function paperGrain(m){if(m.userData.paperPass)return;m.userData.paperPass=true;if(m.color){m.color.lerp(new T.Color(C.shade15),.06);m.color.r=Math.min(.965,Math.max(.07,m.color.r));m.color.g=Math.min(.955,Math.max(.06,m.color.g));m.color.b=Math.min(.945,Math.max(.055,m.color.b));}
 m.onBeforeCompile=sh=>{sh.vertexShader=sh.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 vWg;').replace('#include <worldpos_vertex>','#include <worldpos_vertex>\nvWg=(modelMatrix*vec4(transformed,1.)).xyz;');
 sh.fragmentShader=sh.fragmentShader.replace('#include <common>',`#include <common>
varying vec3 vWg;
float hg(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float vg(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hg(i),hg(i+vec2(1,0)),f.x),mix(hg(i+vec2(0,1)),hg(i+vec2(1,1)),f.x),f.y);}`).replace('#include <alphatest_fragment>',`#include <alphatest_fragment>
{float g=vg(vec2(vWg.x*9.+vWg.y*4.,vWg.z*9.+vWg.y*6.))*.55+vg(vec2(vWg.x*31.,vWg.z*31.+vWg.y*23.))*.45;float f=vg(vec2(vWg.x*3.+vWg.z*2.7,vWg.y*26.))*vg(vec2(vWg.z*17.,vWg.x*4.+vWg.y*3.));diffuseColor.rgb*=.945+.09*g;diffuseColor.rgb*=1.-.05*smoothstep(.3,.8,f);}`);};
 m.customProgramCacheKey=()=>'paperpass';m.needsUpdate=true;}
export function paperPass(group){group.traverse(o=>{if(!o.isMesh||o.userData.outline)return;const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach(m=>{if(m&&m.isMeshLambertMaterial&&!m.transparent)paperGrain(m);});});return group;}
export function finish(group,update=()=>{}){if(C.season!=='winter'){const snow=[];group.traverse(o=>{if(o.userData.seasonalSnow)snow.push(o);});snow.forEach(o=>o.removeFromParent());}addOutline(group);paperPass(group);return {group,update};}
export function snowRoof(p,w,d,y,thick=1){if(C.season!=='winter')return new T.Group();const roof=new T.Group();roof.position.y=y;p.add(roof);for(const side of [-1,1]){const slab=box(roof,[w/2+.085,.05*thick,d+.10],[side*w/4,.10,0],C.snow);slab.rotation.z=-side*.32;for(let i=0;i<6;i++)ball(roof,[.085,.03*thick,.07],[side*(w/2+.02),.02,-d/2+i*d/5],C.snow);}ball(roof,[.07,.035*thick,d/2+.06],[0,.19*(1+.0),0],C.snow);return roof;}
export function snowCone(p,r,h,v,n=16){if(C.season!=='winter')return new T.Object3D();const g=new T.ConeGeometry(r,h,n,1);const a=g.attributes.position;for(let i=0;i<a.count;i++){if(a.getY(i)<0){const angle=Math.atan2(a.getZ(i),a.getX(i));const ripple=1+Math.sin(angle*5+.4)*.022;a.setXYZ(i,a.getX(i)*ripple,a.getY(i)+Math.sin(angle*7)*.012,a.getZ(i)*ripple);}}g.computeVertexNormals();return mesh(p,g,C.white,v);}
export function smoke(p,x,y,z){const discs=[];for(let i=0;i<4;i++){const m=mesh(p,new T.CircleGeometry(.055,7),C.cream,[x,y,z],{transparent:true,opacity:.5,side:T.DoubleSide,depthWrite:false});m.userData.outlined=true;discs.push(m);}return t=>discs.forEach((m,i)=>{const a=(t*.19+i/4)%1;m.position.set(x+Math.sin(t+i)*.025,y+a*.55,z);m.scale.setScalar(.5+a);m.material.opacity=(1-a)*.45;m.rotation.y=t*.2;});}
export function house(p,x,z,w=.36,h=.35,d=.35,blue=false){const g=new T.Group();g.position.set(x,0,z);p.add(g);const frame=blue?C.shade16:C.brown;box(g,[w,h,d],[0,h/2,0],C.felt);box(g,[w*1.02,h*.18,d*1.02],[0,h*.09,0],C.terra);for(const s of [-1,1]){const r=box(g,[w*.57,.06,d+.04],[s*w/4,h+.06,0],blue?C.shade17:C.brown);r.rotation.z=-s*.32;}snowRoof(g,w,d,h+.055);box(g,[w*.19,h*.62,.025],[0,h*.31+.02,d/2+.015],frame);for(const s of [-1,1]){box(g,[w*.20,h*.29,.025],[s*w*.32,h*.6,d/2+.018],frame);box(g,[w*.13,h*.20,.03],[s*w*.32,h*.6,d/2+.025],C.light,{emissive:C.light,emissiveIntensity:.35});}return g;}
let _glowTex=null;function glowTex(){if(typeof document==='undefined')return null;if(_glowTex)return _glowTex;const c=document.createElement('canvas');c.width=c.height=128;const g=c.getContext('2d'),gr=g.createRadialGradient(64,64,0,64,64,64);gr.addColorStop(0,'rgba(255,255,255,1)');gr.addColorStop(.45,'rgba(255,255,255,.55)');gr.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=gr;g.fillRect(0,0,128,128);_glowTex=new T.CanvasTexture(c);return _glowTex;}
export function glow(p,r,pos,color=C.shade18,op=.5){const m=new T.Mesh(new T.PlaneGeometry(r*2,r*2),new T.MeshBasicMaterial({map:glowTex(),color,transparent:true,opacity:op,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-2}));m.rotation.x=-Math.PI/2;m.position.set(...pos);m.userData.outlined=true;m.renderOrder=2;p.add(m);return m;}
export function cyl(p,rt,rb,h,v,c,n=10){return mesh(p,new T.CylinderGeometry(rt,rb,h,n),c,v);}
export {T};

const V2 = (p) => new T.Vector2(p[0], p[1]);

// 平滑轮廓（样条穿过各点）或折线轮廓
function shapeOf(pts, smooth = true) {
  const s = new T.Shape();
  s.moveTo(pts[0][0], pts[0][1]);
  if (smooth) s.splineThru([...pts.slice(1), pts[0]].map(V2));
  else { for (const p of pts.slice(1)) s.lineTo(p[0], p[1]); s.closePath(); }
  return s;
}

function mat(color) {
  return new T.MeshLambertMaterial({ color, flatShading: false });
}

// 把一个 2D 轮廓挤出成有厚度、带圆角的纸片，居中在 z
export function cut(parent, pts, depth, color, { z = 0, smooth = true, bevel = 0.012, pos = [0, 0, 0] } = {}) {
  const geo = new T.ExtrudeGeometry(shapeOf(pts, smooth), {
    depth, curveSegments: 28, bevelEnabled: bevel > 0,
    bevelThickness: bevel, bevelSize: bevel * 0.8, bevelSegments: 3,
  });
  geo.translate(0, 0, -depth / 2);
  const m = new T.Mesh(geo, mat(color));
  m.position.set(pos[0], pos[1], pos[2] + z);
  m.userData.seasonalSnow=color===C.snow;
  m.castShadow = true; m.receiveShadow = true;
  parent.add(m);
  return m;
}


// 带「手绘贴图」的挤出纸片：正反两面贴 canvas 画的细节，侧边纯色
export function paintCut(parent, pts, depth, color, draw, { z = 0, smooth = true, bevel = 0.012, pos = [0, 0, 0], res = 512 } = {}) {
  const m = cut(parent, pts, depth, color, { z, smooth, bevel, pos });
  if (typeof document === 'undefined') return m;
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const pad = 0.05, x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad, y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
  const w = x1 - x0, h = y1 - y0, W = res, H = Math.round(res * h / w);
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const x = c.getContext('2d');
  const P = (px, py) => [(px - x0) / w * W, (1 - (py - y0) / h) * H];
  const S = (d) => d / w * W;
  x.fillStyle = color; x.fillRect(0, 0, W, H);
  draw(x, P, S, W, H);
  const tex = new T.CanvasTexture(c); tex.anisotropy = 8;
  tex.repeat.set(1 / w, 1 / h); tex.offset.set(-x0 / w, -y0 / h);
  const side = m.material;
  m.material = [new T.MeshLambertMaterial({ map: tex }), side];
  return m;
}
const path = (x, P, pts, close = false) => { x.beginPath(); pts.forEach((p, i) => { const [a, b] = P(...p); i ? x.lineTo(a, b) : x.moveTo(a, b); }); if (close) x.closePath(); };

// 沿中心线生成「带宽度的条带」轮廓（脖子、鬃毛、缰绳等）
export function ribbon(center, w0, w1, jag = 0) {
  const curve = new T.CatmullRomCurve3(center.map((p) => new T.Vector3(p[0], p[1], 0)));
  const n = 24, L = [], R = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, p = curve.getPoint(t), d = curve.getTangent(t);
    let w = (w0 + (w1 - w0) * t) / 2;
    if (jag) w += (i % 2 ? jag : -jag * 0.3);
    L.push([p.x - d.y * w, p.y + d.x * w]);
    R.push([p.x + d.y * w, p.y - d.x * w]);
  }
  return [...L, ...R.reverse()];
}

export function ellipse(parent, rx, ry, rz, pos, color) {
  const m = new T.Mesh(new T.SphereGeometry(1, 20, 14), mat(color));
  m.scale.set(rx, ry, rz); m.position.set(...pos);
  m.userData.seasonalSnow=color===C.snow; m.castShadow = true; parent.add(m); return m;
}

// ---------- 腿：带膝盖的锥形纸片 + 深色蹄 ----------
export function leg(parent, x, y, z, len, color, hoof = C.shade19, w = 1) {
  const pivot = new T.Group(); pivot.position.set(x, y, z); parent.add(pivot);
  const k = len / 0.42;
  const pts = [[-0.055, 0.05], [0.055, 0.05], [0.05, -0.15], [0.034, -0.2], [0.03, -0.35], [0.04, -0.38], [-0.04, -0.38], [-0.03, -0.35], [-0.036, -0.2], [-0.06, -0.12]]
    .map(([a, b]) => [a * w, b * k]);
  cut(pivot, pts, 0.055, color, { smooth: false, bevel: 0.008 });
  cut(pivot, [[-0.045, -0.38 * k], [0.05, -0.38 * k], [0.055, -0.42 * k], [-0.05, -0.42 * k]], 0.065, hoof, { smooth: false, bevel: 0.004 });
  return pivot;
}


export function lathe(parent, profilePts, color, {segments=48}={}) { return mesh(parent,new T.LatheGeometry(profilePts.map(p=>new T.Vector2(...p)),segments),color); }
