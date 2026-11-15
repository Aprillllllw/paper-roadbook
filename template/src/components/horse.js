import {T,C,box,ball,cone,finish} from './paperkit.js';
// 马：圆润的身体、厚实的颈、鬃毛、飘动的尾、两段式腿 + 蹄；面向 +X
export function makeHorse({color=C.shade20}={}){
  const group=new T.Group();const dark=C.coffee;
  ball(group,[.34,.20,.15],[0,.52,0],color);                         // 躯干
  ball(group,[.14,.18,.14],[.20,.53,0],color);                       // 胸
  ball(group,[.14,.17,.15],[-.20,.54,0],color);                      // 臀
  const legs=[];
  for(const x of [-.22,.22])for(const z of [-.09,.09]){
    const leg=new T.Group();leg.position.set(x,.48,z);group.add(leg);
    box(leg,[.075,.22,.075],[0,-.10,0],color);                        // 上腿
    box(leg,[.05,.19,.05],[0,-.31,0],color);                          // 下腿
    box(leg,[.075,.065,.075],[.012,-.43,0],dark);                     // 蹄
    legs.push(leg);}
  const neck=new T.Group();neck.position.set(.24,.61,0);group.add(neck);
  const n=box(neck,[.15,.34,.15],[.05,.10,0],color);n.rotation.z=-.38;   // 颈
  ball(neck,[.17,.085,.085],[.15,.27,0],color);                         // 头
  ball(neck,[.07,.062,.075],[.255,.245,0],C.shade21);                   // 鼻口（浅色）
  for(const z of [-.045,.045])cone(neck,.022,.075,[.10,.37,z],color,4); // 耳
  for(const z of [-.078,.078])ball(neck,[.014,.014,.009],[.19,.285,z],dark); // 眼
  for(let i=0;i<5;i++){const m=box(neck,[.045,.10,.03],[-.04+i*.018,.30-i*.055,0],dark);m.rotation.z=-.38+.2;}   // 鬃毛
  const tail=new T.Group();tail.position.set(-.31,.60,0);group.add(tail);
  const t1=cone(tail,.055,.30,[-.07,-.12,0],dark,5);t1.rotation.z=.35;t1.scale.z=.8;   // 尾
  const result=finish(group,t=>{neck.rotation.z=-.12+Math.sin(t*.55)*.21;tail.rotation.x=Math.sin(t*1.8)*.25;});
  group.userData.legs=legs;return {...result,legs,neck};
}
