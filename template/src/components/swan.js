import {T,C,ball,cone,mesh,box,finish} from './paperkit.js';
// 天鹅：S 形长颈 + 折叠的纸翅 + 翘起的尾羽
export function makeSwan(){
  const group=new T.Group();
  ball(group,[.24,.105,.135],[-.03,.12,0],C.white);                 // 身体
  const tail=cone(group,.07,.2,[-.27,.15,0],C.white,4);tail.rotation.z=Math.PI/2+.45;tail.scale.z=.7;
  const neck=new T.Group();group.add(neck);
  const curve=new T.CatmullRomCurve3([[.14,.13,0],[.23,.17,0],[.26,.28,0],[.19,.38,0],[.19,.47,0],[.25,.52,0]].map(p=>new T.Vector3(...p)));   // S 形
  mesh(neck,new T.TubeGeometry(curve,14,.030,6,false),C.white);
  ball(neck,[.07,.045,.042],[.265,.515,0],C.white);                   // 头
  ball(neck,[.026,.025,.040],[.30,.515,0],C.coffee);                  // 嘴基黑
  const beak=cone(neck,.028,.085,[.335,.505,0],C.shade36,4);beak.rotation.z=-Math.PI/2-.12;
  const wings=[-1,1].map(s=>{const pivot=new T.Group();pivot.position.set(-.05,.17,s*.095);pivot.rotation.y=s*-.12;group.add(pivot);
    const wing=mesh(pivot,new T.ConeGeometry(.095,.36,3),C.white);wing.rotation.z=-1.38;wing.rotation.x=0;wing.scale.set(1,1,.22);wing.position.set(-.02,.015,0);   // 折叠纸翅（三角片）
    const tip=mesh(pivot,new T.ConeGeometry(.045,.16,3),C.shade37,[-.2,.045,0]);tip.rotation.z=-1.2;tip.scale.z=.2;
    return pivot;});
  return finish(group,t=>{group.position.y=Math.sin(t*1.3)*.012;neck.rotation.z=Math.sin(t*.7)*.05;wings.forEach((w,i)=>w.rotation.x=(i?1:-1)*Math.max(0,Math.sin(t*.35))**18*.45);});
}
