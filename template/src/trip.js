export function normalizeTrip(data={}) {
 const stops=Object.fromEntries(Object.entries(data.stops||{}).map(([id,s])=>[id,{name:id,zh:'',kind:'sight',info:{},extra:null,...s,info:s.info||{},media:Array.isArray(s.media)?s.media.filter(m=>m?.src):[]} ]));
 return {...data,title:data.title||'',subtitle:data.subtitle||'',lang:data.lang==='en'?'en':'zh',author:{name:'',line:'',...data.author},facts:data.facts||[],stops,days:(data.days||[]).map((d,i)=>({...d,id:d.id||`D${i+1}`,label:d.label||`Day ${i+1}`,title:d.title||'',stops:(d.stops||[]).filter(id=>stops[id])})),disclaimer:data.disclaimer||'方位真实，距离已压缩，比例不按真实。'};
}
