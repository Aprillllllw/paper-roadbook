#!/usr/bin/env python3
"""检查 trip.json 和 scene.json 有没有写错。只用标准库。

用法：
  python3 scripts/validate.py <工程目录>
  python3 scripts/validate.py --trip a/trip.json --scene a/scene.json [--public a/public]

工程目录里会找 src/data/trip.json 和 src/data/scene.json，照片视频在 public/ 下找。
退出码：0 = 没有错误（可以有提醒），1 = 有错误。
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

# 内置组件名（SPEC §5）。工程里实际注册的组件会再扫一遍，扫到的也算已知。
BUILTIN_TYPES = {
    "airport", "bridge", "cabin", "camel", "fence", "horse", "old-town", "radial-town",
    "red-berry-bush", "rider", "service-station", "sheep-flock", "spruce", "suv",
    "swan", "swan-flock", "yurt",
}
KINDS = {"stay", "pass", "sight"}
THEMES = {"winter-blush", "summer-meadow"}
VIEW_FROM = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"[错误] {where}：{msg}")

    def warn(self, where, msg):
        self.warnings.append(f"[提醒] {where}：{msg}")


def load(path, label, rep):
    p = Path(path)
    if not p.is_file():
        rep.err(label, f"找不到文件 {p}")
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        rep.err(label, f"不是合法的 JSON：第 {e.lineno} 行第 {e.colno} 列附近，{e.msg}。常见原因是多了或少了逗号、引号。")
        return None


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_pt(v):
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(is_num(c) for c in v)


def known_types(project):
    types = set(BUILTIN_TYPES)
    if project:
        comp = Path(project) / "template" / "src" / "components"
        for base in (Path(project) / "src" / "components", comp):
            if base.is_dir():
                for f in base.rglob("*.js"):
                    txt = f.read_text(encoding="utf-8", errors="ignore")
                    types.update(re.findall(r"""type\s*:\s*['"]([\w-]+)['"]""", txt))
                    types.update(re.findall(r"""register\(\s*['"]([\w-]+)['"]""", txt))
    return types


