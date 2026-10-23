# Rainfall visualiser — shared memory

## 2026-10-22 — Claude Code

- Changes: Milestone 1 (the latest run + the look of the website). Created `AGENTS.md`, `pyproject.toml`, `.gitignore`, `config/settings.yaml`, `.claude/launch.json`, and `src/rainfall_visualiser/` (`config.py`, `retrieve_opendata.py`, `retrieve_ecpoint.py`, `fields.py`, `build_site.py`, `serve.py`). Front end in `site/` (`index.html`, `assets/app.js`, `assets/palettes.js`, `assets/style.css`, `assets/ne/` Natural Earth 1:50m lines). Python 3.11 venv in `.venv`. Data in `C:\data\rainfall_visualiser` (`raw/`, `web/`). Not a Git repository yet (the name is still to be agreed).
- Reason: Fatima asked to see one run downloaded and the website's look before the rest is built. The agreed plan is in `C:\Users\fatim\.claude\plans\in-this-project-i-partitioned-toast.md` (milestones 1–5; stop for confirmation after each).
- Findings (confirmed on data.ecmwf.int, 22 Oct 2026):
  - IFS HRES 00/12 UTC runs go to T+360 (0.1° and 0.25°), and the 06/18 UTC runs to T+144 (not T+90). The 0.1° 06 UTC files appear later than the 0.25° ones.
  - IFS ENS probabilities (`ep`, `tpg1…tpg100`, 24 h ranges every 12 h) exist for 00 UTC. For 06 UTC they were not published at 14:40 UTC. **Unverified** whether they are produced for 06/18 at all.
  - AIFS ENS publishes `tpg1…tpg100` with the same ranges. **Its `.index` files are wrong:** each `.grib2` is three joined parts, and the offsets restart at 0 for each part, so `ecmwf-opendata` silently returns corrupt fields. This was seen in all runs checked (21 Oct 00/12, 22 Oct 00/06). Workaround in `retrieve_opendata.py`: corrected byte ranges, with every field decoded and checked for the requested parameter and step. Worth reporting to ECMWF (Fatima's call).
  - tp units differ: IFS in m; AIFS in kg m⁻² (= mm). `fields.py` converts using each message's units key.
  - The open-data portal listed only 21 and 22 Oct, so history must be archived daily.
  - Open Charts is reachable from a script with an honest User-Agent (my web-fetch tool was blocked by Anubis; Python requests were not). Each chart takes about 10–12 s to render server-side. The global ecPoint PNGs are 0.8–2.4 MB, about 1.5 MB on average.
  - Network on this PC: from Git Bash and the browser, connections to `pypi.org` and `cdn.jsdelivr.net` are reset. Install with pip from PowerShell. The front end loads OpenLayers 10.2.1 from cdnjs and geotiff.js 2.1.3 from unpkg (the full OpenLayers build needs geotiff.js as the global `GeoTIFF`).
- Volumes (00 UTC run, 22 Oct): raw GRIB 235 MB (HRES 0.1° 70 MB, AIFS Single 13 MB, IFS ENS ep 74 MB, AIFS ENS ep 78 MB). COGs 227 MB (HRES 95 MB). ecPoint about 1.5 MB per chart, so about 270 MB for the full 174 charts of a 00/12 run. Drive C: had about 13 GB free.
- Verification:
  - At 4 points, the values the browser reads from the COGs (`layer.getData`) equal the GRIB values at the nearest grid point, for all 4 products (window T+0–24).
  - Coastlines line up with the fields after switching to Natural Earth lines (world-atlas TopoJSON drew spurious antimeridian lines and world copies).
  - At 375 px width there is no horizontal scroll and the maps render.
  - HRES 24 h differences give small negatives (down to −0.12 mm), which are set to 0; HRES 24 h maxima reach 790 mm in this run.
  - ecPoint: 54 charts (T+24…T+120, 6 thresholds, 00 UTC 22 Oct; 82 MB) were downloaded unchanged. The panel loads the matching PNG and links to the matching Open Charts page (checked through the page state; the final screenshot was not possible because the browser pane was hidden).
  - Not checked: a by-eye comparison of an HRES field with Open Charts.
- Open points for Fatima:
  - Colour for amounts above 500 mm (`rainfall_classes_v1` has none; currently the top class, flagged in the legend).
  - The site size per run (COGs + ecPoint about 500 MB for a 00/12 run) against GitHub Pages' 1 GB limit.
  - The time to fetch all ecPoint charts (about 22 s each, so about 1 h for a 00/12 run).
  - Whether to report the AIFS ENS index fault to ECMWF.
  - The dashboard name.

## 2026-10-22 — Claude Code

- Changes: `MEMORY.md` only. Recorded "Rain Ledger" as the working name for the dashboard, pending Fatima's final decision. No change to `AGENTS.md`, code or the site. No repository or domain has been registered.
- Reason: Fatima chose "Rain Ledger" from the naming discussion (other options included Rain Notebook, Forecast Notebook and Rainfall Almanac) and asked for it to be recorded as the working name.
- Verification (checks run 22 Oct 2026):
  - Web search (standard mode, thin results): no rainfall or weather product called "Rain Ledger" or "Rainfall Ledger". Nearest match is the Rain Tracker app, a rain diary. No extended search was run.
  - GitHub repository names (public API): no matches for "rainledger", "rainfallledger" or "forecastledger".
  - Domain registration (RDAP): rainledger.com is registered and shows an "under construction" placeholder page. rainledger.org, rainledger.io, rainledger.app, rainfallledger.org and rainfallledger.com are not registered.
  - Not checked: trademarks. "Ledger" is a widely used brand (for example, cryptocurrency hardware wallets). This is from general knowledge and has not been verified. Reserved or premium-priced domain status is also unchecked.
- Open points:
  - Trademark check before any public use of the name.
  - Final dashboard name and repository name still to agree. The repository must not be created until then.
  - If the name is confirmed, a .org or .app domain is the likely option, as .com is taken.

## 2026-10-22 — Claude Code (Milestone 1 review changes)

- Changes:
  - `site/assets/palettes.js`: amounts now use the ECMWF-style colour bar supplied by Fatima (0.5 … 1000 mm, then above 1000). The colours are the pixel-sampled values from `projects/irish_ffc/src/irish_ffc/rainfall_style.py`, which matched her image to within a few RGB units. Values below 0.5 mm are white. This replaces `rainfall_classes_v1` for this project and resolves the "above 500 mm" open point.
  - `site/index.html`, `site/assets/app.js`, `site/assets/style.css`:
    - "IFS HRES" is renamed "IFS Control" (the Data & sources page explains it is the ensemble control, formerly HRES, since 50r1).
    - The threshold selector has moved into the probability block's header.
    - The point readout is now its own column, with separate sections for amounts and probabilities; the probability columns are aligned (right edges checked identical across rows).
    - The Verification tab is disabled and greyed, marked "coming soon", and its page removed.
    - A quieter notice bar replaces the amber warning.
    - The legend notes and the fine print under the maps were removed.
  - Ten layout mockups (static HTML from real snapshots, rendered with headless Edge) are in the session scratchpad, not in the project.
- Reason: Fatima's review of Milestone 1. The overall look is still to be chosen from the mockups.
- Verification: table alignment was checked through the DOM. A visual check of the live site was limited because the browser pane was narrow or hidden; the mockups were reviewed as PNGs.

## 2026-10-22 — Claude Code (second review round)

- Changes:
  - IFS ENS probabilities now come from the 0.1° open data (`config/settings.yaml`: `resol: "0p1"`; the files are split `-ep-sfc`/`-ep-pl`, and the index offsets were checked as correct). Raw GRIB is 383 MB per 00 UTC run (was 74 MB) and the COGs 299 MB (was 61 MB), so the COGs for one run now total about 464 MB.
  - `retrieve_opendata.py` has a `--products` option.
  - `build_site.py` writes a copy of each ecPoint chart cropped to its map area (`*_map.png`, 1979×988, plate carrée −180…180, −90…90) next to the unchanged original. The frame `ecpoint.map_frame_px = [10.2, 293.8, 1988.8, 1282.0]` was fitted to the 20°/10° gridlines of 45 charts (spread ≤ 0.2 px). The site states "cropped to the map area; otherwise unchanged".
  - Live site text: "Data & Sources"; "coming soon" in small type below "Verification"; "grid-box values · mm" removed; IFS ENS labelled 0.1°.
  - Mockup 11 (scratchpad) follows Fatima's references: a charcoal top bar with logo tiles, plus an Analytika-like body (white, Roboto, teal accent, cards). It shows the full-width point table under the window runner, three equal probability maps including the cropped ecPoint, a bar chart of 24 h totals by window, and a probability-by-lead-time line chart with threshold tabs.
- Reason: Fatima's review of the mockups; she rejected mockups 01–10 as looking AI-made.
- Verification: the crop frame is consistent across charts; the live page loads the `_map.png` and IFS ENS reports 0.1° (checked through the DOM).
- Open points: approval of the mockup 11 style before restyling the live site; the site size against GitHub Pages' 1 GB limit (now worse with ENS at 0.1°).

## 2026-10-22 — Claude Code (name and model colours)

- Changes: The public name is **Rain Ledger** (Fatima). It is set in `site/index.html` (title and header; the "working title" chip is removed), in mockup 11 (the logo tiles are replaced by one placeholder tile; the logo comes later) and in `AGENTS.md` key decisions. Model colours chosen by Fatima are in `AGENTS.md` and mockup 11: IFS #BA55D3, AIFS #FF6347.
- Reason: Fatima chose the name and the colours.
- Verification: the live page title and header read "Rain Ledger" (grep of the built file); mockup 11 re-rendered and checked by eye.
- Open points: the logo; approval of mockup 11 before restyling; the repository name (Rain Ledger suggests `rain-ledger`, not yet confirmed).

## 2026-10-22 — Claude Code (live site restyled to mockup 11; ecPoint from PDF)

- Changes:
  - `site/index.html`, `site/assets/style.css`, `site/assets/app.js` rewritten to the approved mockup 11:
    - charcoal top bar (logo placeholder, "Rain Ledger", notice), breadcrumb with the run selector, tabs with a teal underline;
    - "Forecast" title with the window runner and a thin teal slider; full-width point table;
    - two amount maps; three probability maps with threshold tabs; two point charts.
  - New `site/assets/charts.js`: dependency-free SVG grouped bars (IFS Control vs AIFS Single by window) and probability lines (IFS ENS vs AIFS ENS for the selected threshold), in the IFS #BA55D3 / AIFS #FF6347 colours. Clicking a window selects it.
  - Point values: click a map to pin a point (remembered in the browser; default Reading, UK, 51.44°N 0.94°W). The page reads the nearest grid point from each window's COG with geotiff.js: the selected window first, then all 29 windows × 4 products for the charts.
  - Maps: each map has its own view, kept in sync so all panels show the same area whatever their width. The ecPoint panel is now an OpenLayers image layer that zooms with the others. The scale bar was removed (misleading in degrees).
  - `fields.py`: COGs are now written with 128 px tiles. One click costs 116 requests and about 4.8 MB, against about 11 MB with 256 px tiles.
  - `serve.py`: loopback-only listeners on both IPv4 and IPv6, plus HTTP/1.1 keep-alive. With the previous IPv4-only HTTP/1.0 server, each request took about 0.4 s in the browser on Windows (a full click took 27 s; now 0.4 s).
  - ecPoint: Open Charts also serves the chart as a vector PDF (`format=pdf`; SVG returns HTTP 500; `width` is ignored). `retrieve_ecpoint.py` now downloads PDFs (`settings.yaml: ecpoint.format: pdf`, about 6.5–9.4 MB each, against about 1.5 MB for a PNG). `build_site.py` checks the frame lines, then renders only the map area (`map_frame_pt: [92.25, 107.29, 749.45, 435.92]`, read from the vector gridlines) to a 6000×3000 lossless WebP (about 0.8 MB). The raw PDFs are kept unchanged; the PNG crop path remains for older PNG downloads.
  - `pyproject.toml`: adds `pymupdf`.
- Verification:
  - Point values in the page match the GRIB (Kingston T+24: 0.1 mm IFS Control, 0.8 mm AIFS Single).
  - All five map extents are identical after zooming one map.
  - At 375 px there is no horizontal overflow.
  - A desktop screenshot (headless Edge) was reviewed against mockup 11.
  - The PDF render is clearly sharper than the PNG in a Caribbean crop, and both crops line up.
- Open points:
  - Downloading PDFs costs ECMWF about 4–6 times more bandwidth per chart than PNGs.
  - The site size against GitHub Pages' 1 GB limit (COGs about 470 MB per run plus ecPoint WebPs).
  - Click latency on GitHub Pages is not yet measured.

## 2026-10-22 — Claude Code (ecPoint to T+360; colour class at the point)

- Changes:
  - `retrieve_ecpoint.py` skips charts already downloaded and saves `charts.json` after every chart. It was run with `--max-lead 360` to fetch the remaining 120 charts of the 00 UTC run (00/12 UTC runs go to T+360; 06/18 UTC to T+144).
  - New `ecpoint_classes.py`: redraws only the chart's legend-coloured drawing (filled polygons with their same-colour outlines, plus stroke-only contour lines in legend colours), in the original order and without anti-aliasing, over the map frame at 6000×3000. It then maps each pixel's colour to the 12 legend classes and writes a uint8 COG (`*_class.tif`, about 0.35 MB each).
  - `build_site.py` makes the WebP and the class raster for each chart in 4 parallel processes, skipping charts already done. `charts.json` on the site gains `class_file` and `class_edges_pct`.
  - `app.js` adds an "ecPoint · chart colour class" row to the point table: one class range per threshold for the selected window (6 small reads). The Data & Sources page explains the method and that it gives a colour class, not a value, and is not used in scores.
- Reason: Fatima asked for all ecPoint charts to T+360 and for the probability range of the chart colour at the chosen point.
- Verification:
  - Class agreement with the chart rendered as published (no anti-aliasing), on pixels showing a clean legend colour: 99.979 % (>10 mm T+48), 99.949 % (>1 mm T+24), 99.996 % (>50 mm T+96). Before adding the outlines and contour lines it was only 92 %.
  - In the page, Rome (41.9N 12.5E, T+24–48) gives classes [9, 5, 3, 0, 0, 0], the same as the displayed colours.
  - Kingston gives [10, 9, 8, 7, 4, 2]. The 7 at >25 mm lies exactly on a 6/7 class boundary under the coastline, so the displayed image shows coastline there.
- Open points:
  - At a class boundary, the class depends on the exact pixel (0.06°); the page shows a single class. It could show both classes when neighbouring pixels differ.

## 2026-10-22 — Claude Code (Juxta Rain; logo; ecPoint band; all charts to T+360)

- Changes:
  - Name changed to **Juxta Rain** (Fatima), replacing "Rain Ledger": title, header, meta description, comments, browser storage key, and `AGENTS.md`.
  - Logo: Fatima's `juxta-rain-logo.svg` is copied to `site/assets/` with only its viewBox tightened to the artwork (179–813 × 88.5–460). It contains the wordmark, so it is shown at 60 px on the white header row (48 px on phones); the charcoal bar keeps a small text name.
  - Probability chart: a transparent teal band shows the ecPoint colour class range at the point, for each window and the selected threshold (`charts.js` `band`; `app.js` `loadEcpointSeries`, 29 small reads cached per point and threshold). The key reads "ecPoint chart colour class (range)"; the Data & Sources page mentions the band.
  - ecPoint: all 174 charts of the 00 UTC run (6 thresholds × T+24…T+360) are downloaded as PDFs and built. The ecPoint image is now smoothed on display (`interpolate: true`), because unsmoothed downsampling of the 6000 px picture speckled the coastlines.
- Verification:
  - Full-page desktop screenshot reviewed: logo, point table with the ecPoint row, band in the probability chart.
  - In the browser at T+360 the ecPoint panel shows `thr10_T360_map.webp`.
- Open points: **site size**. One run is now 921 MB (COGs about 450 MB; ecPoint WebPs 417 MB at about 2.4 MB each; class rasters 57 MB), almost the whole 1 GB GitHub Pages limit. Options: lossy WebP for the ecPoint pictures, a smaller render width, or hosting the rasters elsewhere. Fatima to decide.

## 2026-10-22 — Claude Code (ecPoint pictures as lossy WebP)

- Changes: `build_site.py` `render_pdf_map` encodes each 6000×3000 ecPoint picture twice (lossy WebP at quality 90, method 6; and lossless) and keeps the smaller one. The quality is set in `settings.yaml` (`ecpoint.map_webp_quality: 90`). All 174 pictures were re-rendered; the class rasters are unchanged.
- Reason: Fatima chose high-quality lossy WebP at 6000 px to cut the site size.
- Verification:
  - Test on three charts: lossy q90 halves busy charts (>1 mm T+24: 5.60 → 2.75 MB) but enlarges sparse ones (>100 mm T+120: 0.85 → 0.95 MB), hence the smaller-of-two rule. Mean colour error is 0.4–3.3 out of 255.
  - A zoomed side-by-side over the UK and North Sea of the busiest chart shows no visible difference.
  - New sizes: ecPoint pictures 417 → 273 MB (0.79–2.75 MB each). One run in total 921 → 776 MB: IFS ENS 286 MB, ecPoint pictures 273 MB, IFS Control 93 MB, class rasters 57 MB, AIFS ENS 54 MB, AIFS Single 16 MB.
- Open points: at 776 MB only one run fits within GitHub Pages' 1 GB limit, so more runs online would need other hosting for the rasters. To decide in the hosting milestone.

## 2026-10-23 — Claude Code (published on GitHub Pages)

- Changes:
  - GitHub CLI 2.103.0 installed with winget at `C:\Program Files\GitHub CLI\gh.exe`; it is not on the PATH of terminals opened before the install. Fatima logged in with `gh auth login` as FatimaPillosu.
  - Public repository https://github.com/FatimaPillosu/juxta-rain created. `main` holds the code only (commit f1bd55c; README.md added; `.gitignore` excludes data, `.venv`, `*.egg-info`, `.claude/settings.local.json`).
  - The built site (00 UTC run of 22 Oct, 778 MB) is a separate git repository in `C:\data\rainfall_visualiser\web` on branch `gh-pages` (commit 4fc62b3, with `.nojekyll`), pushed in 3 minutes. GitHub enabled Pages from `gh-pages` automatically; HTTPS is enforced.
  - Download of the 00 UTC run of 23 Oct started (open data, then the 174 ecPoint PDFs).
- Verification: the Pages build reports "built". https://fatimapillosu.github.io/juxta-rain/ returns HTTP 200 with title "Juxta Rain", and `data/runs.json` returns 200. In the browser there were no console errors; a click at Paris filled the table in 0.7 s and both charts in 1.7 s (39 range requests, about 750 kB; GitHub serves HTTP/2).
- Storage on 23 Oct, about 10 UTC: `C:\data\rainfall_visualiser` 3.7 GB.
  - Raw for the 22 Oct run: GRIB 521 MB, ecPoint PDFs plus the earlier PNGs 1.4 GB.
  - `web` 1.6 GB: the 778 MB site plus its git copy in `web/.git`.
  - Drive C: 23 GB free.
- Open points: a retention policy for raw data and runs; how to update `gh-pages` without the repository growing (orphan commit + force-push); the daily automation; observations and verification; the point archive; tests.

## 2026-10-23 — Claude Code (daily automation; 00 UTC only)

- Changes:
  - Fatima decided on a minimum viable product: only the 00 UTC run, updated daily without her PC.
  - The local ecPoint download for 23 Oct was stopped at 30 charts, to avoid requesting the same charts twice. Yesterday's data was deleted from `C:\data` (raw GRIB, ecPoint PDFs, built site and the local `gh-pages` git copy); 1.5 GB remains, all for 23 Oct.
  - New `daily.py`: waits for today's 00 UTC run to be complete (`retrieve_opendata.run_complete`, checks the last step of every product), downloads (skipping complete files), builds the layers, downloads ecPoint (retries; failures are not fatal), and assembles the site with this run only. Optional `--keep-raw-runs` and `--skip-ecpoint`.
  - `config.data_root` honours the `RAIN_DATA_ROOT` environment variable. `build_site` publishes without ecPoint if that step fails, and has `--only-this-run`.
  - `retrieve_ecpoint` retries HTTP errors (30/60/120 s), skips a chart that still fails and reports it. Open Charts returned HTTP 500 once on 23 Oct (T+72 >1 mm), which had stopped the old version.
  - New `.github/workflows/daily.yml`: cron 10:30 UTC plus a manual trigger; ubuntu-latest, Python 3.11; `pip install -e .`; runs `daily`; uploads `/home/runner/rain-data/web` as the Pages artifact; deploys with `actions/deploy-pages@v4`.
  - Pages source switched to "workflow" (`gh api -X PUT .../pages -f build_type=workflow`). Commit 96fc774 pushed; run 39966932932 started for 2026102300.
- Verification:
  - Local test of `daily --run 2026102300 --skip-ecpoint --keep-raw-runs 1`: the completeness check passed, downloads were skipped, the layers and site were built with one run, and nothing was pruned (13 min on this PC).
  - On GitHub, the Install step succeeded (Linux wheels for eccodes, rasterio and pymupdf).
- Open points:
  - Whether Open Charts accepts requests from GitHub's servers (to be seen in this run).
  - Delete the old `gh-pages` branch (778 MB) once the workflow deploy is confirmed.
  - No history is stored anywhere; the verification archive is still to be decided.
