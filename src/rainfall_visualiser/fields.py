"""Turn the raw GRIB files of one run into 24 h fields as Cloud-Optimised GeoTIFFs.

Windows: 24 h ending every 12 h from T+24, aligned with the run's cycle.
- Amounts (ifs_hres, aifs_single): tp(T+L) - tp(T+L-24), converted to mm using
  each message's own units (IFS tp is in m, AIFS tp in kg m-2 = mm). Small
  negative differences (packing noise) are set to 0 and counted in the manifest.
  Stored as uint16 in 0.1 mm, nodata 65535.
- Probabilities (ifs_ens_prob, aifs_ens_prob): tpg<thr> for range "L-24 - L",
  one band per threshold. Stored as uint8 in %, nodata 255.

Overviews use nearest-neighbour resampling, so zoomed-out views show actual
grid values rather than smoothed ones.

Output: DATA_ROOT/web/data/<YYYYMMDDHH>/<product>/T<lead>.tif and fields.json.
"""

import datetime as dt
import json
from pathlib import Path

import eccodes
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.shutil import copy as rio_copy
from rasterio.transform import from_origin

from .config import data_root, load_settings, run_dir

TO_MM = {"m": 1000.0, "kg m**-2": 1.0}
AMOUNT_NODATA, PROB_NODATA = 65535, 255


def read_grib(path):
    """Return {(shortName, stepRange): 2-D array}, units and grid geometry."""
    fields, units, grid = {}, {}, None
    with open(path, "rb") as f:
        while (h := eccodes.codes_grib_new_from_file(f)) is not None:
            try:
                key = (eccodes.codes_get(h, "shortName"), eccodes.codes_get(h, "stepRange"))
                ni, nj = eccodes.codes_get(h, "Ni"), eccodes.codes_get(h, "Nj")
                fields[key] = eccodes.codes_get_values(h).reshape(nj, ni)
                units[key[0]] = eccodes.codes_get(h, "units")
                g = dict(
                    ni=ni,
                    nj=nj,
                    dx=eccodes.codes_get(h, "iDirectionIncrementInDegrees"),
                    lat0=eccodes.codes_get(h, "latitudeOfFirstGridPointInDegrees"),
                    lon0=eccodes.codes_get(h, "longitudeOfFirstGridPointInDegrees"),
                )
                if grid is None:
                    grid = g
                elif g != grid:
                    raise ValueError(f"{path}: mixed grids in one file")
            finally:
                eccodes.codes_release(h)
    # Grids start at 180°E, i.e. -180°, and run eastwards; latitudes run from 90° to -90°.
    if not (grid["lon0"] in (180.0, -180.0) and grid["lat0"] == 90.0):
        raise ValueError(f"{path}: unexpected grid origin {grid}")
    return fields, units, grid


def write_cog(path, bands, grid, dtype, nodata):
    """Write bands (list of 2-D arrays) as a COG; pixels are centred on grid points."""
    dx = grid["dx"]
    profile = dict(
        driver="GTiff",
        width=grid["ni"],
        height=grid["nj"],
        count=len(bands),
        dtype=dtype,
        nodata=nodata,
        crs="EPSG:4326",
        transform=from_origin(-180 - dx / 2, 90 + dx / 2, dx, dx),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with MemoryFile() as mem:
        with mem.open(**profile) as tmp:
            for i, band in enumerate(bands, start=1):
                tmp.write(band.astype(dtype), i)
        with mem.open() as src:
            # 128 px tiles keep single-point reads (the point charts) small: about
            # 25 kB per read instead of about 95 kB with 256 px tiles (measured 22 Oct 2026).
            # Multi-band files are pixel-interleaved, so one tile holds every threshold.
            rio_copy(src, path, driver="COG", compress="DEFLATE", predictor=2, blocksize=128,
                     overview_resampling="nearest")


def accumulations_from_start(fields):
    """Map end step -> tp accumulated from T+0 ("0", "0-12", "0-24", ...)."""
    acc = {}
    for (name, step), values in fields.items():
        start, _, end = step.partition("-")
        if name != "tp" or (end and start != "0"):
            raise ValueError(f"Expected tp accumulated from T+0, got {name} {step}")
        acc[int(end or start)] = values
    return acc


def build_amounts(path, out_dir):
    fields, units, grid = read_grib(path)
    scale = TO_MM[units["tp"]]
    acc = accumulations_from_start(fields)
    windows = []
    for L in sorted(L for L in acc if L >= 24 and L - 24 in acc):
        mm = (acc[L] - acc[L - 24]) * scale
        negative = int((mm < 0).sum())
        min_mm = float(mm.min())
        mm = np.clip(mm, 0, None)
        coded = np.round(mm * 10)
        coded[coded >= AMOUNT_NODATA] = AMOUNT_NODATA - 1
        write_cog(out_dir / f"T{L:03d}.tif", [coded], grid, "uint16", AMOUNT_NODATA)
        windows.append(dict(lead_h=L, file=f"T{L:03d}.tif", max_mm=round(float(mm.max()), 1),
                            negative_cells_set_to_0=negative, min_before_clip_mm=round(min_mm, 3)))
    return grid, windows


def build_probabilities(path, out_dir, thresholds):
    fields, _, grid = read_grib(path)
    windows = []
    ends = {int(step.split("-")[1]) for _, step in fields if "-" in step}
    for L in sorted(L for L in ends if L >= 24):
        step = f"{L - 24}-{L}"
        bands = [np.clip(np.round(fields[(f"tpg{t}", step)]), 0, 100) for t in thresholds]
        write_cog(out_dir / f"T{L:03d}.tif", bands, grid, "uint8", PROB_NODATA)
        windows.append(dict(lead_h=L, file=f"T{L:03d}.tif"))
    return grid, windows


def build_run(run, settings=None):
    settings = settings or load_settings()
    thresholds = settings["thresholds_mm"]
    web_run = data_root(settings) / "web" / "data" / run.strftime("%Y%m%d%H")
    products = {}
    for name, spec in settings["opendata"]["products"].items():
        raw = run_dir("opendata", name, run, settings)
        inventory = json.loads((raw / "inventory.json").read_text())
        grib = Path(inventory["file"])
        prob = spec["type"] == "ep"
        if prob:
            grid, windows = build_probabilities(grib, web_run / name, thresholds)
        else:
            grid, windows = build_amounts(grib, web_run / name)
        size_mb = sum((web_run / name / w["file"]).stat().st_size for w in windows) / 1e6
        products[name] = dict(
            kind="probability" if prob else "amount",
            model=spec["model"],
            resolution_deg=grid["dx"],
            units="%" if prob else "mm",
            encoding=dict(dtype="uint8", scale=1, nodata=PROB_NODATA) if prob
            else dict(dtype="uint16", scale=0.1, nodata=AMOUNT_NODATA),
            bands=[f">{t} mm" for t in thresholds] if prob else ["24 h total"],
            windows=windows,
            size_mb=round(size_mb, 1),
        )
        print(f"{name:14s} {len(windows)} windows, {size_mb:6.1f} MB")
    manifest = dict(run=run.isoformat(), thresholds_mm=thresholds, products=products,
                    built=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    (web_run / "fields.json").write_text(json.dumps(manifest, indent=2))
    return manifest