def check_scene(scene, rep, types):
    if not isinstance(scene, dict):
        rep.err("scene.json", "最外层必须是一个对象 { }")
        return
    if scene.get("version") != 1:
        rep.warn("scene.json", "version 应为 1")
    stops = scene.get("stops")
    if not isinstance(stops, dict) or not stops:
        rep.err("scene.json stops", "必须有 stops，格式 {\"站点id\": [x, z]}")
        stops = {}
    routes = scene.get("routes")
    if not isinstance(routes, dict) or not routes:
        rep.err("scene.json routes", "必须有 routes，格式 {\"D1\": [[x,z], [x,z], ...]}")
        routes = {}

    board = scene.get("board") or {}
    a, b = board.get("a", 62), board.get("b", 46)
    if not (is_num(a) and is_num(b) and a > 0 and b > 0):
        rep.err("scene.json board", "a 和 b 必须是正数（椭圆底板半轴）")
        a, b = 62, 46

    def inside(x, z):
        return (x / a) ** 2 + (z / b) ** 2 <= 1.0 + 1e-9

    for sid, pt in stops.items():
        if not is_pt(pt):
            rep.err(f"stops.{sid}", "坐标必须是 [x, z] 两个数字")
        elif not inside(*pt):
            rep.err(f"stops.{sid}", f"坐标 {pt} 在底板椭圆（a={a}, b={b}）外面，会悬在纸板外。往中心挪一点。")

    for rid, pts in routes.items():
        if not isinstance(pts, list) or len(pts) < 2:
            rep.err(f"routes.{rid}", "至少需要 2 个点")
            continue
        for i, pt in enumerate(pts):
            if not is_pt(pt):
                rep.err(f"routes.{rid}[{i}]", "点必须是 [x, z] 两个数字")
            elif not inside(*pt):
                rep.err(f"routes.{rid}[{i}]", f"点 {pt} 在底板椭圆外面")

    def check_xz(coll, label, key_x="x", key_z="z"):
        for i, it in enumerate(scene.get(coll) or []):
            if not isinstance(it, dict) or not is_num(it.get(key_x)) or not is_num(it.get(key_z)):
                rep.err(f"{coll}[{i}]", f"{label}必须有数字 x 和 z")
            elif not inside(it[key_x], it[key_z]):
                rep.warn(f"{coll}[{i}]", f"{label}位置 ({it[key_x]}, {it[key_z]}) 在底板椭圆外，会露出纸板。")

    # ---- 构图提醒（只是提醒，不算错误；规则见 references/composition-guide.md）
    for sid, pt in stops.items():
        if not is_pt(pt):
            continue
        for i, lk in enumerate(scene.get("lakes") or []):
            if not (isinstance(lk, dict) and all(is_num(lk.get(k)) for k in ("x", "z", "rx", "rz"))):
                continue
            rot = lk.get("rot", 0) if is_num(lk.get("rot", 0)) else 0
            c, sn = math.cos(rot), math.sin(rot)
            dx, dz = pt[0] - lk["x"], pt[1] - lk["z"]
            if lk["rx"] > 0 and lk["rz"] > 0 and math.hypot((dx * c + dz * sn) / lk["rx"], (-dx * sn + dz * c) / lk["rz"]) < 1:
                rep.warn(f"stops.{sid}", f"站点落在湖「{lk.get('id', i)}」的湖面范围里，会像站在水上。把它挪到岸上（离湖心约 rx+3）。")
        for i, pk in enumerate(scene.get("peaks") or []):
            if not (isinstance(pk, dict) and all(is_num(pk.get(k)) for k in ("x", "z"))):
                continue
            R = pk.get("R", 10) if is_num(pk.get("R", 10)) else 10
            d = math.hypot(pt[0] - pk["x"], pt[1] - pk["z"])
            if d < R + 8:
                rep.warn(f"stops.{sid}", f"离山峰「{pk.get('name') or '第 ' + str(i + 1) + ' 座'}」太近（{d:.0f}，构图指南建议至少 R+8={R + 8:.0f}），山会压住站点。把山或站点挪开一点。")
        for i, rg in enumerate(scene.get("ranges") or []):
            pts = rg.get("pts") if isinstance(rg, dict) else None
            if not isinstance(pts, list) or len(pts) < 2 or not all(is_pt(q) for q in pts):
                continue
            half = (rg.get("W", 10) if is_num(rg.get("W", 10)) else 10) / 2
            dmin = 1e18
            for a_, b_ in zip(pts, pts[1:]):
                vx, vz = b_[0] - a_[0], b_[1] - a_[1]
                L2 = vx * vx + vz * vz
                t = 0 if L2 == 0 else max(0, min(1, ((pt[0] - a_[0]) * vx + (pt[1] - a_[1]) * vz) / L2))
                dmin = min(dmin, math.hypot(pt[0] - (a_[0] + t * vx), pt[1] - (a_[1] + t * vz)))
            if dmin < half:
                rep.warn(f"stops.{sid}", f"站点压在山脉「{rg.get('name') or '第 ' + str(i + 1) + ' 条'}」的坡上（离脊线 {dmin:.0f}，山脉半宽 {half:.0f}）。站点要踩在平地上，往外挪一点。")

    check_xz("props", "摆件")
    check_xz("clumps", "树丛")
    check_xz("peaks", "山峰")
    check_xz("lakes", "湖")
    check_xz("pads", "地基")

    for i, p in enumerate(scene.get("props") or []):
        if isinstance(p, dict):
            t = p.get("type")
            if not t:
                rep.err(f"props[{i}]", "缺少 type")
            elif t not in types:
                rep.warn(f"props[{i}]", f"type \"{t}\" 不在已知组件里。引擎会放一张占位纸牌。要么拼错了，要么这个组件你还没做（见 references/component-recipes.md）。")
    for i, c in enumerate(scene.get("clumps") or []):
        if isinstance(c, dict) and c.get("type") and c["type"] not in types:
            rep.warn(f"clumps[{i}]", f"type \"{c['type']}\" 不在已知组件里")
    veh = scene.get("vehicle")
    if isinstance(veh, dict) and veh.get("type") and veh["type"] not in types:
        rep.warn("vehicle", f"type \"{veh['type']}\" 不在已知组件里")

    theme = scene.get("theme") or {}
    if theme.get("preset") and theme["preset"] not in THEMES:
        rep.warn("theme.preset", f"\"{theme['preset']}\" 不是内置主题（{ ' / '.join(sorted(THEMES)) }）")
    vf = (scene.get("meta") or {}).get("viewFrom")
    if vf and vf not in VIEW_FROM:
        rep.warn("meta.viewFrom", "应为 N NE E SE S SW W NW 之一")
    return stops, routes


