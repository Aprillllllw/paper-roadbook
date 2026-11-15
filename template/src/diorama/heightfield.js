// 程序化高度场：山脉脊线 + 锥形雪峰 + 湖盆 + 河道 + 公路走廊
import { GRID, RANGES, LAKES, RIVERS, ROUTES, BRIDGES, SCENE, PADS, curve } from './layout.js';

// ---- 噪声 ----
function h2(x, y) { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); }
function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = h2(xi, yi), b = h2(xi + 1, yi), c = h2(xi, yi + 1), d = h2(xi + 1, yi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function fbm(x, y, o = 4) { let s = 0, a = 0.5, f = 1; for (let i = 0; i < o; i++) { s += a * vnoise(x * f, y * f); f *= 2.03; a *= 0.5; } return s; }
function ridged(x, y, o = 4) { let s = 0, a = 0.5, f = 1; for (let i = 0; i < o; i++) { const n = 1 - Math.abs(vnoise(x * f, y * f) * 2 - 1); s += a * n * n; f *= 2.1; a *= 0.5; } return s / 0.94; }

// ---- 几何 ----
function sampleLine(pts, n) { // 折线 → 密集点
  const c = curve(pts); return c.getSpacedPoints(n).map(p => [p.x, p.z]);
}
function distToPoly(x, z, pts) {
  let best = 1e9;
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, az] = pts[i], [bx, bz] = pts[i + 1], dx = bx - ax, dz = bz - az;
    const t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)));
    const ex = ax + t * dx - x, ez = az + t * dz - z, d = ex * ex + ez * ez;
    if (d < best) best = d;
  }
  return Math.sqrt(best);
}
let rangeLines = RANGES.map(r => ({ ...r, line: sampleLine(r.pts, 30) }));
let riverLines = RIVERS.map(r => ({ ...r, line: sampleLine(r.pts, 50) }));
let roadLines = Object.values(ROUTES).map(p => sampleLine(p, 60));
export function lakeE(l, x, z) { // 椭圆归一化距离
  const c = Math.cos(l.rot), s = Math.sin(l.rot), dx = x - l.x, dz = z - l.z;
  const u = (dx * c + dz * s) / l.rx, v = (-dx * s + dz * c) / l.rz; return Math.hypot(u, v);
}
const smooth = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// ---- 高度函数 ----
function rawHeight(x, z) {
  // 河谷底：略起伏的雪原
  if (!RANGES.length && !LAKES.length && !RIVERS.length && !SCENE.coast && !BRIDGES.length) return .55;
  let h = 0.55 + 0.9 * (fbm(x * 0.06, z * 0.06) - 0.5) + 0.25 * fbm(x * 0.25, z * 0.25);

  // 只留缓坡山麓（雪峰是独立网格）
  let mount = 0;
  const sm = fbm(x * 0.05 + 7, z * 0.05 - 3, 2);
  for (const r of rangeLines) {
    const d = distToPoly(x, z, r.line), w = Math.exp(-((d / r.W) ** 2));
    mount = Math.max(mount, r.H * w * (0.6 + 0.8 * (sm - 0.3)));
  }
  h += mount;

  for(const b of BRIDGES){
    const scale=b.s??1,half=(b.opts?.span??3.2)*scale/2,c=Math.cos(b.rotY||0),sn=Math.sin(b.rotY||0),dx=x-b.x,dz=z-b.z;
    const u=Math.abs(dx*c-dz*sn),v=Math.abs(dx*sn+dz*c);
    const w=smooth(half*.58,half*.75,u)*(1-smooth(half+scale*.67,half+scale*2,u))*(1-smooth(scale*.63,scale*1.75,v));
    h=h*(1-w)+((b.y??.55)+scale*1.02-.25)*w;
  }

  // 湖：湖盆 + 环湖缓坡
  for (const l of LAKES) {
    const e = lakeE(l, x, z);
    if (e < 2.4) {
      h += l.rim * Math.exp(-(((e - 1.75) / 0.42) ** 2));
      const k = 1 - smooth(0.92, 1.25, e);
      h = h * (1 - k) + (l.level - 0.5) * k;
    }
  }

  // 河道：刻进地形
  for (const r of riverLines) {
    const d = distToPoly(x, z, r.line);
    if (d < r.w * 3) {
      const bank = smooth(r.w * 0.55, r.w * 2.6, d);
      const bed = Math.min(h, 0.35);
      h = bed + (h - bed) * bank;
    }
  }
  if(SCENE.coast){const c=SCENE.coast,axis=['N','S'].includes(c.side)?z:x,extent=['N','S'].includes(c.side)?SCENE.board.b:SCENE.board.a,sign=['N','W'].includes(c.side)?-1:1;const k=smooth(extent-(c.inset??12),extent,axis*sign);h=h*(1-k)-.3*k;}
  return h;
}
let padBase = PADS.map(p => ({ ...p, h: Math.max(.5, Math.min(1.1, rawHeight(p.x, p.z))) }));
export function heightAt(x, z) {
  let h = rawHeight(x, z);
  for (const p of padBase) {
    const d = Math.hypot(x - p.x, z - p.z);
    if (d < p.r * 1.5) { const k = 1 - smooth(p.r * 0.85, p.r * 1.4, d); h = h * (1 - k) + p.h * k; }
  }
  return h;
}

// ---- 烘焙成网格，之后用双线性插值采样 ----
export function bakeHeightfield() {
  rangeLines=RANGES.map(r=>({...r,line:sampleLine(r.pts,30)}));
  riverLines=RIVERS.map(r=>({...r,line:sampleLine(r.pts,50)}));
  roadLines=Object.values(ROUTES).map(p=>sampleLine(p,60));
  padBase=PADS.map(p=>({...p,h:Math.max(.5,Math.min(1.1,rawHeight(p.x,p.z)))}));
  const { x0, x1, z0, z1, step } = GRID;
  const nx = Math.round((x1 - x0) / step) + 1, nz = Math.round((z1 - z0) / step) + 1;
  const data = new Float32Array(nx * nz);
  for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) data[j * nx + i] = heightAt(x0 + i * step, z0 + j * step);
  function sample(x, z) {
    const fx = Math.max(0, Math.min(nx - 1.001, (x - x0) / step)), fz = Math.max(0, Math.min(nz - 1.001, (z - z0) / step));
    const i = Math.floor(fx), j = Math.floor(fz), u = fx - i, v = fz - j, k = j * nx + i;
    return (data[k] * (1 - u) + data[k + 1] * u) * (1 - v) + (data[k + nx] * (1 - u) + data[k + nx + 1] * u) * v;
  }
  return { nx, nz, data, sample, distToRoad: (x, z) => Math.min(...roadLines.map(l => distToPoly(x, z, l))),
    distToRiver: (x, z) => Math.min(...riverLines.map(r => distToPoly(x, z, r.line) - r.w)), riverLines };
}
export { fbm, vnoise };
