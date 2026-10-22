// Juxta Rain front end (OpenLayers full build + geotiff.js, no bundler).
"use strict";

const PRODUCTS = {
  ifs_hres: { label: "IFS Control", kind: "amount" },
  aifs_single: { label: "AIFS Single", kind: "amount" },
  ifs_ens_prob: { label: "IFS ENS", kind: "probability" },
  aifs_ens_prob: { label: "AIFS ENS", kind: "probability" },
};
const ECPOINT_PAGE = "https://charts.ecmwf.int/products/medium-point-rain-prob-24h";
// Default point until the user clicks a map: Reading, UK. The last chosen point is remembered per browser.
const DEFAULT_POINT = { lon: -0.94, lat: 51.44 };

const state = { runs: [], run: null, fields: null, ecpoint: null, leads: [], leadIdx: 0, thrIdx: 2,
                point: null, series: null, userMoved: false, seriesToken: 0, ecClasses: null, ecToken: 0,
                ecSeries: new Map(), ecSeriesToken: 0 };
const maps = {}; // product -> { map, layer }
let ecMap = null; // { map, layer }

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n) => String(n).padStart(2, "0");
const fmtTime = (d) => `${DAYS[d.getUTCDay()]} ${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]} ${pad(d.getUTCHours())} UTC`;
const fmtRun = (d) => `${DAYS[d.getUTCDay()]} ${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()} ${pad(d.getUTCHours())} UTC`;
const stamp = (d) => d.toISOString().slice(0, 13).replace(/[-T]/g, "") + "00";
const hexToRgba = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16), 1];
const runDate = () => new Date(state.run.run + "Z");
const fmtPos = ({ lat, lon }) => `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? "N" : "S"} ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? "E" : "W"}`;
const thresholds = () => state.fields.thresholds_mm;
const thr = () => thresholds()[state.thrIdx];

function colourExpr(value, pal) {
  const expr = ["case"];
  for (let i = 1; i < pal.colours.length; i++) expr.push(["<", value, pal.edges[i]], hexToRgba(pal.colours[i - 1]));
  expr.push(hexToRgba(pal.colours[pal.colours.length - 1]));
  return expr;
}

function layerStyle(kind) {
  if (kind === "amount") {
    // band 1 = 0.1 mm units, band 2 = alpha (nodata)
    return { color: ["case", ["==", ["band", 2], 0], [0, 0, 0, 0], colourExpr(["*", ["band", 1], 0.1], AMOUNT)] };
  }
  const nb = thresholds().length;
  return { color: ["case", ["==", ["band", nb + 1], 0], [0, 0, 0, 0], colourExpr(["band", state.thrIdx + 1], PROB)] };
}

// ---------- maps ----------
// Plate carrée, like the global ecPoint chart. The view cannot pan beyond the globe.
// Each map has its own view; views are kept in step so that every panel shows the
// same area whatever its width (see syncFrom).
const newView = () => new ol.View({
  projection: "EPSG:4326", center: [0, 0], zoom: 1, minZoom: 0, maxZoom: 10,
  extent: [-180, -90, 180, 90], showFullExtent: true,
});
let syncing = false;

function syncFrom(map) {
  const size = map.getSize();
  if (syncing || !size || !size[0]) return;
  syncing = true;
  const view = map.getView();
  const span = view.getResolution() * size[0]; // degrees across the panel
  for (const other of allMaps()) {
    const s = other.getSize();
    if (other === map || !s || !s[0]) continue;
    other.getView().setCenter(view.getCenter());
    other.getView().setResolution(span / s[0]);
  }
  syncing = false;
}
// Natural Earth 1:50m coastlines and land boundaries (public domain, v5.1.2), as lines.
const lines = (file) => new ol.source.Vector({ url: "assets/ne/" + file, format: new ol.format.GeoJSON(), wrapX: false, overlaps: false });
const coastSource = lines("coastline_50m.geojson");
const borderSource = lines("borders_50m.geojson");
const pointSource = new ol.source.Vector({ wrapX: false });
const pointFeature = new ol.Feature();
pointSource.addFeature(pointFeature);
const pointStyle = new ol.style.Style({
  image: new ol.style.Circle({ radius: 6, stroke: new ol.style.Stroke({ color: "#2f3538", width: 2 }), fill: new ol.style.Fill({ color: "rgba(255,255,255,0.5)" }) }),
});

