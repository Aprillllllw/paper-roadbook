import {T,C,finish,rod,smoke,cut,ellipse} from './paperkit.js';
const V2=p=>new T.Vector2(...p);
const mat=color=>new T.MeshLambertMaterial({color});
function feltTexture() {
  if(typeof document==='undefined')return null;
  const c = document.createElement('canvas'); c.width = 1024; c.height = 256;
  const x = c.getContext('2d');
  x.fillStyle = C.shade23; x.fillRect(0, 0, 1024, 256);
  for (let i = 0; i < 4000; i++) { x.fillStyle = `rgba(150,110,90,${Math.random() * 0.05})`; x.fillRect(Math.random() * 1024, Math.random() * 256, 2, 2); }
  x.fillStyle = C.shade24; x.fillRect(0, 150, 1024, 64);
  x.fillStyle = C.shade25; x.fillRect(0, 144, 1024, 6); x.fillRect(0, 214, 1024, 6);
  x.strokeStyle = C.shade26; x.lineWidth = 5;
  for (let i = 0; i < 16; i++) {
    const cx = 32 + i * 64, cy = 186;
    x.beginPath(); x.moveTo(cx, cy + 20); x.lineTo(cx, cy - 2);
    x.arc(cx - 11, cy - 2, 11, 0, Math.PI * 1.5, true); x.moveTo(cx, cy - 2); x.arc(cx + 11, cy - 2, 11, Math.PI, Math.PI * 1.5 + Math.PI, false); x.stroke();
  }
  x.strokeStyle = 'rgba(96,60,44,.35)'; x.lineWidth = 2;
  for (let i = 0; i < 64; i++) { x.beginPath(); x.moveTo(i * 16, 0); x.lineTo(i * 16 + 8, 140); x.stroke(); }
  const t = new T.CanvasTexture(c); t.wrapS = T.RepeatWrapping; t.anisotropy = 8; return t;
}
function roofTexture() {
  if(typeof document==='undefined')return null;
  const c = document.createElement('canvas'); c.width = 1024; c.height = 256;
  const x = c.getContext('2d');
  x.fillStyle = C.shade27; x.fillRect(0, 0, 1024, 256);
  for (let i = 0; i < 3000; i++) { x.fillStyle = `rgba(120,90,70,${Math.random() * 0.06})`; x.fillRect(Math.random() * 1024, Math.random() * 256, 2, 2); }
  x.strokeStyle = C.shade28; x.lineWidth = 4;
  for (let i = 0; i < 24; i++) { x.beginPath(); x.moveTo(i * 42.7, 0); x.lineTo(i * 42.7, 256); x.stroke(); }
  const t = new T.CanvasTexture(c); t.wrapS = T.RepeatWrapping; t.anisotropy = 8; return t;
}

// ================= 毡房 =================
export function makeYurt() {
  const g = new T.Group();
  const wall = new T.Mesh(new T.CylinderGeometry(0.5, 0.5, 0.34, 48, 1, true), new T.MeshLambertMaterial({ map: feltTexture(), side: T.DoubleSide }));
  wall.position.y = 0.17; wall.castShadow = wall.receiveShadow = true; g.add(wall);
  const roofProf = [[0.53, 0.32], [0.45, 0.4], [0.33, 0.49], [0.2, 0.56], [0.1, 0.6], [0.0, 0.61]].map(V2);
  const roof = new T.Mesh(new T.LatheGeometry(roofProf, 48), new T.MeshLambertMaterial({ map: roofTexture(), side: T.DoubleSide }));
  roof.castShadow = true; g.add(roof);
  // 屋顶积雪：波浪下沿
  const snowGeo = new T.LatheGeometry([[0.44, 0.415], [0.33, 0.505], [0.2, 0.575], [0.1, 0.615], [0, 0.625]].map(V2), 64);
  const p = snowGeo.attributes.position;
  for (let i = 0; i < p.count; i++) if (p.getY(i) < 0.42) { const a = Math.atan2(p.getZ(i), p.getX(i)); p.setY(i, p.getY(i) - 0.03 - Math.abs(Math.sin(a * 9)) * 0.05); }
  snowGeo.computeVertexNormals();
  const snow = new T.Mesh(snowGeo, new T.MeshLambertMaterial({ color: C.snow, side: T.DoubleSide })); snow.castShadow = true; if(C.season==='winter')g.add(snow);
  // 天窗圈 + 绑绳
  const crown = new T.Mesh(new T.TorusGeometry(0.1, 0.018, 8, 28), mat(C.brown)); crown.rotation.x = Math.PI / 2; crown.position.y = 0.63; g.add(crown);
  for (const y of [0.1, 0.27]) { const band = new T.Mesh(new T.TorusGeometry(0.505, 0.008, 6, 64), mat(C.coffee)); band.rotation.x = Math.PI / 2; band.position.y = y; g.add(band); }
  // 门：红色木门 + 门框 + 小台阶
  const door = new T.Group(); door.position.set(0, 0, 0.5); g.add(door);
  cut(door, [[-0.11, 0], [0.11, 0], [0.11, 0.27], [-0.11, 0.27]], 0.04, C.coffee, { smooth: false, bevel: 0.005 });
  cut(door, [[-0.085, 0], [0.085, 0], [0.085, 0.245], [-0.085, 0.245]], 0.05, C.red, { smooth: false, bevel: 0.005 });
  cut(door, [[-0.05, 0.08], [0, 0.18], [0.05, 0.08], [0, 0.11]], 0.055, C.shade29, { smooth: false, bevel: 0.003 });
  cut(door, [[-0.14, 0], [0.14, 0], [0.13, -0.03], [-0.13, -0.03]], 0.12, C.brown, { smooth: false, bevel: 0.005, pos: [0, 0.03, 0.04] });
  // 墙脚积雪堆
  for (let i = 0; C.season==='winter' && i < 9; i++) { const a = i * 0.7 + 0.9; ellipse(g, 0.09, 0.035, 0.07, [Math.cos(a) * 0.52, 0.015, Math.sin(a) * 0.52], C.snow).rotation.y = -a; }
  const puff = smoke(g, 0, 0.66, 0);
  return finish(g, (t) => puff(t));
}

