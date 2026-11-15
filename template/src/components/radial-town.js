import {T,C,mesh,box,house,cone,cyl,finish} from './paperkit.js';
// 特克斯八卦城：清晰的同心八角环城墙（雪顶）+ 八条放射路 + 环间小屋 + 中心鼓楼；俯视一眼可辨
export function makeRadialTown(){
  const group=new T.Group();
  cyl(group,1.5,1.5,.045,[0,.0225,0],C.shade0,8).rotation.y=Math.PI/8;
  const rings=[];
  // 八角环：Shape 带孔挤出（外壁赤陶、顶覆雪）
  const oct=(r,rot)=>{const p=[];for(let i=0;i<8;i++){const a=i*Math.PI/4+Math.PI/8;p.push([Math.cos(a)*r,Math.sin(a)*r]);}return p;};
  const wall=(ro,ri,h,col,y)=>{const sh=new T.Shape();oct(ro).forEach(([x,z],i)=>i?sh.lineTo(x,z):sh.moveTo(x,z));sh.closePath();const hole=new T.Path();oct(ri).forEach(([x,z],i)=>i?hole.lineTo(x,z):hole.moveTo(x,z));hole.closePath();sh.holes.push(hole);
    const g=new T.ExtrudeGeometry(sh,{depth:h,bevelEnabled:false});g.rotateX(-Math.PI/2);return mesh(group,g,col,[0,y,0]);};
  for(const [r,w] of [[.40,.05],[.80,.055],[1.20,.06],[1.45,.07]]){
    const wl=wall(r+w/2,r-w/2,.07,C.terra,.045);rings.push(wl);
    wall(r+w/2+.004,r-w/2-.004,.025,C.snow,.115);
  }
  // 环间道路带（浅米色）+ 八条放射路
  for(const [r1,r2] of [[.40,.80],[.80,1.20]]){const rg=wall(r2-.04,r1+.04,.012,C.shade1,.045);}
  for(let i=0;i<8;i++){const a=i*Math.PI/4;const road=box(group,[.07,.016,1.45],[Math.sin(a)*.725,.058,Math.cos(a)*.725],C.shade1);road.rotation.y=a;
    const edge=box(group,[.10,.012,1.45],[Math.sin(a)*.725,.056,Math.cos(a)*.725],C.terra);edge.rotation.y=a;}
  // 环间小屋
  for(let i=0;i<8;i++){const angle=i*Math.PI/4+Math.PI/8;for(const r of [.60,1.00,1.33]){const h=house(group,Math.sin(angle)*r,Math.cos(angle)*r,.17,.11+(i%2)*.025,.15);h.rotation.y=angle;h.position.y=.045;}}
  // 中心鼓楼
  cyl(group,.23,.25,.04,[0,.07,0],C.felt,8);
  box(group,[.14,.34,.14],[0,.24,0],C.terra);box(group,[.18,.04,.18],[0,.43,0],C.brown);
  cone(group,.15,.14,[0,.52,0],C.red,8);cone(group,.145,.10,[0,.545,0],C.snow,8);
  return finish(group,t=>rings.forEach((r,i)=>{}));
}
