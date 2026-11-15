#!/usr/bin/env python3
"""检查微缩景观「画面饱满度」：画面空不空、哪里空、该问用户什么。只用标准库。

用法：
  python3 scripts/fullness.py scene.json [trip.json] [--json]
  python3 scripts/fullness.py --pre stops.json|trip.json [--json]     # 事前预估，还没有 scene 时用

退出码：0 = 及格或饱满，1 = 空（不及格），2 = 文件读不了。
这个脚本只做判断和提问，不改任何文件。阈值都在下面的常量里。
"""
import argparse
import json
import math
import sys
from pathlib import Path

# ───────────── 阈值（校准记录见 dev/NOTES_FULLNESS.md）─────────────
GRID_COLS, GRID_ROWS = 10, 8        # 底板外接矩形切成 10×8 格，只算中心在椭圆内的格
COVER_PASS, COVER_EMPTY = 0.70, 0.50  # 覆盖率：>=及格；<空
COVER_FULL, TYPES_FULL = 0.85, 8      # 饱满：覆盖率与种类数同时达到
EMPTY_R_PASS_FRAC = 0.26            # 最大空圆半径及格线 = 底板长半轴 a × 此值（a=62 时约 16）
EMPTY_R_EMPTY_FRAC = 0.37           # 超过 a × 此值算「空」（约 23）
STOP_R = 14.0                       # 站点周围这个半径内要有地标
STOP_LANDMARK_PASS = 0.80           # 有地标的站点占比：>=及格
STOP_LANDMARK_EMPTY = 0.50          # <此值算空
LIVING_PASS_FRAC = 0.5              # 活物总数 >= 站点数 × 此值
LIVING_EMPTY_FRAC = 0.25            # < 站点数 × 此值算空
TYPES_PASS, TYPES_EMPTY = 5, 3      # 不同 type 数：>=5 及格；<=3 空
ROUTE_SIDE = 9.0                    # 路线两侧这个距离内没有 prop/clump 才算空
ROUTE_GAP_PASS = 22.0               # 路线上连续空段长度：<=此值及格
ROUTE_GAP_EMPTY = 40.0              # >此值算空
REPORT_MIN_R_FRAC = 0.60            # 空白圆半径达到及格线的这个比例才在报告里列出
MAX_BLANKS = 3                      # 报告最多列几块空白
PRE_STOPS_PASS, PRE_STOPS_EMPTY = 7, 5   # --pre：站点数
PRE_SLOTS_PASS, PRE_SLOTS_EMPTY = 18, 12  # --pre：内容点数（站点数 + 每站最多 3 件具体事物）

# ───────────── type 分类 ─────────────
# 地标类：建筑、桥、机场；活物类：动物、人、车、船；自然类：树、草丛、栅栏等自然/农田填充。
# 未知 type（自造组件）在 opts.category 里写 landmark / living / nature；没写按地标算。
CATEGORY = {
    "airport": "landmark", "bridge": "landmark", "cabin": "landmark", "old-town": "landmark",
    "radial-town": "landmark", "service-station": "landmark", "yurt": "landmark",
    "camel": "living", "horse": "living", "rider": "living", "sheep-flock": "living",
    "swan": "living", "swan-flock": "living", "suv": "living",
    "spruce": "nature", "red-berry-bush": "nature", "fence": "nature",
}
CAT_NAME = {"landmark": "地标", "living": "活物", "nature": "自然填充"}

COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
VIEW_DEG = {c: i * 45 for i, c in enumerate(COMPASS)}
DIR_AFTER = {"N": "以北", "NE": "东北方向", "E": "以东", "SE": "东南方向",
             "S": "以南", "SW": "西南方向", "W": "以西", "NW": "西北方向"}
DIR_SHORE = {"N": "北岸", "NE": "东北岸", "E": "东岸", "SE": "东南岸",
             "S": "南岸", "SW": "西南岸", "W": "西岸", "NW": "西北岸"}


def category(type_, opts=None):
    c = (opts or {}).get("category") if isinstance(opts, dict) else None
    if c in CAT_NAME:
        return c
    return CATEGORY.get(type_, "landmark")