def check_trip(trip, scene_stops, scene_routes, public_dir, rep):
    if not isinstance(trip, dict):
        rep.err("trip.json", "最外层必须是一个对象 { }")
        return
    if not trip.get("title"):
        rep.err("trip.title", "缺少标题")
    if trip.get("lang") not in (None, "zh", "en"):
        rep.warn("trip.lang", "模板自带 zh 和 en 两套界面文字；用其他语言时，请自己改 src/ui/shell.js 里的文字")
    if not trip.get("disclaimer"):
        rep.warn("trip.disclaimer", "页面需要显示「方位真实，距离已压缩」这类说明，请保留这个字段")

    days = trip.get("days")
    stops = trip.get("stops")
    if not isinstance(days, list) or not days:
        rep.err("trip.days", "至少需要一天")
        days = []
    if not isinstance(stops, dict) or not stops:
        rep.err("trip.stops", "至少需要一个站点")
        stops = {}

    seen_day = set()
    used = set()
    for i, d in enumerate(days):
        w = f"days[{i}]"
        if not isinstance(d, dict):
            rep.err(w, "必须是对象")
            continue
        did = d.get("id")
        if not did:
            rep.err(w, "缺少 id（如 D1）")
        elif did in seen_day:
            rep.err(w, f"id \"{did}\" 重复了")
        seen_day.add(did)
        if not d.get("title"):
            rep.warn(w, "没有 title")
        route = d.get("route")
        if not route:
            rep.err(w, "缺少 route（要对应 scene.json routes 里的键）")
        elif scene_routes is not None and route not in scene_routes:
            rep.err(w, f"route \"{route}\" 在 scene.json 的 routes 里不存在。现有：{', '.join(scene_routes) or '无'}")
        dstops = d.get("stops")
        if not isinstance(dstops, list) or not dstops:
            rep.err(w, "stops 必须是站点 id 的列表，至少一个")
            continue
        for sid in dstops:
            used.add(sid)
            if sid not in stops:
                rep.err(w, f"站点 \"{sid}\" 在 trip.stops 里没有定义")
        if "km" in d and not is_num(d["km"]):
            rep.warn(w, "km 应为数字")

    for sid, s in stops.items():
        w = f"trip.stops.{sid}"
        if scene_stops is not None and sid not in scene_stops:
            rep.err(w, "scene.json 的 stops 里没有这个 id，地图上没处放它。两边 id 必须一致。")
        if sid not in used:
            rep.warn(w, "没有被任何一天引用，不会出现在行程里")
        if not isinstance(s, dict):
            rep.err(w, "必须是对象")
            continue
        if not s.get("name"):
            rep.warn(w, "没有 name")
        if s.get("kind") not in (None, *KINDS):
            rep.warn(w, f"kind 应为 stay / pass / sight，现在是 \"{s.get('kind')}\"")
        for j, m in enumerate(s.get("media") or []):
            mw = f"{w}.media[{j}]"
            if not isinstance(m, dict) or m.get("type") not in ("photo", "video"):
                rep.err(mw, "type 必须是 photo 或 video")
                continue
            for key in ("src", "poster"):
                if key == "poster" and m["type"] != "video":
                    continue
                path = m.get(key)
                if not path:
                    if key == "src":
                        rep.err(mw, "缺少 src")
                    continue
                if public_dir is None:
                    continue
                if not (Path(public_dir) / path).is_file():
                    rep.err(mw, f"文件不存在：{key} = \"{path}\"（在 {public_dir} 下找的）。先跑 process_media.py，或检查路径。")
    if scene_stops is not None:
        for sid in scene_stops:
            if sid not in stops:
                rep.warn(f"scene.stops.{sid}", "trip.json 里没有这个站点，地图上只会有一个没有内容的点")

    av = (trip.get("author") or {}).get("avatar")
    if av and public_dir is not None and not (Path(public_dir) / av).is_file():
        rep.err("trip.author.avatar", f"头像文件不存在：\"{av}\"。没有头像可以删掉这个字段。")


def main():
    ap = argparse.ArgumentParser(description="检查 trip.json 和 scene.json")
    ap.add_argument("project", nargs="?", help="工程目录（里面有 src/data/）")
    ap.add_argument("--trip")
    ap.add_argument("--scene")
    ap.add_argument("--public", help="照片视频所在的 public 目录")
    args = ap.parse_args()

    trip_p, scene_p, public_p = args.trip, args.scene, args.public
    if args.project:
        root = Path(args.project)
        data = root / "src" / "data"
        trip_p = trip_p or (data / "trip.json" if (data / "trip.json").exists() else root / "trip.json")
        scene_p = scene_p or (data / "scene.json" if (data / "scene.json").exists() else root / "scene.json")
        public_p = public_p or (root / "public")
    if not trip_p or not scene_p:
        ap.error("请给出工程目录，或同时给出 --trip 和 --scene")

    rep = Report()
    scene = load(scene_p, "scene.json", rep)
    trip = load(trip_p, "trip.json", rep)
    sstops = sroutes = None
    if scene is not None:
        res = check_scene(scene, rep, known_types(args.project))
        if res:
            sstops, sroutes = res
    if trip is not None:
        check_trip(trip, sstops, sroutes, public_p, rep)

    for line in rep.errors + rep.warnings:
        print(line)
    if rep.errors:
        print(f"\n共 {len(rep.errors)} 个错误，{len(rep.warnings)} 个提醒。错误改完才能构建。")
        return 1
    print(f"\n没有错误。{len(rep.warnings)} 个提醒" + ("，可以看一下。" if rep.warnings else "。"))
    print("提示：想看画面够不够满，可以运行 python3 scripts/fullness.py <scene.json> [trip.json]。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
