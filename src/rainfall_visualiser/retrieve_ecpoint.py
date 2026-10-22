"""Download ecPoint-Rainfall charts from ECMWF Open Charts, exactly as published.

The charts are vector PDFs (or PNG images, setting ecpoint.format) (product medium-point-rain-prob-24h, global area). They
are stored and shown unchanged; no values are extracted from them.
Requests are sequential and paced (settings: ecpoint.pause_s).

Output: DATA_ROOT/raw/ecpoint/global/<YYYYMMDD>/<HH>z/thr<mm>_T<lead>.pdf, plus
charts.json with the chart metadata, licence and the matching Open Charts page.

Usage:
    python -m rainfall_visualiser.retrieve_ecpoint --run 2026102200 --max-lead 120
"""

import argparse
import datetime as dt
import json
import time

import requests

from .config import load_settings, run_dir

USER_AGENT = "rainfall-visualiser/0.1 (educational research dashboard; python-requests)"
PAGE = "https://charts.ecmwf.int/products/{product}"

# Last lead time (h) of the ecPoint charts by run hour (Open Charts API, 22 Oct 2026).
MAX_LEAD = {0: 360, 6: 144, 12: 360, 18: 144}


def chart_requests(run, thresholds_mm, max_lead):
    """24 h charts every 12 h from T+24, as offered by Open Charts."""
    last = min(max_lead, MAX_LEAD[run.hour])
    for lead in range(24, last + 1, 12):
        for thr in thresholds_mm:
            yield lead, thr


def retrieve(run, max_lead, settings):
    cfg = settings["ecpoint"]
    out_dir = run_dir("ecpoint", "global", run, settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    index = out_dir / "charts.json"
    fmt = cfg.get("format", "png")
    # Keep charts already downloaded in this format; fetch only the missing ones.
    known = json.loads(index.read_text())["charts"] if index.exists() else []
    charts = {(c["lead_h"], c["threshold_mm"]): c for c in known
              if c["file"].endswith("." + fmt) and (out_dir / c["file"]).exists()}
    for lead, thr in chart_requests(run, settings["thresholds_mm"], max_lead):
        if (lead, thr) in charts:
            continue
        valid = run + dt.timedelta(hours=lead)
        params = dict(
            base_time=f"{run:%Y-%m-%dT%H:00:00Z}",
            valid_time=f"{valid:%Y-%m-%dT%H:00:00Z}",
            projection=cfg["projection"],
            threshold=str(thr / 1000),  # Open Charts thresholds are in metres
        )
        meta = session.get(f"{cfg['api']}/{cfg['product']}/", params=dict(params, format=fmt), timeout=180)
        meta.raise_for_status()
        meta = meta.json()
        time.sleep(cfg["pause_s"])
        chart = session.get(meta["data"]["link"]["href"], timeout=180)
        chart.raise_for_status()
        name = f"thr{thr}_T{lead:03d}.{fmt}"
        (out_dir / name).write_bytes(chart.content)
        page_params = dict(params, base_time=f"{run:%Y%m%d%H%M}", valid_time=f"{valid:%Y%m%d%H%M}")
        charts[(lead, thr)] = (
            dict(
                file=name,
                threshold_mm=thr,
                lead_h=lead,
                valid_time=valid.isoformat(),
                title=meta["data"]["attributes"]["title"],
                description=meta["data"]["attributes"]["description"],
                licence=meta["meta"]["licence"],
                copyright=meta["meta"]["copyright"],
                terms=meta["meta"]["terms-and-conditions"]["href"],
                page=requests.Request("GET", PAGE.format(product=cfg["product"]), params=page_params).prepare().url,
                size_kb=round(len(chart.content) / 1e3),
            )
        )
        print(f"T+{lead:03d} >{thr:>3} mm  {len(chart.content) / 1e3:6.0f} kB", flush=True)
        # Save the index after every chart, so an interrupted run loses nothing.
        ordered = [charts[k] for k in sorted(charts)]
        index.write_text(json.dumps(dict(run=run.isoformat(), charts=ordered), indent=2))
        time.sleep(cfg["pause_s"])
    return [charts[k] for k in sorted(charts)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, help="Run as YYYYMMDDHH")
    parser.add_argument("--max-lead", type=int, default=360, help="Last lead time in hours")
    args = parser.parse_args()
    retrieve(dt.datetime.strptime(args.run, "%Y%m%d%H"), args.max_lead, load_settings())


if __name__ == "__main__":
    main()
