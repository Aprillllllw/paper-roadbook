#!/usr/bin/env python3
"""把 template/ 复制成你自己的路书工程。只用标准库。

用法：
  python3 scripts/new_project.py <目标目录> [--scene scene.json] [--trip trip.json] [--with-glb] [--force]

只给 --scene 不给 --trip：按 scene.json 的站点和路线生成一份空白占位 trip.json（标题等都是明显的占位文字）。
两个都不给：保留模板自带的示例数据（仅供预览，要替换）。
--with-glb：把 assets/glb/ 里的全部模型复制到工程的 public/glb/，之后在 scene.json 里写 "opts": {"glb": "glb/horse.glb"} 即可使用。

目标目录必须不存在或为空（加 --force 可以覆盖已有文件）。
node_modules 和 dist 不会被复制。
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

SKIP = {"node_modules", "dist", ".DS_Store", ".vite"}


def placeholder_trip(scene):
    """按 scene.json 的 stops / routes 生成空白占位 trip.json。"""
    stops = scene.get("stops") or {}
    routes = scene.get("routes") or {}

    def dist_to_route(pt, pts):
        """返回 (点到折线的最短距离, 折线上最近的位置，用来排先后)。位置 = 段序号 + 段内比例。"""
        if len(pts) == 1:
            return math.hypot(pt[0] - pts[0][0], pt[1] - pts[0][1]), 0.0
        best, at = 1e18, 0.0
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = dx * dx + dy * dy
            t = 0.0 if L < 1e-9 else max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / L))
            d = math.hypot(pt[0] - (a[0] + t * dx), pt[1] - (a[1] + t * dy))
            if d < best:
                best, at = d, i + t
        return best, at

    keys = list(routes.keys()) or ["D1"]
    # 阈值：按整张图的大小算。离某天路线的起点或终点在 NEAR 以内，就算这一天的站
    # （这样「D1 终点 = D2 起点」的站两天都会出现）；离路线本身在 NEAR/2 以内也算。
    allpts = list(stops.values()) + [q for r in routes.values() for q in r]
    if allpts:
        xs = [p[0] for p in allpts]
        zs = [p[1] for p in allpts]
        diag = math.hypot(max(xs) - min(xs), max(zs) - min(zs))
    else:
        diag = 0.0
    NEAR = max(5.0, diag * 0.06)
    assigned = {k: [] for k in keys}
    for sid, pt in stops.items():
        if not routes:
            assigned["D1"].append((0.0, sid))
            continue
        hit = False
        for k in keys:
            pts = routes[k]
            if not pts:
                continue
            d_line, pos = dist_to_route(pt, pts)
            d_end = min(math.hypot(pt[0] - pts[0][0], pt[1] - pts[0][1]),
                        math.hypot(pt[0] - pts[-1][0], pt[1] - pts[-1][1]))
            if d_end <= NEAR or d_line <= NEAR / 2:
                assigned[k].append((pos, sid))
                hit = True
        if not hit:  # 谁都不近：仍然给最近的一天，保证每个站都出现
            cand = [k for k in keys if routes[k]]
            if cand:
                k = min(cand, key=lambda r: dist_to_route(pt, routes[r])[0])
                assigned[k].append((dist_to_route(pt, routes[k])[1], sid))
    days = []
    for n, k in enumerate(keys, 1):
        ids = [sid for _, sid in sorted(assigned[k])]
        if not ids and stops and routes.get(k):
            end = routes[k][-1]  # 这一天没分到站点：取离路线终点最近的一个，保证每天至少一站
            ids = [min(stops, key=lambda sid: math.hypot(stops[sid][0] - end[0], stops[sid][1] - end[1]))]
        days.append({"id": k, "label": f"Day {n}", "title": "在这里写这一天的标题",
                     "drive": "在这里写驾驶时间", "route": k if routes else "D1", "stops": ids})
    return {
        "title": "在这里写路书标题",
        "subtitle": "在这里写一句副标题",
        "author": {"name": "你的名字", "line": "在这里写旅行简介"},
        "lang": "zh",
        "days": days,
        "stops": {sid: {"name": f"在这里写站点名（{sid}）", "zh": "", "kind": "sight", "media": [],
                        "info": {"行程笔记": "在这里写你的游览或住宿体验"}, "extra": None} for sid in stops},
        "facts": [{"label": "天数", "value": f"{len(days)} 天"}],
        "disclaimer": "方位真实，距离已压缩，比例不按真实。",
    }


def main():
    ap = argparse.ArgumentParser(description="用模板新建路书工程")
    ap.add_argument("dest", help="新工程目录")
    ap.add_argument("--scene", help="用这个文件覆盖 src/data/scene.json")
    ap.add_argument("--trip", help="用这个文件覆盖 src/data/trip.json")
    ap.add_argument("--with-glb", action="store_true",
                    help="把 assets/glb/ 里的全部 3D 模型复制到工程的 public/glb/")
    ap.add_argument("--force", action="store_true", help="目标目录非空时也继续")
    args = ap.parse_args()

    template = Path(__file__).resolve().parent.parent / "template"
    if not template.is_dir():
        sys.exit(f"找不到模板目录：{template}。这个脚本要放在 Skill 根目录的 scripts/ 下。")

    dest = Path(args.dest).expanduser().resolve()
    if dest.exists() and any(dest.iterdir()) and not args.force:
        sys.exit(f"目标目录 {dest} 已经有内容。换一个目录，或加 --force。")

    for label, src in (("--scene", args.scene), ("--trip", args.trip)):
        if src and not Path(src).is_file():
            sys.exit(f"{label} 指定的文件不存在：{src}")

    shutil.copytree(template, dest, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*SKIP))
    data = dest / "src" / "data"
    data.mkdir(parents=True, exist_ok=True)
    if args.scene:
        shutil.copyfile(args.scene, data / "scene.json")
    if args.trip:
        shutil.copyfile(args.trip, data / "trip.json")
    elif args.scene:
        try:
            scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"--scene 不是合法的 JSON：第 {e.lineno} 行附近，{e.msg}")
        (data / "trip.json").write_text(
            json.dumps(placeholder_trip(scene), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("没有给 --trip：已按 scene.json 的站点和路线生成空白占位 trip.json，请把里面的占位文字换成你的内容。")
    else:
        print("注意：这是示例数据（新疆伊犁河谷），请替换成你自己的 trip.json 和 scene.json。")

    if args.with_glb:
        glb_src = Path(__file__).resolve().parent.parent / "assets" / "glb"
        files = sorted(glb_src.glob("*.glb")) if glb_src.is_dir() else []
        if not files:
            print(f"提醒：没找到 {glb_src} 里的模型文件，跳过 --with-glb。")
        else:
            (dest / "public" / "glb").mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copyfile(f, dest / "public" / "glb" / f.name)
            print(f"已复制 {len(files)} 个模型到 public/glb/。用法：在 scene.json 的摆件里写 \"opts\": {{\"glb\": \"glb/horse.glb\"}}")

    print(f"已创建工程：{dest}")
    print("数据文件在 src/data/（trip.json 写内容，scene.json 写微缩构图）。照片视频放 public/media/。")
    print("\n下一步：")
    print(f"  cd {dest}")
    print("  npm install")
    print("  npm run dev        # 本地预览，终端里会给出网址")
    print("  npm run build      # 打包，产物在 dist/")
    skill = Path(__file__).resolve().parent
    print(f"\n检查数据：python3 {skill / 'validate.py'} {dest}")


if __name__ == "__main__":
    main()
