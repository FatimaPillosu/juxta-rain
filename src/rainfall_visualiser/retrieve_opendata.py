"""Download 24 h rainfall inputs for one run from ECMWF open data.

Products (see config/settings.yaml):
- ifs_hres, aifs_single: total precipitation (tp, accumulated from T+0, in m)
  every 12 h, so that any 24 h window aligned with the run's cycle can be
  formed by differencing.
- ifs_ens_prob, aifs_ens_prob: ensemble probabilities tpg<thr> for 24 h ranges
  every 12 h ("0-24", "12-36", ...).

Each product is written to DATA_ROOT/raw/opendata/<product>/<YYYYMMDD>/<HH>z/
together with an inventory (inventory.json) of what was retrieved.

Usage:
    python -m rainfall_visualiser.retrieve_opendata            # latest common run
    python -m rainfall_visualiser.retrieve_opendata --run 2026102200
"""

import argparse
import datetime as dt
import json
import time
from collections import Counter

import eccodes
import requests
from ecmwf.opendata import Client

from .config import load_settings, run_dir

# Last forecast step published, by product family and run hour (checked on
# data.ecmwf.int on 22 Oct 2026: HRES and ENS 00/12 UTC to 360 h, 06/18 UTC to 144 h;
# AIFS Single and AIFS ENS 6-hourly to 360 h).
MAX_STEP = {
    "ifs": {0: 360, 6: 144, 12: 360, 18: 144},
    "aifs-single": {0: 360, 6: 360, 12: 360, 18: 360},
    "aifs-ens": {0: 360, 6: 360, 12: 360, 18: 360},
}


def client_for(spec, settings):
    return Client(
        source=settings["opendata"]["source"],
        model=spec["model"],
        resol=spec["resol"],
        infer_stream_keyword=False,
    )


def request_for(spec, run, thresholds):
    max_step = MAX_STEP[spec["model"]][run.hour]
    base = dict(date=run.strftime("%Y%m%d"), time=run.hour, stream=spec["stream"], type=spec["type"])
    if spec["type"] == "ep":
        steps = [f"{s}-{s + 24}" for s in range(0, max_step - 23, 12)]
        return dict(base, param=[f"tpg{t}" for t in thresholds], step=steps)
    return dict(base, param=spec["param"], step=list(range(0, max_step + 1, 12)))


def latest_run(settings):
    """Most recent run for which every configured product is published."""
    runs = []
    for spec in settings["opendata"]["products"].values():
        client = client_for(spec, settings)
        req = request_for(spec, dt.datetime(2000, 1, 1), settings["thresholds_mm"])
        req.pop("date"), req.pop("time")
        # Ask only for the first step so that latest() checks a file that exists for every run.
        req["step"] = req["step"][:1]
        runs.append(client.latest(**req))
    return min(runs)


def ep_file_urls(spec, run, max_step):
    """URLs of the ensemble-probability files, which are grouped by last step (240 h, 360 h)."""
    root = "https://data.ecmwf.int/forecasts"
    stamp = run.strftime("%Y%m%d%H0000")
    folder = f"{root}/{run:%Y%m%d}/{run:%H}z/{spec['model']}/{spec['resol']}/{spec['stream']}"
    return [f"{folder}/{stamp}-{s}h-{spec['stream']}-ep" for s in (240, 360) if s <= max_step]


def corrected_index(base_url, session):
    """Read a .index file and return entries with absolute byte offsets.

    On 22 Oct 2026 the AIFS ENS probability files were found to be several
    GRIB files joined together, while the offsets in their .index restart at 0
    for each part. A new part starts wherever an entry does not follow on from
    the previous one; its offsets are shifted by the bytes of all earlier parts.
    For correctly indexed files this leaves the offsets unchanged.
    """
    entries = [json.loads(line) for line in session.get(base_url + ".index").text.splitlines() if line.strip()]
    shift, prev_end_rel, prev_end_abs = 0, None, 0
    for e in entries:
        if prev_end_rel is not None and e["_offset"] != prev_end_rel:
            shift = prev_end_abs - e["_offset"]
        e["_abs_offset"] = e["_offset"] + shift
        prev_end_rel = e["_offset"] + e["_length"]
        prev_end_abs = e["_abs_offset"] + e["_length"]
    return entries


