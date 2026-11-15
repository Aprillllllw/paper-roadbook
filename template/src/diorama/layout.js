import * as T from 'three';
import {normalizeScene} from '../scene.js';
export let SCENE, BOARD, GRID, STOPS, RANGES, MASSIF, LAKES, RIVERS, ROUTES, PADS, KEEP, CLUMPS, BRIDGES;
export function configureScene(data) {
 SCENE=normalizeScene(data); BOARD=SCENE.board; GRID={x0:-BOARD.a-4,x1:BOARD.a+4,z0:-BOARD.b-4,z1:BOARD.b+4,step:.4};
 ({stops:STOPS,ranges:RANGES,peaks:MASSIF,lakes:LAKES,rivers:RIVERS,routes:ROUTES,pads:PADS,clumps:CLUMPS}=SCENE);
 KEEP=SCENE.props.map(p=>[p.x,p.z,p.opts?.keepRadius??(p.s||1)]); BRIDGES=SCENE.props.filter(p=>p.type==='bridge');
 return SCENE;
}
configureScene({});
export function curve(pts, y = 0) {
  return new T.CatmullRomCurve3(pts.map(([x, z]) => new T.Vector3(x, y, z)), false, 'centripetal');
}

// 撕纸底板轮廓：返回该角度下的半径缩放（围绕椭圆）
function hash(n) { const s = Math.sin(n * 127.1) * 43758.5453; return s - Math.floor(s); }
function vnoise1(t) { const i = Math.floor(t), f = t - i, u = f * f * (3 - 2 * f); return T.MathUtils.lerp(hash(i), hash(i + 1), u); }
export function edgeScale(theta) {
  const t = (theta + Math.PI) / (2 * Math.PI);
  return 1 + 0.09 * (vnoise1(t * 6) - 0.5) * 2 + 0.04 * (vnoise1(t * 19 + 5) - 0.5) * 2 + 0.018 * (vnoise1(t * 71 + 11) - 0.5) * 2 + 0.009 * (vnoise1(t * 260 + 3) - 0.5) * 2;
}
// >1 在底板外
export function boardRho(x, z) {
  const theta = Math.atan2(z / BOARD.b, x / BOARD.a);
  return Math.hypot(x / BOARD.a, z / BOARD.b) / edgeScale(theta);
}


export function surfaceAt(x,z,sample=()=>0) {
 const lake=LAKES.find(l=>{const c=Math.cos(l.rot),s=Math.sin(l.rot),dx=x-l.x,dz=z-l.z;return Math.hypot((dx*c+dz*s)/l.rx,(-dx*s+dz*c)/l.rz)<1;});
 return lake?lake.level+.14:sample(x,z)-.02;
}
export function bridgeAt(x,z,sample=()=>0) {
 let result={weight:0,height:sample(x,z)};
 for(const b of BRIDGES) {
  const c=Math.cos(b.rotY||0),s=Math.sin(b.rotY||0),dx=x-b.x,dz=z-b.z;
  const u=Math.abs(dx*c-dz*s),v=Math.abs(dx*s+dz*c),scale=b.s??1,half=(b.opts?.span??3.2)*scale/2;
  const weight=(1-T.MathUtils.smoothstep(u,Math.max(0,half-1.5),half+1.5))*(1-T.MathUtils.smoothstep(v,.12*scale,.30*scale));
  if(weight>result.weight)result={weight,height:(b.y??surfaceAt(b.x,b.z,sample)) + 1.02*scale};
 }
 return result;
}
