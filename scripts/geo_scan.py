#!/usr/bin/env python3
"""geo_scan.py -- 地理骨架扫描 (geographic skeleton scan)

Turns a list of trip stops (or just a bounding box) into:
  skeleton.json         machine-readable geographic facts
  skeleton_card.md      Chinese card for the user to confirm or correct
  skeleton_preview.png  quick map: contour bands, water, stops, compass, camera direction
  scene.draft.json      first-draft diorama layout (see references/scene-schema.md)

Principle: bearings are real, distances are compressed, scale is not real.

No API key, no registration. Public data only:
  - elevation: AWS Open Data "Terrarium" tiles
  - water / coast / named peaks: OpenStreetMap via Overpass (optional, degrades gracefully)
  - geocoding: OSM Nominatim (only for stops without lat/lon, <=1 request/second)
  - road shape: OSRM public demo server (optional, falls back to straight lines)
Requires: Python 3.9+, numpy, Pillow.

Usage:
  python3 geo_scan.py stops.json --out scan/
  python3 geo_scan.py --bbox 80.5 42.4 83.4 44.9 --out scan/
  python3 geo_scan.py stops.json --view-from W --season summer --name "My Trip"

stops.json:
  [ {"id": "a", "name": "Place A", "lat": 44.6, "lon": 81.18}, {"id": "b", "name": "Place B"} ]
  or {"stops": [...], "days": [ {"id": "D1", "stops": ["a", "b"]} ]}
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError as _e:  # pragma: no cover
    sys.exit(
        "缺少依赖：%s\n请先安装：  python3 -m pip install numpy Pillow\n"
        "(Missing dependency. Install with: python3 -m pip install numpy Pillow)" % _e
    )

UA = "paper-roadbook-skill/1.0 (open-source travel diorama tool)"
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org/route/v1/driving/"

DIR8_EN = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
DIR8_ZH = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
DIR8_DEG = {d: i * 45 for i, d in enumerate(DIR8_EN)}
ZH = dict(zip(DIR8_EN, DIR8_ZH))

BOARD_A, BOARD_B = 62.0, 46.0


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def log(*a):
    print(*a, file=sys.stderr, flush=True)


def die(msg, hint=None):
    log("\n[geo_scan 出错] " + msg)
    if hint:
        log("怎么办：" + hint)
    sys.exit(1)


def _curl(url, data, timeout):
    """Fallback for old Python/LibreSSL builds that cannot complete some TLS handshakes."""
    import shutil
    import subprocess
    exe = shutil.which("curl")
    if not exe:
        raise OSError("TLS 握手失败，且系统里没有 curl 可作备用。可升级 Python（python.org 或 Homebrew 版）。")
    cmd = [exe, "-sS", "-L", "-m", str(timeout), "-A", UA, "-f"]
    if data is not None:
        cmd += ["--data-binary", "@-"]
    cmd.append(url)
    r = subprocess.run(cmd, input=data, capture_output=True)
    if r.returncode != 0:
        raise OSError("curl 失败：%s" % r.stderr.decode("utf-8", "ignore").strip()[:200])
    return r.stdout


def http(url, data=None, timeout=45, retries=3, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 502, 503, 504):
                time.sleep(2 + 3 * i)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            if "SSL" in repr(e) or "ssl" in repr(e):
                try:
                    return _curl(url, data, timeout)
                except OSError as e2:
                    last = e2
                    break
            time.sleep(1.5 * (i + 1))
    raise last


def bearing(dx_east, dy_north):
    return (math.degrees(math.atan2(dx_east, dy_north)) + 360) % 360


def dir8(deg):
    return DIR8_EN[int(((deg % 360) + 22.5) // 45) % 8]


def haversine(lon1, lat1, lon2, lat2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1, math.sqrt(a)))


def slug(s, fallback):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or fallback


def rdp(pts, eps):
    """Douglas-Peucker on [(x,y)...]."""
    if len(pts) < 3:
        return list(pts)
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1e-9
    dmax, idx = -1, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * (pts[i][0] - x1) - dx * (pts[i][1] - y1)) / L
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        a = rdp(pts[: idx + 1], eps)
        b = rdp(pts[idx:], eps)
        return a[:-1] + b
    return [pts[0], pts[-1]]


def simplify_to(pts, n):
    """Reduce polyline to at most n points by growing the DP tolerance."""
    if len(pts) <= n:
        return list(pts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    eps = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.005 + 1e-9
    out = pts
    for _ in range(40):
        out = rdp(pts, eps)
        if len(out) <= n:
            return out
        eps *= 1.35
    return [pts[0], pts[-1]]


def label_components(mask):
    h, w = mask.shape
    lab = np.zeros((h, w), dtype=np.int32)
    sizes = [0]
    n = 0
    for sy in range(h):
        for sx in range(w):
            if mask[sy, sx] and lab[sy, sx] == 0:
                n += 1
                q = deque([(sy, sx)])
                lab[sy, sx] = n
                cnt = 0
                while q:
                    y, x = q.popleft()
                    cnt += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and lab[yy, xx] == 0:
                                lab[yy, xx] = n
                                q.append((yy, xx))
                sizes.append(cnt)
    return lab, sizes


# ----------------------------------------------------------------------------
# input
# ----------------------------------------------------------------------------
def load_stops(path):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        die("找不到站点文件：%s" % path, "检查路径；或改用 --bbox W S E N 只扫描一个范围。")
    except json.JSONDecodeError as e:
        die("站点文件不是合法 JSON：%s" % e, "格式见脚本顶部说明：[{id,name,lat,lon}]。")
    days = []
    if isinstance(raw, dict):
        stops = raw.get("stops") or []
        days = raw.get("days") or []
    else:
        stops = raw
    if isinstance(stops, dict):  # trip.json style {id: {...}}
        stops = [dict(v, id=k) for k, v in stops.items()]
    out = []
    for i, s in enumerate(stops):
        if not isinstance(s, dict):
            die("站点第 %d 项不是对象。" % (i + 1))
        sid = str(s.get("id") or slug(str(s.get("name", "")), "s%d" % (i + 1)))
        name = str(s.get("name") or s.get("zh") or sid)
        out.append({"id": sid, "name": name, "lat": s.get("lat"), "lon": s.get("lon")})
    ids = [s["id"] for s in out]
    if len(set(ids)) != len(ids):
        die("站点 id 有重复：%s" % ids)
    return out, days


def geocode(stops, out_dir, offline=False):
    cache_f = out_dir / "cache" / "geocode.json"
    cache = {}
    if cache_f.exists():
        try:
            cache = json.loads(cache_f.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    missing = []
    last = 0.0
    for s in stops:
        if s["lat"] is not None and s["lon"] is not None:
            s["lat"], s["lon"], s["geocoded"] = float(s["lat"]), float(s["lon"]), False
            continue
        key = s["name"]
        if key in cache:
            s["lat"], s["lon"], s["geocoded"] = cache[key][0], cache[key][1], True
            continue
        if offline:
            missing.append(s["name"])
            continue
        wait = 1.1 - (time.time() - last)
        if wait > 0:
            time.sleep(wait)  # Nominatim policy: max 1 request/second
        last = time.time()
        url = NOMINATIM + "?" + urllib.parse.urlencode({"q": s["name"], "format": "jsonv2", "limit": 5})
        try:
            res = json.loads(http(url, timeout=30).decode("utf-8"))
        except Exception as e:
            die("地理编码失败（%s）：%s" % (s["name"], e),
                "网络不通或被限流。可以稍后重试，或在站点清单里直接给 lat/lon 后重跑。")
        if not res:
            missing.append(s["name"])
            continue
        # prefer a point feature (a town/peak/lake node) over an administrative-area centroid
        best = next((r for r in res if r.get("osm_type") == "node"), res[0])
        s["lat"], s["lon"], s["geocoded"] = float(best["lat"]), float(best["lon"]), True
        cache[key] = [s["lat"], s["lon"]]
        log("  地理编码  %s -> %.4f, %.4f  (%s)" % (s["name"], s["lat"], s["lon"], best.get("display_name", "")[:60]))
    if missing:
        die("这些站点没有查到坐标：%s" % "、".join(missing),
            "在站点清单里给这些站点补上 lat/lon（可以在地图应用里长按取坐标）后重跑。")
    cache_f.parent.mkdir(parents=True, exist_ok=True)
    cache_f.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def auto_bbox(stops, margin):
    lons = [s["lon"] for s in stops]
    lats = [s["lat"] for s in stops]
    w, e, s_, n = min(lons), max(lons), min(lats), max(lats)
    clat = (s_ + n) / 2
    kx = 111.32 * math.cos(math.radians(clat))
    spanx, spany = (e - w), (n - s_)
    mx = max(spanx * margin, 0.12)
    my = max(spany * margin, 0.12)
    w, e, s_, n = w - mx, e + mx, s_ - my, n + my
    # keep the aspect between 1:2.4 and 2.4:1 (in km) so the map is not a sliver
    wk, hk = (e - w) * kx, (n - s_) * 110.57
    if wk < hk / 2.4:
        need = hk / 2.4 / kx
        c = (w + e) / 2
        w, e = c - need / 2, c + need / 2
    elif hk < wk / 2.4:
        need = wk / 2.4 / 110.57
        c = (s_ + n) / 2
        s_, n = c - need / 2, c + need / 2
    return [round(max(-180, w), 4), round(max(-80, s_), 4), round(min(180, e), 4), round(min(80, n), 4)]


# ----------------------------------------------------------------------------
# DEM
# ----------------------------------------------------------------------------
def gpx(lon, lat, z):
    n = 2 ** z * 256
    lat = max(-85.0511, min(85.0511, lat))
    x = (lon + 180) / 360 * n
    r = math.radians(lat)
    y = (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n
    return x, y


def gpx_inv(x, y, z):
    n = 2 ** z * 256
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def choose_zoom(bbox, forced=None):
    if forced:
        return forced
    W, S, E, N = bbox
    for z in range(14, 2, -1):
        x0, y0 = gpx(W, N, z)
        x1, y1 = gpx(E, S, z)
        if max(x1 - x0, y1 - y0) <= 1100:
            return z
    return 3


def fetch_dem(bbox, z, cache_dir):
    W, S, E, N = bbox
    x0, y0 = gpx(W, N, z)
    x1, y1 = gpx(E, S, z)
    tx0, tx1 = int(x0 // 256), int(x1 // 256)
    ty0, ty1 = int(y0 // 256), int(y1 // 256)
    count = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    if count > 80:
        die("范围太大，需要 %d 张高程瓦片。" % count, "缩小 --bbox，或用 --zoom 指定更小的缩放级别。")
    cache_dir.mkdir(parents=True, exist_ok=True)
    maxt = 2 ** z

    def get(t):
        tx, ty = t
        f = cache_dir / ("dem_%d_%d_%d.png" % (z, tx, ty))
        if f.exists() and f.stat().st_size > 100:
            return t, f.read_bytes(), None
        try:
            b = http(TILE_URL.format(z=z, x=tx % maxt, y=ty), timeout=40)
            f.write_bytes(b)
            return t, b, None
        except Exception as e:
            return t, None, e

    tiles = [(x, y) for y in range(ty0, ty1 + 1) for x in range(tx0, tx1 + 1)]
    log("下载高程瓦片 z=%d，共 %d 张（已缓存的会跳过）…" % (z, count))
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(get, tiles))
    bad = [(t, e) for t, b, e in results if b is None]
    if bad:
        die("高程瓦片下载失败 %d/%d 张：%s" % (len(bad), count, bad[0][1]),
            "多半是没联网或网络受限。检查网络后重跑（已下载的瓦片会复用）；"
            "若确实无法联网，可手写骨架卡，直接按 references/composition-guide.md 构图。")
    mosaic = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), dtype=np.float32)
    for (tx, ty), b, _ in results:
        import io
        im = np.array(Image.open(io.BytesIO(b)).convert("RGB")).astype(np.float32)
        elev = im[..., 0] * 256 + im[..., 1] + im[..., 2] / 256 - 32768
        mosaic[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = elev
    ox, oy = int(math.floor(x0)), int(math.floor(y0))
    cw, ch = int(math.ceil(x1)) - ox, int(math.ceil(y1)) - oy
    crop = mosaic[oy - ty0 * 256: oy - ty0 * 256 + ch, ox - tx0 * 256: ox - tx0 * 256 + cw]
    return crop, {"z": z, "ox": ox, "oy": oy, "cw": cw, "ch": ch}


class Geo:
    """Coordinate conversions on one scan: lon/lat <-> crop pixel <-> local km plane."""

    def __init__(self, bbox, meta):
        self.bbox = bbox
        self.z, self.ox, self.oy, self.cw, self.ch = meta["z"], meta["ox"], meta["oy"], meta["cw"], meta["ch"]
        self.lon0 = (bbox[0] + bbox[2]) / 2
        self.lat0 = (bbox[1] + bbox[3]) / 2
        self.kx = 111.32 * math.cos(math.radians(self.lat0))
        self.ky = 110.57

    def px(self, lon, lat):
        x, y = gpx(lon, lat, self.z)
        return x - self.ox, y - self.oy

    def ll_from_px(self, x, y):
        return gpx_inv(x + self.ox, y + self.oy, self.z)

    def km(self, lon, lat):
        return (lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky

    def ll(self, kx, ky):
        return self.lon0 + kx / self.kx, self.lat0 + ky / self.ky


# ----------------------------------------------------------------------------
# OSM / Overpass (optional)
# ----------------------------------------------------------------------------
OSM_DEADLINE = [None]  # wall-clock deadline shared by all Overpass queries (set in main)


def overpass(query, cache_dir, label, offline=False):
    key = hashlib.sha1(query.encode()).hexdigest()[:12]
    f = cache_dir / ("osm_%s_%s.json" % (label, key))
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8")), None
        except Exception:
            pass
    if offline:
        return None, "offline"
    data = urllib.parse.urlencode({"data": query}).encode()
    err = None
    for n_try, url in enumerate(OVERPASS):
        if n_try > 0 and OSM_DEADLINE[0] and time.time() > OSM_DEADLINE[0]:
            return None, "OSM 查询总时间预算用完（%s）" % (err or "服务器很慢")
        try:
            raw = http(url, data=data, timeout=45, retries=1)
            js = json.loads(raw.decode("utf-8"))
            if "elements" not in js:
                raise ValueError("no elements")
            cache_dir.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(js), encoding="utf-8")
            return js, None
        except Exception as e:
            err = "%s: %s" % (url.split("/")[2], e)
            time.sleep(1)
    return None, err


def clean_name(tags):
    """Prefer a Chinese name; strip other scripts from multi-language OSM names."""
    for k in ("name:zh", "name:zh-Hans", "name:en"):
        if tags.get(k):
            return tags[k]
    n = tags.get("name") or ""
    m = re.findall(r"[\u3400-\u9fff][\u3400-\u9fff·\-（）()]*", n)
    if m:
        return m[0]
    return n.split(" ")[0] if re.search(r"[\u0600-\u06ff\u1800-\u18af]", n) else n


def _pca2(points):
    a = np.array(points, dtype=np.float64)
    c = a.mean(axis=0)
    cov = np.cov((a - c).T) if len(a) > 2 else np.eye(2)
    vals, vecs = np.linalg.eigh(cov)
    return c, np.maximum(vals, 1e-9), vecs


def _geom(points):
    """Overpass `out geom(bbox)` puts null for nodes outside the box; skip those."""
    return [(p["lon"], p["lat"]) for p in points if p]


def fetch_osm(geo, args, cache_dir):
    """Return dict(lakes, rivers, coast, peaks, status)."""
    W, S, E, N = geo.bbox
    bb = "%.4f,%.4f,%.4f,%.4f" % (S, W, N, E)
    res = {"lakes": [], "rivers": [], "coast": [], "peaks": [], "ranges": [], "status": {}}
    if args.no_osm:
        res["status"] = {k: "skipped (--no-osm)" for k in ("lakes", "rivers", "coast", "peaks")}
        return res
    off = args.offline

    # --- lakes: rank by bbox area first, then fetch geometry for the top ones
    try:
        q = ('[out:json][timeout:80];(way["natural"="water"]["water"~"^(lake|reservoir|basin)$"](%s);'
             'relation["natural"="water"]["water"~"^(lake|reservoir|basin)$"](%s);'
             'way["natural"="water"][!"water"]["name"](%s);'
             'relation["natural"="water"][!"water"]["name"](%s););out bb tags 600;') % (bb, bb, bb, bb)
        js, err = overpass(q, cache_dir, "lakes_bb", off)
        if js is None:
            res["status"]["lakes"] = "failed: %s" % err
        else:
            cand = []
            for el in js["elements"]:
                b = el.get("bounds")
                if not b:
                    continue
                wk = (b["maxlon"] - b["minlon"]) * geo.kx
                hk = (b["maxlat"] - b["minlat"]) * geo.ky
                cand.append((wk * hk * 0.7, el))
            cand.sort(key=lambda t: -t[0])
            total_km2 = (E - W) * geo.kx * (N - S) * geo.ky
            top = [c for c in cand if c[0] >= 0.003 * total_km2][: args.lakes]
            res["status"]["lakes"] = "ok (%d candidates, using %d)" % (len(cand), len(top))
            # first-pass lakes from bounding boxes (ellipse approximation); refined below if geometry arrives
            by_key = {}
            for area, el in top:
                bd = el["bounds"]
                cx, cy = geo.km((bd["minlon"] + bd["maxlon"]) / 2, (bd["minlat"] + bd["maxlat"]) / 2)
                wk = (bd["maxlon"] - bd["minlon"]) * geo.kx
                hk = (bd["maxlat"] - bd["minlat"]) * geo.ky
                tags = el.get("tags", {})
                lk = {"name": clean_name(tags),
                      "center_km": [cx, cy], "major_km": max(wk, hk) / 2, "minor_km": min(wk, hk) / 2,
                      "major_dir": [1.0, 0.0] if wk >= hk else [0.0, 1.0],
                      "rings": [[(bd["minlon"], bd["minlat"]), (bd["maxlon"], bd["minlat"]), (bd["maxlon"], bd["maxlat"]),
                                 (bd["minlon"], bd["maxlat"]), (bd["minlon"], bd["minlat"])]],
                      "area_km2": area, "approx": True}
                by_key[(el["type"], el["id"])] = lk
                res["lakes"].append(lk)
            if top:
                ids_w = [str(e["id"]) for _, e in top if e["type"] == "way"]
                ids_r = [str(e["id"]) for _, e in top if e["type"] == "relation"]
                parts = []
                if ids_w:
                    parts.append("way(id:%s);" % ",".join(ids_w))
                if ids_r:
                    parts.append("relation(id:%s);" % ",".join(ids_r))
                q2 = "[out:json][timeout:60];(%s);out geom tags;" % "".join(parts)
                js2, err2 = overpass(q2, cache_dir, "lakes_geom", off)
                if js2 is None:
                    res["status"]["lakes"] = "ok but outlines approximated from bounding boxes (geometry query failed: %s)" % err2
                else:
                    for el in js2["elements"]:
                        rings = []
                        if el["type"] == "way" and el.get("geometry"):
                            rings.append(_geom(el["geometry"]))
                        elif el["type"] == "relation":
                            for m in el.get("members", []):
                                if m.get("type") == "way" and m.get("role") in ("outer", "") and m.get("geometry"):
                                    rings.append(_geom(m["geometry"]))
                        pts = [p for r in rings for p in r]
                        lk = by_key.get((el["type"], el["id"]))
                        if len(pts) < 4 or lk is None:
                            continue
                        kms = [geo.km(*p) for p in pts]
                        c, vals, vecs = _pca2(kms)
                        major = vecs[:, 1]
                        lk.update({"center_km": [float(c[0]), float(c[1])], "major_km": float(math.sqrt(2 * vals[1])),
                                   "minor_km": float(math.sqrt(2 * vals[0])), "major_dir": [float(major[0]), float(major[1])],
                                   "rings": rings, "approx": False})
            res["lakes"].sort(key=lambda l: -l["area_km2"])
        time.sleep(1)
    except Exception as e:  # never let a surprising OSM reply kill the scan
        res["status"]["lakes"] = "failed (unexpected data: %r)" % (e,)

    # --- rivers: rank named rivers by extent first (small reply), then fetch geometry for the top few
    try:
        q = '[out:json][timeout:60];way["waterway"="river"]["name"](%s);out bb tags 2500;' % bb
        js, err = overpass(q, cache_dir, "rivers_bb", off)
        if js is None:
            res["status"]["rivers"] = "failed: %s" % err
        else:
            groups = {}
            for el in js["elements"]:
                b = el.get("bounds")
                if not b:
                    continue
                t = el.get("tags", {})
                nm = clean_name(t) or None
                ext = math.hypot((b["maxlon"] - b["minlon"]) * geo.kx, (b["maxlat"] - b["minlat"]) * geo.ky)
                g = groups.setdefault(nm, {"ids": [], "ext": 0.0})
                g["ids"].append(el["id"])
                g["ext"] += ext
            ranked = sorted(groups.items(), key=lambda kv: -kv[1]["ext"])[: args.rivers]
            res["status"]["rivers"] = "ok (%d named rivers in range, using %d)" % (len(groups), len(ranked))
            if ranked:
                ids = [str(i) for _, g in ranked for i in g["ids"]]
                q2 = "[out:json][timeout:60];way(id:%s);out geom(%s);" % (",".join(ids), bb)
                js2, err2 = overpass(q2, cache_dir, "rivers_geom", off)
                if js2 is None:
                    res["status"]["rivers"] = "failed (geometry): %s" % err2
                else:
                    geoms = {el["id"]: _geom(el["geometry"]) for el in js2["elements"] if el.get("geometry")}
                    for nm, g in ranked:
                        ways = [geoms[i] for i in g["ids"] if i in geoms and len(geoms[i]) >= 2]
                        if not ways:
                            continue
                        line = _chain(ways)
                        length = sum(haversine(*line[i], *line[i + 1]) for i in range(len(line) - 1))
                        res["rivers"].append({"name": nm, "line": line, "length_km": length})
                    res["rivers"].sort(key=lambda r: -r["length_km"])
        time.sleep(1)
    except Exception as e:  # never let a surprising OSM reply kill the scan
        res["status"]["rivers"] = "failed (unexpected data: %r)" % (e,)

    # --- coastline
    try:
        q = '[out:json][timeout:80];way["natural"="coastline"](%s);out geom(%s) 800;' % (bb, bb)
        js, err = overpass(q, cache_dir, "coast", off)
        if js is None:
            res["status"]["coast"] = "failed: %s" % err
        else:
            res["coast"] = [_geom(el["geometry"]) for el in js["elements"] if el.get("geometry")]
            res["status"]["coast"] = "ok (%d ways)" % len(res["coast"])
        time.sleep(1)
    except Exception as e:  # never let a surprising OSM reply kill the scan
        res["status"]["coast"] = "failed (unexpected data: %r)" % (e,)
    # --- named peaks and mountain ranges
    try:
        q = ('[out:json][timeout:60];(node["natural"="peak"]["name"](%s);'
             'nwr["natural"~"^(mountain_range|ridge)$"]["name"](%s););out center tags 500;') % (bb, bb)
        js, err = overpass(q, cache_dir, "peaks2", off)
        if js is None:
            res["status"]["peaks"] = "failed: %s" % err
        else:
            for el in js["elements"]:
                t = el.get("tags", {})
                lon = el.get("lon", (el.get("center") or {}).get("lon"))
                lat = el.get("lat", (el.get("center") or {}).get("lat"))
                if lon is None or lat is None:
                    continue
                nm = clean_name(t)
                if t.get("natural") == "peak":
                    ele = None
                    try:
                        ele = float(str(t.get("ele", "")).split()[0].replace(",", "."))
                    except Exception:
                        pass
                    res["peaks"].append({"name": nm, "lon": lon, "lat": lat, "ele": ele})
                else:
                    res["ranges"].append({"name": nm, "lon": lon, "lat": lat})
            res["status"]["peaks"] = "ok (%d named peaks, %d named ranges)" % (len(res["peaks"]), len(res["ranges"]))
    except Exception as e:  # never let a surprising OSM reply kill the scan
        res["status"]["peaks"] = "failed (unexpected data: %r)" % (e,)

    return res




def _chain(ways):
    """Greedy-join OSM ways that share end points; return the longest chain."""
    ways = [list(w) for w in ways]
    chains = []
    while ways:
        cur = ways.pop(0)
        grew = True
        while grew:
            grew = False
            for i, w in enumerate(ways):
                if w[0] == cur[-1]:
                    cur += w[1:]
                elif w[-1] == cur[0]:
                    cur = w[:-1] + cur
                elif w[-1] == cur[-1]:
                    cur += w[::-1][1:]
                elif w[0] == cur[0]:
                    cur = w[::-1][:-1] + cur
                else:
                    continue
                ways.pop(i)
                grew = True
                break
        chains.append(cur)
    chains.sort(key=lambda c: -len(c))
    return chains[0]


# ----------------------------------------------------------------------------
# terrain analysis
# ----------------------------------------------------------------------------
class Terrain:
    def __init__(self, dem, geo):
        self.dem = dem
        self.geo = geo
        gw = min(200, dem.shape[1])
        gh = max(8, int(round(gw * dem.shape[0] / dem.shape[1])))
        self.gw, self.gh = gw, gh
        im = Image.fromarray(dem.astype(np.float32)).resize((gw, gh), Image.BOX)
        self.z = np.array(im, dtype=np.float32)
        # km coordinates of grid centres
        cols = [(i + 0.5) * geo.cw / gw for i in range(gw)]
        rows = [(j + 0.5) * geo.ch / gh for j in range(gh)]
        self.KX = np.array([geo.km(*geo.ll_from_px(c, geo.ch / 2))[0] for c in cols])
        self.KY = np.array([geo.km(*geo.ll_from_px(geo.cw / 2, r))[1] for r in rows])
        self.dx_km = float(abs(self.KX[1] - self.KX[0])) if gw > 1 else 1.0
        self.dy_km = float(abs(self.KY[1] - self.KY[0])) if gh > 1 else 1.0
        self.size_km = (float(abs(self.KX[-1] - self.KX[0]) + self.dx_km), float(abs(self.KY[0] - self.KY[-1]) + self.dy_km))
        self.diag_km = math.hypot(*self.size_km)
        # sea: z<=0 and connected to the map edge or big (not an inland depression)
        sea0 = self.z <= 0.0
        lab, sizes = label_components(sea0)
        sea = np.zeros_like(sea0)
        edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist()) - {0}
        for k in range(1, len(sizes)):
            if k in edge or sizes[k] >= 0.03 * gw * gh:
                sea |= lab == k
        self.sea = sea
        land = self.z[~sea]
        if land.size < 20:
            land = self.z.ravel()
        self.p10, self.p50, self.p98 = [float(np.percentile(land, q)) for q in (10, 50, 98)]
        self.p90 = float(np.percentile(land, 90))
        self.zmin, self.zmax = float(land.min()), float(land.max())
        self.relief = self.p98 - self.p10
        self.flat = self.relief < 250
        span = max(self.p98 - self.p10, 1.0)
        self.e = np.clip((self.z - self.p10) / span, 0, 1.15)
        self.e[sea] = 0.0
        KXg, KYg = np.meshgrid(self.KX, self.KY)
        self.bear = (np.degrees(np.arctan2(KXg, KYg)) + 360) % 360

    # elevation at a lon/lat on full-res DEM
    def elev_at(self, lon, lat):
        x, y = self.geo.px(lon, lat)
        xi = int(round(min(max(x, 0), self.dem.shape[1] - 1)))
        yi = int(round(min(max(y, 0), self.dem.shape[0] - 1)))
        sub = self.dem[max(0, yi - 1): yi + 2, max(0, xi - 1): xi + 2]
        return float(np.median(sub))

    def e_at_km(self, kx, ky):
        i = int(np.clip(np.argmin(np.abs(self.KX - kx)), 0, self.gw - 1))
        j = int(np.clip(np.argmin(np.abs(self.KY - ky)), 0, self.gh - 1))
        return float(self.e[j, i]), float(self.z[j, i])

    def sides(self):
        """3x3 summary. Returns cells dict and per-side classification."""
        gh, gw = self.gh, self.gw
        names = [["NW", "N", "NE"], ["W", "C", "E"], ["SW", "S", "SE"]]
        cells = {}
        for r in range(3):
            for c in range(3):
                sl = (slice(r * gh // 3, (r + 1) * gh // 3), slice(c * gw // 3, (c + 1) * gw // 3))
                cells[names[r][c]] = {"e": float(self.e[sl].mean()), "high": float((self.e[sl] >= 0.45).mean()),
                                      "sea": float(self.sea[sl].mean()),
                                      "zmax": float(self.z[sl].max()), "zmean": float(self.z[sl].mean())}
        sides = {}
        trip = {"N": ("NW", "N", "NE"), "S": ("SW", "S", "SE"), "W": ("NW", "W", "SW"), "E": ("NE", "E", "SE")}
        for s, (c1, m, c2) in trip.items():
            e_mean = (cells[c1]["e"] + cells[m]["e"] + cells[c2]["e"]) / 3
            high = (cells[c1]["high"] + cells[m]["high"] + cells[c2]["high"]) / 3
            sea = (cells[c1]["sea"] + cells[m]["sea"] + cells[c2]["sea"]) / 3
            corner = (cells[c1]["e"] + cells[c2]["e"]) / 2
            kind = "mid"
            if sea > 0.35:
                kind = "sea"
            elif self.flat:
                kind = "flat"
            elif cells[m]["e"] < 0.42 and cells[m]["e"] <= corner - 0.12:
                kind = "opening"
            elif e_mean >= 0.5 or high >= 0.3:
                kind = "wall"
            elif e_mean >= 0.3:
                kind = "hills"
            else:
                kind = "low"
            sides[s] = {"e": e_mean, "high": high, "sea": sea, "mid_e": cells[m]["e"], "corner_e": corner, "kind": kind}
        return cells, sides

    def wedge(self, center_deg, half=45.0):
        d = np.abs(((self.bear - center_deg + 180) % 360) - 180)
        m = d <= half
        if not m.any():
            return 0.0, 0.0
        return float(self.e[m].mean()), float(self.sea[m].mean())

    def find_peaks(self, osm_peaks, want=8, pool=24):
        if self.flat:
            return [], []
        k = np.ones((3, 3)) / 9.0
        pad = np.pad(self.z, 1, mode="edge")
        sm = sum(pad[i:i + self.gh, j:j + self.gw] * k[i, j] for i in range(3) for j in range(3))
        sm[self.sea] = -1e9
        order = np.dstack(np.unravel_index(np.argsort(-sm, axis=None), sm.shape))[0]
        radius = 0.07 * self.diag_km
        floor_z = self.p50 + 0.3 * (self.p98 - self.p50)
        picked = []
        for j, i in order:
            zv = float(sm[j, i])
            if zv < floor_z or len(picked) >= pool:
                break
            kx, ky = float(self.KX[i]), float(self.KY[j])
            if all(math.hypot(kx - p["kx"], ky - p["ky"]) >= radius for p in picked):
                picked.append({"kx": kx, "ky": ky, "elev": zv, "gi": int(i), "gj": int(j)})
        # names from OSM within 10 km (prefer the highest tagged one nearby)
        for p in picked:
            lon, lat = self.geo.ll(p["kx"], p["ky"])
            p["lon"], p["lat"] = lon, lat
            p["e"] = float(np.clip((p["elev"] - self.p10) / max(self.relief, 1), 0, 1.15))
            best = None
            for op in osm_peaks:
                dkm = haversine(lon, lat, op["lon"], op["lat"])
                if dkm <= 10 and (best is None or (op["ele"] or 0) > (best["ele"] or 0)):
                    best = op
            p["name"] = best["name"] if best else ""
        # ranges: join peaks along ridges when the saddle between them stays high
        n = len(picked)
        lo = self.p10
        edges = []
        for a in range(n):
            for b in range(a + 1, n):
                pa, pb = picked[a], picked[b]
                d = math.hypot(pa["kx"] - pb["kx"], pa["ky"] - pb["ky"])
                if d > 0.34 * self.diag_km:
                    continue
                saddle = min(self._line_min(pa, pb, 28), min(pa["elev"], pb["elev"]))
                if saddle >= lo + 0.5 * (min(pa["elev"], pb["elev"]) - lo):
                    edges.append((d, a, b))
        edges.sort()
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        tree = {i: [] for i in range(n)}
        for d, a, b in edges:  # Kruskal -> MST forest
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
                tree[a].append((b, d))
                tree[b].append((a, d))
        seen, ranges = set(), []
        for s in range(n):
            if s in seen:
                continue
            comp = [s]
            seen.add(s)
            dq = deque([s])
            while dq:
                u = dq.popleft()
                for v, _ in tree[u]:
                    if v not in seen:
                        seen.add(v)
                        comp.append(v)
                        dq.append(v)
            if len(comp) < 2:
                continue
            ranges.append(self._order_along_axis(picked, comp))
        return picked, ranges

    def _line_min(self, pa, pb, n):
        m = 1e9
        for t in np.linspace(0, 1, n):
            kx = pa["kx"] + (pb["kx"] - pa["kx"]) * t
            ky = pa["ky"] + (pb["ky"] - pa["ky"]) * t
            i = int(np.clip(np.argmin(np.abs(self.KX - kx)), 0, self.gw - 1))
            j = int(np.clip(np.argmin(np.abs(self.KY - ky)), 0, self.gh - 1))
            m = min(m, float(self.z[j, i]))
        return m

    @staticmethod
    def _order_along_axis(picked, comp):
        pts = np.array([[picked[i]["kx"], picked[i]["ky"]] for i in comp])
        c = pts.mean(axis=0)
        vals, vecs = np.linalg.eigh(np.cov((pts - c).T))
        proj = (pts - c) @ vecs[:, 1]
        return [comp[k] for k in np.argsort(proj)]

    @staticmethod
    def _diameter(tree, comp):
        def far(src):
            dist = {src: 0.0}
            prev = {}
            dq = deque([src])
            while dq:
                u = dq.popleft()
                for v, d in tree[u]:
                    if v not in dist:
                        dist[v] = dist[u] + d
                        prev[v] = u
                        dq.append(v)
            t = max(dist, key=dist.get)
            return t, prev

        a, _ = far(comp[0])
        b, prev = far(a)
        path = [b]
        while path[-1] != a:
            path.append(prev[path[-1]])
        return path


# ----------------------------------------------------------------------------
# camera direction
# ----------------------------------------------------------------------------
def choose_view(terr, sides, stops_km, forced=None):
    scores = {}
    for d in DIR8_EN:
        deg = DIR8_DEG[d]
        e_front, sea_front = terr.wedge(deg)
        e_back, sea_back = terr.wedge((deg + 180) % 360)
        s = (e_back - e_front) + 0.5 * (sea_front - sea_back)
        if d in sides and sides[d]["kind"] == "opening":
            s += 0.25
        if d in sides and sides[d]["kind"] == "sea":
            s += 0.2
        # stops spread: board is wider than deep, prefer the long axis across the screen
        if len(stops_km) >= 3:
            xs = [p[0] for p in stops_km]
            ys = [p[1] for p in stops_km]
            ex, ey = (max(xs) - min(xs)), (max(ys) - min(ys))
            long_is_ew = ex >= ey
            cross_is_ew = d in ("N", "S")
            if long_is_ew and cross_is_ew or (not long_is_ew and d in ("E", "W")):
                s += 0.08
        scores[d] = round(s, 3)
    pick = forced or max(scores, key=scores.get)
    return pick, scores


def view_reason(pick, forced, terr, sides):
    back = DIR8_EN[(DIR8_EN.index(pick) + 4) % 8]
    e_f, sea_f = terr.wedge(DIR8_DEG[pick])
    e_b, sea_b = terr.wedge(DIR8_DEG[back])
    pre = "由你指定从「%s」方向看进来。" % ZH[pick] if forced else "自动选择从「%s」方向看进来。" % ZH[pick]
    if terr.flat:
        return pre + "这片区域地势平坦，镜头方向主要由站点分布决定，你可以改成任意方向。"
    if sea_f > 0.3:
        front = "是海，朝向观众，像站在岸边看海"
    elif pick in sides and sides[pick]["kind"] == "opening":
        front = "是向外敞开的谷口或低地，朝向观众"
    elif e_f < 0.35:
        front = "地势较低，朝向观众"
    else:
        front = "地势起伏较小，朝向观众"
    if sea_b > 0.3:
        back = "是海，放在后方"
    elif e_b >= 0.35:
        back = "山地较高，排在后排当背景墙"
    else:
        back = "地势略高，排在后排"
    return pre + "「%s」侧%s；「%s」侧%s。" % (ZH[pick], front, ZH[back_dir(pick)], back)


def back_dir(d):
    return DIR8_EN[(DIR8_EN.index(d) + 4) % 8]


# ----------------------------------------------------------------------------
# scene mapping
# ----------------------------------------------------------------------------
class Mapper:
    KNEE, ASYM_RANGE = 0.55, 0.40

    def __init__(self, view_from, center_km, stops_km, a=BOARD_A, b=BOARD_B, fit=0.68):
        th = math.radians(DIR8_DEG[view_from])
        self.front = (math.sin(th), math.cos(th))
        self.right = (-math.cos(th), math.sin(th))
        self.c = center_km
        self.a, self.b = a, b
        r = 0.0
        for kx, ky in stops_km:
            x, z = self._rot(kx - center_km[0], ky - center_km[1])
            r = max(r, math.hypot(x / a, z / b))
        self.k = fit / r if r > 1e-6 else 0.4

    def _rot(self, dx, dy):
        return (dx * self.right[0] + dy * self.right[1], dx * self.front[0] + dy * self.front[1])

    def soft(self, rho):
        if rho <= self.KNEE:
            return rho
        return self.KNEE + self.ASYM_RANGE * (1 - math.exp(-(rho - self.KNEE) / self.ASYM_RANGE))

    def point(self, kx, ky):
        x, z = self._rot(kx - self.c[0], ky - self.c[1])
        x, z = x * self.k, z * self.k
        rho = math.hypot(x / self.a, z / self.b)
        if rho < 1e-9:
            return [0.0, 0.0]
        f = self.soft(rho) / rho
        return [x * f, z * f]

    def local_scale(self, kx, ky):
        x, z = self._rot(kx - self.c[0], ky - self.c[1])
        rho = math.hypot(x * self.k / self.a, z * self.k / self.b)
        return self.k * (self.soft(rho) / rho if rho > 1e-9 else 1.0)

    def vec(self, vx, vy):
        x, z = self._rot(vx, vy)
        return x, z


def rho_of(p, a=BOARD_A, b=BOARD_B):
    return math.hypot(p[0] / a, p[1] / b)


def clamp_ellipse(p, limit, a=BOARD_A, b=BOARD_B):
    r = rho_of(p, a, b)
    if r > limit:
        return [p[0] * limit / r, p[1] * limit / r]
    return p


def spread_stops(pos, min_d=13.0, limit=0.86, iters=400):
    pos = [list(p) for p in pos]
    n = len(pos)
    moved = [0.0] * n
    orig = [list(p) for p in pos]
    for it in range(iters):
        changed = False
        for i in range(n):
            for j in range(i + 1, n):
                dx, dz = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
                d = math.hypot(dx, dz)
                if d < min_d:
                    if d < 1e-6:
                        ang = (i * 2.399963 + j) % (2 * math.pi)
                        dx, dz, d = math.cos(ang), math.sin(ang), 1.0
                    push = (min_d - d) / 2 + 0.01
                    ux, uz = dx / d, dz / d
                    pos[i][0] -= ux * push
                    pos[i][1] -= uz * push
                    pos[j][0] += ux * push
                    pos[j][1] += uz * push
                    changed = True
        for i in range(n):
            pos[i] = clamp_ellipse(pos[i], limit)
        if not changed:
            break
    for i in range(n):
        moved[i] = math.hypot(pos[i][0] - orig[i][0], pos[i][1] - orig[i][1])
    return pos, moved


def r1(v, nd=1):
    return round(float(v), nd)


def _ellipse_radius(rx, rz, phi):
    return 1.0 / math.sqrt((math.cos(phi) / rx) ** 2 + (math.sin(phi) / rz) ** 2)


def pick_diverse(peaks, want):
    """Pick high peaks that are also spread out, so one huge range does not take every slot."""
    if not peaks:
        return []
    cand = sorted(peaks, key=lambda p: -p["elev"])
    chosen = [cand[0]]
    rest = cand[1:]
    top = cand[0]["elev"]
    lo = cand[-1]["elev"]
    span = max(top - lo, 1.0)
    while rest and len(chosen) < want:
        def score(p):
            dmin = min(math.hypot(p["kx"] - q["kx"], p["ky"] - q["ky"]) for q in chosen)
            return (0.35 + 0.65 * (p["elev"] - lo) / span) * min(1.0, dmin / 40.0)
        best = max(rest, key=score)
        rest.remove(best)
        chosen.append(best)
    return chosen


def build_scene(geo, terr, osm, stops, days, routes_real, view_from, args, notes):
    stops_km = [geo.km(s["lon"], s["lat"]) for s in stops]
    if stops_km:
        xs, ys = [p[0] for p in stops_km], [p[1] for p in stops_km]
        center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    else:
        center = (0.0, 0.0)
    mp = Mapper(view_from, center, stops_km)
    raw = [mp.point(*p) for p in stops_km]

    # ---- lakes first (stops that sit "in" a lake are moved to its shore)
    scene_lakes = []
    for li, lk in enumerate(osm["lakes"]):
        c = lk["center_km"]
        bpnt = clamp_ellipse(mp.point(*c), 0.9)
        sc = mp.local_scale(*c)
        rx = float(np.clip(lk["major_km"] * sc * 1.05, 5.0, 15.0))
        rz = float(np.clip(lk["minor_km"] * sc * 1.05, 0.45 * rx, rx))
        vx, vz = mp.vec(*lk["major_dir"])
        rot = math.atan2(vz, vx)
        if rot > math.pi / 2:
            rot -= math.pi
        elif rot < -math.pi / 2:
            rot += math.pi
        ident = slug(lk["name"], "") if re.search(r"[A-Za-z]", lk["name"]) else ""
        scene_lakes.append({"id": ident or "lake-%d" % (li + 1), "x": r1(bpnt[0]), "z": r1(bpnt[1]), "rx": r1(rx), "rz": r1(rz),
                            "rot": round(rot, 2), "level": 0.85, "_name": lk["name"]})
    for lk in scene_lakes:
        for i in range(len(raw)):
            dx, dz = raw[i][0] - lk["x"], raw[i][1] - lk["z"]
            u = dx * math.cos(lk["rot"]) + dz * math.sin(lk["rot"])
            v = -dx * math.sin(lk["rot"]) + dz * math.cos(lk["rot"])
            q = math.hypot(u / lk["rx"], v / lk["rz"])
            if q < 1.15:
                d = math.hypot(dx, dz)
                ux, uz = (dx / d, dz / d) if d > 1.5 else (0.0, 1.0)  # no usable offset: put it on the viewer-facing shore
                phi = math.atan2(uz, ux) - lk["rot"]
                rr = _ellipse_radius(lk["rx"], lk["rz"], phi) + 4.0
                raw[i] = clamp_ellipse([lk["x"] + ux * rr, lk["z"] + uz * rr], 0.88)
                notes.append("站点「%s」压缩后会落在湖「%s」的湖面上，草稿里已把它挪到湖岸。" % (stops[i]["name"], lk["_name"] or lk["id"]))

    pos, moved = spread_stops(raw)
    stop_pos = {s["id"]: [r1(p[0]), r1(p[1])] for s, p in zip(stops, pos)}
    shifted = [(stops[i]["name"], r1(moved[i])) for i in range(len(stops)) if moved[i] > 4]
    if shifted:
        notes.append("有 %d 个站点因为靠得太近被拉开了一些（%s，单位为盆景单位），方位基本不变。" % (
            len(shifted), "、".join("%s 约 %.0f" % x for x in shifted)))
    bearing_err = 0.0
    for i in range(len(stops)):
        for j in range(i + 1, len(stops)):
            dkm = math.hypot(stops_km[j][0] - stops_km[i][0], stops_km[j][1] - stops_km[i][1])
            if dkm < 25:
                continue  # very close pairs get pushed apart on purpose; their bearing is not meaningful
            rb = bearing(stops_km[j][0] - stops_km[i][0], stops_km[j][1] - stops_km[i][1])
            sx, sz = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
            sb = bearing(sx * mp.right[0] + sz * mp.front[0], sx * mp.right[1] + sz * mp.front[1])
            bearing_err = max(bearing_err, abs(((sb - rb + 180) % 360) - 180))
    if bearing_err > 30:
        notes.append("距离压缩后，有两个相距较远的站点之间的方位偏了 %.0f°，请在骨架卡确认时留意相对方位。" % bearing_err)

    # ---- peaks
    peaks_all, range_paths = terr.find_peaks(osm["peaks"], want=args.peaks)
    peaks_sorted = pick_diverse(peaks_all, args.peaks)
    hscale = 0.0 if terr.flat else float(np.clip(terr.relief / 1500.0, 0.45, 1.0))
    scene_peaks = []
    if peaks_sorted:
        zmax = max(p["elev"] for p in peaks_sorted)
        zmin = min(p["elev"] for p in peaks_sorted)
        for p in peaks_sorted:
            t = (p["elev"] - zmin) / (zmax - zmin) if zmax > zmin else 1.0
            H = min((15 + 21 * (0.25 + 0.75 * t)) * hscale, 36.0)
            bp = clamp_ellipse(mp.point(p["kx"], p["ky"]), 0.93)
            R = 7 + 5.5 * (H / 36.0)
            for _ in range(6):
                moved_p = False
                for sp in stop_pos.values():
                    d = math.hypot(bp[0] - sp[0], bp[1] - sp[1])
                    if d < R + 8.0:
                        ux, uz = ((bp[0] - sp[0]) / d, (bp[1] - sp[1]) / d) if d > 1e-6 else (0.0, -1.0)
                        bp = clamp_ellipse([bp[0] + ux * (R + 8.5 - d), bp[1] + uz * (R + 8.5 - d)], 0.95)
                        moved_p = True
                if not moved_p:
                    break
            label = p["name"] or "无名峰 %d 米" % round(p["elev"])
            if bp[1] > 8:
                H *= 0.55
                notes.append("山峰「%s」落在前排，已压低到 H≈%.0f 免得挡住站点；构图时可考虑换到后排或删掉。" % (label, H))
            scene_peaks.append({"x": r1(bp[0]), "z": r1(bp[1]), "H": r1(H), "R": r1(R), "n": 6 if H > 24 else 5, "name": label})

    # ---- ranges (foothill ridges through connected peaks), named from OSM when a named range is near
    scene_ranges = []
    for pi, path in enumerate(range_paths):
        raw_pts = [(peaks_all[i]["kx"], peaks_all[i]["ky"]) for i in path]
        nb = min(5, max(2, (len(raw_pts) + 1) // 2))  # path is ordered along the main axis; average chunks into a clean spine
        chunks = [raw_pts[round(k * len(raw_pts) / nb): round((k + 1) * len(raw_pts) / nb)] for k in range(nb)]
        pts = [(float(np.mean([p[0] for p in c])), float(np.mean([p[1] for p in c]))) for c in chunks if c]
        if len(pts) >= 2:
            (x0, y0), (x1, y1) = pts[0], pts[1]
            pts[0] = (x0 + (x0 - x1) * 0.12, y0 + (y0 - y1) * 0.12)
            (x0, y0), (x1, y1) = pts[-1], pts[-2]
            pts[-1] = (x0 + (x0 - x1) * 0.12, y0 + (y0 - y1) * 0.12)
        bp = simplify_to([tuple(clamp_ellipse(mp.point(*q), 0.93)) for q in pts], 6)
        e_mean = min(1.0, float(np.mean([peaks_all[i]["e"] for i in path])))
        cx = float(np.mean([peaks_all[i]["kx"] for i in path]))
        cy = float(np.mean([peaks_all[i]["ky"] for i in path]))
        dname = dir8(bearing(cx - center[0], cy - center[1]))
        real_name = ""
        clon, clat = geo.ll(cx, cy)
        near = [(haversine(clon, clat, o["lon"], o["lat"]), o["name"]) for o in osm.get("ranges", [])]
        near = [n for n in near if n[0] <= 70]
        if near:
            real_name = min(near)[1]
        scene_ranges.append({
            "name": slug(real_name, "") if re.search(r"[A-Za-z]", real_name) else "%s-range-%d" % (dname.lower(), pi + 1),
            "H": r1((4 + 3 * e_mean) * (0.7 + 0.3 * hscale)), "W": r1(9 + 5 * e_mean),
            "pts": [[r1(q[0]), r1(q[1])] for q in bp],
            "_dir": dname, "_e": round(e_mean, 2), "_real_name": real_name,
            "_peaks": [peaks_all[i]["name"] or "%dm" % round(peaks_all[i]["elev"]) for i in path]})

    # ---- rivers
    scene_rivers = []
    for ri, rv in enumerate(osm["rivers"]):
        line = rv["line"]
        zs = terr.elev_at(*line[0]), terr.elev_at(*line[-1])
        if zs[0] + 5 < zs[1]:
            line = line[::-1]  # make the polyline run downhill
        kmpts = simplify_to([geo.km(*p) for p in line], 7)
        bp = [clamp_ellipse(mp.point(*q), 0.95) for q in kmpts]
        w = float(np.clip(1.8 + rv["length_km"] / 120.0, 2.0, 3.2))
        ident = slug(rv["name"], "") if re.search(r"[A-Za-z]", rv["name"]) else ""
        scene_rivers.append({"id": ident or "river-%d" % (ri + 1), "w": r1(w), "pts": [[r1(q[0]), r1(q[1])] for q in bp],
                             "_name": rv["name"], "_flow_dir": dir8(bearing(kmpts[-1][0] - kmpts[0][0], kmpts[-1][1] - kmpts[0][1]))})

    # ---- coast (side is in the *scene* frame: S = front/viewer, N = back, W = left, E = right)
    coast, sea_scene_side = None, None
    sea_frac = float(terr.sea.mean())
    if sea_frac >= 0.06:
        votes = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
        KXg, KYg = np.meshgrid(terr.KX, terr.KY)
        Xs = (KXg - center[0]) * mp.right[0] + (KYg - center[1]) * mp.right[1]
        Zs = (KXg - center[0]) * mp.front[0] + (KYg - center[1]) * mp.front[1]
        hx, hz = max(float(np.abs(Xs).max()), 1e-6), max(float(np.abs(Zs).max()), 1e-6)
        nx, nz = Xs[terr.sea] / hx, Zs[terr.sea] / hz  # normalised so a thin map is not biased
        for a_, b_ in zip(nx, nz):
            if abs(b_) >= abs(a_):
                votes["S" if b_ > 0 else "N"] += 1
            else:
                votes["E" if a_ > 0 else "W"] += 1
        sea_scene_side = max(votes, key=votes.get)
        coast = {"side": sea_scene_side, "inset": r1(float(np.clip(sea_frac * 60, 8, 22)))}

    # ---- routes
    scene_routes = {}
    for rid, leg_list in routes_real.items():
        pts = []
        for a_id, b_id, poly in leg_list:
            A_, B_ = stop_pos[a_id], stop_pos[b_id]
            seg = [A_]
            ab = (B_[0] - A_[0], B_[1] - A_[1])
            L2 = ab[0] ** 2 + ab[1] ** 2
            if poly and math.sqrt(L2) > 14:
                # keep only the bends that matter: between the two stops, off the straight line, not hugging a stop
                for q in simplify_to([geo.km(*p) for p in poly], 6)[1:-1]:
                    bp = mp.point(*q)
                    t = ((bp[0] - A_[0]) * ab[0] + (bp[1] - A_[1]) * ab[1]) / L2
                    off = abs((bp[0] - A_[0]) * ab[1] - (bp[1] - A_[1]) * ab[0]) / math.sqrt(L2)
                    if not (0.12 < t < 0.88) or off < 3.0 or off > 18:
                        continue
                    if any(math.hypot(bp[0] - sp[0], bp[1] - sp[1]) < 6 for sp in stop_pos.values()):
                        continue
                    if seg and math.hypot(bp[0] - seg[-1][0], bp[1] - seg[-1][1]) < 6:
                        continue
                    seg.append([r1(bp[0]), r1(bp[1])])
            seg.append(B_)
            if pts and pts[-1] == seg[0]:
                seg = seg[1:]
            pts += seg
        if pts:
            scene_routes[rid] = pts

    scene = {
        "version": 1,
        "meta": {"name": args.name, "bbox": [r1(v, 4) for v in geo.bbox], "viewFrom": view_from,
                 "scaleNote": "方位真实，距离已压缩，比例不按真实"},
        "theme": {"season": args.season, "preset": "winter-blush" if args.season == "winter" else "summer-meadow"},
        "board": {"a": int(BOARD_A), "b": int(BOARD_B)},
        "stops": stop_pos,
        "ranges": [{k: v for k, v in r.items() if not k.startswith("_")} for r in scene_ranges],
        "peaks": scene_peaks,
        "lakes": [{k: v for k, v in l.items() if not k.startswith("_")} for l in scene_lakes],
        "rivers": [{k: v for k, v in r.items() if not k.startswith("_")} for r in scene_rivers],
        "coast": coast,
        "routes": scene_routes,
        "pads": [{"x": p[0], "z": p[1], "r": 9.0} for p in stop_pos.values()],
        "props": [],
        "clumps": [],
    }
    extra = {"ranges": scene_ranges, "lakes": scene_lakes, "rivers": scene_rivers, "peaks": scene_peaks,
             "peaks_all": peaks_all, "range_paths": range_paths, "bearing_err_deg": round(bearing_err, 1),
             "scale": round(mp.k, 4), "sea_scene_side": sea_scene_side, "sea_frac": round(sea_frac, 3), "stop_pos": stop_pos}
    return scene, extra


# ----------------------------------------------------------------------------
# routes
# ----------------------------------------------------------------------------
def build_routes(stops, days, args, cache_dir, notes):
    byid = {s["id"]: s for s in stops}
    if not days:
        if len(stops) >= 2:
            days = [{"id": "D1", "stops": [s["id"] for s in stops]}]
            notes.append("你没有给分天行程，草稿里把所有站点按清单顺序连成一条路线 D1；请在确认骨架卡时告诉我真实的分天与顺序。")
        else:
            return {}, "n/a"
    routes = {}
    used_osrm, failed = 0, 0
    last = 0.0
    for d in days:
        rid = str(d.get("route") or d.get("id") or "D%d" % (len(routes) + 1))
        ids = [i for i in d.get("stops", []) if i in byid]
        legs = []
        for a, b in zip(ids, ids[1:]):
            if a == b:
                continue
            poly = None
            if not args.no_route:
                A, B = byid[a], byid[b]
                key = "%.4f,%.4f;%.4f,%.4f" % (A["lon"], A["lat"], B["lon"], B["lat"])
                f = cache_dir / ("osrm_%s.json" % hashlib.sha1(key.encode()).hexdigest()[:12])
                js = None
                if f.exists():
                    try:
                        js = json.loads(f.read_text())
                    except Exception:
                        js = None
                if js is None and not args.offline:
                    wait = 1.0 - (time.time() - last)
                    if wait > 0:
                        time.sleep(wait)
                    last = time.time()
                    try:
                        raw = http(OSRM + key + "?overview=simplified&geometries=geojson", timeout=25, retries=1)
                        js = json.loads(raw.decode())
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        f.write_text(json.dumps(js))
                    except Exception:
                        js = None
                if js and js.get("routes"):
                    poly = [tuple(c) for c in js["routes"][0]["geometry"]["coordinates"]]
                    used_osrm += 1
                else:
                    failed += 1
            legs.append((a, b, poly))
        if legs:
            routes[rid] = legs
    if args.no_route:
        status = "straight lines (--no-route)"
    elif failed and not used_osrm:
        status = "failed, straight lines used"
        notes.append("公路走向没取到（OSRM 公共服务不可用，或该地区无路网数据），草稿里的路线是站点之间的直线，需要你按真实走法手调。")
    elif failed:
        status = "partial (%d legs straight)" % failed
        notes.append("有 %d 段公路没取到，草稿里用直线代替。" % failed)
    else:
        status = "ok"
    return routes, status


# ----------------------------------------------------------------------------
# preview image
# ----------------------------------------------------------------------------
CJK_FONTS = [
    "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc", "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
]


def get_font(size):
    for p in CJK_FONTS:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size), True
            except Exception:
                continue
    try:
        return ImageFont.load_default(size), False
    except TypeError:
        return ImageFont.load_default(), False


def has_cjk(s):
    return bool(re.search(r"[\u3400-\u9fff]", s))


def draw_preview(path, geo, terr, osm, stops, view_from, scene_extra, scene, status_note):
    dem = terr.dem
    h, w = dem.shape
    sea = dem <= 0
    lo, hi = terr.p10, max(terr.p98, terr.p10 + 1)
    t = np.clip((dem - lo) / (hi - lo), 0, 1.0)
    stops_c = np.array([[0.00, 140, 182, 112], [0.25, 190, 205, 130], [0.50, 206, 184, 130],
                        [0.75, 168, 134, 108], [0.92, 215, 210, 205], [1.00, 255, 255, 255]], dtype=np.float32)
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    for c in range(3):
        rgb[..., c] = np.interp(t, stops_c[:, 0], stops_c[:, c + 1])
    # hillshade, light from the north-west
    cell_m = 156543.03 * math.cos(math.radians(geo.lat0)) / (2 ** geo.z)
    gy, gx = np.gradient(dem.astype(np.float32), cell_m)
    slope = np.arctan(np.hypot(gx, gy) * 1.6)
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(315), math.radians(45)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(0.8 + 0.5 * (shade - 0.7), 0.7, 1.15)
    rgb *= shade[..., None]
    # contour bands
    interval = max(50, int(round(terr.relief / 9 / 100.0)) * 100) if terr.relief > 600 else max(20, int(round(terr.relief / 8 / 10.0)) * 10)
    band = np.floor(dem / interval)
    edge = np.zeros((h, w), dtype=bool)
    edge[:, :-1] |= band[:, :-1] != band[:, 1:]
    edge[:-1, :] |= band[:-1, :] != band[1:, :]
    rgb[edge] *= 0.82
    # sea
    depth = np.clip(-dem / 800.0, 0, 1)
    sea_rgb = np.stack([150 - 60 * depth, 190 - 60 * depth, 225 - 40 * depth], axis=-1)
    rgb = np.where(sea[..., None], sea_rgb, rgb)
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    scale = 1.0
    if w < 700:
        scale = 700 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    W_, H_ = img.size

    def P(lon, lat):
        x, y = geo.px(lon, lat)
        return x * scale, y * scale

    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for lk in osm["lakes"]:
        if lk.get("approx"):
            cx_, cy_ = P(*geo.ll(*lk["center_km"]))
            ppk = 1.0 / (cell_m / 1000.0) * scale
            rx_, rz_ = lk["major_km"] * ppk, lk["minor_km"] * ppk
            ang = math.atan2(lk["major_dir"][1], lk["major_dir"][0])
            pts = [(cx_ + rx_ * math.cos(t) * math.cos(ang) + rz_ * math.sin(t) * math.sin(ang),
                    cy_ - rx_ * math.cos(t) * math.sin(ang) + rz_ * math.sin(t) * math.cos(ang)) for t in np.linspace(0, 2 * math.pi, 40)]
            d.polygon(pts, fill=(70, 130, 220, 235), outline=(30, 80, 170, 255))
            continue
        for ring in lk["rings"]:
            pts = [P(*p) for p in ring]
            if len(pts) >= 3 and ring[0] == ring[-1]:
                d.polygon(pts, fill=(70, 130, 220, 235), outline=(30, 80, 170, 255))
            else:
                d.line(pts, fill=(30, 80, 170, 255), width=2)
    for rv in osm["rivers"]:
        d.line([P(*p) for p in rv["line"]], fill=(40, 100, 210, 255), width=3)
    for cl in osm["coast"]:
        d.line([P(*p) for p in cl], fill=(20, 60, 140, 255), width=2)
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img)
    font, cjk = get_font(15)
    fsm, _ = get_font(12)
    fbig, _ = get_font(18)
    # peaks
    for p in scene_extra["peaks_all"]:
        x, y = P(p["lon"], p["lat"])
        d.polygon([(x, y - 7), (x - 6, y + 4), (x + 6, y + 4)], fill=(90, 60, 50, 255), outline=(255, 255, 255, 255))
        d.text((x + 8, y - 8), "%dm" % round(p["elev"]), fill=(60, 40, 30, 255), font=fsm, stroke_width=2, stroke_fill=(255, 255, 255, 220))
    # stops
    legend = []
    for i, s in enumerate(stops, 1):
        x, y = P(s["lon"], s["lat"])
        d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=(220, 50, 60, 255), outline=(255, 255, 255, 255), width=2)
        tw = d.textlength(str(i), font=font)
        d.text((x - tw / 2, y - 9), str(i), fill=(255, 255, 255, 255), font=font)
        nm = s["name"] if (cjk or not has_cjk(s["name"])) else s["id"]
        legend.append("%d  %s  %dm" % (i, nm, round(s.get("elev", 0))))
    # compass (north) top-right
    cx, cy = W_ - 40, 48
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(255, 255, 255, 200), outline=(60, 60, 60, 255))
    d.polygon([(cx, cy - 22), (cx - 8, cy + 8), (cx, cy + 2), (cx + 8, cy + 8)], fill=(40, 40, 40, 255))
    d.text((cx - 5, cy + 8), "N", fill=(40, 40, 40, 255), font=fsm)
    # camera direction: arrow on the viewFrom edge, pointing to the centre
    deg = math.radians(DIR8_DEG[view_from])
    ux, uy = math.sin(deg), -math.cos(deg)  # screen vector toward the camera side (y down)
    mx, my = W_ / 2, H_ / 2
    ex, ey = mx + ux * (W_ / 2 - 50), my + uy * (H_ / 2 - 40)
    tx, ty = ex - ux * 46, ey - uy * 46
    d.line([(ex, ey), (tx, ty)], fill=(20, 20, 20, 255), width=5)
    ang = math.atan2(ty - ey, tx - ex)
    ca, sa = math.cos(ang), math.sin(ang)
    hd = [(tx + 18 * ca, ty + 18 * sa), (tx - 6 * sa, ty + 6 * ca), (tx + 6 * sa, ty - 6 * ca)]
    d.polygon(hd, fill=(20, 20, 20, 255))
    d.rounded_rectangle([ex - 34, ey - 12, ex + 34, ey + 12], radius=6, fill=(255, 235, 120, 255), outline=(20, 20, 20, 255))
    d.text((ex - 26, ey - 9), "CAMERA", fill=(20, 20, 20, 255), font=fsm)
    # scale bar
    km_px = 1.0 / (cell_m / 1000.0) / (1 / scale)  # pixels per km in the scaled image
    bar_km = max(1, int(round(terr.size_km[0] / 5 / 10.0)) * 10) if terr.size_km[0] > 60 else max(1, int(terr.size_km[0] / 5))
    d.rectangle([14, H_ - 24, 14 + bar_km * km_px, H_ - 18], fill=(20, 20, 20, 255))
    d.text((14, H_ - 44), "%d km (real)" % bar_km, fill=(20, 20, 20, 255), font=fsm, stroke_width=2, stroke_fill=(255, 255, 255, 220))

    # side panel
    panel_w = 300
    canvas = Image.new("RGBA", (W_ + panel_w, H_), (250, 247, 240, 255))
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    y = 14
    d.text((W_ + 14, y), "Skeleton preview", fill=(30, 30, 30, 255), font=fbig)
    y += 30
    lines = ["viewFrom = %s  (camera side)" % view_from, "contour every %d m" % interval, "north is up; bearings real,", "distances & scale not real", ""]
    lines += legend
    lines += [""]
    for lk in osm["lakes"]:
        lines.append("lake  %s" % ((lk["name"] if (cjk or not has_cjk(lk["name"])) else "") or "unnamed"))
    for rv in osm["rivers"]:
        lines.append("river %s" % ((rv["name"] if (cjk or not has_cjk(rv["name"])) else "") or "unnamed"))
    if status_note:
        lines += ["", status_note]
    for ln in lines:
        d.text((W_ + 14, y), ln[:38], fill=(40, 40, 40, 255), font=font)
        y += 20
        if y > H_ - 20:
            break
    canvas.convert("RGB").save(path, optimize=True)


# ----------------------------------------------------------------------------
# card
# ----------------------------------------------------------------------------
KIND_ZH = {"wall": "高山屏障", "opening": "向外敞开的谷口/低地", "sea": "海", "hills": "丘陵或中等起伏", "low": "低地", "flat": "平坦", "mid": "起伏不大"}


def summarize_terrain(terr, sides, osm, sea_scene_side, coast_dirs):
    if terr.flat:
        base = "整片范围地势平坦（相对高差不到 250 米），没有明显的山脉"
        if coast_dirs:
            base += "，%s侧临海" % "、".join(ZH[d] for d in coast_dirs)
        return base + "。"
    walls = [ZH[s] for s, v in sides.items() if v["kind"] == "wall"]
    opens = [ZH[s] for s, v in sides.items() if v["kind"] == "opening"]
    seas = [ZH[s] for s, v in sides.items() if v["kind"] == "sea"]
    lows = [ZH[s] for s, v in sides.items() if v["kind"] in ("low",)]
    hills = [ZH[s] for s, v in sides.items() if v["kind"] in ("hills",)]
    parts = []
    if walls:
        parts.append("%s侧是高山" % "、".join(walls))
    if seas:
        parts.append("%s侧是海" % "、".join(seas))
    if opens:
        parts.append("%s侧是向外敞开的低地或谷口" % "、".join(opens))
    if lows:
        parts.append("%s侧是低地" % "、".join(lows))
    if hills:
        parts.append("%s侧是丘陵" % "、".join(hills))
    if not parts:
        parts.append("地势起伏平缓")
    s = "，".join(parts) + "。"
    s += "最高处约 %d 米，八成陆地在 %d–%d 米之间。" % (round(terr.zmax), round(terr.p10), round(terr.p90))
    return s


def write_card(path, a):
    L = []
    A = L.append
    A("# 地理骨架卡（请确认或纠正）")
    A("")
    A("> **方位真实，距离已压缩，比例不按真实。** 微缩景观用来配合照片、视频和攻略，不是导航地图。")
    A("")
    A("**范围**：经度 %.2f–%.2f，纬度 %.2f–%.2f（约 %d × %d 公里）。" % (
        a["bbox"][0], a["bbox"][2], a["bbox"][1], a["bbox"][3], round(a["size_km"][0]), round(a["size_km"][1])))
    A("")
    A("## 一句话地貌")
    A("")
    A(a["summary"])
    A("")
    A("## 镜头方位")
    A("")
    A("建议 `viewFrom = %s`（%s侧朝向观众）。%s" % (a["view"], ZH[a["view"]], a["view_reason"]))
    A("")
    if a["stops"]:
        A("## 站点")
        A("")
        A("| # | 站点 | 海拔 | 在范围中心的 | 备注 |")
        A("|---|---|---|---|---|")
        for i, s in enumerate(a["stops"], 1):
            rel = "中心" if s["rel_dir"] is None else "%s %d 公里" % (ZH[s["rel_dir"]], s["rel_km"])
            note = "坐标由地名查得，请核对" if s.get("geocoded") else ""
            if s["elev_m"] <= 0:
                note = (note + "；" if note else "") + "海拔≤0，可能在海边或坐标有误"
            A("| %d | %s | %d 米 | %s | %s |" % (i, s["name"], round(s["elev_m"]), rel, note))
        A("")
        if len(a["stops"]) >= 2:
            A("### 站点之间的方位与直线距离")
            A("")
            if len(a["stops"]) <= 9:
                names = [str(i + 1) for i in range(len(a["stops"]))]
                A("| 从＼到 | " + " | ".join(names) + " |")
                A("|---|" + "---|" * len(names))
                for i, s in enumerate(a["stops"]):
                    row = []
                    for j, t in enumerate(a["stops"]):
                        if i == j:
                            row.append("—")
                        else:
                            pr = a["pair"][(i, j)]
                            row.append("%s %d" % (ZH[pr["dir"]], round(pr["km"])))
                    A("| %d %s | " % (i + 1, s["name"]) + " | ".join(row) + " |")
                A("")
                A("（表中格子是「行站点看向列站点」的方位和直线公里数。）")
            else:
                for (i, j), pr in a["pair"].items():
                    if j == i + 1:
                        A("- %s → %s：%s，%d 公里" % (a["stops"][i]["name"], a["stops"][j]["name"], ZH[pr["dir"]], round(pr["km"])))
            A("")
    A("## 山")
    A("")
    if not a["peaks"] and not a["ranges"]:
        A("没有检测到明显的山脉。")
    for r in a["ranges"]:
        nm = "（%s）" % r["_real_name"] if r.get("_real_name") else ""
        A("- **%s侧山脉%s**：沿%s方向展开，相对高度 %.2f（0 = 低地，1 = 最高处），包含 %s。" % (
            ZH[r["_dir"]], nm, r["axis"], min(1.0, r["_e"]), "、".join(r["_peaks"][:5])))
    if a["peaks"]:
        A("")
        A("最显著的山峰：")
        A("")
        A("| 山峰 | 海拔 | 在范围中心的 |")
        A("|---|---|---|")
        for p in a["peaks"]:
            A("| %s | %d 米 | %s |" % (p["name"] or "（无名峰）", round(p["elev"]), ZH[p["dir"]] + (" %d 公里" % round(p["km"]))))
    A("")
    A("## 水")
    A("")
    status = a["osm_status"]
    def _failed(key):
        # 没查到（失败或被跳过）和「查了但是空」是两回事，分开说
        return str(status.get(key, "")).startswith(("failed", "skipped"))
    lakes_failed, rivers_failed = _failed("lakes"), _failed("rivers")
    if lakes_failed and rivers_failed:
        A("**水系数据这次没取到**（公共地图服务暂时连不上，或被设为跳过）。下面没有湖泊和河流；可以稍后重跑一次，或者直接告诉我行程里有哪些湖和河、大概在哪。")
    else:
        if a["lakes"]:
            for l in a["lakes"]:
                where = "在范围中心的%s" % ZH[l["dir_center"]]
                if l["near_stop"]:
                    where += "；" + ("就在站点「%s」那里" % l["near_stop"] if l["km_stop"] < 3 else "离站点「%s」最近，在它的%s %d 公里" % (
                        l["near_stop"], ZH[l["dir_stop"]], round(l["km_stop"])))
                A("- 湖：**%s**，%s，长约 %d 公里。" % (l["name"] or "（无名湖）", where, round(l["major_km"])))
        elif lakes_failed:
            A("- 湖泊数据这次没取到，不代表这里没有湖。可以稍后重跑，或者直接告诉我。")
        else:
            A("- 范围内没有找到大湖。")
        if a["rivers"]:
            for r in a["rivers"]:
                A("- 河：**%s**，长约 %d 公里（范围内），总体向%s流。" % (r["name"] or "（无名河）", round(r["length_km"]), ZH[r["flow_dir"]]))
        elif rivers_failed:
            A("- 河流数据这次没取到，不代表这里没有河。可以稍后重跑，或者直接告诉我。")
        else:
            A("- 范围内没有找到主要河流。")
    if a["coast"]:
        A("- 海：%s侧是海（海面约占范围的 %d%%），景观里海岸放在画面的%s。" % (
            "、".join(ZH[d] for d in a["coast_dirs"]) or "—", round(a["sea_frac"] * 100), {"N": "后方", "S": "前方（朝向观众）", "E": "右侧", "W": "左侧"}[a["coast"]["side"]]))
    A("")
    A("## 路线")
    A("")
    A(a["route_text"])
    A("")
    A("## 请确认或纠正")
    A("")
    for q in a["checklist"]:
        A("- [ ] " + q)
    A("")
    if a["notes"]:
        A("## 提醒")
        A("")
        for n in a["notes"]:
            A("- " + n)
        A("")
    A("---")
    A("数据来源：高程为 AWS Open Data 的 Terrarium 瓦片；水系、海岸、山峰名为 OpenStreetMap 贡献者；公路走向为 OSRM 公共服务（有就用，没有则为直线）。以上均为公开数据，仅供构图参考。")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="地理骨架扫描：站点清单 -> 骨架卡 + 草稿 scene.json（无需任何 API key）")
    ap.add_argument("stops", nargs="?", help="站点清单 JSON：[{id,name,lat,lon}]，或 {stops:[...], days:[{id,stops:[...]}]}")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"), help="手动指定范围；不给则由站点外扩")
    ap.add_argument("--out", default="geo_scan_out", help="输出目录（默认 ./geo_scan_out）")
    ap.add_argument("--view-from", choices=DIR8_EN, help="手动指定镜头方位（镜头在真实世界的哪个方向）")
    ap.add_argument("--name", default="My Trip", help="写进 scene.draft.json 的名字")
    ap.add_argument("--season", choices=["winter", "summer"], default="winter")
    ap.add_argument("--margin", type=float, default=0.3, help="站点范围外扩比例（默认 0.3）")
    ap.add_argument("--zoom", type=int, help="强制高程瓦片缩放级别")
    ap.add_argument("--lakes", type=int, default=3, help="最多保留几个大湖（默认 3）")
    ap.add_argument("--rivers", type=int, default=3, help="最多保留几条主要河流（默认 3）")
    ap.add_argument("--peaks", type=int, default=6, help="草稿里放几座山峰（默认 6，范围 3–8）")
    ap.add_argument("--osm-budget", type=int, default=100, help="OSM 查询总时间预算（秒，默认 100；每类数据至少会试一次）；超时就只用高程继续")
    ap.add_argument("--no-osm", action="store_true", help="不查 OSM 水系/海岸/山名，只用高程")
    ap.add_argument("--no-route", action="store_true", help="不查公路走向，站点间用直线")
    ap.add_argument("--offline", action="store_true", help="只用缓存，不联网（缓存里没有的就跳过）")
    args = ap.parse_args()
    args.peaks = int(min(8, max(3, args.peaks)))

    if not args.stops and not args.bbox:
        ap.error("请给站点清单 JSON，或用 --bbox W S E N 指定范围。")
    out = Path(args.out)
    (out / "cache").mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    notes = []

    stops, days = ([], [])
    if args.stops:
        stops, days = load_stops(args.stops)
        geocode(stops, out, args.offline)
        for s in stops:
            if not (-90 <= s["lat"] <= 90 and -180 <= s["lon"] <= 180):
                die("站点「%s」的坐标超出范围：lat=%s lon=%s（是不是填反了？）" % (s["name"], s["lat"], s["lon"]))
        (out / "stops.resolved.json").write_text(
            json.dumps({"stops": [{k: s[k] for k in ("id", "name", "lat", "lon")} for s in stops], "days": days}, ensure_ascii=False, indent=1),
            encoding="utf-8")
    if args.bbox:
        bbox = [float(v) for v in args.bbox]
        if not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
            die("--bbox 应为 W S E N，且 W<E、S<N。")
    else:
        if not stops:
            die("没有站点，也没有 --bbox。")
        bbox = auto_bbox(stops, args.margin)
    for s in stops:
        if not (bbox[0] <= s["lon"] <= bbox[2] and bbox[1] <= s["lat"] <= bbox[3]):
            notes.append("站点「%s」在 --bbox 之外，它会被放到景观边缘。" % s["name"])

    log("范围 W S E N = %s" % bbox)
    z = choose_zoom(bbox, args.zoom)
    dem, meta = fetch_dem(bbox, z, cache)
    geo = Geo(bbox, meta)
    terr = Terrain(dem, geo)
    log("高程图 %dx%d px，约 %d × %d km，陆地最高 %d m" % (dem.shape[1], dem.shape[0], terr.size_km[0], terr.size_km[1], terr.zmax))

    OSM_DEADLINE[0] = time.time() + args.osm_budget
    log("查询水系（OpenStreetMap，通常十几秒，每类数据至少试一次，备用服务器共最多再等 %d 秒）…" % args.osm_budget)
    osm = fetch_osm(geo, args, cache)
    for k, v in osm["status"].items():
        log("  %-6s %s" % (k, v))
    failed_parts = [k for k, v in osm["status"].items() if str(v).startswith("failed")]
    if failed_parts:
        zh_part = {"lakes": "湖泊", "rivers": "河流", "coast": "海岸线", "peaks": "山名"}
        notes.append("%s数据这次没取到（公共地图服务暂时连不上或太慢），草稿里对应的部分是空的。可以稍后原样重跑一次，或者直接告诉我这方面的情况（比如有哪些主要的河、湖、山）。" % (
            "、".join(zh_part.get(k, k) for k in failed_parts)))
        log("  （原始原因，仅供排查：%s）" % "; ".join("%s=%s" % (k, osm["status"][k]) for k in failed_parts)[:300])

    # stop elevations and pairs
    for s in stops:
        s["elev_m"] = terr.elev_at(s["lon"], s["lat"])
    stops_km = [geo.km(s["lon"], s["lat"]) for s in stops]

    cells, sides = terr.sides()
    view, scores = choose_view(terr, sides, stops_km, args.view_from)
    reason = view_reason(view, bool(args.view_from), terr, sides)

    routes_real, route_status = build_routes(stops, days, args, cache, notes)
    scene, ex = build_scene(geo, terr, osm, stops, days, routes_real, view, args, notes)

    # ---- derived facts for the card
    cx_km, cy_km = 0.0, 0.0  # bbox centre
    st_out = []
    for s, (kx, ky) in zip(stops, stops_km):
        dd = math.hypot(kx - cx_km, ky - cy_km)
        st_out.append({"id": s["id"], "name": s["name"], "lat": round(s["lat"], 5), "lon": round(s["lon"], 5),
                       "elev_m": round(s["elev_m"]), "geocoded": s.get("geocoded", False),
                       "rel_dir": None if dd < 3 else dir8(bearing(kx - cx_km, ky - cy_km)), "rel_km": round(dd)})
    pair = {}
    pair_json = []
    for i, A_ in enumerate(stops):
        for j, B_ in enumerate(stops):
            if i == j:
                continue
            dk = haversine(A_["lon"], A_["lat"], B_["lon"], B_["lat"])
            br = bearing(stops_km[j][0] - stops_km[i][0], stops_km[j][1] - stops_km[i][1])
            pair[(i, j)] = {"dir": dir8(br), "km": dk}
            if i < j:
                pair_json.append({"from": A_["id"], "to": B_["id"], "bearing_deg": round(br), "dir": dir8(br), "km": round(dk, 1)})

    def near_stop(kx, ky):
        if not stops_km:
            return None, None, None
        k = min(range(len(stops)), key=lambda i: math.hypot(kx - stops_km[i][0], ky - stops_km[i][1]))
        dx, dy = kx - stops_km[k][0], ky - stops_km[k][1]
        return stops[k]["name"], dir8(bearing(dx, dy)), math.hypot(dx, dy)

    lakes_out = []
    for lk in ex["lakes"]:
        src = next((l for l in osm["lakes"] if l["name"] == lk["_name"]), None)
        cx, cy = src["center_km"]
        ns, dns, kns = near_stop(cx, cy)
        lakes_out.append({"name": lk["_name"], "id": lk["id"], "center_ll": [round(v, 4) for v in geo.ll(cx, cy)],
                          "dir_center": dir8(bearing(cx, cy)), "major_km": round(src["major_km"] * 2, 1),
                          "area_km2": round(src["area_km2"]), "near_stop": ns, "dir_stop": dns or "N", "km_stop": kns or 0})
    rivers_out = []
    for rv, src in zip(ex["rivers"], osm["rivers"]):
        rivers_out.append({"name": rv["_name"], "id": rv["id"], "length_km": round(src["length_km"]), "flow_dir": rv["_flow_dir"]})
    peaks_out = []
    for p in sorted(pick_diverse(ex["peaks_all"], 8), key=lambda p: -p["elev"]):
        peaks_out.append({"name": p["name"], "elev": round(p["elev"]), "lat": round(p["lat"], 4), "lon": round(p["lon"], 4),
                          "dir": dir8(bearing(p["kx"], p["ky"])), "km": math.hypot(p["kx"], p["ky"]), "e": round(p["e"], 2)})
    # axis names for ranges (real compass), computed from the peaks list order
    for r, path in zip(ex["ranges"], ex["range_paths"]):
        pa, pb = ex["peaks_all"][path[0]], ex["peaks_all"][path[-1]]
        ax = bearing(pb["kx"] - pa["kx"], pb["ky"] - pa["ky"]) % 180
        r["axis"] = "南北" if (ax < 22.5 or ax >= 157.5) else ("东北—西南" if ax < 67.5 else ("东西" if ax < 112.5 else "东南—西北"))

    coast_dirs = [d for d, v in sides.items() if v["kind"] == "sea"]
    summary = summarize_terrain(terr, sides, osm, ex["sea_scene_side"], coast_dirs)

    # route text
    if scene["routes"]:
        lines = []
        for rid, legs in routes_real.items():
            names = []
            for a_, b_, _ in legs:
                if not names:
                    names.append(next(s["name"] for s in stops if s["id"] == a_))
                names.append(next(s["name"] for s in stops if s["id"] == b_))
            lines.append("- %s：%s" % (rid, " → ".join(names)))
        rt = "\n".join(lines) + "\n\n路线形状来源：%s。" % ("公路走向（OSRM）" if route_status == "ok" else route_status)
    else:
        rt = "没有给出站点顺序，草稿里没有路线。"

    checklist = [
        "镜头方位「%s」可以吗？（想让哪一侧在画面后排、哪一侧朝向观众，直接告诉我）" % ZH[view],
        "站点的相对方位对不对？有没有哪个站点我放反了方向？",
        "上面的山、湖、河、海，有没有漏掉你行程里重要的？有没有多出来你觉得不该出现的？",
        "各站点的海拔和你的印象是否一致？（差很多说明坐标可能不对）",
    ]
    if any(s.get("geocoded") for s in stops):
        checklist.append("标注「坐标由地名查得」的站点，请核对是不是你要去的那个地方。")
    if not days:
        checklist.append("路线的分天和顺序是什么？")
    if sum(1 for _ in scene["lakes"]) == 0 and not terr.flat:
        checklist.append("行程里有没有湖或河需要出现在景观里？（没查到的话告诉我大概位置）")

    card_data = {
        "bbox": bbox, "size_km": terr.size_km, "summary": summary, "view": view, "view_reason": reason,
        "stops": st_out, "pair": pair, "peaks": peaks_out, "ranges": ex["ranges"], "lakes": lakes_out, "rivers": rivers_out,
        "coast": scene["coast"], "coast_dirs": coast_dirs, "sea_frac": ex["sea_frac"], "osm_status": osm["status"],
        "route_text": rt, "checklist": checklist, "notes": notes,
    }
    write_card(out / "skeleton_card.md", card_data)

    skeleton = {
        "version": 1, "tool": "geo_scan.py", "bbox": bbox, "size_km": [round(v) for v in terr.size_km], "zoom": z,
        "elevation": {"min": round(terr.zmin), "max": round(terr.zmax), "p10": round(terr.p10), "p50": round(terr.p50), "p98": round(terr.p98),
                      "relief": round(terr.relief), "flat": terr.flat, "sea_fraction": ex["sea_frac"]},
        "terrain": {"summary": summary, "sides": {k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in sides.items()},
                    "cells": {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in cells.items()}},
        "viewFrom": {"value": view, "forced": bool(args.view_from), "reason": reason, "scores": scores},
        "stops": st_out, "stop_pairs": pair_json,
        "peaks": peaks_out,
        "ranges": [{"name": r["name"], "dir": r["_dir"], "axis": r.get("axis"), "relative_height": r["_e"], "peaks": r["_peaks"]} for r in ex["ranges"]],
        "lakes": lakes_out, "rivers": rivers_out,
        "coast": {"scene": scene["coast"], "sea_sides_real": coast_dirs, "sea_fraction": ex["sea_frac"]},
        "routes": {"status": route_status, "legs": {k: [[a, b, bool(p)] for a, b, p in v] for k, v in routes_real.items()}},
        "compression": {"scale_km_to_unit": ex["scale"], "max_pair_bearing_error_deg": ex["bearing_err_deg"],
                        "note": "方位真实，距离已压缩，比例不按真实"},
        "osm_status": osm["status"], "notes": notes,
    }
    (out / "skeleton.json").write_text(json.dumps(skeleton, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "scene.draft.json").write_text(json.dumps(scene, ensure_ascii=False, indent=1), encoding="utf-8")

    for s in stops:
        s["elev"] = s["elev_m"]
    pstat = ""
    if failed_parts:
        pstat = "OSM missing: " + ",".join(failed_parts)
    draw_preview(out / "skeleton_preview.png", geo, terr, osm, [dict(s, elev=s["elev_m"]) for s in stops], view, ex, scene, pstat)

    log("\n完成。输出在 %s/：" % out)
    for f in ("skeleton_card.md", "skeleton.json", "skeleton_preview.png", "scene.draft.json"):
        log("  - " + f)
    log("下一步：把 skeleton_card.md 给用户确认；确认后按 references/composition-guide.md 调整 scene.draft.json。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
