import {glsl} from '../theme.js';
import {theme} from '../theme.js';
// 纸雕地形 + 铜版排线 + 撕纸底板 + 湖 + 河 + 云杉
import * as T from 'three';
import { GRID, BOARD, LAKES, KEEP, CLUMPS, SCENE, edgeScale, boardRho } from './layout.js';
import { buildPeaks } from './peaks.js';
import { bakeHeightfield, lakeE } from './heightfield.js';

export const PAL = new Proxy({}, {get:(_,k)=>theme[k==='card'?'cream':k==='ink'?'brown':k]});

// 铜版排线 + 冷灰蓝阴影：注入 Lambert 材质（这样能接收真实阴影）
const HATCH_GLSL = () => /* glsl */`
float lum(vec3 c){ return dot(c, vec3(.299,.587,.114)); }
float hatchLines(vec2 p, float ang, float pitch, float w){
  vec2 d = vec2(cos(ang), sin(ang));
  float f = fract(dot(p, d) / pitch);
  return 1.0 - smoothstep(w, w + .18, abs(f - .5) * 2.0 - (1.0 - 2.0*w));
}
vec3 inkShade(vec3 base, vec3 lit, vec2 frag, float hatchGain, float cool){
  float s = clamp(lum(lit) / max(lum(base), .001), 0., 1.25);
  vec3 blue = mix(${glsl(theme.pigment3)}, mix(${glsl(theme.pigment4)}, ${glsl(theme.pigment5)}, .25), cool);   // 暖粉紫影 → 蓝灰影
  vec3 deep = mix(${glsl(theme.pigment6)}, mix(${glsl(theme.pigment7)}, ${glsl(theme.pigment8)}, .12), cool);
  vec3 ink = ${glsl(theme.pigment9)};
  vec3 col = mix(mix(deep, blue, smoothstep(.40,.70,s)) * mix(vec3(1.), base, mix(.55,.25,cool)), base, smoothstep(.62,1.02,s));
  col *= 1.0 + max(s - 1.0, 0.) * .22;
  float h1 = hatchLines(frag, .78, 4.2, .80) * (1. - smoothstep(.45,.88,s));
  float h2 = hatchLines(frag, -.78, 4.2, .82) * (1. - smoothstep(.30,.55,s));
  col = mix(col, ink, clamp((h1*.22 + h2*.20) * hatchGain, 0., .32));
  return col;
}`;

