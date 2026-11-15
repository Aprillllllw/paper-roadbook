#!/usr/bin/env python3
"""把旅行素材处理成网页用的小文件，并清除 GPS 等元数据。

用法：
  python3 scripts/process_media.py <素材文件夹> --out <工程>/public/media

素材文件夹的结构：每个站点一个子文件夹，文件夹名就是站点 id（要和 trip.json 里的一致）。
  素材/
    sayram/  IMG_001.heic  clip.mov
    yining/  a.jpg
直接放在素材文件夹根目录的文件会归到 "_unassigned"，处理完要你自己分配。

输出：
  照片  -> webp，长边最长 1600 像素
  视频  -> mp4，720p，无声，最长 15 秒；同时生成封面 webp
  所有输出都不带 EXIF / GPS / 拍摄设备信息
  media_manifest.json（默认写在当前目录，不进 public）-> 每个站点可直接粘进 trip.json 的 media 列表；
    默认只含 type/src/poster，加 --debug-manifest 才多写原始文件名等信息

依赖：ffmpeg（视频）、Pillow（照片）。HEIC 照片还需要 pillow-heif，
macOS 上没有 pillow-heif 时会尝试系统自带的 sips。
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VID = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm"}
IMG = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_PHOTO = 1600
MAX_CLIP = 15.0


def need(cond, msg):
    if not cond:
        sys.exit(msg)


def load_pillow():
    try:
        from PIL import Image, ImageOps  # noqa
    except ImportError:
        return None
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    return True


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "命令失败")


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def save_photo(src, dst):
    """读、转正方向、缩小、另存为不带任何元数据的 webp。"""
    from PIL import Image, ImageOps
    tmp = None
    try:
        try:
            im = Image.open(src)
            im.load()
        except Exception:
            if src.suffix.lower() in (".heic", ".heif") and shutil.which("sips"):
                tmp = Path(tempfile.mkstemp(suffix=".jpg")[1])
                run(["sips", "-s", "format", "jpeg", str(src), "--out", str(tmp)])
                im = Image.open(tmp)
                im.load()
            elif src.suffix.lower() in (".heic", ".heif"):
                raise RuntimeError("读不了 HEIC。请先 pip install pillow-heif，或把照片导出成 JPG。")
            else:
                raise
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        im.thumbnail((MAX_PHOTO, MAX_PHOTO), Image.LANCZOS)
        # 新建一张只含像素的图：不会带上任何 EXIF / GPS / ICC
        clean = Image.frombytes(im.mode, im.size, im.tobytes())
        clean.save(dst, "WEBP", quality=80, method=4, exif=b"", icc_profile=None)
        return im.size
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def save_video(src, dst_mp4, dst_poster):
    dur = probe_duration(src)
    if dur <= 0:
        raise RuntimeError("读不出视频时长，文件可能损坏")
    if dur <= MAX_CLIP:
        start, length = 0.0, dur
    else:  # 长视频：跳过开头的晃动，取 25% 处开始的 15 秒
        start = round(min(max(dur * 0.25, 1.0), dur - MAX_CLIP), 2)
        length = MAX_CLIP
    run(["ffmpeg", "-y", "-ss", str(start), "-i", str(src), "-t", f"{length:.2f}", "-an",
         "-map_metadata", "-1", "-map_chapters", "-1",
         "-vf", "scale='if(gt(iw,ih),-2,720)':'if(gt(iw,ih),720,-2)',fps=30",
         "-c:v", "libx264", "-crf", "26", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst_mp4)])
    from PIL import Image
    tmp = Path(tempfile.mkstemp(suffix=".jpg")[1])
    try:
        run(["ffmpeg", "-y", "-ss", str(min(length / 2, 2.0)), "-i", str(dst_mp4),
             "-frames:v", "1", "-q:v", "3", str(tmp)])
        im = Image.open(tmp)
        im.load()
        im = im.convert("RGB")
        clean = Image.frombytes("RGB", im.size, im.tobytes())
        clean.save(dst_poster, "WEBP", quality=80, exif=b"", icc_profile=None)
    finally:
        tmp.unlink(missing_ok=True)
    return start, length, dur


def main():
    ap = argparse.ArgumentParser(description="处理旅行照片和视频，清除 GPS")
    ap.add_argument("src", help="素材文件夹（每个站点一个子文件夹）")
    ap.add_argument("--out", default="media", help="输出目录，默认 ./media。放进工程时用 <工程>/public/media")
    ap.add_argument("--only", help="只处理这个站点子文件夹")
    ap.add_argument("--manifest", default="media_manifest.json",
                    help="清单文件位置，默认当前目录。别放进 public/")
    ap.add_argument("--debug-manifest", action="store_true",
                    help="清单里额外写出原始文件名、视频秒数等调试信息（默认不写，避免泄露原始文件名）")
    args = ap.parse_args()

    src_root = Path(args.src).expanduser()
    need(src_root.is_dir(), f"素材文件夹不存在：{src_root}")
    out_root = Path(args.out).expanduser()
    prefix = out_root.name  # trip.json 里写 "media/xxx"，对应 public/media/xxx

    has_video = any(p.suffix.lower() in VID for p in src_root.rglob("*") if p.is_file())
    has_image = any(p.suffix.lower() in IMG for p in src_root.rglob("*") if p.is_file())
    if has_video:
        need(shutil.which("ffmpeg") and shutil.which("ffprobe"),
             "素材里有视频，但没找到 ffmpeg。请先安装：macOS 用 brew install ffmpeg，Windows 用 winget install ffmpeg，Ubuntu 用 sudo apt install ffmpeg。")
    pil_ok = load_pillow()
    if has_image or has_video:
        need(pil_ok, "没找到 Pillow。请先运行：pip install Pillow")

    groups = {}
    for f in sorted(src_root.rglob("*")):
        if not f.is_file() or f.name.startswith("."):
            continue
        ext = f.suffix.lower()
        if ext not in VID and ext not in IMG:
            continue
        rel = f.relative_to(src_root)
        stop = rel.parts[0] if len(rel.parts) > 1 else "_unassigned"
        if args.only and stop != args.only:
            continue
        groups.setdefault(stop, []).append(f)

    need(groups, "没找到可处理的照片或视频。支持：" + " ".join(sorted(IMG | VID)))

    manifest, failed = {}, []
    for stop, files in groups.items():
        sd = out_root / stop
        sd.mkdir(parents=True, exist_ok=True)
        items = []
        for n, f in enumerate(files, 1):
            base = f"{stop}_{n:02d}"
            try:
                if f.suffix.lower() in VID:
                    mp4, poster = sd / f"{base}.mp4", sd / f"{base}_poster.webp"
                    start, length, dur = save_video(f, mp4, poster)
                    item = {"type": "video", "src": f"{prefix}/{stop}/{mp4.name}",
                            "poster": f"{prefix}/{stop}/{poster.name}"}
                    if args.debug_manifest:
                        item.update({"origin": f.name, "seconds": round(length, 1)})
                    items.append(item)
                    note = f"视频 {length:.0f} 秒" + ("（从原片截取）" if dur > MAX_CLIP else "")
                else:
                    webp = sd / f"{base}.webp"
                    w, h = save_photo(f, webp)
                    item = {"type": "photo", "src": f"{prefix}/{stop}/{webp.name}"}
                    if args.debug_manifest:
                        item["origin"] = f.name
                    items.append(item)
                    note = f"照片 {w}x{h}"
                print(f"完成 {stop}/{f.name}：{note}", flush=True)
            except Exception as e:  # 单个文件失败不影响其他
                failed.append((f, str(e)))
                print(f"失败 {stop}/{f.name}：{e}", file=sys.stderr, flush=True)
        if items:
            manifest[stop] = items

    out_root.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest).expanduser()
    manifest_path.write_text(
        json.dumps({"stops": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v) for v in manifest.values())
    print(f"\n处理完成：{total} 个文件，{len(manifest)} 个站点。输出在 {out_root}")
    print(f"清单：{manifest_path}。把对应站点的列表粘进 trip.json 的 media。")
    print("所有输出都已清除 GPS 和拍摄设备信息，原始素材没有被改动。")
    if "_unassigned" in manifest:
        print("注意：有文件没放进站点子文件夹，归在 _unassigned 里。请移到对应站点再重新运行。")
    if failed:
        print(f"\n有 {len(failed)} 个文件失败，见上面的提示。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
