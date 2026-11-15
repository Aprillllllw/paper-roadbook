import {T,C,box,ball,cyl,glow,snowRoof,smoke,finish,mesh} from './paperkit.js';import {makeFence} from './fence.js';
// 库尔德宁木屋：圆木叠砌 + 圆木端头 + 厚雪屋顶（带出檐）+ 暖光窗 + 雪地光斑 + 烟囱 + 围栏
export function makeCabin(){
  const group=new T.Group();
  // 圆木墙：水平圆柱，两种暖木色交替
  for(let i=0;i<9;i++){
    const col=i%2?C.log2:C.log1,y=.05+i*.066;
    for(const sz of [-1,1]){const l=cyl(group,.036,.036,1.16,[0,y,sz*.335],col,8);l.rotation.z=Math.PI/2;}
    for(const sx of [-1,1]){const l=cyl(group,.036,.036,.74,[sx*.545,y+.033,0],i%2?C.log1:C.log2,8);l.rotation.x=Math.PI/2;}
  }
  box(group,[1.04,.56,.64],[0,.30,0],C.shade9);                      // 墙芯
  // 山墙三角
  const gable=new T.Shape();gable.moveTo(-.36,0);gable.lineTo(.36,0);gable.lineTo(0,.24);gable.closePath();
  for(const sx of [-1,1]){const gm=mesh(group,new T.ExtrudeGeometry(gable,{depth:.03,bevelEnabled:false}),C.log2,[sx*.535,.62,0]);gm.rotation.y=Math.PI/2;}
  // 坡屋顶：深褐木瓦 + 厚雪 + 出檐
  for(const s of [-1,1]){const r=box(group,[.70,.055,.90],[s*.30,.68,0],C.shade9);r.rotation.z=-s*.34;}
  const roof=snowRoof(group,1.28,.92,.67,2.0);roof.scale.set(1.03,1.1,1.03);
  for(const s of [-1,1]){const top=box(group,[.72,.075,.95],[s*.30,.745,0],C.snow);top.rotation.z=-s*.34;}
  for(let i=0;i<7;i++)ball(group,[.07,.05,.06],[-.58+i*.19,.63+Math.sin(i)*.012,.47],C.snow);   // 檐口雪团
  // 门廊 + 台阶
  box(group,[1.40,.06,.36],[0,.03,.52],C.shade10);
  for(const x of [-.62,.62])cyl(group,.025,.025,.54,[x,.30,.66],C.log1,6);
  // 暖光窗 + 门
  const windows=[];
  for(const x of [-.36,.34]){
    box(group,[.31,.31,.035],[x,.34,.352],C.log1);
    windows.push(box(group,[.24,.24,.04],[x,.34,.372],C.light,{emissive:C.light,emissiveIntensity:.8}));
    box(group,[.014,.25,.045],[x,.34,.40],C.log1);box(group,[.25,.014,.045],[x,.34,.40],C.log1);
    glow(group,.34,[x,.075,.84],C.shade11,.85).scale.set(1,1.4,1);
  }
  box(group,[.20,.44,.04],[0,.23,.355],C.shade9);box(group,[.15,.34,.045],[0,.28,.378],C.light,{emissive:C.light,emissiveIntensity:.5});
  glow(group,.42,[0,.07,.95],C.shade12,.7).scale.set(1.3,1.5,1);
  // 烟囱 + 雪帽 + 烟
  box(group,[.13,.34,.14],[.37,.80,-.17],C.shade13);box(group,[.17,.04,.18],[.37,.99,-.17],C.snow);
  // 围栏
  const fence=makeFence(1.5);fence.group.position.set(0,0,.98);group.add(fence.group);
  for(const x of [-.74,.74]){const f=makeFence(.6);f.group.rotation.y=Math.PI/2;f.group.position.set(x,0,.70);group.add(f.group);}
  // 柴堆
  for(let i=0;i<3;i++)cyl(group,.04,.04,.28,[-.77,.05+i*.05,-.1+ (i%2)*.04],C.log2,6).rotation.x=Math.PI/2;
  const animate=smoke(group,.37,1.02,-.17);
  return finish(group,t=>{animate(t);windows.forEach((m,i)=>m.material.emissiveIntensity=.78+Math.sin(t*1.7+i)*.04);});
}
