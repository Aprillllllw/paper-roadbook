import * as T from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import tripData from '../data/trip.json';
import sceneData from '../data/scene.json';
import {normalizeTrip} from '../trip.js';
import {setTheme,theme,glsl} from '../theme.js';
const trip=normalizeTrip(tripData);
configureScene(sceneData);setTheme(sceneData.theme);
document.documentElement.dataset.season=theme.season;document.documentElement.style.setProperty('--paper-background',theme.pink);
import { createUI, makePins } from '../ui/shell.js';
import { STOPS, ROUTES, SCENE, configureScene, curve, bridgeAt } from './layout.js';
import { buildLandscape } from './landscape.js';
import { placeProps, avatarTexture } from './props.js';
import { makeClouds } from './clouds.js';
import { makeSnow } from './snow.js';
import '../style.css';

T.ColorManagement.enabled = false; // 十六进制颜色原样输出，背景和纸色不被色彩管理改变

const loading = document.querySelector('#loading');
loading.textContent = trip.lang==='en'?'Unfolding the map…':'正在展开纸雕地图…';

function boot() {
  const mobile = matchMedia('(max-width:767px)').matches;
  const scene = new T.Scene();
  const renderer = new T.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' });
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = T.LinearSRGBColorSpace;
  renderer.toneMapping = T.NoToneMapping;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.VSMShadowMap;
  renderer.setPixelRatio(Math.min(devicePixelRatio, mobile ? 1.5 : 2));
  document.querySelector('#scene').appendChild(renderer.domElement);

  // 灯光：西南方向低角度暖光（右前方），给山体真实的明暗
  scene.add(new T.HemisphereLight(theme.shade40, theme.shade41, 2.1));
  const sun = new T.DirectionalLight(theme.shade42, 1.75);
  sun.position.set(70, 55, 60); sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  Object.assign(sun.shadow.camera, { left: -80, right: 80, top: 80, bottom: -80, near: 1, far: 300 });
  sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.05; sun.shadow.radius = 7; sun.shadow.blurSamples = 16;
  scene.add(sun);

  const land = buildLandscape(scene, { mobile });

  const H = (x, z) => land.sample(x, z);

  // ---------- 路线（红色虚线纸带，已开过的变实线） ----------
  const routes = {};
  const routeMat = (active) => new T.ShaderMaterial({
    uniforms: { progress: { value: 0 }, uActive: { value: active ? 1 : 0 } },
    vertexShader: 'attribute float along; attribute float side; varying float vA; varying float vS; void main(){ vA = along; vS = side; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
    fragmentShader: `uniform float progress; uniform float uActive; varying float vA; varying float vS;
      void main(){ float dash = step(.42, fract(vA / 2.2)); bool done = vA < progress;
        if (!done && dash < .5) discard;
        vec3 red = ${glsl(theme.pigment0)}, ink = ${glsl(theme.pigment1)};
        vec3 col = uActive > .5 ? red : ink; float a = uActive > .5 ? 1. : .9;
        if (abs(vS) > .72) col = mix(col, ${glsl(theme.pigment2)}, .8);
        gl_FragColor = vec4(col, a); }`,
    transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
  });
  for (const [day, pts] of Object.entries(ROUTES)) {
    const c = curve(pts), n = 500, sp = c.getSpacedPoints(n), v = [], al = [], sd = [], idx = [];
    const width = .32; let L = 0; const samples = [];
    for (let i = 0; i <= n; i++) {
      const p = sp[i], q = sp[Math.min(n, i + 1)], o = sp[Math.max(0, i - 1)];
      const dx = q.x - o.x, dz = q.z - o.z, len = Math.hypot(dx, dz) || 1, nx = -dz / len, nz = dx / len;
      if (i) L += Math.hypot(p.x - sp[i - 1].x, p.z - sp[i - 1].z);
      const roadY = (x, z) => { const b = bridgeAt(x,z,H); return H(x,z)*(1-b.weight)+b.height*b.weight+.12; };
      const y = roadY(p.x, p.z); samples.push(new T.Vector3(p.x, y, p.z));
      for (const s of [-1, 1]) { v.push(p.x + nx * width * s, roadY(p.x + nx * width * s, p.z + nz * width * s), p.z + nz * width * s); al.push(L); sd.push(s); }
      if (i < n) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 2, a + 1, a + 3); }
    }
    const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(v, 3));
    g.setAttribute('along', new T.Float32BufferAttribute(al, 1)); g.setAttribute('side', new T.Float32BufferAttribute(sd, 1)); g.setIndex(idx);
    const mat = routeMat(day === 'D1'); const mesh = new T.Mesh(g, mat); mesh.renderOrder = 3; scene.add(mesh);
    const path = new T.CatmullRomCurve3(samples);
    routes[day] = { mesh, material: mat, length: L, at: (t) => path.getPointAt(Math.min(1, Math.max(0, t))), tangent: (t) => path.getTangentAt(Math.min(.999, Math.max(.001, t))) };
  }

  const clouds = makeClouds(scene);
  const snow = theme.season==='winter'?makeSnow(scene, { mobile }):{toggle:()=>false,update:()=>{}};
  const props = placeProps(scene, land, routes, SCENE.vehicle?.sticker?avatarTexture(SCENE.vehicle.sticker):null);

  // ---------- 站点 ----------
  const positions = {};
  for (const id of Object.keys(trip.stops)) { const k = STOPS[id] || STOPS[trip.stops[id].point]; if (!k) { console.warn('no point for', id); continue; } positions[id] = new T.Vector3(k[0], H(k[0], k[1]) + .2, k[1]); }

  // ---------- 镜头：正交、斜俯视 ----------
  const camera = new T.OrthographicCamera(-1, 1, 1, -1, .1, 800);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = .07;
  controls.minPolarAngle = T.MathUtils.degToRad(28); controls.maxPolarAngle = T.MathUtils.degToRad(62);
  controls.minZoom = .8; controls.maxZoom = 6; controls.autoRotateSpeed = .3;
  const home = { target: new T.Vector3(mobile ? 0 : -14, 5, -2), dir: new T.Vector3(0, Math.sin(T.MathUtils.degToRad(45)), Math.cos(T.MathUtils.degToRad(45))).applyAxisAngle(new T.Vector3(0, 1, 0), T.MathUtils.degToRad(-6)), zoom: 1 };
  camera.position.copy(home.target).addScaledVector(home.dir, 300); controls.target.copy(home.target); camera.zoom = home.zoom;

  let flight = null, lastInteraction = performance.now();
  function fly(target, zoom, ms = 2000) {
    const dir = camera.position.clone().sub(controls.target).normalize();
    flight = { t0: performance.now(), ms, fromT: controls.target.clone(), toT: target.clone(), fromZ: camera.zoom, toZ: zoom, dir };
    lastInteraction = performance.now();
  }
  let playing = true, elapsed = 0, RUN = 16; const PAUSE = 4;
  let dayIdx = 0, curRoute = routes[trip.days[0]?.route];

  // 把某一天的路线（加上该天的站点）装进「左栏之外、底部信息条之上」的可用区域：返回镜头目标和缩放
  function frameFor(i) {
    const d = trip.days[i], r = routes[d.route], pts = [];
    if(!r)return {target:home.target.clone(),zoom:1};
    for (let k = 0; k <= 48; k++) pts.push(r.at(k / 48));
    for (const id of d.stops) if(positions[id])pts.push(positions[id]);
    const dir = camera.position.clone().sub(controls.target).normalize();
    const right = new T.Vector3().crossVectors(new T.Vector3(0, 1, 0), dir).normalize(), up = new T.Vector3().crossVectors(dir, right);
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9; const c3 = new T.Vector3();
    for (const p of pts) { const vx = p.dot(right), vy = p.dot(up); x0 = Math.min(x0, vx); x1 = Math.max(x1, vx); y0 = Math.min(y0, vy); y1 = Math.max(y1, vy); c3.add(p); }
    c3.multiplyScalar(1 / pts.length);
    const upp = (camera.top - camera.bottom) / innerHeight; // 缩放 1 时每像素的世界单位
    const A = mobile ? { l: 10, r: innerWidth - 10, t: 250, b: innerHeight - 150 } : { l: 340, r: innerWidth - 40, t: 50, b: innerHeight - 105 };
    const padX = mobile ? 110 : 260, padY = mobile ? 90 : 150;
    const zx = (A.r - A.l - padX) / Math.max(1, (x1 - x0) / upp), zy = (A.b - A.t - padY) / Math.max(1, (y1 - y0) / upp);
    const zoom = T.MathUtils.clamp(Math.min(zx, zy), 1, 3);
    const u = upp / zoom, ox = (A.l + A.r) / 2 - innerWidth / 2, oy = (A.t + A.b) / 2 + padY * .15 - innerHeight / 2;
    const target = new T.Vector3().addScaledVector(right, (x0 + x1) / 2 - ox * u).addScaledVector(up, (y0 + y1) / 2 + oy * u).addScaledVector(dir, c3.dot(dir));
    return { target, zoom };
  }
  const ui = createUI(trip, (id, di) => {
    if (di !== undefined && di !== dayIdx) selectDay(di, false);
    if(!positions[id])return; const p = positions[id].clone(); if (!mobile) p.x += 3.5; fly(p, 3.2);
  }, {
    selectDay(i) { if (i === dayIdx) { elapsed = 0; playing = true; ui.setPlaying(true); props.reset(); } else selectDay(i, true); if (i === dayIdx) { const f = frameFor(i); fly(f.target, f.zoom); } },
    replay() { elapsed = 0; playing = true; ui.setPlaying(true); props.reset(); },
    snow() { return snow.toggle(); },
    reset() { ui.close(); flight = { t0: performance.now(), ms: 2000, fromT: controls.target.clone(), toT: home.target.clone(), fromZ: camera.zoom, toZ: home.zoom, dir: home.dir.clone() }; },
    play() { playing = !playing; return playing; },
  });
  const pins = makePins(trip, positions, ui.open);
  function selectDay(i, doFly) {
    dayIdx = i; const d = trip.days[i]; curRoute = routes[d.route];
    for (const [k, r] of Object.entries(routes)) { const on = k === d.route; r.material.uniforms.uActive.value = on ? 1 : 0; r.material.uniforms.progress.value = 0; r.mesh.renderOrder = on ? 4 : 3; }
    RUN = Math.max(9, 4.5 * d.stops.length); elapsed = 0; playing = true; props.reset();
    for (const p of pins) p.show = p.day === i;
    ui.setDay(i); ui.setPlaying(true);
    if (doFly) { const f = frameFor(i); fly(f.target, f.zoom); }
  }
  if(trip.days.length)selectDay(0, false);
  // 纸带横幅 “Tianshan Mountains”（HTML，随 3D 点投影）
  const ribbon = document.createElement('div'); ribbon.id = 'ribbon';
  const ribbonText=SCENE.meta.name||'';
  const ribbonSpan=document.createElement('span');ribbonSpan.textContent=ribbonText;ribbon.appendChild(ribbonSpan);ribbon.hidden=!ribbonText;
  Object.assign(ribbon.style, { position: 'absolute', left: 0, top: 0, pointerEvents: 'none', zIndex: 2, willChange: 'transform' });
  const rs = document.createElement('style');
  rs.textContent = `#ribbon span{display:block;position:relative;font:italic 500 17px 'Playfair Display',serif;color:#603C2C;padding:7px 30px 8px;background:#FFF6F3;border:1px solid #8B5E4A88;border-radius:3px;box-shadow:0 5px 10px #603C2C33;letter-spacing:.02em;white-space:nowrap;transform:rotate(-4deg)}
#ribbon span:before,#ribbon span:after{content:'';position:absolute;top:7px;width:20px;height:100%;background:#F1DED6;border:1px solid #8B5E4A66;z-index:-1}
#ribbon span:before{left:-15px;clip-path:polygon(0 0,100% 0,100% 100%,0 100%,25% 50%)}#ribbon span:after{right:-15px;clip-path:polygon(0 0,100% 0,75% 50%,100% 100%,0 100%)}
@media(max-width:767px){#ribbon span{font-size:11px;padding:4px 18px}}`;
  document.head.appendChild(rs); document.querySelector('#labels').appendChild(ribbon);
  const ribbonAt = new T.Vector3(-4, 31, -33);
  controls.addEventListener('start', () => { flight = null; lastInteraction = performance.now(); controls.autoRotate = false; });
  controls.addEventListener('end', () => { lastInteraction = performance.now(); });

  function resize() {
    // 手机竖屏：保证整块底板（约 124 单位宽）左右都进画面，所以按宽度反推可视高度
    const aspect = innerWidth / innerHeight, viewH = mobile ? Math.max(170, 138 / aspect) : Math.max(112, 150 / aspect);
    camera.left = -viewH * aspect / 2; camera.right = viewH * aspect / 2; camera.top = viewH / 2; camera.bottom = -viewH / 2;
    camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight);
    // 手机：行程按钮紧跟在标题下面，不管标题折成几行
    if (mobile) { const hd = document.querySelector('#heading'), dd = document.querySelector('#days'); if (hd && dd) dd.style.top = Math.round(hd.getBoundingClientRect().bottom + 14) + 'px'; }
  }
  addEventListener('resize', resize); resize();

  if (import.meta.env.DEV) window.__colorCheck = () => { renderer.render(scene, camera); const gl = renderer.getContext(), px = new Uint8Array(4); gl.readPixels(0, gl.drawingBufferHeight - 1, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); return Array.from(px); };
  window.__view = { camera, controls, scene, seek: (sec) => { elapsed = sec; }, get day() { return dayIdx; } }; // seek：调试用，直接把车跳到第 sec 秒

  loading.classList.add('done');
  let last = performance.now(), time = 0;
  renderer.setAnimationLoop((now) => {
    const dt = Math.min((now - last) / 1000, .05); last = now; time += dt;
    if (playing) elapsed = (elapsed + dt) % (RUN + PAUSE);
    const prog = Math.min(1, elapsed / RUN);
    if(curRoute)curRoute.material.uniforms.progress.value = prog * curRoute.length;
    props.update(time, playing && prog < 1 ? dt : 0, prog, curRoute);
    land.water.uniforms.time.value = time; clouds.update(time, camera); snow.update(time, dt);
    if (flight) {
      const k = Math.min(1, (now - flight.t0) / flight.ms), e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      controls.target.lerpVectors(flight.fromT, flight.toT, e); camera.zoom = T.MathUtils.lerp(flight.fromZ, flight.toZ, e);
      camera.position.copy(controls.target).addScaledVector(flight.dir, 300); camera.updateProjectionMatrix();
      if (k === 1) flight = null;
    }
    controls.autoRotate = !flight && now - lastInteraction > 25000;
    controls.update();
    // 图钉位置
    camera.updateMatrixWorld(); const occupied = [];
    const daysBox = mobile ? document.querySelector('#days').getBoundingClientRect() : null, topLimit = mobile && daysBox ? daysBox.bottom + 4 : 12;
    for (const pin of pins) if (!pin.show) pin.element.style.visibility = 'hidden';
    for (const pin of pins.filter(p => p.show).sort((a, b) => b.priority - a.priority)) {
      const q = pin.position.clone().project(camera), x = (q.x * .5 + .5) * innerWidth, y = (-q.y * .5 + .5) * innerHeight;
      const w = pin.element.offsetWidth, h = pin.element.offsetHeight; let chosen = null;
      for (const [dx, dy] of pin.offsets) {
        const r = { x: x + dx, y: y + dy - h, w, h };
        if (r.x < 8 || r.x + w > innerWidth - 8 || r.y < topLimit || r.y + h > innerHeight - (mobile ? 150 : 92)) continue;
        if (!mobile && r.x < 330 && r.y < innerHeight - 100) continue;
        if (!occupied.some(o => r.x < o.x + o.w + 8 && r.x + r.w + 8 > o.x && r.y < o.y + o.h + 8 && r.y + r.h + 8 > o.y)) { chosen = r; break; }
      }
      pin.element.style.visibility = chosen ? 'visible' : 'hidden';
      if (chosen) { occupied.push(chosen); pin.element.style.transform = `translate(${chosen.x}px,${chosen.y}px)`; }
    }
    { const q = ribbonAt.clone().project(camera); let ry = (-q.y * .5 + .5) * innerHeight - ribbon.offsetHeight / 2;
      if (mobile && daysBox) ry = Math.max(ry, daysBox.bottom + 12); // 手机上不压住标题和行程按钮
      ribbon.style.transform = `translate(${(q.x * .5 + .5) * innerWidth - ribbon.offsetWidth / 2}px,${ry}px)`; }
    renderer.render(scene, camera);
  });
}
try { boot(); } catch (e) { console.error(e); loading.textContent = trip.lang==='en'?'Unable to open the map.':'地图暂时无法打开。'; }