# ───────────── 几何 ─────────────
def seg_dist(px, pz, ax, az, bx, bz):
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


def poly_dist(px, pz, pts):
    if len(pts) == 1:
        return math.hypot(px - pts[0][0], pz - pts[0][1])
    return min(seg_dist(px, pz, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
               for i in range(len(pts) - 1))


def ellipse_dist(px, pz, cx, cz, rx, rz, rot):
    c, s = math.cos(-rot), math.sin(-rot)
    u, v = (px - cx) * c - (pz - cz) * s, (px - cx) * s + (pz - cz) * c
    d = math.hypot(u / rx, v / rz)
    return (d - 1.0) * min(rx, rz)


class Item:
    """一块有占地的内容。dist(x,z) = 到它边缘的距离（在内部为负）。"""
    def __init__(self, kind, ref, shape, **kw):
        self.kind, self.ref, self.shape, self.kw = kind, ref, shape, kw

    def dist(self, x, z):
        k, s = self.kw, self.shape
        if s == "circle":
            return math.hypot(x - k["x"], z - k["z"]) - k["r"]
        if s == "poly":
            return poly_dist(x, z, k["pts"]) - k["hw"]
        return ellipse_dist(x, z, k["x"], k["z"], k["rx"], k["rz"], k["rot"])


def num(v, d=0.0):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else d


def pts_of(v):
    return [(num(p[0]), num(p[1])) for p in v or [] if isinstance(p, (list, tuple)) and len(p) == 2]


def build_items(scene):
    items = []
    for sid, p in (scene.get("stops") or {}).items():
        if isinstance(p, (list, tuple)) and len(p) == 2:
            items.append(Item("stop", sid, "circle", x=num(p[0]), z=num(p[1]), r=4.0))
    for i, p in enumerate(scene.get("props") or []):
        s = num(p.get("s"), 3.0)
        items.append(Item("prop", i, "circle", x=num(p.get("x")), z=num(p.get("z")), r=max(2.0, 0.6 * s)))
    for i, c in enumerate(scene.get("clumps") or []):
        items.append(Item("clump", i, "circle", x=num(c.get("x")), z=num(c.get("z")), r=num(c.get("r"), 3) + 1.5))
    for i, l in enumerate(scene.get("lakes") or []):
        items.append(Item("lake", i, "ellipse", x=num(l.get("x")), z=num(l.get("z")),
                          rx=max(num(l.get("rx"), 5), 1), rz=max(num(l.get("rz"), 5), 1), rot=num(l.get("rot"))))
    for i, r in enumerate(scene.get("rivers") or []):
        pts = pts_of(r.get("pts"))
        if pts:
            items.append(Item("river", i, "poly", pts=pts, hw=num(r.get("w"), 2.6) / 2 + 0.5))
    for i, p in enumerate(scene.get("peaks") or []):
        items.append(Item("peak", i, "circle", x=num(p.get("x")), z=num(p.get("z")), r=num(p.get("R"), 8)))
    for i, r in enumerate(scene.get("ranges") or []):
        pts = pts_of(r.get("pts"))
        if pts:
            items.append(Item("range", i, "poly", pts=pts, hw=num(r.get("W"), 8) / 2))
    for k, route in (scene.get("routes") or {}).items():
        pts = pts_of(route)
        if pts:
            items.append(Item("route", k, "poly", pts=pts, hw=2.0))
    return items


def densify(pts, step=1.0):
    out = []
    for i in range(len(pts) - 1):
        (ax, az), (bx, bz) = pts[i], pts[i + 1]
        n = max(1, int(math.hypot(bx - ax, bz - az) / step))
        for j in range(n):
            out.append((ax + (bx - ax) * j / n, az + (bz - az) * j / n))
    if pts:
        out.append(pts[-1])
    return out


# ───────────── 方位描述 ─────────────
class Geo:
    def __init__(self, scene, trip):
        self.scene = scene
        self.a = num((scene.get("board") or {}).get("a"), 62)
        self.b = num((scene.get("board") or {}).get("b"), 46)
        vf = (scene.get("meta") or {}).get("viewFrom")
        self.view = VIEW_DEG.get(vf) if vf in VIEW_DEG else None
        self.stops = {k: (num(v[0]), num(v[1])) for k, v in (scene.get("stops") or {}).items()
                      if isinstance(v, (list, tuple)) and len(v) == 2}
        ts = (trip or {}).get("stops") or {}
        self.names = {}
        for sid in self.stops:
            t = ts.get(sid) or {}
            self.names[sid] = t.get("zh") or t.get("name") or sid
        self.lakes = scene.get("lakes") or []
        self.peaks = scene.get("peaks") or []
        self.ranges = scene.get("ranges") or []

    def compass(self, dx, dz):
        """画面向量（x 向右，z 朝镜头）→ 8 方位。没有 viewFrom 时返回 None。"""
        if self.view is None or math.hypot(dx, dz) < 1e-6:
            return None
        phi = math.radians(self.view + 180)           # 镜头朝向的方位角
        fe, fn = math.sin(phi), math.cos(phi)
        re, rn = math.sin(phi + math.pi / 2), math.cos(phi + math.pi / 2)
        e, n = -dz * fe + dx * re, -dz * fn + dx * rn
        deg = math.degrees(math.atan2(e, n)) % 360
        return COMPASS[int((deg + 22.5) // 45) % 8]

    def region(self, x, z):
        u, v = x / self.a, z / self.b
        col = "左" if u < -0.3 else "右" if u > 0.3 else ""
        row = "后" if v < -0.3 else "前" if v > 0.3 else ""
        if col and row:
            return f"画面{col}{row}方"
        if row:
            return f"画面正{row}方"
        if col:
            return f"画面{col}侧"
        return "画面中央"

    def nearest_stop(self, x, z):
        best = None
        for sid, (sx, sz) in self.stops.items():
            d = math.hypot(x - sx, z - sz)
            if best is None or d < best[0]:
                best = (d, sid)
        return best

    def rel_stop(self, x, z):
        """「丽江以西」「丽江周边」；没有站点返回空串。"""
        ns = self.nearest_stop(x, z)
        if not ns:
            return ""
        d, sid = ns
        name = self.names[sid]
        if d <= 14:
            return f"{name}周边"
        sx, sz = self.stops[sid]
        c = self.compass(x - sx, z - sz)
        if c:
            return f"{name}{DIR_AFTER[c]}"
        side = ("右" if x > sx else "左") if abs(x - sx) > abs(z - sz) else ("前" if z > sz else "后")
        return f"{name}的{side}边"

    def terrain(self, x, z):
        """找最近的水或山，返回 (类型, 描述, id)。"""
        best = None
        for i, l in enumerate(self.lakes):
            d = ellipse_dist(x, z, num(l.get("x")), num(l.get("z")), num(l.get("rx"), 5), num(l.get("rz"), 5), num(l.get("rot")))
            if d <= 12 and (best is None or d < best[0]):
                best = (d, "lake", l)
        for p in self.peaks:
            d = math.hypot(x - num(p.get("x")), z - num(p.get("z"))) - num(p.get("R"), 8)
            if d <= 10 and (best is None or d < best[0]):
                best = (d, "foot", p)
        for r in self.ranges:
            pts = pts_of(r.get("pts"))
            if pts:
                d = poly_dist(x, z, pts) - num(r.get("W"), 8) / 2
                if d <= 10 and (best is None or d < best[0]):
                    best = (d, "foot", r)
        return best

    def describe(self, x, z):
        """返回 (人话位置, 地貌类型, 附带名字)。"""
        reg = self.region(x, z)
        t = self.terrain(x, z)
        rel = self.rel_stop(x, z)
        if t and t[1] == "lake":
            l = t[2]
            nm = l.get("name") or l.get("id") or "湖"
            c = self.compass(x - num(l.get("x")), z - num(l.get("z")))
            if c:
                return f"{reg}，{nm}{DIR_SHORE[c]}", "lake", nm
            side = "右" if x > num(l.get("x")) else "左"
            return f"{reg}，{nm}{side}岸", "lake", nm
        if t and t[1] == "foot":
            return (f"{reg}，{rel}的山脚" if rel else f"{reg}的山脚"), "foot", rel
        if rel and "周边" in rel:
            return f"{reg}，{rel}", "stop", rel
        return (f"{reg}，{rel}的空地" if rel else f"{reg}的空地"), "open", rel


# ───────────── 指标 ─────────────
def zone_hi(v, ok, empty):      # 越大越好
    return "ok" if v >= ok else ("empty" if v < empty else "grey")


def zone_lo(v, ok, empty):      # 越小越好
    return "ok" if v <= ok else ("empty" if v > empty else "grey")


def inside(x, z, a, b, k=1.0):
    return (x / a) ** 2 + (z / b) ** 2 <= k * k


def analyze(scene, trip=None):
    g = Geo(scene, trip)
    a, b = g.a, g.b
    items = build_items(scene)
    props = scene.get("props") or []
    clumps = scene.get("clumps") or []
    pc_items = [it for it in items if it.kind in ("prop", "clump")]

    # 1. 覆盖率
    cw, ch = 2 * a / GRID_COLS, 2 * b / GRID_ROWS
    rc = 0.5 * min(cw, ch)
    cells = total = covered = 0
    empty_cells = []
    for i in range(GRID_COLS):
        for j in range(GRID_ROWS):
            x, z = -a + (i + 0.5) * cw, -b + (j + 0.5) * ch
            if not inside(x, z, a, b):
                continue
            total += 1
            if any(it.dist(x, z) <= rc for it in items):
                covered += 1
            else:
                empty_cells.append((x, z))
    coverage = covered / total if total else 0.0

    # 2. 最大空圆（逐块找）
    step = 1.5
    grid = []
    x = -a
    while x <= a:
        z = -b
        while z <= b:
            if inside(x, z, a, b, 0.93):
                edge = (1 - math.hypot(x / a, z / b)) * min(a, b)
                grid.append([x, z, min(it.dist(x, z) for it in items) if items else 99.0, edge + 4])
            z += step
        x += step
    blanks = []
    pass_r = a * EMPTY_R_PASS_FRAC
    for _ in range(MAX_BLANKS):
        best = max(grid, key=lambda q: min(q[2], q[3]), default=None)
        if not best:
            break
        r = min(best[2], best[3])
        if r < pass_r * REPORT_MIN_R_FRAC:
            break
        blanks.append({"x": round(best[0], 1), "z": round(best[1], 1), "r": round(r, 1)})
        for q in grid:
            q[2] = min(q[2], math.hypot(q[0] - best[0], q[1] - best[1]) - r)
    max_r = blanks[0]["r"] if blanks else max((min(q[2], q[3]) for q in grid), default=0.0)
    max_r = max(max_r, 0.0)

    # 3. 站点丰富度
    land_pos = [(num(p.get("x")), num(p.get("z"))) for p in props if category(p.get("type"), p.get("opts")) == "landmark"]
    no_land = []
    for sid, (sx, sz) in g.stops.items():
        if not any(math.hypot(sx - px, sz - pz) <= STOP_R for px, pz in land_pos):
            no_land.append(sid)
    n_stops = len(g.stops)
    land_share = 1 - len(no_land) / n_stops if n_stops else 1.0
    living = sum(1 for p in props if category(p.get("type"), p.get("opts")) == "living")
    living += sum(1 for c in clumps if category(c.get("type"), c) == "living")
    living_need = math.ceil(n_stops * LIVING_PASS_FRAC)

    # 4. 种类数
    types = sorted({p.get("type") for p in props if p.get("type")} | {c.get("type") for c in clumps if c.get("type")})

    # 5. 路段空白
    gaps = []
    for rid, route in (scene.get("routes") or {}).items():
        pts = densify(pts_of(route))
        run = []
        for q in pts + [None]:
            empty = q is not None and all(it.dist(q[0], q[1]) > ROUTE_SIDE for it in pc_items)
            if empty:
                run.append(q)
            else:
                if len(run) > 1:
                    length = sum(math.hypot(run[k + 1][0] - run[k][0], run[k + 1][1] - run[k][1]) for k in range(len(run) - 1))
                    if length > ROUTE_GAP_PASS * 0.7:
                        gaps.append({"route": rid, "len": round(length, 1), "start": run[0], "end": run[-1]})
                run = []
    # 去重：往返的同一路段只留一条
    uniq = []
    for gp in sorted(gaps, key=lambda q: -q["len"]):
        mx, mz = (gp["start"][0] + gp["end"][0]) / 2, (gp["start"][1] + gp["end"][1]) / 2
        gp["mid"] = (mx, mz)
        if not any(math.hypot(mx - u["mid"][0], mz - u["mid"][1]) < 10 for u in uniq):
            uniq.append(gp)
    gaps = uniq
    longest_gap = gaps[0]["len"] if gaps else 0.0

    zones = {
        "覆盖率": zone_hi(coverage, COVER_PASS, COVER_EMPTY),
        "最大空白": zone_lo(max_r, pass_r, a * EMPTY_R_EMPTY_FRAC),
        "站点地标": zone_hi(land_share, STOP_LANDMARK_PASS, STOP_LANDMARK_EMPTY),
        "活物数量": zone_hi(living, living_need, n_stops * LIVING_EMPTY_FRAC),
        "种类数": zone_hi(len(types), TYPES_PASS, TYPES_EMPTY + 1),
        "路段空白": zone_lo(longest_gap, ROUTE_GAP_PASS, ROUTE_GAP_EMPTY),
    }
    vals = list(zones.values())
    if "empty" in vals or "grey" in vals:
        verdict = "空"
    elif coverage >= COVER_FULL and len(types) >= TYPES_FULL:
        verdict = "饱满"
    else:
        verdict = "及格"

    # 空白说明与建议
    blank_out = []
    for bl in blanks:
        where, kind, nm = g.describe(bl["x"], bl["z"])
        blank_out.append(dict(bl, where=where, kind=kind, **suggest(kind, nm, where)))
    gap_out = []
    for gp in gaps:
        if gp["len"] <= ROUTE_GAP_PASS:
            continue
        sa, sb = g.nearest_stop(*gp["start"]), g.nearest_stop(*gp["end"])
        na, nb = (g.names[sa[1]] if sa else "起点"), (g.names[sb[1]] if sb else "终点")
        if na == nb:
            where = f"{na}附近的路段两侧"
            ask = f"{na}附近的路两边是什么样？有村子、牲畜、路边摊或加油站吗？"
        else:
            where = f"{na}和{nb}之间的路段两侧"
            ask = f"{na}到{nb}的路上，两边都是什么？有村子、牲畜、路边摊或加油站吗？"
        gap_out.append({"route": gp["route"], "len": gp["len"], "where": where,
                        "suggest_concrete": ["村落", "牲畜", "路边摊或加油站"],
                        "suggest_nature": ["树丛", "草丛", "田地"], "ask": ask})
    stop_out = [{"stop": sid, "name": g.names[sid],
                 "ask": f"{g.names[sid]}最有代表性的东西是什么？有标志建筑、特色小景或常见的人和动物吗？"} for sid in no_land]

    return {
        "verdict": verdict,
        "zones": zones,
        "metrics": {
            "coverage": round(coverage, 3), "cells": total, "covered_cells": covered,
            "max_empty_radius": round(max_r, 1), "max_empty_pass": round(pass_r, 1),
            "stops": n_stops, "stops_without_landmark": no_land,
            "living": living, "living_needed": living_need,
            "types": len(types), "type_list": types,
            "longest_route_gap": round(longest_gap, 1),
        },
        "blanks": blank_out, "route_gaps": gap_out, "stops_need_landmark": stop_out,
    }


def suggest(kind, nm, where):
    nature = ["树丛", "草丛", "石头"]
    if kind == "lake":
        return {"suggest_concrete": ["船", "水鸟", "码头", "岸边的村子"], "suggest_nature": ["芦苇", "岸边树丛"],
                "ask": f"{nm}的这一侧实际有什么？有船、水鸟、码头，还是村子？"}
    if kind == "foot":
        return {"suggest_concrete": ["寺庙或观景台", "梯田或草场上的牲畜", "山脚的村子"], "suggest_nature": ["树林", "梯田", "草场"],
                "ask": f"{nm + '的' if nm else '这里'}山脚下你见过什么？有寺庙、观景台、梯田或草场吗？"}
    if kind == "stop":
        return {"suggest_concrete": ["该地的标志建筑", "当地的人物或动物"], "suggest_nature": ["树丛"],
                "ask": f"{nm}最有代表性的东西是什么？是某座建筑，还是某种动物或人？"}
    return {"suggest_concrete": ["村子", "牲畜", "路边小店"], "suggest_nature": ["草场", "田地", "树丛", "石头"],
            "ask": f"{nm + '那一带' if nm else '这一片'}你见过什么？是草场、农田，还是有村子？"}


# ───────────── 事前预估 ─────────────
def is_blank_text(v):
    return not isinstance(v, str) or not v.strip() or v.strip().startswith("在这里")


def analyze_pre(data):
    stops = []   # (id, name, things)
    if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("stops"), list)):
        lst = data if isinstance(data, list) else data["stops"]
        for s in lst:
            stops.append((s.get("id"), s.get("name") or s.get("zh") or s.get("id"), 0))
    elif isinstance(data, dict) and isinstance(data.get("stops"), dict):
        for sid, s in data["stops"].items():
            info = s.get("info") or {}
            things = sum(1 for v in info.values() if not is_blank_text(v)) + len(s.get("media") or [])
            stops.append((sid, s.get("zh") or s.get("name") or sid, things))
    n = len(stops)
    slots = n + sum(min(t, 3) for _, _, t in stops)
    poor = [(sid, nm) for sid, nm, t in stops if t < 2]
    zones = {
        "站点数": zone_hi(n, PRE_STOPS_PASS, PRE_STOPS_EMPTY),
        "内容点数": zone_hi(slots, PRE_SLOTS_PASS, PRE_SLOTS_EMPTY),
    }
    verdict = "空" if any(z != "ok" for z in zones.values()) else "及格"
    asks = []
    if n < PRE_STOPS_PASS:
        asks.append("除了这几站，路上还有哪些值得画上去的地方？比如观景点、吃饭的小镇、路过的湖或村子。")
    for sid, nm in poor[:5]:
        asks.append(f"{nm}：你在那里看到、吃到、住到什么？有没有一样最能代表它的东西（建筑、动物、人、船、车）？")
    if len(poor) > 5:
        asks.append(f"其余 {len(poor) - 5} 个站点也这样问：你在那里见过什么？有没有最能代表它的东西？")
    asks.append("两站之间的路上，你见过什么？比如牛羊、村子、桥、加油站、路边摊。")
    return {"verdict": verdict, "zones": zones,
            "metrics": {"stops": n, "content_slots": slots, "stops_with_few_things": [nm for _, nm in poor]},
            "ask": asks}


# ───────────── 输出 ─────────────
ZONE_TXT = {"ok": "及格", "grey": "不够", "empty": "空"}


def print_report(r):
    m = r["metrics"]
    z = r["zones"]
    print(f"画面饱满度：{r['verdict']}")
    if r["verdict"] == "空" and "empty" not in z.values():
        print("（没有哪一项严重偏空，但有几项没到及格线，所以还要再补。）")
    print()
    print(f"- 覆盖率 {m['coverage']*100:.0f}%（{m['covered_cells']}/{m['cells']} 格有内容），{ZONE_TXT[z['覆盖率']]}。及格线 {COVER_PASS*100:.0f}%。")
    print(f"- 最大空白半径 {m['max_empty_radius']}，{ZONE_TXT[z['最大空白']]}。及格线 {m['max_empty_pass']}。")
    print(f"- 站点地标：{m['stops'] - len(m['stops_without_landmark'])}/{m['stops']} 个站点周围有地标，{ZONE_TXT[z['站点地标']]}。")
    print(f"- 活物（动物、人、车、船）{m['living']} 个，至少要 {m['living_needed']} 个，{ZONE_TXT[z['活物数量']]}。")
    print(f"- 种类 {m['types']} 种，至少 {TYPES_PASS} 种，{ZONE_TXT[z['种类数']]}。")
    print(f"- 路线上最长的空段 {m['longest_route_gap']}，{ZONE_TXT[z['路段空白']]}。及格线 {ROUTE_GAP_PASS:g}。")
    if r["verdict"] in ("及格", "饱满"):
        print("\n不用再补。想更满可以按上面几项继续加；如果是有意留白，保持就好。")
        return
    print("\n哪里空，可以问用户什么：")
    k = 0
    for b in r["blanks"]:
        k += 1
        print(f"\n{k}. {b['where']}有一大片空白。")
        print(f"   可以直接补（自然填充，不用问）：{'、'.join(b['suggest_nature'])}。")
        print(f"   具体的东西要问用户，给他选：{'、'.join(b['suggest_concrete'])}。")
        print(f"   问：{b['ask']}")
    for gp in r["route_gaps"]:
        k += 1
        print(f"\n{k}. {gp['where']}很空（连续约 {gp['len']:g} 个单位没有东西）。")
        print(f"   可以直接补（自然填充，不用问）：{'、'.join(gp['suggest_nature'])}。")
        print(f"   具体的东西要问用户，给他选：{'、'.join(gp['suggest_concrete'])}。")
        print(f"   问：{gp['ask']}")
    for s in r["stops_need_landmark"]:
        k += 1
        print(f"\n{k}. {s['name']}周围没有地标。")
        print(f"   问：{s['ask']}")
    if z["活物数量"] != "ok":
        k += 1
        print(f"\n{k}. 画面里活物太少。")
        print("   问：这一路上你见过哪些动物、人、车或船？比如牛羊、马、水鸟、渡船。用户说过的才能放。")
    if z["种类数"] != "ok":
        k += 1
        print(f"\n{k}. 东西种类太单一。")
        print("   自然填充可以直接换花样（树换几种、加草丛、石头）；具体的东西要问用户。")
    print("\n补完重跑本脚本，到「及格」为止。用户明确说「就这样」可以跳过。")
    print("界线：树、草丛、石头、云、普通田地可以自己按当地地貌补；建筑、动物、人、船、车、地标必须是用户说过或确认过的。")


def print_pre(r):
    m, z = r["metrics"], r["zones"]
    print(f"事前预估：{r['verdict']}（还没摆构图，只看内容地图）\n")
    print(f"- 站点 {m['stops']} 个，{ZONE_TXT[z['站点数']]}。至少 {PRE_STOPS_PASS} 个更稳。")
    print(f"- 内容点 {m['content_slots']} 个（站点数加上用户已经说过的具体事物），{ZONE_TXT[z['内容点数']]}。至少 {PRE_SLOTS_PASS} 个。")
    if m["stops_with_few_things"]:
        print(f"- 这些站点几乎没有具体内容：{'、'.join(m['stops_with_few_things'])}。")
    if r["verdict"] == "空":
        print("\n按现在的内容地图，画面会比较空。建议先问用户这些：")
        for q in r["ask"]:
            print(f"- {q}")
        print("\n用户回答之前，不要自己编站点和景物。树、草丛这类自然填充可以到构图时再补。")
    else:
        print("\n内容够摆一张像样的构图，可以往下走。")


def main():
    ap = argparse.ArgumentParser(description="检查微缩景观的画面饱满度")
    ap.add_argument("files", nargs="+", help="scene.json [trip.json]；--pre 时给 stops.json 或 trip.json")
    ap.add_argument("--pre", action="store_true", help="事前预估：只有站点清单或 trip 草稿，没有 scene")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()
    try:
        data = [json.loads(Path(f).read_text(encoding="utf-8")) for f in args.files]
    except (OSError, json.JSONDecodeError) as e:
        print(f"读不了文件：{e}")
        return 2
    if args.pre:
        res = analyze_pre(data[0])
        out = print_pre
    else:
        if not isinstance(data[0], dict) or not data[0].get("stops"):
            print("scene.json 里没有 stops，没法检查。")
            return 2
        res = analyze(data[0], data[1] if len(data) > 1 else None)
        out = print_report
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, default=list))
    else:
        out(res)
    return 1 if res["verdict"] == "空" else 0


if __name__ == "__main__":
    sys.exit(main())
