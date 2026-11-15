import {theme} from '../theme.js';
// 可选 GLB 替换，保留位置、大小和整体动画
import * as T from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';

export const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const cache = new Map();
function load(url) {
  if (!cache.has(url)) cache.set(url, loader.loadAsync(url).then(g => {
    g.scene.traverse(o => {
      if (!o.isMesh) return;
      const map = o.material.map;
      if (map) { map.colorSpace = T.LinearSRGBColorSpace; map.anisotropy = 8; map.needsUpdate = true; }
      o.material = new T.MeshLambertMaterial({ map, color: theme.shade38 });
      o.castShadow = true; o.receiveShadow = true;
    });
    return g.scene;
  }));
  return cache.get(url);
}

// 物体在自身坐标系下的包围盒（排除 keep 里的对象）
function localBox(group, skip) {
  group.updateWorldMatrix(true, true);
  const box = new T.Box3(), inv = new T.Matrix4().copy(group.matrixWorld).invert(), tmp = new T.Box3();
  group.traverse(o => {
    if (!o.isMesh || skip.some(s => s === o || isDescendant(o, s))) return;
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    tmp.copy(o.geometry.boundingBox).applyMatrix4(new T.Matrix4().multiplyMatrices(inv, o.matrixWorld));
    box.union(tmp);
  });
  return box;
}
function isDescendant(o, root) { for (let p = o.parent; p; p = p.parent) if (p === root) return true; return false; }

/**
 * group: 要替换内容的 Group；url: GLB；opts.rot: GLB 朝向修正（弧度）；opts.fit: 'xz' 按水平尺寸 | 'y' 按高度；opts.scale: 额外倍数；opts.keep: 保留的子对象
 */
export async function swapInto(group, url, { rot = 0, fit = 'xz', scale = 1, keep = [] } = {}) {
  const src = await load(url);
  const box = localBox(group, keep);
  if (box.isEmpty()) return null;
  const size = box.getSize(new T.Vector3()), center = box.getCenter(new T.Vector3());
  const model = src.clone(true); model.rotation.y = rot;
  const holder = new T.Group(); holder.add(model);
  const mb = new T.Box3().setFromObject(holder), ms = mb.getSize(new T.Vector3());
  const k = (fit === 'y' ? size.y / ms.y : Math.max(size.x, size.z) / Math.max(ms.x, ms.z)) * scale;
  holder.scale.setScalar(k);
  if (import.meta.env?.DEV) console.log('[swap]', url, 'proc', size.toArray().map(v=>+v.toFixed(2)), 'glb', ms.toArray().map(v=>+v.toFixed(2)), 'k', +k.toFixed(3));
  const mb2 = new T.Box3().setFromObject(holder), mc = mb2.getCenter(new T.Vector3());
  holder.position.set(center.x - mc.x, box.min.y - mb2.min.y, center.z - mc.z);
  for (const c of [...group.children]) if (!keep.includes(c)) group.remove(c);
  group.add(holder);
  return holder;
}
