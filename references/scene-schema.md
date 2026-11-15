# scene.json 字段说明

`scene.json` 描述那块微缩景观：底板上有哪些山、湖、河，站点在哪，路线怎么走，摆了哪些纸雕小物件。位置：工程里的 `src/data/scene.json`。

一般不用手写。流程是：`geo_scan.py` 生成草稿 `scene.draft.json`，再按 `composition-guide.md` 调整成 `scene.json`。这份文档用来读懂和修改它。

## 坐标

单位叫「盆景单位」。`x` 向右，`z` 朝向镜头（屏幕下方），`y` 向上。底板是椭圆，默认半轴 `a=62`、`b=46`，**所有内容都要放在椭圆里**：`(x/a)² + (z/b)² ≤ 1`。

镜头默认从 `+z` 方向斜俯视，所以 **z 为负的后排是背景墙**，最高的山放在那里。

三条原则（写进页面说明）：方位真实，距离压缩，比例不按真实。

## 最小示例

只有 `stops` 和 `routes` 就能渲染出一张平坦的纸板地图：

```json
{
  "version": 1,
  "stops":  { "airport": [20, 25], "beach-inn": [-18, 8] },
  "routes": { "D1": [[20, 25], [5, 15], [-18, 8]] }
}
```

## 完整字段

```jsonc
{
  "version": 1,
  "meta": {
    "name": "地区名",
    "bbox": [80.5, 42.4, 83.4, 44.9],   // 真实范围 [西, 南, 东, 北]，只做记录
    "viewFrom": "W",                      // 镜头在真实世界的哪个方位：N NE E SE S SW W NW
    "scaleNote": "方位真实，距离已压缩"
  },
  "theme": { "season": "winter", "preset": "winter-blush" },
  "board": { "a": 62, "b": 46 },
  "stops":  { "sayram": [-17, 6.5] },
  "ranges": [ { "name": "back-wall", "H": 6.5, "W": 13, "pts": [[-46,-24],[48,-26]] } ],
  "peaks":  [ { "x": 24, "z": -39, "H": 36, "R": 12, "n": 6, "name": "山名" } ],
  "lakes":  [ { "id": "sayram", "x": -30, "z": -5, "rx": 15, "rz": 10, "rot": 0.2, "level": 0.85 } ],
  "rivers": [ { "id": "ili", "w": 2.6, "pts": [[6,-33],[1,-22]] } ],
  "coast":  null,
  "routes": { "D1": [[22,28],[14,22],[-17,6.5]] },
  "pads":   [ { "x": 22, "z": 35, "r": 12 } ],
  "props":  [ { "type": "yurt", "x": 34, "z": 30.5, "s": 6.5, "rotY": 0, "opts": {} } ],
  "clumps": [ { "type": "spruce", "x": 6, "z": -17, "n": 7, "r": 3.2 } ],
  "vehicle": { "type": "suv", "sticker": "media/avatar_chibi.png" }
}
```

| 字段 | 说明 |
|---|---|
| `meta` | 只做记录和说明，不影响画面（`viewFrom` 供你和助手核对方位） |
| `theme.season` | `winter` 有雪、屋顶积雪；其他季节没有 |
| `theme.preset` | 内置两套：`winter-blush`（粉米色冬景）、`summer-meadow`（绿草地蓝天） |
| `board` | 底板椭圆半轴 |
| `stops` | 站点 id 到 `[x, z]`。**id 必须和 `trip.json` 的 `stops` 键一致** |
| `ranges` | 缓坡山麓。`pts` 是脊线折线，`H` 高度，`W` 宽度 |
| `peaks` | 独立的低多边形山峰。`H` 高，`R` 底半径，`n` 面数（5–7），`name` 可省 |
| `lakes` | 湖。`rx`/`rz` 两个半径，`rot` 旋转（弧度），`level` 水面相对高度 |
| `rivers` | 河。`w` 宽度，`pts` 折线 |
| `coast` | 某一侧是海：`{ "side": "S", "inset": 12 }`。没有海就是 `null` |
| `routes` | 路线折线。**键要对应 `trip.json` 里 `days[].route`**。路线经过 `type=bridge` 的摆件时，路面会贴桥面 |
| `pads` | 平整地基，给城镇、机场之类的大摆件一块平地 |
| `props` | 纸雕摆件。`type` 是组件名，`s` 缩放，`rotY` 绕竖轴旋转（弧度），`y` 省略时自动贴地，`opts` 传给组件，`opts.glb` 可改用模型（用法见下） |
| `clumps` | 成片的树。`n` 棵数，`r` 散布半径 |
| `vehicle` | 沿路线行驶的车。`sticker` 是贴在车上的图（可省） |

所有数组（比如 `ranges`、`peaks`）都可以是空的 `[]`。

## 可用的 props 类型

内置组件名：`airport`、`bridge`、`cabin`、`camel`、`fence`、`horse`、`old-town`、`radial-town`、`red-berry-bush`、`rider`、`service-station`、`sheep-flock`、`spruce`、`suv`、`swan`、`swan-flock`、`yurt`。具体以工程里 `src/components/` 为准。

`type` 写了不存在的名字，页面不会崩，会放一张占位纸牌，`validate.py` 会提醒。缺的组件按 `component-recipes.md` 现做，放进 `src/components/custom/`。

## 可选：用 GLB 模型替换摆件

默认的摆件都是代码画的，不需要模型。想用 `assets/glb/` 里的模型（`horse.glb`、`camel.glb`、`yurt.glb`、`suv.glb`、`swan.glb`、`bridge.glb`、`rider.glb`、`spruce_meshy.glb`、`yining_town.glb`）：

1. 把要用的文件复制到工程的 `public/glb/`。建工程时加 `--with-glb` 可以一次复制全部。
2. 在摆件里写 `"opts": {"glb": "glb/horse.glb"}`。

```json
{ "type": "horse", "x": 10, "z": 5, "s": 2, "opts": { "glb": "glb/horse.glb" } }
```

路径是相对 `public/` 的：写 `glb/horse.glb`，不要写 `assets/glb/horse.glb`，也不要在前面加斜杠。引擎照原位置和大小用模型替换代码画的部件，文件找不到时只在控制台打一条警告，摆件保持原样。`type` 仍要写对应的组件名，模型按它的尺寸缩放。

## 改完检查

```
python3 scripts/validate.py <工程目录>
```

它会检查坐标是否在椭圆内、站点 id 两边是否一致、路线是否存在，并对未知的 `type` 给出提醒。
