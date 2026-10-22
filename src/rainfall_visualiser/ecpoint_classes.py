"""Probability classes of an ecPoint chart, read from its own filled polygons.

The Open Charts PDF draws each probability class as vector polygons filled with
one of the 12 legend colours, outlined and contoured with lines in the same
colours. To tell which class covers a point, only this legend-coloured drawing is
redrawn (in its original order, so the stacking is the same), without coastlines,
gridlines or anti-aliasing, over the map area. Every pixel then carries exactly
one legend colour, which is converted to its class index (0 = 0-0.5 %, ...,
11 = 80.5-100 %). Pixels not covered by any class polygon are white on the
chart, i.e. class 0.

Checked on 22 Oct 2026 against the chart rendered as published (no anti-aliasing):
the class agrees on 99.95-99.996 % of the pixels showing a clean legend colour
(charts > 1, 10 and 50 mm).

This identifies the colour class shown on the chart; it does not recover the
underlying probability, only its class range.
"""

import numpy as np
import pymupdf
import rasterio
from rasterio.transform import from_bounds

# Legend of medium-point-rain-prob-24h (Open Charts API, 22 Oct 2026): colour -> class.
LEGEND = ["#FFFFFF", "#93E5EF", "#03BFDB", "#08B542", "#16EF5E", "#BFEA19", "#96BC06",
          "#E08204", "#FC9916", "#F75466", "#DD42F9", "#840896"]
EDGES = [0, 0.5, 2.5, 4.5, 7.5, 10.5, 15.5, 20.5, 30.5, 40.5, 60.5, 80.5, 100]
RGB = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in LEGEND]
NODATA = 255


def _is_legend(colour):
    if not colour or len(colour) != 3:
        return False
    rgb = tuple(round(c * 255) for c in colour)
    return any(max(abs(a - b) for a, b in zip(rgb, ref)) <= 3 for ref in RGB)


def _redraw_fills(src_page, frame):
    """New one-page PDF holding only the legend-coloured drawing inside the frame.

    Kept, in their original order: filled polygons (with their same-colour
    outline) and stroke-only contour lines drawn in a legend colour. Dropped:
    coastlines, borders, gridlines and anything else not in a legend colour.
    """
    out = pymupdf.open()
    page = out.new_page(width=src_page.rect.width, height=src_page.rect.height)
    shape = page.new_shape()
    drawn = 0
    for path in src_page.get_drawings():
        if not path["rect"].intersects(frame):
            continue
        fill = path.get("fill") if _is_legend(path.get("fill")) else None
        stroke = path.get("color") if path.get("type") in ("s", "fs") and _is_legend(path.get("color")) else None
        if fill is None and stroke is None:
            continue
        for item in path["items"]:
            kind = item[0]
            if kind == "l":
                shape.draw_line(item[1], item[2])
            elif kind == "c":
                shape.draw_bezier(item[1], item[2], item[3], item[4])
            elif kind == "re":
                shape.draw_rect(item[1])
            elif kind == "qu":
                shape.draw_quad(item[1])
        # The chart also strokes each polygon in its fill colour, which widens the
        # coloured area; keep the stroke so the classes match what is displayed.
        shape.finish(fill=fill, color=stroke, width=(path.get("width") or 0) if stroke else 0,
                     lineCap=max(path.get("lineCap") or (0,)), lineJoin=path.get("lineJoin") or 0,
                     even_odd=path.get("even_odd", False), closePath=path.get("closePath", fill is not None))
        drawn += 1
    shape.commit()
    return out, drawn


def classify_pdf(pdf_path, out_path, frame_pt, width_px):
    """Write a uint8 GeoTIFF of class indices over -180..180, -90..90."""
    src = pymupdf.open(pdf_path)
    frame = pymupdf.Rect(*frame_pt)
    doc, drawn = _redraw_fills(src[0], frame)
    zoom = width_px / frame.width
    aa = pymupdf.TOOLS.show_aa_level()
    pymupdf.TOOLS.set_aa_level(0)
    try:
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=frame, alpha=False)
    finally:
        pymupdf.TOOLS.set_aa_level(aa["graphics"])
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).astype(np.int16)
    # The PDF stores colours as fractions, so rendered values can be 1 unit off the
    # legend (e.g. 0.898 * 255 = 228.99 -> 228); match within 3 units per channel.
    classes = np.full(rgb.shape[:2], NODATA, np.uint8)
    for k, colour in enumerate(RGB):
        classes[(np.abs(rgb - np.array(colour, np.int16)) <= 3).all(axis=2)] = k
    unmatched = int((classes == NODATA).sum())
    profile = dict(driver="COG", width=pix.width, height=pix.height, count=1, dtype="uint8", nodata=NODATA,
                   crs="EPSG:4326", transform=from_bounds(-180, -90, 180, 90, pix.width, pix.height),
                   compress="DEFLATE", blocksize=128, overviews="NONE")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(classes, 1)
    return dict(polygons=drawn, unmatched_pixels=unmatched, total_pixels=int(classes.size))
