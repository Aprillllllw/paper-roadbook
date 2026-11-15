import {theme,glsl} from '../theme.js';
// v8 自然纸雕雪山：脊线噪声 + 宽底山体 + 多山肩/副峰 + 铜版排线 + 雪线勾边
// 一整张高度场网格（只保留山体有高度的三角形），平面/平滑法线混合着色；
// 受光面暖象牙白 #FFF7F0（脊线带一点蜜桃光），背光面 #8FA8C7 向粉紫 #C9AFB6 偏 25%，深影 #7F93B3
import * as T from 'three';
import { MASSIF, GRID, boardRho } from './layout.js';
import { vnoise } from './heightfield.js';

const HS = .80;     // 高度比例
const RAD = 1.62;   // 影响半径 = R * RAD（宽底）
const STEP = .62;

function ridged(x, y, o = 4) { let s = 0, a = .5, f = 1, w = 0; for (let i = 0; i < o; i++) { const n = 1 - Math.abs(vnoise(x * f + i * 17.3, y * f - i * 9.1) * 2 - 1); s += a * n * n; w += a; f *= 2.13; a *= .5; } return s / w; }
const sstep = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// 山体高度（相对于地形）
export function peakField(x, z) {
  // 域扭曲：让山脚和山脊不呈同心圆
  const wx = x + (vnoise(x * .06 + 3, z * .06) - .5) * 9, wz = z + (vnoise(x * .06, z * .06 + 8) - .5) * 9;
  let best = 0;
  for (const m of MASSIF) {
    const R = m.R * RAD, dx = wx - m.x, dz = (wz - m.z) * 1.12;
    if (Math.abs(dx) > R || Math.abs(dz) > R) continue;
    const q = Math.hypot(dx, dz) / R; if (q >= 1) continue;
    const env = 1 - q, ang = Math.atan2(dz, dx), sd = m.x * .37 + m.z * .21;
    // 放射状山脊（arête）：沿角度采样脊线噪声，近顶点少脊、远处分叉
    const kr = 1.05 + 1.5 * q;
    const arete = ridged(Math.cos(ang) * kr + sd, Math.sin(ang) * kr - sd, 2);
    const rid = ridged(x * .085, z * .085, 2);
    const crest = Math.pow(env, 2.1) * .52;                       // 尖锐山顶
    const body = Math.pow(env, 1.15) * (.10 + .50 * arete + .20 * rid);   // 宽缓山肩 + 脊线 + 副峰
    const h = m.H * HS * (crest + body);
    if (h > best) best = h;
  }
  // 板边渐隐，避免山体被撕纸边缘垂直切开
  const rho = boardRho(x, z);
  return best * (1 - sstep(.80, .965, rho));
}