function baseMap(target, layers) {
  const map = new ol.Map({
    target, view: newView(), layers: [...layers, new ol.layer.Vector({ source: pointSource, style: pointStyle })],
    controls: [new ol.control.Zoom()],
  });
  map.getView().on(["change:center", "change:resolution"], () => syncFrom(map));
  map.on("singleclick", (e) => setPoint({ lon: e.coordinate[0], lat: e.coordinate[1] }));
  // Keep the whole globe in view when panels resize, until the user zooms or pans.
  for (const ev of ["wheel", "pointerdown"]) map.getViewport().addEventListener(ev, () => (state.userMoved = true), { passive: true });
  map.on("change:size", () => { if (!state.userMoved) fitGlobe(); });
  return map;
}

function makeMap(product) {
  const layer = new ol.layer.WebGLTile({ style: layerStyle(PRODUCTS[product].kind) });
  const map = baseMap("map-" + product, [
    layer,
    new ol.layer.Vector({ source: borderSource, style: new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(110,110,110,0.55)", width: 0.5 }) }) }),
    new ol.layer.Vector({ source: coastSource, style: new ol.style.Style({ stroke: new ol.style.Stroke({ color: "#555", width: 0.8 }) }) }),
  ]);
  maps[product] = { map, layer };
}

function makeEcpointMap() {
  // The cropped chart already carries ECMWF's own coastlines and grid, so no vector layers are added.
  const layer = new ol.layer.Image();
  ecMap = { map: baseMap("map-ecpoint", [layer]), layer };
}

function allMaps() {
  return [...Object.values(maps), ...(ecMap ? [ecMap] : [])].map(({ map }) => map);
}

// Show the whole globe in every panel.
function fitGlobe() {
  syncing = true;
  for (const m of allMaps()) {
    const s = m.getSize();
    if (s && s[0] > 0) m.getView().fit([-180, -90, 180, 90], { size: s });
  }
  syncing = false;
}

function windowFor(product, lead) {
  const p = state.fields.products[product];
  return p && p.windows.find((w) => w.lead_h === lead);
}

function updateMaps() {
  const lead = state.leads[state.leadIdx];
  for (const product of Object.keys(PRODUCTS)) {
    const { layer } = maps[product];
    const w = windowFor(product, lead);
    const note = $("note-" + product);
    note.hidden = !!w;
    layer.setVisible(!!w);
    if (!w) {
      note.textContent = `No ${PRODUCTS[product].label} data for this window.`;
      continue;
    }
    layer.setSource(new ol.source.GeoTIFF({
      sources: [{ url: `data/${state.run.id}/${product}/${w.file}` }],
      normalize: false, interpolate: false, wrapX: false,
    }));
    layer.setStyle(layerStyle(PRODUCTS[product].kind));
  }
  updateEcpoint();
  updateLeadLabel();
}

// ---------- ecPoint ----------
function ecpointPage(lead, t) {
  const run = runDate();
  const valid = new Date(run.getTime() + lead * 3600e3);
  const q = new URLSearchParams({ base_time: stamp(run), projection: "opencharts_global", threshold: String(t / 1000), valid_time: stamp(valid) });
  return `${ECPOINT_PAGE}?${q}`;
}

function updateEcpoint() {
  const lead = state.leads[state.leadIdx];
  const charts = (state.ecpoint && state.ecpoint.charts) || [];
  const chart = charts.find((c) => c.lead_h === lead && c.threshold_mm === thr());
  const note = $("note-ecpoint"), link = $("ecpoint-link");
  link.href = chart ? chart.page : ecpointPage(lead, thr());
  if (chart) {
    ecMap.layer.setSource(new ol.source.ImageStatic({
      url: `data/${state.run.id}/ecpoint/${chart.map_file}`,
      // A picture, not data: smooth it when shown smaller than its 6000 px (otherwise coastlines speckle).
      imageExtent: state.ecpoint.map_extent, projection: "EPSG:4326", interpolate: true,
      attributions: "© ECMWF, CC BY 4.0 (cropped to the map area)",
    }));
    ecMap.layer.setVisible(true);
    note.hidden = true;
    return;
  }
  ecMap.layer.setVisible(false);
  note.hidden = false;
  const runHour = runDate().getUTCHours();
  const maxLead = runHour % 12 === 0 ? 360 : 144;
  if (lead > maxLead) {
    note.textContent = `ecPoint is not available after T+${maxLead} for ${pad(runHour)} UTC runs.`;
  } else {
    const last = charts.length ? Math.max(...charts.map((c) => c.lead_h)) : 0;
    note.textContent = `This ecPoint chart has not been downloaded yet (charts to T+${last}). Use “original” to open it on ECMWF Open Charts.`;
  }
}

// ---------- point series (nearest grid point of each model) ----------
const tiffCache = new Map();

async function readPixel(url, { lon, lat }) {
  if (!tiffCache.has(url)) tiffCache.set(url, GeoTIFF.fromUrl(url, { blockSize: 16384 }).then((t) => t.getImage()));
  const img = await tiffCache.get(url);
  const [ox, oy] = img.getOrigin();
  const [rx, ry] = img.getResolution();
  const x = Math.floor((lon - ox) / rx), y = Math.floor((lat - oy) / ry);
  if (x < 0 || y < 0 || x >= img.getWidth() || y >= img.getHeight()) return null;
  const nodata = img.getGDALNoData();
  const r = await img.readRasters({ window: [x, y, x + 1, y + 1], interleave: true });
  return Array.from(r, (v) => (v === nodata ? NaN : v));
}

async function pool(tasks, limit = 8) {
  const out = new Array(tasks.length);
  let next = 0;
  await Promise.all(Array.from({ length: limit }, async () => {
    while (next < tasks.length) { const i = next++; out[i] = await tasks[i](); }
  }));
  return out;
}

// Reads the selected window first (so the table fills at once), then the rest for the charts.
async function loadSeries() {
  const token = ++state.seriesToken;
  const point = state.point;
  const series = {};
  const task = (product, i) => async () => {
    const w = windowFor(product, state.leads[i]);
    if (w) series[product][i] = await readPixel(`data/${state.run.id}/${product}/${w.file}`, point);
  };
  const products = Object.keys(PRODUCTS);
  products.forEach((p) => (series[p] = new Array(state.leads.length).fill(null)));
  const first = state.leadIdx;
  await pool(products.map((p) => task(p, first)));
  if (token !== state.seriesToken) return; // a newer point or run was chosen meanwhile
  state.series = series;
  state.seriesComplete = false;
  renderPoint();
  await pool(products.flatMap((p) => state.leads.map((_, i) => i).filter((i) => i !== first).map((i) => task(p, i))), 12);
  if (token !== state.seriesToken) return;
  state.seriesComplete = true;
  renderPoint();
}

// ecPoint: class of the chart colour at the point, for every threshold of the selected window.
// The class rasters are made at build time from the chart's own coloured polygons
// (ecpoint_classes.py); this reads the colour class, not a forecast value.
async function loadEcpointClasses() {
  const token = ++state.ecToken;
  state.ecClasses = null;
  const charts = (state.ecpoint && state.ecpoint.charts) || [];
  const lead = state.leads[state.leadIdx];
  if (!state.point || !charts.some((c) => c.lead_h === lead && c.class_file)) { renderPoint(); return; }
  const point = state.point;
  const classes = await Promise.all(thresholds().map(async (t) => {
    const c = charts.find((x) => x.lead_h === lead && x.threshold_mm === t && x.class_file);
    if (!c) return null;
    const v = await readPixel(`data/${state.run.id}/ecpoint/${c.class_file}`, point);
    return v && Number.isFinite(v[0]) ? v[0] : null;
  }));
  if (token !== state.ecToken) return;
  state.ecClasses = classes;
  renderPoint();
}

// ecPoint colour class at the point for every window, for the selected threshold
// (drawn as a shaded band in the probability chart). Cached per point and threshold.
async function loadEcpointSeries() {
  const token = ++state.ecSeriesToken;
  if (!state.point || !state.ecpoint) return;
  const t = thr();
  const key = `${state.run.id}|${state.point.lon},${state.point.lat}|${t}`;
  if (state.ecSeries.has(key)) { renderPoint(); return; }
  const point = state.point;
  const charts = state.ecpoint.charts;
  const classes = await pool(state.leads.map((L) => async () => {
    const c = charts.find((x) => x.lead_h === L && x.threshold_mm === t && x.class_file);
    if (!c) return null;
    const v = await readPixel(`data/${state.run.id}/ecpoint/${c.class_file}`, point);
    return v && Number.isFinite(v[0]) ? v[0] : null;
  }), 8);
  state.ecSeries.set(key, classes);
  if (token === state.ecSeriesToken) renderPoint();
}

function ecBand() {
  if (!state.point || !state.run) return null;
  const classes = state.ecSeries.get(`${state.run.id}|${state.point.lon},${state.point.lat}|${thr()}`);
  if (!classes) return null;
  const e = (state.ecpoint && state.ecpoint.class_edges_pct) || PROB.edges;
  return classes.map((k) => (k === null || k === undefined ? null : [e[k], e[k + 1]]));
}

function ecRange(k) {
  const e = (state.ecpoint && state.ecpoint.class_edges_pct) || PROB.edges;
  return k === null || k === undefined ? "–" : `${e[k]}–${e[k + 1]}<small>%</small>`;
}

const amountAt = (product, i) => { const v = state.series && state.series[product][i]; return v ? v[0] * 0.1 : NaN; };
const probAt = (product, i, t) => { const v = state.series && state.series[product][i]; return v ? v[t] : NaN; };

function renderPoint() {
  const i = state.leadIdx;
  const fmt = (v, unit) => (Number.isFinite(v) ? `${v.toFixed(unit === "mm" ? 1 : 0)}<small>${unit === "mm" ? "mm" : "%"}</small>` : "–");
  $("ro-place").innerHTML = state.point
    ? `<b>${fmtPos(state.point)}</b> · nearest grid point of each model · click a map to change`
    : "Click any map to choose a point";
  $("ro-ctrl").innerHTML = fmt(amountAt("ifs_hres", i), "mm");
  $("ro-aifs").innerHTML = fmt(amountAt("aifs_single", i), "mm");
  const hl = (k) => (k === state.thrIdx ? ' class="hl"' : "");
  const row = (p) => `<tr><th class="m">${PRODUCTS[p].label}</th>${thresholds().map((_, k) => `<td${hl(k)}>${fmt(probAt(p, i, k), "%")}</td>`).join("")}</tr>`;
  const ecRow = `<tr class="ec-row"><th class="m">ecPoint <span class="note">chart colour class</span></th>${thresholds().map((_, k) => `<td${hl(k)}>${state.ecClasses ? ecRange(state.ecClasses[k]) : "–"}</td>`).join("")}</tr>`;
  $("ro-table").innerHTML = `<tr><th></th>${thresholds().map((t, k) => `<th${hl(k)}>&gt; ${t} mm</th>`).join("")}</tr>${row("ifs_ens_prob")}${row("aifs_ens_prob")}${ecRow}`;
  const where = state.point ? fmtPos(state.point) : "the point";
  if (!state.series || !state.seriesComplete) {
    const msg = state.point ? `<p class="chart-empty">Loading values at ${where}…</p>` : `<p class="chart-empty">Click any map to choose a point.</p>`;
    $("chart-bars").innerHTML = msg;
    $("chart-lines").innerHTML = msg;
    return;
  }
  $("bars-title").textContent = `24 h totals at ${where}`;
  $("lines-title").textContent = `Probability above threshold at ${where}`;
  $("lines-sub").textContent = `P(24 h precipitation > ${thr()} mm) by 24 h window`;
  const idx = state.leads.map((_, k) => k);
  barChart($("chart-bars"), { leads: state.leads, sel: i, onSelect: setLead,
    ifs: idx.map((k) => amountAt("ifs_hres", k)), aifs: idx.map((k) => amountAt("aifs_single", k)) });
  lineChart($("chart-lines"), { leads: state.leads, sel: i, onSelect: setLead, band: ecBand(),
    ifs: idx.map((k) => probAt("ifs_ens_prob", k, state.thrIdx)), aifs: idx.map((k) => probAt("aifs_ens_prob", k, state.thrIdx)) });
}

function setPoint(point) {
  state.point = { lon: Math.max(-180, Math.min(180, point.lon)), lat: Math.max(-90, Math.min(90, point.lat)) };
  pointFeature.setGeometry(new ol.geom.Point([state.point.lon, state.point.lat]));
  try { localStorage.setItem("juxta-rain-point", JSON.stringify(state.point)); } catch (e) { /* storage unavailable */ }
  state.series = null;
  state.seriesComplete = false;
  renderPoint();
  loadSeries();
  loadEcpointClasses();
  loadEcpointSeries();
}

// ---------- controls ----------
function updateLeadLabel() {
  const lead = state.leads[state.leadIdx];
  const end = new Date(runDate().getTime() + lead * 3600e3);
  const start = new Date(end.getTime() - 24 * 3600e3);
  $("lead-label").textContent = `${fmtTime(start)} → ${fmtTime(end)} · T+${lead - 24}–${lead}`;
  const slider = $("lead-slider");
  slider.value = state.leadIdx;
  slider.style.setProperty("--pct", `${(state.leadIdx / Math.max(1, state.leads.length - 1)) * 100}%`);
}

function setLead(i) {
  state.leadIdx = Math.max(0, Math.min(state.leads.length - 1, i));
  updateMaps();
  renderPoint();
  loadEcpointClasses();
}

function setThreshold(k) {
  state.thrIdx = k;
  renderThresholdTabs();
  updateMaps();
  renderPoint();
  loadEcpointSeries();
}

function renderThresholdTabs() {
  document.querySelectorAll("[data-thr-tabs]").forEach((el) => {
    el.innerHTML = thresholds().map((t, k) => `<button class="ttab${k === state.thrIdx ? " on" : ""}" data-k="${k}">&gt; ${t} mm</button>`).join("");
  });
}

function renderTicks() {
  const n = state.leads.length;
  $("lead-ticks").innerHTML = state.leads
    .map((L, i) => ((L - state.leads[0]) % 48 === 0 || i === n - 1 ? `<span style="left:${(i / (n - 1)) * 100}%">T+${L}</span>` : ""))
    .join("");
}

function buildLegend(el, pal, title) {
  const colours = pal.colours.slice(pal.legendFrom);
  const edges = pal.edges.slice(pal.legendFrom);
  const n = colours.length;
  const cells = colours.map((c) => `<span class="lg-cell${c === "#FFFFFF" ? " white" : ""}" style="background:${c}"></span>`).join("");
  const ticks = edges.map((e, i) => `<span class="lg-tick" style="left:${(i / n) * 100}%">${e === Infinity ? "inf" : e}</span>`).join("");
  el.innerHTML = `<span class="lg-title">${title}</span><div class="lg-body"><div class="lg-bar">${cells}</div><div class="lg-ticks">${ticks}</div></div>`;
}

async function loadRun(id) {
  state.run = state.runs.find((r) => r.id === id);
  state.fields = await (await fetch(`data/${state.run.fields}`)).json();
  state.ecpoint = state.run.ecpoint ? await (await fetch(`data/${state.run.ecpoint}`)).json() : null;
  const leads = new Set();
  Object.values(state.fields.products).forEach((p) => p.windows.forEach((w) => leads.add(w.lead_h)));
  state.leads = [...leads].sort((a, b) => a - b);
  state.leadIdx = Math.min(state.leadIdx, state.leads.length - 1);
  state.thrIdx = Math.min(state.thrIdx, thresholds().length - 1);
  $("lead-slider").max = state.leads.length - 1;
  renderTicks();
  renderThresholdTabs();
  $("build-info").textContent = `Run ${fmtRun(runDate())} · built ${state.fields.built.replace("T", " ").slice(0, 16)} UTC`;
  if (!Object.keys(maps).length) { Object.keys(PRODUCTS).forEach(makeMap); makeEcpointMap(); }
  tiffCache.clear();
  updateMaps();
  if (!state.userMoved) fitGlobe();
  setPoint(state.point || DEFAULT_POINT);
}

function showView() {
  const requested = (location.hash || "#forecast").slice(1);
  const name = ["forecast", "sources"].includes(requested) ? requested : "forecast";
  document.querySelectorAll(".view").forEach((v) => (v.hidden = v.id !== "view-" + name));
  document.querySelectorAll(".tabs a").forEach((a) => a.classList.toggle("active", a.dataset.view === name));
  if (name === "forecast") allMaps().forEach((m) => m.updateSize());
}

async function init() {
  window.addEventListener("hashchange", showView);
  showView();
  buildLegend($("legend-amount"), AMOUNT, "mm / 24 h");
  buildLegend($("legend-prob"), PROB, "%");
  try { state.point = JSON.parse(localStorage.getItem("juxta-rain-point")) || null; } catch (e) { state.point = null; }
  $("lead-slider").addEventListener("input", (e) => setLead(+e.target.value));
  $("lead-prev").addEventListener("click", () => setLead(state.leadIdx - 1));
  $("lead-next").addEventListener("click", () => setLead(state.leadIdx + 1));
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".ttab");
    if (b) setThreshold(+b.dataset.k);
  });
  document.addEventListener("keydown", (e) => {
    if ($("view-forecast").hidden || ["SELECT", "INPUT"].includes(document.activeElement.tagName)) return;
    if (e.key === "ArrowRight") setLead(state.leadIdx + 1);
    if (e.key === "ArrowLeft") setLead(state.leadIdx - 1);
  });
  state.runs = await (await fetch("data/runs.json")).json();
  const runSel = $("run-select");
  runSel.innerHTML = state.runs.map((r) => `<option value="${r.id}">${fmtRun(new Date(r.run + "Z"))}</option>`).join("");
  runSel.addEventListener("change", (e) => loadRun(e.target.value));
  await loadRun(state.runs[0].id);
}

init();
