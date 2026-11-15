// 纸剪云：分层纸云（去白底 PNG），做成面向镜头的纸片立牌，在雪峰前后缓慢漂移
import * as T from 'three';

const FILES = [
  { url: '/clouds/cloud_01.png', aspect: 1024 / 255 },
  { url: '/clouds/cloud_02.png', aspect: 1024 / 397 },
  { url: '/clouds/cloud_03.png', aspect: 556 / 288 },
  { url: '/clouds/cloud_04.png', aspect: 1024 / 156 },
];
// [x, y, z, 宽度, 图编号, 漂移幅度]
const SPOTS = [
  [-38, 24, -34, 22, 0, 3], [6, 30, -44, 18, 1, 2.5], [40, 26, -34, 16, 1, 3],
  [56, 18, -12, 10, 2, 2], [-58, 17, 4, 11, 2, 2],
  [-14, 12, -24, 34, 3, 4], [30, 11, -20, 26, 3, 3.5],   // 贴着山腰的薄雾带
];

export function makeClouds(scene) {
  const group = new T.Group(); scene.add(group);
  const loader = new T.TextureLoader();
  const mats = FILES.map(f => {
    const tex = loader.load(f.url); tex.colorSpace = T.LinearSRGBColorSpace; tex.anisotropy = 4;
    return new T.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, alphaTest: .02 });
  });
  const clouds = SPOTS.map(([x, y, z, w, i, amp], k) => {
    const m = new T.Mesh(new T.PlaneGeometry(w, w / FILES[i].aspect), mats[i]);
    m.position.set(x, y, z); m.renderOrder = 6; group.add(m);
    return { m, x, y, amp, speed: .035 + (k % 3) * .012, phase: k * 1.7 };
  });
  return {
    update(time, camera) {
      for (const c of clouds) {
        c.m.quaternion.copy(camera.quaternion);
        c.m.position.x = c.x + Math.sin(time * c.speed + c.phase) * c.amp;
        c.m.position.y = c.y + Math.sin(time * c.speed * 1.7 + c.phase) * .25;
      }
    },
  };
}