export function buildPeaks(scene, sample) {
  const { x0, x1, z0, z1 } = GRID;
  const nx = Math.round((x1 - x0) / STEP) + 1, nz = Math.round((z1 - z0) / STEP) + 1;
  const H = new Float32Array(nx * nz);
  for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) H[j * nx + i] = peakField(x0 + i * STEP, z0 + j * STEP);

  // 只保留有山的顶点（含一圈余量），重新编号
  const keep = new Uint8Array(nx * nz);
  for (let j = 0; j < nz - 1; j++) for (let i = 0; i < nx - 1; i++) {
    const k = j * nx + i; if (H[k] > .02 || H[k + 1] > .02 || H[k + nx] > .02 || H[k + nx + 1] > .02) { keep[k] = keep[k + 1] = keep[k + nx] = keep[k + nx + 1] = 1; }
  }
  const map = new Int32Array(nx * nz).fill(-1); const pos = [], ah = []; let cnt = 0;
  for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) {
    const k = j * nx + i; if (!keep[k]) continue;
    const x = x0 + i * STEP, z = z0 + j * STEP, h = H[k];
    map[k] = cnt++; pos.push(x, sample(x, z) + h + (h > .02 ? .02 : -.2), z); ah.push(h);
  }
  const idx = [];
  for (let j = 0; j < nz - 1; j++) for (let i = 0; i < nx - 1; i++) {
    const k = j * nx + i, a = map[k], b = map[k + 1], c = map[k + nx], d = map[k + nx + 1];
    if (a < 0 || b < 0 || c < 0 || d < 0) continue;
    if (H[k] <= .02 && H[k + 1] <= .02 && H[k + nx] <= .02 && H[k + nx + 1] <= .02) continue;
    // 对角线随位置交替，避免整片条纹感
    if ((i + j) % 2) idx.push(a, c, b, b, c, d); else idx.push(a, c, d, a, d, b);
  }
  const geo = new T.BufferGeometry();
  geo.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
  geo.setAttribute('aH', new T.Float32BufferAttribute(ah, 1));
  geo.setIndex(idx); geo.computeVertexNormals();

  const mat = new T.ShaderMaterial({
    uniforms: { uSun: { value: new T.Vector3(.70, .55, .60).normalize() } },
    vertexShader: `attribute float aH; varying float vH; varying vec3 vW; varying vec3 vN;
      void main(){ vH = aH; vN = normal; vec4 w = modelMatrix * vec4(position,1.); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `varying float vH; varying vec3 vW; varying vec3 vN; uniform vec3 uSun;
      float hs(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
      float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(hs(i),hs(i+vec2(1,0)),f.x), mix(hs(i+vec2(0,1)),hs(i+vec2(1,1)),f.x), f.y); }
      float lines(float c, float w){ float f = abs(fract(c) - .5) * 2.; return 1. - smoothstep(w, w + .35, f); }
      void main(){
        if (vH < .05) discard;
        vec3 nf = normalize(cross(dFdx(vW), dFdy(vW)));
        vec3 ns = normalize(vN);
        vec3 n = normalize(mix(nf, ns, .74));
        float L = dot(n, uSun);
        float curv = length(fwidth(ns)) * 6.;                    // 曲率：脊线处大
        float shade = 1. - smoothstep(.20, .58, L);              // 0 受光 / 1 背光
        // —— 色板 ——
        vec3 ivory = ${glsl(theme.season==='winter'?theme.snow:theme.pine)};                       // #FFF7F0
        vec3 peach = ${glsl(theme.cream)};
        vec3 blue  = mix(${glsl(theme.pigment4)}, ${glsl(theme.pigment26)}, .25);   // #8FA8C7 → 粉紫 25%
        vec3 deep  = ${glsl(theme.pigment7)};                        // #7F93B3
        vec3 pinkA = ${glsl(theme.pigment27)};                        // 远景暖粉
        vec3 lit = mix(ivory, peach, smoothstep(.45, 1.1, curv) * .55 + smoothstep(.55,.95,L) * .12);
        vec3 sh  = mix(deep, blue, smoothstep(-.15, .42, L));
        // 雪线：陡面/低处露出蓝灰岩面
        float nz = vn(vW.xz * .55) * .6 + vn(vW.xz * 1.7 + 4.) * .4;
        float steep = 1. - smoothstep(.22, .55, n.y);
        float snowLine = 7. + 6. * nz;
        float rock = clamp(steep * 1.1 - smoothstep(snowLine, snowLine + 10., vW.y) * .6 + (nz - .5) * .45, 0., 1.);
        vec3 rockCol = mix(${glsl(theme.pigment28)}, ${glsl(theme.pigment29)}, .3);
        vec3 baseLit = mix(lit, mix(lit, rockCol, .42), smoothstep(.45,.62,rock));
        vec3 col = mix(baseLit, sh, shade);
        // 雪线勾边：白与岩的交界，咖啡/墨棕细线
        float edge = 1. - smoothstep(.0, .07, abs(rock - .53));
        col = mix(col, ${glsl(theme.pigment9)}, edge * .30 * (.5 + .5*nz));
        // 铜版沿坡排线（背光面 + 岩面），线向坡下
        vec2 dir = normalize(n.xz + vec2(1e-4)); vec2 perp = vec2(-dir.y, dir.x);
        float across = dot(vW.xz, perp) * 2.35 + vn(vW.xz * .9) * 1.6 + vW.y * .05;
        float l1 = lines(across, .60) * (.45 + .55 * vn(vec2(across * .35, vW.y * .35)));
        float across2 = dot(vW.xz, perp) * 1.17 + vW.y * .12;
        float l2 = lines(across2 + .25, .74) * smoothstep(.55, .9, shade);
        float hatch = clamp(l1 * (shade * .26 + rock * .08 + .03) + l2 * .12, 0., .34);
        col = mix(col, ${glsl(theme.pigment9)}, hatch);
        // 山脊暖线（受光面脊线）
        col = mix(col, ${glsl(theme.pigment30)}, smoothstep(.9, 2.2, curv) * (1. - shade) * .26);
        // 空气透视：远景（z 越负）更浅更粉
        float far = smoothstep(-16., -50., vW.z);
        col = mix(col, pinkA, far * .26);
        // 近景拉开对比
        col *= 1. + smoothstep(-12., 8., vW.z) * .04 * (1. - 2.*shade);
        // 山脚融入粉纸地面
        col = mix(col, ${glsl(theme.pigment31)}, (1. - smoothstep(.05, 1.8, vH)) * .6);
        gl_FragColor = vec4(col, 1.);
      }`,
    extensions: { derivatives: true },
  });
  const mesh = new T.Mesh(geo, mat); mesh.castShadow = true; mesh.receiveShadow = false; scene.add(mesh);
  return { mesh, edges: null };
}
