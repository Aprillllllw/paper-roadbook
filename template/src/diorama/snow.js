import {theme} from '../theme.js';
// 纸剪雪花：六角星小纸片，翻转飘落；默认关闭，开关时淡入淡出
import * as T from 'three';
import { boardRho, BOARD } from './layout.js';

function flakeShape() {
  const s = new T.Shape(), n = 6;
  for (let i = 0; i <= n * 2; i++) {
    const a = (i / (n * 2)) * Math.PI * 2, r = i % 2 ? .16 : .42;
    const x = Math.cos(a) * r, y = Math.sin(a) * r; i ? s.lineTo(x, y) : s.moveTo(x, y);
  }
  return s;
}

export function makeSnow(scene, { mobile = false } = {}) {
  if(theme.season!=='winter')return {toggle:()=>false,update:()=>{}};
  const N = mobile ? 400 : 1000;
  const geo = new T.ShapeGeometry(flakeShape());
  const mat = new T.MeshBasicMaterial({ color: theme.shade38, side: T.DoubleSide, transparent: true, opacity: 0, depthWrite: false });
  const inst = new T.InstancedMesh(geo, mat, N); inst.frustumCulled = false; inst.renderOrder = 7; inst.visible = false;
  // 每片：位置、速度、旋转
  const P = [], V = [], R = [], W = [];
  const reset = (i, top) => {
    let x, z; do { x = -BOARD.a + Math.random() * BOARD.a*2; z = -BOARD.b + Math.random() * BOARD.b*2; } while (boardRho(x, z) > 1.05);
    P[i] = new T.Vector3(x, top ? 30 + Math.random() * 14 : Math.random() * 44, z);
    V[i] = .9 + Math.random() * 1.1;                       // 下落速度
    R[i] = new T.Euler(Math.random() * 6, Math.random() * 6, Math.random() * 6);
    W[i] = [Math.random() * 6.28, .6 + Math.random() * .9, (Math.random() - .5) * 2.4]; // 摆动相位、频率、翻转速度
  };
  for (let i = 0; i < N; i++) reset(i, false);
  const backMat = new T.MeshBasicMaterial({ color: theme.shade39, side: T.DoubleSide, transparent: true, opacity: 0, depthWrite: false });
  const back = new T.InstancedMesh(geo, backMat, N); back.frustumCulled = false; back.renderOrder = 6; back.visible = false;
  scene.add(back); scene.add(inst);
  const M = new T.Matrix4(), Q = new T.Quaternion(), S = new T.Vector3();
  let on = false, fade = 0;
  return {
    get on() { return on; },
    toggle(v = !on) { on = v; if (on) inst.visible = back.visible = true; return on; },
    update(time, dt) {
      fade = T.MathUtils.clamp(fade + (on ? dt : -dt) / .8, 0, 1);
      mat.opacity = .6 * fade; backMat.opacity = .3 * fade;
      if (fade === 0) { inst.visible = back.visible = false; return; }
      for (let i = 0; i < N; i++) {
        const p = P[i], w = W[i];
        p.y -= V[i] * dt * 2.2;
        p.x += Math.sin(time * w[1] + w[0]) * dt * .9;      // 左右飘
        p.z += Math.cos(time * w[1] * .7 + w[0]) * dt * .5;
        R[i].x += w[2] * dt; R[i].y += w[2] * .7 * dt;       // 纸片翻转
        if (p.y < 0) reset(i, true);
        const s = .5 + (i % 7) * .05; S.set(s, s, s);
        inst.setMatrixAt(i, M.compose(p, Q.setFromEuler(R[i]), S));
        S.multiplyScalar(1.22); back.setMatrixAt(i, M.compose(p, Q, S));
      }
      inst.instanceMatrix.needsUpdate = true; back.instanceMatrix.needsUpdate = true;
    },
  };
}
