"""Daily update: the 00 UTC run of today, from download to a ready-to-publish site.

Steps:
1. wait until every open-data product of the run is published (up to --max-wait-h, default 2 h);
2. download the open data and build the 24 h map layers;
3. download the ecPoint charts to T+360, waiting up to 1.5 h for Open Charts to list
   the run (failures are reported, not fatal);
4. assemble the site in DATA_ROOT/web with this run only;
5. optionally delete raw files of older runs (--keep-raw-runs).

Used by .github/workflows/daily.yml; also runs locally.

Usage:
    python -m rainfall_visualiser.daily                    # today's 00 UTC run
    python -m rainfall_visualiser.daily --run 2026102300
"""

import argparse
import datetime as dt
import shutil
import time

from . import retrieve_ecpoint, retrieve_opendata
from .build_site import build
from .config import data_root, load_settings
from .fields import build_run


def wait_for_run(run, settings, max_wait_h, poll_min=10):
    deadline = time.monotonic() + max_wait_h * 3600
    while True:
        try:
            if retrieve_opendata.run_complete(run, settings):
                return
        except Exception as err:  # network hiccups while checking: keep waiting
            print(f"availability check failed: {err!r}")
        if time.monotonic() > deadline:
            raise SystemExit(f"Run {run:%Y-%m-%d %H} UTC still incomplete after {max_wait_h} h")
        print(f"Run {run:%Y-%m-%d %H} UTC not complete yet; checking again in {poll_min} min", flush=True)
        time.sleep(poll_min * 60)


def prune_raw(settings, keep):
    """Delete raw run folders (YYYYMMDD/HHz) beyond the newest `keep` runs."""
    raw = data_root(settings) / "raw"
    run_dirs = sorted(raw.glob("*/*/[0-9]*/[0-9][0-9]z"), key=lambda p: (p.parent.name, p.name))
    stamps = sorted({(p.parent.name, p.name) for p in run_dirs}, reverse=True)
    for stamp in stamps[keep:]:
        for p in run_dirs:
            if (p.parent.name, p.name) == stamp:
                shutil.rmtree(p)
        print(f"Deleted raw files of run {stamp[0]} {stamp[1]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", help="Run as YYYYMMDDHH (default: today 00 UTC)")
    parser.add_argument("--max-wait-h", type=float, default=2, help="Hours to wait for the open data")
    parser.add_argument("--skip-ecpoint", action="store_true", help="Do not download ecPoint charts")
    parser.add_argument("--keep-raw-runs", type=int, default=None, help="Keep raw files of this many runs")
    args = parser.parse_args()
    settings = load_settings()
    if args.run:
        run = dt.datetime.strptime(args.run, "%Y%m%d%H")
    else:
        today = dt.datetime.now(dt.timezone.utc).date()
        run = dt.datetime(today.year, today.month, today.day, 0)
    print(f"Run: {run:%Y-%m-%d %H} UTC; data root: {data_root(settings)}", flush=True)

    wait_for_run(run, settings, args.max_wait_h)
    retrieve_opendata.retrieve(run, settings)
    build_run(run, settings)
    if not args.skip_ecpoint:
        try:
            retrieve_ecpoint.retrieve(run, 360, settings)
        except Exception as err:  # the forecasts are published even without ecPoint
            print(f"WARNING: ecPoint download stopped: {err!r}")
    build(run, rebuild_fields=False, settings=settings, only_this_run=True)
    if args.keep_raw_runs is not None:
        prune_raw(settings, args.keep_raw_runs)


if __name__ == "__main__":
    main()
