import {T,C,box,finish} from './paperkit.js';
export function makeFence(len=1){const group=new T.Group(),n=Math.max(1,Math.ceil(len/.25));for(let i=0;i<=n;i++)box(group,[.035,.23,.035],[-len/2+i*len/n,.115,0],C.brown);for(const y of [.08,.18])box(group,[len+.04,.028,.026],[0,y,0],C.brown);return finish(group);}
