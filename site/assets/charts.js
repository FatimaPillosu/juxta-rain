// Point charts drawn as plain SVG (no chart library), in the Juxta Rain style.
"use strict";

const CHART_COLOURS = {
  ifs: "#BA55D3", ifsTint: "#DDAAE9",   // medium orchid (IFS)
  aifs: "#FF6347", aifsTint: "#FFB1A3", // tomato (AIFS)
  grid: "#eceff1", axis: "#9aa5ad",
  ecBand: "rgba(26, 163, 154, 0.18)", ecEdge: "rgba(14, 127, 120, 0.45)", // ecPoint class range
};
const SVG_NS = "http://www.w3.org/2000/svg";

function niceStep(max, targetTicks = 5) {
  const raw = max / targetTicks;
  const pow = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= raw);
}

function svgEl(tag, attrs, text) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  return el;
}

// Shared frame: slots for each window, y grid on the right, T+ labels every 48 h,
// a marker on the selected window, and a transparent hit area per slot.
function chartFrame(el, { leads, sel, onSelect, yMax, yStep, yFmt, height }) {
  const W = 1100, H = height, top = 22, bot = 28, left = 8, right = 46;
  const slot = (W - left - right) / leads.length;
  const x = (i) => left + (i + 0.5) * slot;
  const y = (v) => H - bot - (Math.min(v, yMax) / yMax) * (H - top - bot);
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  for (let v = 0; v <= yMax + 1e-9; v += yStep) {
    svg.append(svgEl("line", { x1: left, x2: W - right, y1: y(v), y2: y(v), stroke: CHART_COLOURS.grid }));
    svg.append(svgEl("text", { x: W - right + 8, y: y(v) + 4 }, yFmt(v)));
  }
  svg.append(svgEl("line", { x1: left, x2: W - right, y1: H - bot, y2: H - bot, stroke: CHART_COLOURS.axis }));
  leads.forEach((L, i) => {
    if ((L - leads[0]) % 48 === 0) svg.append(svgEl("text", { x: x(i), y: H - 8, "text-anchor": "middle" }, `T+${L}`));
  });
  if (sel >= 0) {
    svg.append(svgEl("line", { x1: x(sel), x2: x(sel), y1: top - 10, y2: H - bot, stroke: CHART_COLOURS.axis }));
    const label = `T+${leads[sel] - 24}–${leads[sel]}`;
    const nearRight = x(sel) > W - right - 90;
    svg.append(svgEl("text", { x: x(sel) + (nearRight ? -5 : 5), y: top - 1, "text-anchor": nearRight ? "end" : "start", fill: "#7a868e" }, label));
  }
  const hits = svgEl("g", {});
  leads.forEach((L, i) => {
    const g = svgEl("g", { class: "bar-hit" });
    g.append(svgEl("rect", { class: "bg", x: left + i * slot, y: top - 10, width: slot, height: H - bot - top + 10, fill: "transparent" }));
    g.append(svgEl("title", {}, `T+${L - 24}–${L}`));
    g.addEventListener("click", () => onSelect(i));
    hits.append(g);
  });
  el.replaceChildren(svg);
  return { svg, hits, x, y, slot, H, bot };
}

// Grouped bars: IFS (left) and AIFS (right) per window; the selected window in full colour.
function barChart(el, { leads, ifs, aifs, sel, onSelect }) {
  const max = Math.max(1, ...ifs.filter(Number.isFinite), ...aifs.filter(Number.isFinite));
  const step = niceStep(max);
  const yMax = Math.ceil(max / step) * step;
  const f = chartFrame(el, { leads, sel, onSelect, yMax, yStep: step, yFmt: (v) => +v.toFixed(1), height: 250 });
  const w = f.slot * 0.36;
  const bars = svgEl("g", {});
  leads.forEach((L, i) => {
    [[ifs[i], -w, CHART_COLOURS.ifs, CHART_COLOURS.ifsTint], [aifs[i], 0, CHART_COLOURS.aifs, CHART_COLOURS.aifsTint]].forEach(([v, dx, full, tint]) => {
      if (!Number.isFinite(v)) return;
      const y0 = f.y(v);
      bars.append(svgEl("rect", { x: f.x(i) + dx, y: y0, width: w, height: f.H - f.bot - y0, fill: i === sel ? full : tint }));
    });
  });
  f.svg.insertBefore(bars, f.svg.firstChild.nextSibling);
  f.svg.append(f.hits);
}

// Probability lines for one threshold, 0–100 %. Optional band: per window [low, high]
// (the ecPoint colour class range) or null, drawn as a transparent shade behind the lines.
function lineChart(el, { leads, ifs, aifs, sel, onSelect, band }) {
  const f = chartFrame(el, { leads, sel, onSelect, yMax: 100, yStep: 25, yFmt: (v) => `${v}%`, height: 230 });
  if (band) {
    // One polygon per run of consecutive windows with a class; a lone window gets a short bar.
    let run = [];
    const flush = () => {
      if (!run.length) return;
      const half = f.slot * 0.3;
      const top = run.map((i) => [f.x(i), f.y(band[i][1])]);
      const bottom = run.map((i) => [f.x(i), f.y(band[i][0])]).reverse();
      if (run.length === 1) { top.unshift([top[0][0] - half, top[0][1]]); top[1][0] += half; bottom.unshift([bottom[0][0] + half, bottom[0][1]]); bottom[1][0] -= half; }
      const pts = [...top, ...bottom].map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(" ");
      f.svg.append(svgEl("polygon", { points: pts, fill: CHART_COLOURS.ecBand, stroke: CHART_COLOURS.ecEdge, "stroke-width": 0.8 }));
      run = [];
    };
    band.forEach((b, i) => (b ? run.push(i) : flush()));
    flush();
  }
  for (const [vals, col] of [[ifs, CHART_COLOURS.ifs], [aifs, CHART_COLOURS.aifs]]) {
    let d = "";
    vals.forEach((v, i) => {
      if (!Number.isFinite(v)) return;
      d += `${d && Number.isFinite(vals[i - 1]) ? "L" : "M"}${f.x(i).toFixed(1)},${f.y(v).toFixed(1)}`;
    });
    f.svg.append(svgEl("path", { d, fill: "none", stroke: col, "stroke-width": 2 }));
    vals.forEach((v, i) => {
      if (Number.isFinite(v)) f.svg.append(svgEl("circle", { cx: f.x(i), cy: f.y(v), r: i === sel ? 4 : 2.3, fill: col }));
    });
  }
  f.svg.append(f.hits);
}
