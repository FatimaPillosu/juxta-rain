# Rainfall visualiser

Read `../../AGENTS.md` (workspace instructions) first, then this file. Read `MEMORY.md` in this directory, if it exists, before starting work, and maintain it under the rules in the workspace `AGENTS.md` ("Shared project memory").

## Purpose and scope

A public, forecaster-style dashboard for a technical audience. It shows global 24 h rainfall forecasts from ECMWF open data (IFS HRES, AIFS Single, IFS ENS and AIFS ENS probabilities) on zoomable maps, next to the published ecPoint-Rainfall charts from ECMWF Open Charts. Past days are verified against point observations (NOAA GHCNh). The aim is to show the difference between gridded forecasts and point observations, and what it is reasonable to expect from each.

- The scope is 24 h rainfall only.
- **This is not a warning service.** Every page carries a disclaimer that points users to their national meteorological service.
- The data sources, licences and attribution are reported on the site.

## Key decisions (agreed with Fatima, 22 Oct 2026)

- Observations: NOAA NCEI GHCNh (hourly). 24 h totals are built strictly from complete reports.
- Domain: global (land and sea). The user zooms into any region; verification applies to land stations.
- Runs: **only the 00 UTC run**, lead times to T+360, 24 h windows ending at 00 and 12 UTC (decided by Fatima on 23 Oct 2026 for the minimum viable product; this replaces the earlier plan for all four runs). The site shows the 00 UTC run of the current day.
- Daily update: `.github/workflows/daily.yml` runs `python -m rainfall_visualiser.daily` on GitHub's servers and deploys to GitHub Pages (Pages source: GitHub Actions), with no involvement from Fatima. Schedules: 09:37 UTC, then backups every 2 h to 17:37 UTC (24 Oct 2026); a quick `check` job stops a run if the day's run is already published (Actions cache marker `published-YYYYMMDDHH`, or the live `runs.json`). Data exist only on the temporary runner during the job; the published site holds one run and is replaced each day. Nothing is archived yet. `C:\data\rainfall_visualiser` is only a local workspace for development.
- ecPoint: the global Open Charts chart (`medium-point-rain-prob-24h`, `projection=opencharts_global`) is displayed **exactly as published**. No values are extracted from the images, so the comparison is qualitative only and ecPoint is excluded from the scores. Requests must be sequential and paced; never work around the Open Charts bot protection.
- Colours: amounts use the ECMWF-style 24 h scale supplied by Fatima on 22 Oct 2026 (0.5 … 1000 mm, then above 1000; values as in `projects/irish_ffc/src/irish_ffc/rainfall_style.py`). Probabilities use the 12-class Open Charts ecPoint palette.
- Model colours in charts: IFS (Control and ENS) #BA55D3; AIFS (Single and ENS) #FF6347. The selected window is drawn in the full colour and other windows in 50 % tints (#DDAAE9, #FFB1A3). Chosen by Fatima on 22 Oct 2026.
- Naming: the deterministic IFS forecast is called "IFS Control" (the ensemble control, formerly HRES).
- Verification is shown as "coming soon" (not clickable) for the first public release.
- Maps: GRIB → 24 h field → Cloud-Optimised GeoTIFF → OpenLayers in the browser (static site).
- Public name: **Juxta Rain** (Fatima, 22 Oct 2026; replaces the earlier "Rain Ledger"). Logo: `site/assets/juxta-rain-logo.svg`, Fatima's file with only its viewBox tightened to the artwork; it contains the wordmark, so it is shown at 60 px height on the white header row. The project folder keeps its name `rainfall_visualiser`.
- Hosting: public repository https://github.com/FatimaPillosu/juxta-rain (code only on `main`), site https://fatimapillosu.github.io/juxta-rain/.
- Work milestone by milestone, and stop for Fatima's confirmation at the end of each. Tests come last. The plan is in `MEMORY.md` and the agreed plan file.

## Conventions

- Python 3.11 venv in `.venv` (Python 3.12 is not installed on this PC). Install packages from PowerShell: Git Bash's connections to pypi.org are reset on this network.
- Raw and processed data live outside OneDrive in `DATA_ROOT` (default `C:\data\rainfall_visualiser`, set in `config/settings.yaml`). Never commit data.
- Drive C: had only about 13 GB free on 22 Oct 2026, so keep only a few runs of raw GRIB locally.

## Relevant files

- `config/settings.yaml`: data root, products, thresholds.
- `src/rainfall_visualiser/`: retrieval and processing code.
- `site/`: static front end. Serve it with `python -m http.server` from `site/`.
