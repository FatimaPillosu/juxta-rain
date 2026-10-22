"""Assemble the local website in DATA_ROOT/web.

Copies the static front end from site/, the ecPoint charts (map area only) of each
built run, and writes data/runs.json listing the runs the front end can show.

Usage:
    python -m rainfall_visualiser.build_site --run 2026102200
    (then serve DATA_ROOT/web with: python -m http.server 8000)
"""

import argparse
import datetime as dt
import io
import json
import os
import shutil
from concurrent.futures import ProcessPoolExecutor

import pymupdf
from PIL import Image

from .config import PROJECT_ROOT, data_root, load_settings, run_dir
from .ecpoint_classes import EDGES, classify_pdf
from .fields import build_run


def check_pdf_frame(pdf_path, frame):
    """Confirm that the chart's vector frame lines are where settings say (to 0.05 pt)."""
    page = pymupdf.open(pdf_path)[0]
    xs, ys = set(), set()
    for path in page.get_drawings():
        for item in path["items"]:
            if item[0] == "l":
                a, b = item[1], item[2]
                if abs(a.x - b.x) < 0.01 and abs(a.y - b.y) > 100:
                    xs.add(a.x)
                if abs(a.y - b.y) < 0.01 and abs(a.x - b.x) > 200:
                    ys.add(a.y)
    for v, found in ((frame[0], xs), (frame[2], xs), (frame[1], ys), (frame[3], ys)):
        if not any(abs(v - f) < 0.05 for f in found):
            raise ValueError(f"{pdf_path.name}: no frame line at {v} pt; the chart layout may have changed")


def render_pdf_map(pdf_path, out_path, frame, width_px, quality):
    """Render only the map area of a vector chart as WebP: the smaller of lossy (quality) and lossless."""
    page = pymupdf.open(pdf_path)[0]
    clip = pymupdf.Rect(*frame)
    zoom = width_px / clip.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    encoded = []
    for options in (dict(quality=quality, method=6), dict(lossless=True, method=4)):
        buf = io.BytesIO()
        im.save(buf, "WEBP", **options)
        encoded.append(buf.getvalue())
    out_path.write_bytes(min(encoded, key=len))


def _fresh(out, raw):
    return out.exists() and out.stat().st_mtime >= raw.stat().st_mtime


def prepare_chart(raw, dst, cfg):
    """Map-area image (and, for PDFs, the colour-class raster) of one chart; skips work already done."""
    stem = raw.stem
    out = {}
    if raw.suffix == ".pdf":
        out["map_file"] = f"{stem}_map.webp"
        if not _fresh(dst / out["map_file"], raw):
            render_pdf_map(raw, dst / out["map_file"], cfg["map_frame_pt"], cfg["map_width_px"],
                           cfg.get("map_webp_quality", 90))
        out["class_file"] = f"{stem}_class.tif"
        if not _fresh(dst / out["class_file"], raw):
            classify_pdf(raw, dst / out["class_file"], cfg["map_frame_pt"], cfg["map_width_px"])
    else:
        left, top, right, bottom = (round(v) for v in cfg["map_frame_px"])
        out["map_file"] = f"{stem}_map.png"
        if not _fresh(dst / out["map_file"], raw):
            with Image.open(raw) as im:
                im.crop((left, top, right, bottom)).save(dst / out["map_file"], optimize=True)
    return out


def copy_ecpoint(run, web_run, settings):
    """Prepare the ecPoint charts: only the map area, otherwise unchanged.

    PDF charts are rendered (map area only) to WebP at ecpoint.map_width_px, and
    their colour classes are written as a raster so the page can show the class
    range at a point (ecpoint_classes.py). PNG charts are cropped to the map area.
    """
    src = run_dir("ecpoint", "global", run, settings)
    index = src / "charts.json"
    if not index.exists():
        return None
    cfg = settings["ecpoint"]
    dst = web_run / "ecpoint"
    dst.mkdir(parents=True, exist_ok=True)
    charts = json.loads(index.read_text())
    pdfs = [src / c["file"] for c in charts["charts"] if c["file"].endswith(".pdf")]
    if pdfs:
        check_pdf_frame(pdfs[0], cfg["map_frame_pt"])
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) // 2)) as pool:
        results = pool.map(prepare_chart, [src / c["file"] for c in charts["charts"]],
                           [dst] * len(charts["charts"]), [cfg] * len(charts["charts"]))
        for chart, extra in zip(charts["charts"], results):
            chart.update(extra)
    charts["map_extent"] = [-180, -90, 180, 90]
    charts["class_edges_pct"] = EDGES
    (dst / "charts.json").write_text(json.dumps(charts, indent=2))
    return "ecpoint/charts.json"


def update_runs_index(web, run, ecpoint):
    path = web / "data" / "runs.json"
    runs = json.loads(path.read_text()) if path.exists() else []
    stamp = run.strftime("%Y%m%d%H")
    runs = [r for r in runs if r["id"] != stamp]
    runs.append(dict(id=stamp, run=run.isoformat(), fields=f"{stamp}/fields.json",
                     ecpoint=f"{stamp}/{ecpoint}" if ecpoint else None))
    runs.sort(key=lambda r: r["id"], reverse=True)
    path.write_text(json.dumps(runs, indent=2))


def build(run, rebuild_fields, settings):
    web = data_root(settings) / "web"
    web_run = web / "data" / run.strftime("%Y%m%d%H")
    if rebuild_fields or not (web_run / "fields.json").exists():
        build_run(run, settings)
    shutil.copytree(PROJECT_ROOT / "site", web, dirs_exist_ok=True)
    ecpoint = copy_ecpoint(run, web_run, settings)
    update_runs_index(web, run, ecpoint)
    print(f"Site assembled in {web}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, help="Run as YYYYMMDDHH")
    parser.add_argument("--rebuild-fields", action="store_true", help="Rebuild the COGs even if present")
    args = parser.parse_args()
    build(dt.datetime.strptime(args.run, "%Y%m%d%H"), args.rebuild_fields, load_settings())


if __name__ == "__main__":
    main()
