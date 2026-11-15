import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import * as T from 'three';
import {normalizeScene} from '../src/scene.js';
import {normalizeTrip} from '../src/trip.js';
import {configureScene,bridgeAt,curve} from '../src/diorama/layout.js';
import {bakeHeightfield} from '../src/diorama/heightfield.js';
import {make,types} from '../src/components/registry.js';
import {setTheme,theme} from '../src/theme.js';
import {buildLandscape} from '../src/diorama/landscape.js';
import {placeProps} from '../src/diorama/props.js';
import {cut,paintCut,ribbon,ellipse,leg,lathe} from '../src/components/paperkit.js';
// 纯 node 里 import.meta.glob 不可用，registry 不会注册 custom 组件：这里从文件里读出 type，对这些类型不做「已注册」断言
const customTypes=new Set();
try{for(const f of await readdir(new URL('../src/components/custom/',import.meta.url))){if(!f.endsWith('.js'))continue;const m=(await readFile(new URL('../src/components/custom/'+f,import.meta.url),'utf8')).match(/type\s*:\s*['"]([^'"]+)['"]/);if(m)customTypes.add(m[1]);}}catch{}
if(customTypes.size)console.log(`custom 组件（node 下无法注册，已跳过注册断言，请到 /gallery.html 目检）：${[...customTypes].join(', ')}`);
const demo=JSON.parse(await readFile(new URL('../src/data/scene.json',import.meta.url)));
const trip=normalizeTrip(JSON.parse(await readFile(new URL('../src/data/trip.json',import.meta.url))));
const noGlb=scene=>({...scene,props:(scene.props||[]).map(p=>p.opts?.glb?{...p,opts:{...p.opts,glb:undefined}}:p)}); // node 里没法加载 GLB，浏览器里才会换模型
for(const [label,input] of [['minimal',{stops:{a:[0,0],b:[5,5]},routes:{D1:[[0,0],[5,5]]}}],['demo',noGlb(demo)],['coast',{stops:{},routes:{},coast:{side:'S',inset:12}}]]){
 const data=configureScene(input);assert.equal(normalizeScene(input).board.a,62);
 const hf=bakeHeightfield();assert(hf.data.every(Number.isFinite));assert(Number.isFinite(hf.sample(0,0)));
 if(label==='minimal'){assert(hf.data.every(v=>Math.abs(v-.55)<1e-6));assert.equal(data.props.length,0);}
 const scene=new T.Scene();setTheme(data.theme);const land=buildLandscape(scene);
 const routes=Object.fromEntries(Object.entries(data.routes).map(([k,pts])=>{const path=curve(pts);return[k,{at:t=>path.getPoint(t),tangent:t=>path.getTangent(t)}];}));
 const props=placeProps(scene,land,routes,null);props.update(1,.016,.5,Object.values(routes)[0]);
 scene.updateMatrixWorld(true);scene.traverse(o=>{if(o.isMesh){const p=o.geometry.attributes.position;assert([...p.array].every(Number.isFinite));for(const m of Array.isArray(o.material)?o.material:[o.material]){if(m.onBeforeCompile){const sh={uniforms:{},vertexShader:T.ShaderLib.lambert.vertexShader,fragmentShader:T.ShaderLib.lambert.fragmentShader};m.onBeforeCompile(sh);assert(!sh.fragmentShader.includes('undefined'));assert(!sh.fragmentShader.includes('${'));}}}});
 for(const p of data.props)assert(types().includes(p.type)||customTypes.has(p.type),`未知组件类型：${p.type}`);
 console.log(`${label}: ${hf.nx}×${hf.nz}, ${scene.children.length} scene objects, finite geometry`);
}
for(const season of ['winter','summer']){
 setTheme({season,preset:season==='winter'?'winter-blush':'summer-meadow'});
 for(const type of types()){
  const made=make(type,{},theme);assert(made.group.isObject3D);assert.equal(typeof made.update,'function');made.update(1,.016,2);made.group.updateMatrixWorld(true);
  const size=new T.Box3().setFromObject(made.group).getSize(new T.Vector3());assert(size.toArray().every(Number.isFinite));
  if(season==='summer')made.group.traverse(o=>assert(!o.userData.seasonalSnow));
  console.log(`${season} ${type}: bounds ${size.toArray().map(n=>n.toFixed(3)).join(' × ')}`);
 }
}
configureScene({props:[{type:'bridge',x:3,z:4,s:2,y:1,rotY:Math.PI/2,opts:{span:4}}]});
const bridge=bridgeAt(3,4);assert.equal(bridge.weight,1);assert.equal(bridge.height,3.04);assert(bridgeAt(3,7).weight>0);assert.equal(bridgeAt(7,4).weight,0);
assert(make('unregistered',{},theme).group.isGroup);
const g=new T.Group();cut(g,[[0,0],[1,0],[1,1]],.2,theme.cream);paintCut(g,[[0,0],[1,0],[1,1]],.2,theme.cream,()=>{});ellipse(g,.2,.3,.2,[0,0,0],theme.cream);leg(g,0,1,0,.4,theme.brown);lathe(g,[[.5,0],[.2,1],[0,1.1]],theme.cream,{segments:32});assert(ribbon([[0,0],[1,1]],.2,.1).length>0);
for(const d of trip.days){assert(d.route in demo.routes);for(const id of d.stops)assert(id in demo.stops);}
assert.equal(normalizeTrip({}).days.length,0);assert(normalizeTrip({}).disclaimer);
console.log('All scene, factory, theme, bridge, paperkit and trip checks passed. Canvas textures require a browser for visual verification.');