// ================= 果子沟斜拉桥 =================
export function makeBridge({span=3.2}={}) {
  const g = new T.Group();
  const L = span, deckY = 0.62, cream = C.shade26;
  // 桥面：微弯的箱梁 + 护栏 + 路面红线
  cut(g, [[-L / 2, deckY], [L / 2, deckY], [L / 2, deckY - 0.08], [-L / 2, deckY - 0.08]], 0.26, cream, { smooth: false, bevel: 0.01 }).rotation.y = 0;
  cut(g, [[-L / 2, deckY + 0.002], [L / 2, deckY + 0.002], [L / 2, deckY - 0.004], [-L / 2, deckY - 0.004]], 0.2, C.shade30, { smooth: false, bevel: 0 }).position.y = 0.006;
  for (const s of [-1, 1]) {
    for (let i = 0; i <= 40; i++) rod(g, [-L / 2 + i * L / 40, deckY, s * 0.125], [-L / 2 + i * L / 40, deckY + 0.05, s * 0.125], 0.008, C.coffee).userData.outlined = true;
    rod(g, [-L / 2, deckY + 0.05, s * 0.125], [L / 2, deckY + 0.05, s * 0.125], 0.014, C.coffee);
    // 雪沿
    if(C.season==='winter')cut(g, [[-L / 2, 0], [L / 2, 0], [L / 2, 0.015], [-L / 2, 0.015]], 0.03, C.snow, { smooth: false, bevel: 0.004, pos: [0, deckY, s * 0.1] });
  }
  // 两座 H 形塔 + 横梁（塔高出桥面很多，拉索才成扇形）
  const TOP = 1.75;
  for (const px of [-0.85, 0.85]) {
    for (const s of [-1, 1]) cut(g, [[-0.045, -0.4], [0.045, -0.4], [0.03, TOP], [-0.03, TOP]], 0.05, cream, { smooth: false, bevel: 0.008, pos: [px, 0, s * 0.16] });
    for (const y of [0.45, 1.25]) cut(g, [[-0.035, 0], [0.035, 0], [0.035, 0.05], [-0.035, 0.05]], 0.34, cream, { smooth: false, bevel: 0.006, pos: [px, y, 0] });
    cut(g, [[-0.04, TOP - 0.04], [0.04, TOP - 0.04], [0.04, TOP + 0.03], [-0.04, TOP + 0.03]], 0.37, C.red, { smooth: false, bevel: 0.006, pos: [px, 0, 0] });
    for (const s of [-1, 1]) for (let k = 1; k <= 8; k++) for (const dir of [-1, 1]) {
      rod(g, [px, TOP - 0.06 - k * 0.045, s * 0.16], [px + dir * k * 0.095, deckY + 0.02, s * 0.12], 0.006, C.shade31).userData.outlined = true;
    }
    cut(g, [[-0.06, -0.4], [0.06, -0.4], [0.05, 0.54], [-0.05, 0.54]], 0.22, C.shade27, { smooth: false, bevel: 0.008, pos: [px, 0, 0] });
  }
  // 引桥墩
  for (const px of [-1.4, 1.4]) cut(g, [[-0.04, -0.2], [0.04, -0.2], [0.035, 0.54], [-0.035, 0.54]], 0.16, C.shade27, { smooth: false, bevel: 0.006, pos: [px, 0, 0] });
  g.position.y = 0.4;
  const wrap = new T.Group(); wrap.add(g);
  return finish(wrap);
}
