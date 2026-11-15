import {T,C,house,mesh,box,cone,cyl,ball,rod,snowRoof,finish} from './paperkit.js';
// 伊宁：奶油赤陶色小楼（蓝窗框、雪顶）+ 一座圆顶清真寺式建筑 + 一座塔楼 + 粉花树/红果树
function tree(parent,x,z,kind,s=1){
  const g=new T.Group();g.position.set(x,0,z);g.scale.setScalar(s);parent.add(g);
  cyl(g,.02,.03,.22,[0,.11,0],C.brown,5);
  const cols=kind==='blossom'?[C.blossom,C.shade33,C.shade34]:[C.shade6,C.shade35];
  const n=kind==='blossom'?6:4;
  for(let i=0;i<n;i++){const a=i*2.4,b=ball(g,[.10,.085,.10],[Math.cos(a)*.08,.26+(i%3)*.06,Math.sin(a)*.08],cols[i%cols.length]);}
  if(kind==='berry')for(let i=0;i<7;i++){const a=i*1.9;ball(g,[.022,.022,.022],[Math.cos(a)*.13,.22+(i%3)*.07,Math.sin(a)*.13],C.red);}
  if(kind==='blossom')for(let i=0;i<4;i++){ball(g,[.05,.03,.05],[Math.cos(i*1.7)*.09,.40-(i%2)*.03,Math.sin(i*1.7)*.09],C.snow);}
  return g;
}
export function makeOldTown(){
  const group=new T.Group();
  // 环绕的小楼（不同大小，朝向中心）
  const ring=[[.0,.95,.42,.30],[.52,.82,.36,.34],[-.55,.80,.38,.28],[-1.02,.45,.40,.34],[1.02,.40,.36,.30],[-1.18,-.12,.38,.26],[1.22,-.05,.40,.32],[-.95,-.62,.36,.30],[.9,-.68,.38,.28],[-.35,-.95,.40,.30],[.35,-1.0,.36,.34]];
  ring.forEach(([x,z,w,h],i)=>{const hh=house(group,x,z,w+(i%3)*.04,h,.38,true);hh.rotation.y=Math.atan2(-x,-z)+Math.PI;});
  // 中央：主楼 + 圆顶 + 塔
  const main=new T.Group();main.scale.setScalar(1.22);group.add(main);
  box(main,[.72,.62,.58],[0,.31,0],C.felt);box(main,[.74,.10,.60],[0,.05,0],C.terra);
  for(const x of [-.24,0,.24])box(main,[.10,.30,.03],[x,.28,.30],C.shade16);
  box(main,[.74,.04,.60],[0,.64,0],C.terra);
  cyl(main,.28,.28,.12,[0,.70,0],C.felt,12);
  mesh(main,new T.SphereGeometry(.30,14,6,0,Math.PI*2,0,Math.PI/2),C.shade16,[0,.76,0]);
  mesh(main,new T.SphereGeometry(.31,14,4,0,Math.PI*2,0,Math.PI*.34),C.snow,[0,.775,0]);
  cone(main,.025,.14,[0,1.15,0],C.red,5);
  // 塔楼：方塔 + 蓝顶 + 雪
  const tw=new T.Group();tw.position.set(-.68,0,.05);tw.scale.setScalar(1.15);group.add(tw);
  box(tw,[.20,1.10,.20],[0,.55,0],C.felt);box(tw,[.22,.08,.22],[0,.80,0],C.terra);box(tw,[.22,.06,.22],[0,1.12,0],C.terra);
  for(const y of [.35,.65])box(tw,[.07,.13,.215],[0,y,0],C.shade16);
  cone(tw,.16,.30,[0,1.30,0],C.shade16,4).rotation.y=Math.PI/4;cone(tw,.15,.16,[0,1.36,0],C.snow,4).rotation.y=Math.PI/4;
  ball(tw,[.03,.03,.03],[0,1.52,0],C.red);
  // 树：粉花 + 红果
  [[-1.5,.75,'blossom',1.3],[-1.35,.35,'blossom',1.1],[-1.6,.1,'berry',1],[1.45,.65,'blossom',1.25],[1.55,.2,'berry',1],[1.35,-.45,'blossom',1.2],[-1.35,-.95,'berry',1.1],[.1,-1.35,'blossom',1.2],[.95,1.12,'berry',1],[-.95,1.15,'blossom',1.1],[1.1,-1.1,'berry',1]].forEach(([x,z,k,s])=>tree(group,x,z,k,s));
  const windows=[];group.traverse(o=>{if(o.isMesh&&o.material.emissive?.getHex())windows.push(o);});
  return finish(group,t=>windows.forEach((m,i)=>m.material.emissiveIntensity=.35+Math.sin(t*.6+i)*.06));
}
