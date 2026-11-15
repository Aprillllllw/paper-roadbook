import * as T from 'three';
import {make,types} from './components/registry.js';
import {setTheme,theme} from './theme.js';
const query=new URLSearchParams(location.search),summer=query.get('season')==='summer';
setTheme({preset:summer?'summer-meadow':'winter-blush',season:summer?'summer':'winter'});
T.ColorManagement.enabled=false;
const renderer=new T.WebGLRenderer({antialias:true,alpha:true});renderer.outputColorSpace=T.LinearSRGBColorSpace;renderer.setPixelRatio(Math.min(devicePixelRatio,2));document.body.appendChild(renderer.domElement);
const views=[];
for(const type of query.has('type')?[query.get('type')]:types()){
 const section=document.createElement('section'),heading=document.createElement('h2'),angles=document.createElement('div');heading.textContent=type;angles.className='angles';section.append(heading,angles);document.querySelector('main').append(section);
 for(const [label,dir] of [['斜俯视',[3,2.5,4]],['正侧面',[0,0,1]],['正前方',[1,0,0]]]){
  const element=document.createElement('div');element.className='view';const caption=document.createElement('span');caption.textContent=label;element.append(caption);angles.append(element);
  const scene=new T.Scene(),made=make(type,{},theme);scene.add(made.group);scene.add(new T.HemisphereLight(theme.white,theme.brown,2));const light=new T.DirectionalLight(theme.cream,2);light.position.set(3,5,4);scene.add(light);
  made.group.updateMatrixWorld(true);const box=new T.Box3().setFromObject(made.group),center=box.getCenter(new T.Vector3()),size=box.getSize(new T.Vector3()),radius=Math.max(size.x,size.y,size.z,.1)*.7;
  const camera=new T.OrthographicCamera(-radius,radius,radius,-radius,.01,100);camera.position.copy(center).addScaledVector(new T.Vector3(...dir).normalize(),15);camera.lookAt(center);views.push({element,scene,camera,made,radius});
 }
}
renderer.setAnimationLoop(now=>{
 renderer.setSize(innerWidth,innerHeight,false);renderer.setScissorTest(false);renderer.setClearColor(0,0);renderer.clear();renderer.setScissorTest(true);
 for(const v of views){const b=v.element.getBoundingClientRect();if(b.bottom<0||b.top>innerHeight)continue;const aspect=b.width/b.height;v.camera.left=-v.radius*Math.max(aspect,1);v.camera.right=-v.camera.left;v.camera.top=v.radius/Math.min(aspect,1);v.camera.bottom=-v.camera.top;v.camera.updateProjectionMatrix();v.made.update?.(now/1000,1/60);renderer.setViewport(b.left,innerHeight-b.bottom,b.width,b.height);renderer.setScissor(Math.max(0,b.left),Math.max(0,innerHeight-b.bottom),Math.min(b.width,innerWidth-b.left),Math.min(b.bottom,innerHeight)-Math.max(0,b.top));renderer.render(v.scene,v.camera);}
});
