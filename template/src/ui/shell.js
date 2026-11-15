const iconPaths={
 plane:'M3 13l7-2 1-8 2-1 1 8 7 3v2l-7-1-1 6h-2l-1-6-7 1z',
 camel:'M3 17l1-7 3-3 3 3 3-3 3 3 2-6 3 1-1 8-3 1-1 7m-11-7-1 7m9-7 1 7M7 14l1 7',
 bridge:'M2 19h20M6 19V4h3v15m6 0V4h3v15M2 15l5-9 10 0 5 9',
 swan:'M3 16q4 7 12 2l5-3-6 1q-4-1-3-5l2-5q1-5 4-2l-1 2-2-1m-7 9 5 3',
 calendar:'M4 5h16v16H4zM8 2v6m8-6v6M4 10h16M8 14h2m4 0h2m-8 4h2',
 car:'M3 16V9l3-5h12l3 5v7zM3 10h18M6 16v4m12-4v4M6 13h2m8 0h2',
 bed:'M2 21V7m0 10h20v4m-20-8h20v4M6 9V5h13v8M7 9h5',
 food:'M5 2v8m-3-8v6q3 6 6 0V2M5 12v10M18 22V2q-6 5 0 12',
 wallet:'M3 5h17v16H3zM3 5l14-3v3m-3 6h8v6h-8z',
 horse:'M3 18l2-9 9-1 3-6 4 4-2 6-4 1-1 8m-8-8-2 8m4-8 2 8',
 house:'M2 11l10-8 10 8M5 9.5V21h14V9.5M10 21v-6h4v6M16 5V3h3v4',
 lake:'M2 8q2.5-2.5 5 0t5 0 5 0 5 0M2 13q2.5-2.5 5 0t5 0 5 0 5 0M5 18q2.5-2.5 5 0t5 0 4-.5'
};
const stopIcon={stay:'bed',pass:'car',sight:'lake'};
const esc=v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); // trip.json 里的文字一律先转义再拼进 innerHTML
const mediaURL=src=>/^(?:https?:|data:|blob:|\/)/.test(src)?src:'/'+src;
function icon(name){return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${iconPaths[name]||iconPaths.swan}"/></svg>`;}
export function createUI(trip,onStop,actions){
 const ui=trip.lang==='en'?{brand:'Travel journal',eyebrow:'Paper road book',dayList:'Itinerary',distanceUnit:'km',about:'About',snow:'Snow',reset:'Reset',pause:'Pause',play:'Play',hint:'Drag to rotate · Scroll to zoom',close:'Close',previous:'Previous',next:'Next',explore:'Explore',mediaUnavailable:'Media unavailable',replay:'Replay',prevStop:'Previous stop',nextStop:'Next stop'}:{brand:'旅行手记',eyebrow:'纸雕路书',dayList:'行程',distanceUnit:'公里',about:'关于作者',snow:'飘雪',reset:'复位',pause:'暂停',play:'播放',hint:'拖动旋转 · 滚动缩放',close:'关闭',previous:'上一张',next:'下一张',explore:'探索',mediaUnavailable:'媒体暂不可用',replay:'重播',prevStop:'上一站',nextStop:'下一站'},$=s=>document.querySelector(s);document.title=trip.title;
 $('#heading').innerHTML=`<div class="brand"><svg viewBox="0 0 80 36" aria-hidden="true"><path d="M2 32 23 12 32 23 45 2 78 32M17 27l6-15 4 13M35 20 45 2 51 23 45 17 41 26"/></svg><span>${ui.brand}</span></div><div class="heading-rule"></div><p class="eyebrow">${ui.eyebrow}</p><h1>${esc(trip.title)}</h1><p class="subtitle">${esc(trip.subtitle)}</p>`;
 $('#days').innerHTML=`<p class="eyebrow">${ui.dayList}</p>`+trip.days.map((d,i)=>`<button class="day ${i===0?'active':''}" data-day="${i}" aria-pressed="${i===0}"><span class="day-number">${esc(d.id)}</span><span><strong>${esc(d.title)}</strong><small>${d.km==null?'':esc(d.km)+' '+ui.distanceUnit} ${esc(d.drive||'')}</small></span><span class="day-arrow">↗</span></button>`).join('');
 const dayButtons=[...document.querySelectorAll('#days .day')];dayButtons.forEach((b,i)=>b.onclick=()=>actions.selectDay(i));
 const seq=trip.days.flatMap((d,di)=>d.stops.map(id=>({di,id})));
 const avatar=trip.author.avatar?`<span class="avatar"><img src="${esc(trip.author.avatar)}" alt=""></span>`:'';$('#author').innerHTML=`${avatar}<div><p class="eyebrow">${ui.about}</p><strong>${esc(trip.author.name)}</strong><p>${esc(trip.author.line)}</p></div>`;
 const disclaimer=document.createElement('p');disclaimer.id='disclaimer';disclaimer.textContent=trip.disclaimer;document.querySelector('#app').appendChild(disclaimer);
 document.documentElement.lang=trip.lang;$('#days').setAttribute('aria-label',ui.dayList);
 for(const key of ['description','og:description','og:title']){const m=document.querySelector(`meta[${key.startsWith('og:')?'property':'name'}="${key}"]`);if(m)m.content=key==='og:title'?trip.title:trip.subtitle;}
 const facts=document.createElement('section');facts.id='facts';facts.innerHTML=trip.facts.map(f=>`<div class="fact">${icon(f.icon)}<div><strong>${esc(f.label)}</strong><p title="${esc(f.value)}">${esc(f.value)}</p></div></div>`).join('');document.querySelector('#app').appendChild(facts);
 const decoration=document.createElement('div');decoration.className='winter-branches';decoration.setAttribute('aria-hidden','true');
 const branch=`<svg viewBox="0 0 120 200"><g fill="none" stroke="#805d4b" stroke-width="1.3"><path d="M12 195Q70 116 75 12M38 152Q26 110 9 91M53 118Q91 100 111 61M65 77Q46 52 39 23M73 42l26-24M30 165q25-6 39-24M48 130q-21-3-30-18"/><path d="M35 146q-25-19-20-36 19 9 20 36M57 116q27-25 43-21-9 21-43 21M66 71Q43 55 45 41q20 6 21 30" fill="#a5aa8c" fill-opacity=".2"/></g><g fill="#b91c24" stroke="#813c31" stroke-width=".6">${[[75,13],[39,23],[99,18],[111,61],[10,91],[27,70],[54,41],[91,78],[80,96]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="4"/><circle cx="${x-1}" cy="${y-1}" r="1.1" fill="#f3b5a1" stroke="none"/>`).join('')}</g></svg>`;
 decoration.innerHTML=branch+branch;decoration.hidden=document.documentElement.dataset.season!=='winter';document.querySelector('#app').appendChild(decoration);
 $('#controls').innerHTML=`<div class="tool-row"><button id="snow" aria-pressed="false">❄ <span>${ui.snow}</span></button><button id="reset">↺ <span>${ui.reset}</span></button><button id="replay">↻ <span>${ui.replay} ${esc(trip.days[0]?.label||'')}</span></button><button id="play">Ⅱ <span>${ui.pause}</span></button></div><p>${ui.hint}</p>`;
 if(trip.lang==='en')$('#panel').setAttribute('aria-label','Stop details');else $('#panel').setAttribute('aria-label','站点详情');
 if(document.documentElement.dataset.season!=='winter')$('#snow').hidden=true;
 $('#snow').onclick=()=>{const enabled=actions.snow();$('#snow').setAttribute('aria-pressed',enabled);};$('#reset').onclick=actions.reset;$('#replay').onclick=()=>actions.replay();$('#play').onclick=()=>{const playing=actions.play();$('#play').innerHTML=`${playing?'Ⅱ':'▷'} <span>${playing?ui.pause:ui.play}</span>`;};
 const panel=$('#panel');let current=null,index=0,trigger=null,seqIndex=-1;
 function mediaHTML(m){return m.type==='video'?`<video src="${esc(mediaURL(m.src))}" ${m.poster?`poster="${esc(mediaURL(m.poster))}"`:''} autoplay muted loop playsinline controls preload="metadata"></video>`:`<img src="${esc(mediaURL(m.src))}" alt="${esc(current.name)}">`;}
 function render(){const stop=current,day=trip.days[seq[seqIndex].di],hasPrev=seqIndex>0,hasNext=seqIndex<seq.length-1;
  panel.innerHTML=`<button class="close" aria-label="${ui.close}">×</button>${stop.media.length?`<div class="media">${mediaHTML(stop.media[index])}${stop.media.length>1?`<div class="carousel-controls"><button class="prev" aria-label="${ui.previous}">‹</button><div class="dots">${stop.media.map((_,i)=>`<button aria-label="${i+1}" aria-current="${index===i}" data-slide="${i}"></button>`).join('')}</div><button class="next" aria-label="${ui.next}">›</button></div>`:''}</div>`:''}<div class="panel-copy"><p class="eyebrow">${esc(day.label)} · ${ui.explore}</p><h2>${esc(stop.name)}</h2><p class="zh">${esc(stop.zh)}</p><dl>${Object.entries(stop.info).map(([label,text])=>`<div><dt>${esc(label)}</dt><dd>${esc(text)}</dd></div>`).join('')}</dl>${stop.extra?`<section class="extra"><h3>${esc(stop.extra.title)}</h3><p>${esc(stop.extra.text)}</p>${stop.extra.media?.src?mediaHTML(stop.extra.media):''}</section>`:''}</div><nav class="panel-nav" aria-label="${ui.dayList}"><button class="stop-prev" ${hasPrev?'':'disabled'}>← ${ui.prevStop}</button><button class="stop-next" ${hasNext?'':'disabled'}>${ui.nextStop} →</button></nav>`;
  panel.querySelector('.close').onclick=close;panel.querySelector('.prev')?.addEventListener('click',()=>slide(index-1));panel.querySelector('.next')?.addEventListener('click',()=>slide(index+1));panel.querySelectorAll('[data-slide]').forEach(b=>b.onclick=()=>slide(+b.dataset.slide));
  panel.querySelector('.stop-prev').onclick=()=>step(-1);panel.querySelector('.stop-next').onclick=()=>step(1);
  panel.querySelectorAll('video,img').forEach(el=>el.addEventListener('error',()=>{if(el.tagName==='VIDEO'&&el.poster){const image=new Image();image.src=el.poster;image.alt=current.name;el.replaceWith(image);}else el.replaceWith(Object.assign(document.createElement('p'),{className:'media-error',textContent:ui.mediaUnavailable}));}));}
 function slide(i){panel.querySelectorAll('video').forEach(v=>v.pause());index=(i+current.media.length)%current.media.length;render();}
 function close(){panel.querySelectorAll('video').forEach(v=>v.pause());panel.hidden=true;panel.innerHTML='';document.body.classList.remove('panel-open');trigger?.focus();}
 document.addEventListener('keydown',e=>{if(e.key==='Escape')close();if(!panel.hidden&&e.key==='Tab'){const elements=[...panel.querySelectorAll('button:not([disabled]),video[controls]')],first=elements[0],last=elements.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 function show(i,focusSel){panel.querySelectorAll('video').forEach(v=>v.pause());seqIndex=i;const {id,di}=seq[i];current=trip.stops[id];index=0;panel.hidden=false;document.body.classList.add('panel-open');render();panel.scrollTop=0;(panel.querySelector(focusSel)||panel.querySelector('.close')).focus();onStop(id,di);}
 function open(id,di){trigger=document.activeElement;let i=seq.findIndex(s=>s.id===id&&(di===undefined||s.di===di));if(i<0)i=seq.findIndex(s=>s.id===id);if(i>=0)show(i,'.close');}
 function step(dir){const i=seqIndex+dir;if(i<0||i>=seq.length)return;show(i,dir>0&&i<seq.length-1?'.stop-next':dir<0&&i>0?'.stop-prev':'.close');}
 function setDay(i){dayButtons.forEach((b,k)=>{b.classList.toggle('active',k===i);b.setAttribute('aria-pressed',k===i);});$('#replay').innerHTML=`↻ <span>${ui.replay} ${esc(trip.days[i].label)}</span>`;}
 function setPlaying(p){$('#play').innerHTML=`${p?'Ⅱ':'▷'} <span>${p?ui.pause:ui.play}</span>`;}
 return {open,close,setDay,setPlaying};
}
export function makePins(trip,positions,open){const root=document.querySelector('#labels');const pins=[];
 trip.days.forEach((day,di)=>{const seen=new Set();day.stops.forEach((id,i)=>{if(!positions[id]||seen.has(id))return;seen.add(id);const stop=trip.stops[id],button=document.createElement('button');
  button.className=`map-pin `;
  button.innerHTML=`<span class="pin-flag">${icon(stopIcon[stop.kind])}</span><span class="pin-card"><span class="pin-day">${esc(day.label)}</span><strong>${esc(stop.name)}</strong><small>${esc(stop.zh)}</small></span>`;
  button.onclick=()=>open(id,di);root.appendChild(button);
  pins.push({id,day:di,show:di===0,element:button,position:positions[id].clone().add({x:0,y:3,z:0}),priority:2-i*.1,offsets:[[8,-12],[-165,-12],[8,-80],[8,60],[-165,60],[-165,-80]]});});});
 return pins;}