def retrieve_ep_verified(spec, run, req, target):
    """Download ensemble-probability fields by byte range and check each one.

    Every message is decoded and must carry the requested parameter and step
    range, so a faulty index cannot silently produce the wrong field.
    """
    wanted = {(p, s) for p in req["param"] for s in req["step"]}
    max_step = int(req["step"][-1].split("-")[1])
    session = requests.Session()
    found = set()
    with open(target, "wb") as out:
        for url in ep_file_urls(spec, run, max_step):
            for e in corrected_index(url, session):
                key = (e["param"], e["step"])
                if key not in wanted:
                    continue
                start = e["_abs_offset"]
                r = session.get(url + ".grib2", headers={"Range": f"bytes={start}-{start + e['_length'] - 1}"})
                r.raise_for_status()
                h = eccodes.codes_new_from_message(r.content)
                try:
                    got = (eccodes.codes_get(h, "shortName"), eccodes.codes_get(h, "stepRange"))
                finally:
                    eccodes.codes_release(h)
                if got != key:
                    raise RuntimeError(f"{url}: asked for {key}, received {got}")
                out.write(r.content)
                found.add(key)
    missing = wanted - found
    if missing:
        raise RuntimeError(f"Missing fields: {sorted(missing)[:5]} ... ({len(missing)} in total)")


def run_complete(run, settings):
    """True when the last forecast step of `run` is published for every product."""
    for spec in settings["opendata"]["products"].values():
        req = request_for(spec, run, settings["thresholds_mm"])
        req.pop("date"), req.pop("time")
        req["step"] = req["step"][-1:]
        if client_for(spec, settings).latest(**req) < run:
            return False
    return True


def grib_summary(path):
    """Count GRIB messages by parameter and list their steps."""
    params, steps = Counter(), set()
    with open(path, "rb") as f:
        while (h := eccodes.codes_grib_new_from_file(f)) is not None:
            try:
                params[eccodes.codes_get(h, "shortName")] += 1
                steps.add(eccodes.codes_get(h, "stepRange"))
            finally:
                eccodes.codes_release(h)
    return dict(params), sorted(steps, key=lambda s: [int(x) for x in s.split("-")])


def retrieve(run, settings, only=None):
    thresholds = settings["thresholds_mm"]
    entries = []
    for name, spec in settings["opendata"]["products"].items():
        if only and name not in only:
            continue
        req = request_for(spec, run, thresholds)
        out_dir = run_dir("opendata", name, run, settings)
        out_dir.mkdir(parents=True, exist_ok=True)
        start = str(req["step"][0]).split("-")[0]
        end = str(req["step"][-1]).split("-")[-1]
        target = out_dir / f"{spec['type']}_{spec.get('param', 'tpg')}_{start}-{end}h.grib2"
        inventory = out_dir / "inventory.json"
        if target.exists() and inventory.exists():
            done = json.loads(inventory.read_text())
            if done["run"] == run.isoformat() and len(done["steps"]) == len(req["step"]):
                print(f"{name:14s} already downloaded")
                entries.append(done)
                continue
        t0 = time.perf_counter()
        if spec.get("verified_ranges"):
            retrieve_ep_verified(spec, run, req, target)
        else:
            client_for(spec, settings).retrieve(target=str(target), **req)
        seconds = time.perf_counter() - t0
        params, steps = grib_summary(target)
        entry = dict(
            product=name,
            model=spec["model"],
            resol=spec["resol"],
            stream=spec["stream"],
            type=spec["type"],
            run=run.isoformat(),
            file=str(target),
            size_mb=round(target.stat().st_size / 1e6, 2),
            download_s=round(seconds, 1),
            messages_by_param=params,
            steps=steps,
        )
        (out_dir / "inventory.json").write_text(json.dumps(entry, indent=2))
        entries.append(entry)
        print(f"{name:14s} {entry['size_mb']:8.1f} MB {seconds:6.1f} s  {sum(params.values())} messages")
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", help="Run as YYYYMMDDHH (default: latest common run)")
    parser.add_argument("--products", nargs="+", help="Only these products (names in settings.yaml)")
    args = parser.parse_args()
    settings = load_settings()
    run = dt.datetime.strptime(args.run, "%Y%m%d%H") if args.run else latest_run(settings)
    print(f"Run: {run:%Y-%m-%d %H} UTC")
    retrieve(run, settings, args.products)


if __name__ == "__main__":
    main()