function paperNoise() {
  if(typeof document==='undefined'){const t=new T.DataTexture(new Uint8Array([245,240,235,255]),1,1);t.needsUpdate=true;return t;} // 纸纤维纹理（CanvasTexture）
  const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d');
  const img = g.createImageData(256, 256);
  for (let i = 0; i < img.data.length; i += 4) { const v = 236 + Math.random() * 19; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255; }
  g.putImageData(img, 0, 0); g.globalAlpha = .07; g.strokeStyle = theme.shade44;
  for (let i = 0; i < 260; i++) { g.beginPath(); const x = Math.random() * 256, y = Math.random() * 256, a = Math.random() * 6.3, l = 4 + Math.random() * 14; g.moveTo(x, y); g.quadraticCurveTo(x + Math.cos(a) * l * .5 + 3, y + Math.sin(a) * l * .5, x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke(); }
  const t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping; t.colorSpace = T.SRGBColorSpace; return t;
}

export function buildLandscape(scene, { mobile = false } = {}) {
  const hf = bakeHeightfield();
  const { x0, z0, step } = GRID, { nx, nz, data } = hf;
  const paper = paperNoise();

  // ---------- 地形网格 ----------
  const geo = new T.PlaneGeometry(GRID.x1 - x0, GRID.z1 - z0, nx - 1, nz - 1); geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position;
  for (let k = 0; k < pos.count; k++) { const x = pos.getX(k), z = pos.getZ(k); pos.setY(k, hf.sample(x, z)); }
  geo.computeVertexNormals();

  const terrainMat = new T.MeshLambertMaterial({ color: theme.shade38, flatShading: true });
  terrainMat.onBeforeCompile = (sh) => {
    sh.uniforms.uPaper = { value: paper };
    sh.uniforms.uBoard = { value: new T.Vector2(BOARD.a, BOARD.b) };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vW;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvW = (modelMatrix * vec4(transformed,1.)).xyz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
varying vec3 vW; uniform sampler2D uPaper;
float hs(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(hs(i),hs(i+vec2(1,0)),f.x), mix(hs(i+vec2(0,1)),hs(i+vec2(1,1)),f.x), f.y); }
${HATCH_GLSL()}`)
      .replace('#include <color_fragment>', `#include <color_fragment>
  vec3 nrm = normalize(cross(dFdx(vW), dFdy(vW)));
  float slope = 1.0 - nrm.y;
  float n1 = vn(vW.xz * .35), n2 = vn(vW.xz * 1.7);
  // 粉纸地面 #F7E3DE → #F3DAD3（带纤维），白色只留给高处雪帽
  vec3 valley = mix(${glsl(theme.groundA)}, ${glsl(theme.groundB)}, smoothstep(.25,.75,n1));
  valley = mix(valley, ${glsl(theme.groundShade)}, smoothstep(.55,.85,vn(vW.xz*.09+4.))*.5);
  valley = mix(valley, ${glsl(theme.groundA)}, smoothstep(.62,.8,vn(vW.xz*.22)) * .28 * (1.-smoothstep(1.2,2.2,vW.y))); // 田地淡米色笔触
  float snow = smoothstep(3.4, 6.2, vW.y + n2 * 1.4) * (1. - smoothstep(.55, .85, slope) * .55);
  vec3 rock = mix(${glsl(theme.pigment10)}, ${glsl(theme.pigment11)}, smoothstep(4.,12.,vW.y));
  vec3 base = mix(mix(valley, rock, smoothstep(1.4, 3.2, vW.y)), ${glsl(theme.pigment12)}, snow * .85 * ${theme.season==='winter'?'1.':'0.'});
  base = mix(base, ${glsl(theme.pigment13)}, smoothstep(.30,.62,slope) * .70);  // 陡坡/峡谷壁：偏暖的蓝灰岩面
  // 纸层：等高带的轻微色差 + 纸纤维
  float band = floor(vW.y / 1.15);
  base *= 1. - .028 * hs(vec2(band, 3.1));
  base *= mix(.94, 1.03, texture2D(uPaper, vW.xz * .045).r);
  base *= mix(.955, 1.03, texture2D(uPaper, vW.xz * .31).r);
  float fib = vn(vec2(vW.x * 2.2 + vW.z * .6, vW.z * 11.)) * vn(vec2(vW.x * 9., vW.z * 1.7 - vW.x * .5));
  base *= 1. - .045 * smoothstep(.35, .8, fib);
  diffuseColor.rgb = base;`)
      .replace('#include <opaque_fragment>', `
  vec3 litCol = inkShade(diffuseColor.rgb, outgoingLight, gl_FragCoord.xy, .3, smoothstep(.30,.62,slope) * .8 + smoothstep(6.,14.,vW.y) * .5);
  // 铜版等高线：每 1.15 单位一条咖啡色细线，平地上更淡
  float hb = vW.y / 1.9; float cl = abs(fract(hb - .5) - .5) / max(fwidth(hb), 1e-4);
  float contour = (1. - smoothstep(.6, 1.6, cl)) * smoothstep(.8, 1.6, vW.y) * mix(.04, .09, smoothstep(.15,.5, 1.-nrm.y));
  litCol = mix(litCol, ${glsl(theme.pigment14)}, contour);
  // 撕纸底板外的部分丢弃
  #ifdef BOARD_CLIP
  #endif
  gl_FragColor = vec4(litCol, 1.0);`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
  if (texture2D(uBoardMask, vec2((vW.x - ${GRID.x0.toFixed(1)}) / ${(GRID.x1-GRID.x0).toFixed(1)}, (vW.z - ${GRID.z0.toFixed(1)}) / ${(GRID.z1-GRID.z0).toFixed(1)})).r < .5) discard;`)
      .replace('uniform sampler2D uPaper;', 'uniform sampler2D uPaper; uniform sampler2D uBoardMask;');
    sh.uniforms.uBoardMask = { value: boardMaskTex };
  };

  // 底板遮罩纹理（撕纸轮廓）
  const MW = 1024, MH = Math.round(1024 * (GRID.z1-GRID.z0) / (GRID.x1-GRID.x0));
  const md = {data:new Uint8Array(MW*MH*4)};
  for (let j = 0; j < MH; j++) for (let i = 0; i < MW; i++) {
    const x = GRID.x0 + (i + .5) / MW * (GRID.x1-GRID.x0), z = GRID.z0 + (j + .5) / MH * (GRID.z1-GRID.z0); const v = boardRho(x, z) < 1 ? 255 : 0;
    const k = (j * MW + i) * 4; md.data[k] = md.data[k + 1] = md.data[k + 2] = v; md.data[k + 3] = 255;
  }
  const boardMaskTex = new T.DataTexture(md.data,MW,MH); boardMaskTex.needsUpdate=true; boardMaskTex.flipY = false; boardMaskTex.minFilter = T.LinearFilter;

  const terrain = new T.Mesh(geo, terrainMat); terrain.receiveShadow = true; terrain.castShadow = true; scene.add(terrain);

  // ---------- 撕纸底板侧面：顶层地形切面（四色纸层）+ 4 张叠放的撕边纸 ----------
  const edge = new T.Group(); scene.add(edge);
  const N = 900, ring = [];
  for (let i = 0; i < N; i++) { const th = -Math.PI + (i / N) * Math.PI * 2, s = edgeScale(th); ring.push([Math.cos(th) * BOARD.a * s, Math.sin(th) * BOARD.b * s]); }
  const FIBRE = (m) => { // 纸纤维 + 暖色（世界坐标噪声）
    const prev = m.onBeforeCompile;
    m.onBeforeCompile = (sh, r) => {
      if (prev) prev(sh, r);
      if (!sh.vertexShader.includes('varying vec3 vWf;')) sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWf;').replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWf = (modelMatrix * vec4(transformed,1.)).xyz;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
varying vec3 vWf;
float hf1(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
float vf1(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(hf1(i),hf1(i+vec2(1,0)),f.x), mix(hf1(i+vec2(0,1)),hf1(i+vec2(1,1)),f.x), f.y); }`)
        .replace('#include <alphatest_fragment>', `#include <alphatest_fragment>
  { float g = vf1(vec2(vWf.x * 3. + vWf.y * 7., vWf.z * 3. + vWf.y * 2.)) * .5 + vf1(vec2(vWf.x * 11., vWf.z * 11. + vWf.y * 9.)) * .5;
    float st = vf1(vec2(vWf.x * 1.3 + vWf.z * 1.1, vWf.y * 22.)) * vf1(vec2(vWf.x * 14., vWf.z * 3. + vWf.y * 3.));
    diffuseColor.rgb *= .955 + .075 * g; diffuseColor.rgb *= 1. - .05 * smoothstep(.3,.8,st); }`);
    };
    m.customProgramCacheKey = () => 'fibre' + (m.userData.k || '');
    m.emissive = new T.Color(m.userData.k === 'side3' ? theme.shade45 : theme.shade46);
    return m;
  };
  function skirt(scale, yTopFn, yBot) {
    const g = new T.BufferGeometry(), v = [], idx = [];
    ring.forEach(([x, z], i) => {
      const X = x * scale, Z = z * scale, yt = yTopFn(X, Z);
      v.push(X, yt, Z, X, yBot, Z);
      const a = i * 2, b = ((i + 1) % N) * 2; idx.push(a, a + 1, b, b, a + 1, b + 1);
    });
    g.setAttribute('position', new T.Float32BufferAttribute(v, 3)); g.setIndex(idx); g.computeVertexNormals();
    const m = new T.MeshLambertMaterial({ color: theme.shade15, side: T.DoubleSide });
    m.userData.k = 'skirt';
    m.onBeforeCompile = (sh) => {
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying float vY;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvY = position.y;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying float vY;').replace('#include <color_fragment>', `#include <color_fragment>
        float wob = (vf1(vWf.xz * .55) - .5) * .85 + (vf1(vWf.xz * 2.3 + 7.) - .5) * .25;
        float u = (vY + 1.5) / .62 + wob; float id = floor(u), fr = fract(u);
        float mm = mod(id, 4.);
        vec3 c0 = ${glsl(theme.pigment15)}, c1 = ${glsl(theme.pigment16)}, c2 = ${glsl(theme.pigment17)}, c3 = ${glsl(theme.pigment18)};
        vec3 lay = mm < 1. ? c0 : (mm < 2. ? c1 : (mm < 3. ? c2 : c3));
        lay = mix(lay, ${glsl(theme.pigment19)}, (1. - smoothstep(.0, .09, fr)) * .55);   // 纸层之间的暗缝
        lay = mix(lay, ${glsl(theme.pigment20)}, smoothstep(.88, 1., fr) * .25);            // 上一张纸的受光边
        diffuseColor.rgb = lay;`);
    };
    FIBRE(m);
    const mesh = new T.Mesh(g, m); mesh.castShadow = true; mesh.receiveShadow = true; edge.add(mesh); return mesh;
  }
  skirt(1.0, (x, z) => hf.sample(x * .995, z * .995), -1.5);

  // 4 张撕边纸：各自不同的毛边轮廓，向外错开 0.3–0.8 单位
  const h1 = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
  const vn1 = (t) => { const i = Math.floor(t), f = t - i, u = f * f * (3 - 2 * f); return h1(i) * (1 - u) + h1(i + 1) * u; };
  const SHEETS = [
    { off: .38, seed: 3,  top: theme.shade15, side: theme.shade47, y: -1.5 },
    { off: .62, seed: 11, top: theme.shade48, side: theme.shade49, y: -2.05 },
    { off: .46, seed: 23, top: theme.shade50, side: theme.shade51, y: -2.6 },
    { off: .78, seed: 37, top: theme.shade50, side: theme.shade25, y: -3.15 },
  ];
  SHEETS.forEach((sh, k) => {
    const shape = new T.Shape();
    for (let i = 0; i < N; i++) {
      const th = -Math.PI + (i / N) * Math.PI * 2, t = i / N, [x, z] = ring[i];
      const nx = x / BOARD.a, nz = z / BOARD.b, nl = Math.hypot(nx, nz) || 1;
      const jag = (vn1(t * 40 + sh.seed) - .5) * .5 + (vn1(t * 140 + sh.seed * 3) - .5) * .28 + (vn1(t * 380 + sh.seed) - .5) * .12;
      const o = sh.off + jag + (vn1(t * 9 + sh.seed) - .5) * .5;
      const X = x + nx / nl * o * 1.0, Z = z + nz / nl * o * .9;
      i ? shape.lineTo(X, -Z) : shape.moveTo(X, -Z);
    }
    const geo = new T.ExtrudeGeometry(shape, { depth: .5, bevelEnabled: false, curveSegments: 1 }); geo.rotateX(-Math.PI / 2); geo.translate(0, sh.y - .5, 0);
    const mt = FIBRE(new T.MeshLambertMaterial({ color: sh.top })); mt.userData.k = 'top' + k;
    const ms = FIBRE(new T.MeshLambertMaterial({ color: sh.side })); ms.userData.k = 'side' + k; if (k === 3) ms.emissive.set(theme.shade52);
    const mesh = new T.Mesh(geo, [mt, ms]); mesh.receiveShadow = true; mesh.castShadow = true; edge.add(mesh);
  });

  // ---------- 湖：一圈圈纸层 + 白色雪边 + 波纹 ----------
  const water = { uniforms: { time: { value: 0 } } };
  for (const l of LAKES) {
    const lake = new T.Group(); lake.position.set(l.x, l.level, l.z); lake.rotation.y = -l.rot; scene.add(lake);
    const shapeAt = (scale, wob) => { const s = new T.Shape(); for (let i = 0; i <= 96; i++) { const a = i / 96 * Math.PI * 2, r = scale * (1 + wob * Math.sin(a * 5 + l.x) * .5 + wob * Math.sin(a * 11 + l.z) * .3); const X = Math.cos(a) * l.rx * r, Z = Math.sin(a) * l.rz * r; i ? s.lineTo(X, -Z) : s.moveTo(X, -Z); } return s; };
    const layers = [[1.12, theme.season==='winter'?theme.snow:theme.pine, 0], [1.0, theme.shade53, .03], [.82, theme.shade5, .06], [.62, theme.shade54, .09], [.42, theme.shade55, .12]];
    for (const [sc, col, y] of layers) {
      const g = new T.ShapeGeometry(shapeAt(sc, .05), 1); g.rotateX(-Math.PI / 2);
      const m = new T.MeshLambertMaterial({ color: col });
      if (sc < 1.05) m.onBeforeCompile = (sh) => {
        sh.uniforms.time = water.uniforms.time;
        sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec2 vP;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvP = position.xz;');
        sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec2 vP; uniform float time;').replace('#include <color_fragment>', `#include <color_fragment>
          float w = sin(vP.x * 2.2 + sin(vP.y * 1.3) * 1.5 + time * .8) * .5 + .5;
          float line = smoothstep(.93, .985, w) * (.5 + .5 * sin(vP.y * 9. + time));
          diffuseColor.rgb = mix(diffuseColor.rgb, vec3(1.), line * .45);`);
      };
      const mesh = new T.Mesh(g, m); mesh.position.y = y; mesh.receiveShadow = true; lake.add(mesh);
    }
  }

  if(SCENE.coast){
    const c=SCENE.coast,ns=['N','S'].includes(c.side),extent=ns?BOARD.b:BOARD.a,sign=['N','W'].includes(c.side)?-1:1;
    const vertices=[],indices=[],step=1;
    for(let z=-BOARD.b;z<BOARD.b;z+=step)for(let x=-BOARD.a;x<BOARD.a;x+=step){
      const corners=[[x,z],[x+step,z],[x+step,z+step],[x,z+step]];
      if(corners.some(([X,Z])=>boardRho(X,Z)>.985 || (ns?Z:X)*sign<extent-(c.inset??12)*.65))continue;
      const k=vertices.length/3;corners.forEach(([X,Z])=>vertices.push(X,.12,Z));indices.push(k,k+2,k+1,k,k+3,k+2);
    }
    const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(vertices,3));geo.setIndex(indices);geo.computeVertexNormals();
    const ocean=new T.Mesh(geo,new T.MeshLambertMaterial({color:theme.blue}));ocean.receiveShadow=true;scene.add(ocean);
  }

  // ---------- 河：蓝色纸带（浅色中线 + 墨线描边） ----------
  const riverMat = new T.ShaderMaterial({
    uniforms: { time: water.uniforms.time },
    vertexShader: `attribute float side; varying float vS; varying float vL; attribute float along; void main(){ vS = side; vL = along; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }`,
    // 冬季冰河：和赛里木湖同一套分层纸色（中心深蓝活水 → 冷灰蓝 → 浅蓝 → 岸边冰架 → 白雪岸），冰架宽度沿河随机变化
    fragmentShader: `varying float vS; varying float vL; uniform float time;
      float h1(float x){ return fract(sin(x*127.1)*43758.5453); }
      float n1(float x){ float i=floor(x), f=fract(x); f=f*f*(3.-2.*f); return mix(h1(i), h1(i+1.), f); }
      void main(){ float a = abs(vS);
      float ice = .50 + .22 * n1(vL * .45 + (vS > 0. ? 7.3 : 1.1)) + .08 * n1(vL * 2.1);   // 冰架从这里开始（越小冰越宽）
      vec3 c0 = ${glsl(theme.pigment21)}, c1 = ${glsl(theme.pigment22)}, c2 = ${glsl(theme.pigment4)}, c3 = ${glsl(theme.pigment23)};
      vec3 col = a < ice*.35 ? c0 : (a < ice*.62 ? c1 : (a < ice*.85 ? c2 : c3));            // 与湖一致的分层色带
      float w = sin(vL * 1.6 + sin(vS * 3.) * 1.2 - time * .9) * .5 + .5;
      col = mix(col, vec3(1.), smoothstep(.93, .985, w) * (1. - smoothstep(ice*.7, ice, a)) * .45); // 与湖同款白色细波纹
      vec3 iceC = mix(${glsl(theme.pigment24)}, ${glsl(theme.pigment25)}, n1(vL*3.7 + vS*5.));
      col = mix(col, iceC, smoothstep(ice, ice + .03, a)*${theme.season==='winter'?'1.':'0.'});                                     // 冰架
      col = mix(col, ${glsl(theme.season==='winter'?theme.snow:theme.pine)}, smoothstep(.90, .93, a));                              // 白雪岸
      col = mix(col, ${glsl(theme.pigment9)}, smoothstep(.975, .995, a) * .28);                    // 细墨线
      gl_FragColor = vec4(col, 1.); }`,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
  });
  for (const r of hf.riverLines) {
    const c = new T.CatmullRomCurve3(r.line.map(([x, z]) => new T.Vector3(x, 0, z)));
    const n = 220, pts = c.getSpacedPoints(n), v = [], sideA = [], alongA = [], idx = [], inside = [];
    let L = 0;
    for (let i = 0; i <= n; i++) {
      const p = pts[i], q = pts[Math.min(n, i + 1)], o = pts[Math.max(0, i - 1)];
      const dx = q.x - o.x, dz = q.z - o.z, len = Math.hypot(dx, dz) || 1, nxv = -dz / len, nzv = dx / len;
      const w = r.w * (0.75 + 0.25 * Math.min(1, i / 40)) * (0.9 + 0.2 * Math.sin(i * .21));
      if (i) L += p.distanceTo(pts[i - 1]);
      for (const s of [-1, 1]) {
        const X = p.x + nxv * w * s, Z = p.z + nzv * w * s;
        v.push(X, hf.sample(X, Z) + .07, Z); inside.push(boardRho(X, Z) < .985);
        sideA.push(s); alongA.push(L);
      }
      if (i) { const a = (i - 1) * 2; if (inside[a] && inside[a + 1] && inside[a + 2] && inside[a + 3]) idx.push(a, a + 1, a + 2, a + 2, a + 1, a + 3); }
    }
    const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(v, 3));
    g.setAttribute('side', new T.Float32BufferAttribute(sideA, 1)); g.setAttribute('along', new T.Float32BufferAttribute(alongA, 1)); g.setIndex(idx);
    const m = new T.Mesh(g, riverMat); m.renderOrder = 2; scene.add(m);
  }

  // ---------- 云杉：200–300 棵，3–4 倍高，小丛分布 ----------
  const tree = spruceGeometry();
  const treeMat = new T.MeshLambertMaterial({ vertexColors: true, flatShading: true });
  const spots = [];
  let seed = 4242; const rnd = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
  for (const {x:cx,z:cz,n=1,r:rad=1} of CLUMPS.filter(c=>c.type==='spruce')) {
    let got = 0;
    for (let t = 0; t < n * 30 && got < n; t++) {
      const a = rnd() * 6.283, d = Math.sqrt(rnd()) * rad, x = cx + Math.cos(a) * d, z = cz + Math.sin(a) * d;
      if (boardRho(x, z) > .94) continue;
      const h = hf.sample(x, z);
      if (h < .3 || h > 6.5) continue;
      if (LAKES.some(l => lakeE(l, x, z) < 1.2)) continue;
      if (KEEP.some(([kx, kz, kr]) => Math.hypot(x - kx, z - kz) < kr)) continue;
      if (hf.distToRiver(x, z) < 1.6 || hf.distToRoad(x, z) < 2.4) continue;
      if (spots.some(p => Math.hypot(p.x - x, p.z - z) < 1.9)) continue;
      const gx = hf.sample(x + .4, z) - hf.sample(x - .4, z), gz = hf.sample(x, z + .4) - hf.sample(x, z - .4);
      if (Math.hypot(gx, gz) > 1.6) continue;
      spots.push({ x, z, h, s: 2.5 + rnd() * .9 }); got++;
    }
  }
  const inst = new T.InstancedMesh(tree, treeMat, spots.length);
  inst.castShadow = true; inst.receiveShadow = true;
  const M = new T.Matrix4(), Q = new T.Quaternion(), S = new T.Vector3(), P = new T.Vector3(), up = new T.Vector3(0, 1, 0);
  spots.forEach((p, i) => {
    P.set(p.x, p.h - .05, p.z); Q.setFromAxisAngle(up, rnd() * 6.28); S.set(p.s * .95, p.s * (1 + rnd() * .2), p.s * .95);
    inst.setMatrixAt(i, M.compose(P, Q, S));
  });
  scene.add(inst);
  const peaks = buildPeaks(scene, hf.sample);

  return { hf, water, terrain, sample: hf.sample, trees: inst, peaks, treeCount: spots.length };
}

// 三层雪顶云杉（顶点色：松绿 + 白雪），高约 1.6
export function spruceGeometry() {
  const parts = [];
  const green = new T.Color(theme.shade35), dark = new T.Color(theme.shade6), mid = new T.Color(theme.shade7), snowC = new T.Color(theme.shade56), snowS = new T.Color(theme.shade8), trunk = new T.Color(theme.shade57);
  const add = (g, col) => { const c = []; const p = g.attributes.position; for (let i = 0; i < p.count; i++) c.push(col.r, col.g, col.b); g.setAttribute('color', new T.Float32BufferAttribute(c, 3)); parts.push(g.toNonIndexed ? g.toNonIndexed() : g); };
  const t = CylinderLike(.06, .08, .3); add(t, trunk);
  // 层叠的雪顶枝层：每层一个宽锥 + 偏小的雪帽（盖住上半、露出下沿的霜绿）
  const tiers = [[.60, .52, .20], [.52, .48, .44], [.44, .46, .68], [.35, .42, .92], [.25, .38, 1.16], [.14, .30, 1.42]];
  tiers.forEach(([r, h, y], i) => {
    const g = new T.ConeGeometry(r, h, 7, 1); g.rotateY(i * .5); g.translate(0, y + h / 2, 0); add(g, i % 3 === 0 ? green : (i % 3 === 1 ? dark : mid));
    const s = new T.ConeGeometry(r * .80, h * .60, 7, 1); s.rotateY(i * .5); s.translate(0, y + h * .70, 0); if(theme.season==='winter')add(s, i % 2 ? snowC : snowS);
  });
  const merged = mergeGeos(parts); merged.computeVertexNormals(); return merged;
}
function CylinderLike(a, b, h) { const g = new T.CylinderGeometry(a, b, h, 5); g.translate(0, h / 2, 0); return g; }
function mergeGeos(list) {
  const pos = [], col = [];
  for (const g of list) { const a = g.index ? g.toNonIndexed() : g; pos.push(...a.attributes.position.array); col.push(...a.attributes.color.array); }
  const out = new T.BufferGeometry(); out.setAttribute('position', new T.Float32BufferAttribute(pos, 3)); out.setAttribute('color', new T.Float32BufferAttribute(col, 3)); return out;
}


