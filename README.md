# Juxta Rain

**Educational resource, not a forecasting or warning service.** Do not use it to make safety decisions. For weather warnings, consult your national meteorological service (in Europe, see [Meteoalarm](https://www.meteoalarm.org)).

Juxta Rain puts side by side the 24 h precipitation forecasts that ECMWF publishes as open data:

- **IFS Control** (physics-based, 0.1°) and **AIFS Single** (machine-learned, 0.25°): 24 h totals as grid-box values.
- **IFS ENS** (0.1°) and **AIFS ENS** (0.25°): raw ensemble probabilities of exceeding 1, 5, 10, 25, 50 and 100 mm in 24 h.
- **ecPoint-Rainfall**: point-rainfall probabilities, shown as the published ECMWF Open Charts map (map area only).

It shows the difference between gridded forecasts and point values, and what it is reasonable to expect from each. A verification view against point observations is planned.

Site: <https://fatimapillosu.github.io/juxta-rain/>

## Data and licences

- ECMWF real-time open data (IFS, AIFS), `data.ecmwf.int`, retrieved with [`ecmwf-opendata`](https://github.com/ecmwf/ecmwf-opendata). Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and the ECMWF Terms of Use; [doi:10.21957/open-data](https://doi.org/10.21957/open-data).
- ecPoint-Rainfall charts: ECMWF Open Charts, product `medium-point-rain-prob-24h` (global area). © ECMWF, CC BY 4.0.
- Coastlines and boundaries: [Natural Earth](https://www.naturalearthdata.com) 1:50m (public domain).

This output is based on data and products of the European Centre for Medium-Range Weather Forecasts (ECMWF). Changes were made: 24 h totals are formed from accumulated precipitation, fields are re-encoded as Cloud-Optimised GeoTIFFs, and the ecPoint charts are cropped to their map area. ECMWF does not accept any liability whatsoever for any error or omission in the data, their availability, or for any loss or damage arising from their use. The site's *Data & Sources* page gives the full details.

## How it works

- `src/rainfall_visualiser/retrieve_opendata.py`: downloads one run of the four ECMWF products.
- `src/rainfall_visualiser/retrieve_ecpoint.py`: downloads the ecPoint charts from Open Charts (vector PDFs, sequential and paced).
- `src/rainfall_visualiser/fields.py`: 24 h windows → Cloud-Optimised GeoTIFFs.
- `src/rainfall_visualiser/ecpoint_classes.py`: the colour class of the ecPoint chart at each point (a class range, not a value).
- `src/rainfall_visualiser/build_site.py`: assembles the static site in `DATA_ROOT/web` (see `config/settings.yaml`).
- `site/`: the front end (OpenLayers, geotiff.js, plain SVG charts; no build step).

```bash
python -m rainfall_visualiser.retrieve_opendata --run 2026102200
python -m rainfall_visualiser.retrieve_ecpoint --run 2026102200
python -m rainfall_visualiser.build_site --run 2026102200
python -m rainfall_visualiser.serve
```

Data are not stored in this repository. The published site is a built snapshot on the `gh-pages` branch.
