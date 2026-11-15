import {T,C,box,mesh,ball,cone,cyl,finish} from './paperkit.js';
// 伊宁机场：弧形雪顶航站楼 + 玻璃幕面 + 塔台 + 停机坪上的小飞机
export function makeAirport(){
  const group=new T.Group();
  box(group,[3.1,.035,1.7],[0,.0175,0],C.cream);                                   // 停机坪
  for(let i=0;i<8;i++)box(group,[.22,.012,.04],[-1.2+i*.34,.04,.62],C.shade2);   // 滑行线
  box(group,[1.95,.30,.64],[-.45,.185,-.26],C.felt);                              // 航站楼主体
  box(group,[1.97,.06,.66],[-.45,.05,-.26],C.terra);
  // 玻璃幕面 + 立柱
  box(group,[1.80,.20,.02],[-.45,.21,.07],C.shade3,{emissive:C.shade4,emissiveIntensity:.12});
  for(let i=0;i<=10;i++){const x=-1.35+i*.18;box(group,[.025,.24,.04],[x,.20,.085],C.cream);}
  // 弧形屋顶：蓝灰底 + 厚雪盖
  const prof=(r,h)=>{const sh=new T.Shape();sh.moveTo(-1.05,0);for(let i=0;i<=16;i++){const x=-1.05+i*2.1/16;sh.lineTo(x,r+Math.sin(i*Math.PI/16)*h);}sh.lineTo(1.05,0);return sh;};
  const roof=mesh(group,new T.ExtrudeGeometry(prof(.10,.20),{depth:.80,bevelEnabled:false}),C.shade5,[-.45,.31,-.67]);
  const cap=mesh(group,new T.ExtrudeGeometry(prof(.14,.205),{depth:.76,bevelEnabled:false}),C.snow,[-.45,.335,-.65]);cap.scale.set(1.0,1,1);
  for(let i=0;i<9;i++)ball(group,[.12,.04,.05],[-1.45+i*.22,.34+Math.sin(i*Math.PI/8)*.02,.14],C.snow);   // 檐口雪团
  // 塔台：方柱 + 蓝玻璃驾驶舱 + 雪盖 + 天线
  box(group,[.24,.90,.25],[.82,.45,-.22],C.felt);box(group,[.26,.05,.27],[.82,.62,-.22],C.terra);
  cyl(group,.25,.19,.20,[.82,.95,-.22],C.shade3,8);
  cyl(group,.265,.265,.04,[.82,1.075,-.22],C.coffee,8);cone(group,.30,.10,[.82,1.14,-.22],C.snow,8);
  cyl(group,.012,.012,.20,[.82,1.30,-.22],C.coffee,5);
  const beacon=ball(group,[.035,.035,.035],[.82,1.41,-.22],C.red);beacon.material.emissive.set(C.red);
  // 小飞机：圆柱机身 + 鼻锥 + 后掠机翼 + 红尾翼
  const plane=new T.Group();plane.position.set(.60,.12,.50);plane.rotation.y=-.25;group.add(plane);
  const fus=cyl(plane,.07,.07,.56,[0,.07,0],C.white,10);fus.rotation.z=Math.PI/2;
  cone(plane,.07,.14,[.34,.07,0],C.white,10).rotation.z=-Math.PI/2;
  cone(plane,.07,.20,[-.37,.085,0],C.white,10).rotation.z=Math.PI/2;
  const w=box(plane,[.20,.022,.82],[-.02,.06,0],C.white);w.rotation.y=-.22;
  box(plane,[.16,.022,.32],[-.40,.10,0],C.white);box(plane,[.14,.20,.022],[-.40,.19,0],C.red);
  for(const z of [-.2,.2])cyl(plane,.028,.028,.12,[.04,.02,z],C.deep,8).rotation.z=Math.PI/2;
  for(let i=0;i<5;i++)box(plane,[.03,.025,.005],[.20-i*.09,.085,.07],C.shade3);
  return finish(group,t=>beacon.material.emissiveIntensity=Math.sin(t*3)>.7?1:.05);
}
