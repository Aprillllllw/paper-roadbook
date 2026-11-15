export function normalizeScene(value={}) {
 const array=k=>Array.isArray(value[k])?value[k]:[];
 const lines=k=>array(k).filter(r=>Array.isArray(r.pts)&&r.pts.length>=2);
 return {...value, meta:value.meta||{},theme:value.theme||{},board:{a:62,b:46,...value.board},stops:value.stops||{},routes:Object.fromEntries(Object.entries(value.routes||{}).filter(([,p])=>Array.isArray(p)&&p.length>=2)),ranges:lines('ranges'),peaks:array('peaks'),lakes:array('lakes').map(l=>({rot:0,level:.85,rim:.4,...l})),rivers:lines('rivers'),pads:array('pads'),props:array('props'),clumps:array('clumps'),vehicle:value.vehicle||null,coast:value.coast||null};
}
