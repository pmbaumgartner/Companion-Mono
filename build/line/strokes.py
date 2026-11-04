# /// script
# requires-python = ">=3.12"
# dependencies = ["shapely==2.1.2"]
# ///
"""Load single-stroke glyphs: Iosevka centerline trees (from extract.mjs) and SVG fonts."""

import heapq
import json
import math
import re
import xml.etree.ElementTree as ET

from shapely import (
    LineString,
    MultiLineString,
    MultiPoint,
    Point,
    Polygon,
    voronoi_polygons,
)
from shapely.ops import linemerge, substring, unary_union


def flatten(bez, tol=4.0):
    """Polyline through one cubic, a point every `tol` units of chord length or so."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = bez
    est = (
        math.dist((x0, y0), (x1, y1))
        + math.dist((x1, y1), (x2, y2))
        + math.dist((x2, y2), (x3, y3))
    )
    n = (
        max(1, math.ceil(est / tol))
        if est > math.dist((x0, y0), (x3, y3)) + 0.01
        else 1
    )
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append(
            (
                u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3,
                u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3,
            )
        )
    return pts


def contour_points(contour):
    pts = []
    for bez in contour:
        seg = flatten(bez)
        pts.extend(seg if not pts else seg[1:])
    return pts


def region(contours):
    """Filled area of Iosevka contours (nonzero: the larger orientation fills, the other cuts)."""
    rings = [Polygon(p) for c in contours if len(p := contour_points(c)) >= 3]
    rings = [r if r.is_valid else r.buffer(0) for r in rings]
    if not rings:
        return Polygon()

    def signed(c):
        p = contour_points(c)
        return sum(
            a[0] * b[1] - b[0] * a[1] for a, b in zip(p, p[1:] + p[:1], strict=True)
        )

    signs = [signed(c) for c in contours if len(contour_points(c)) >= 3]
    major = max(range(len(signs)), key=lambda i: abs(signs[i]))
    fill = unary_union(
        [r for r, s in zip(rings, signs, strict=True) if (s > 0) == (signs[major] > 0)]
    )
    cut = unary_union(
        [r for r, s in zip(rings, signs, strict=True) if (s > 0) != (signs[major] > 0)]
    )
    return fill.difference(cut)


def lines_of(geom):
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    return [g for part in getattr(geom, "geoms", []) for g in lines_of(part)]


def resolve(node):
    """(lines, region, fill_outlines) for a tree node."""
    kind = node["kind"]
    if kind == "stroke":
        lines = [LineString(contour_points(c)) for c in node["center"] if c]
        return lines, region(node["region"]), []
    if kind == "fill":
        r = region(node["region"])
        return [], r, [r]
    parts = [resolve(c) for c in node["children"]]
    if not parts:
        return [], Polygon(), []
    if kind == "union":
        return (
            [line for p in parts for line in p[0]],
            unary_union([p[1] for p in parts]),
            [f for p in parts for f in p[2]],
        )
    if kind == "intersection":
        lines, fills = [], []
        for i, (ls, _, _) in enumerate(parts):
            others = [p[1] for j, p in enumerate(parts) if j != i]
            mask = others[0]
            for o in others[1:]:
                mask = mask.intersection(o)
            lines += [g for line in ls for g in lines_of(line.intersection(mask))]
        whole = parts[0][1]
        for p in parts[1:]:
            whole = whole.intersection(p[1])
        if all(not p[0] for p in parts):  # only fills: keep the intersected fill
            fills = [whole]
        return lines, whole, fills
    if kind == "difference":
        (ls, r, fs), rest = parts[0], parts[1:]
        cut = unary_union([p[1] for p in rest])
        lines = [g for line in ls for g in lines_of(line.difference(cut))]
        return lines, r.difference(cut), [f.difference(cut) for f in fs]
    raise ValueError(kind)


def skeleton(poly):
    """Medial axis of a thin filled shape: the longest path through its Voronoi skeleton."""
    ring = poly.exterior.segmentize(2)
    edges = voronoi_polygons(MultiPoint(ring.coords), only_edges=True)
    inner = poly.buffer(-0.5)
    graph = {}
    for e in getattr(edges, "geoms", [edges]):
        if not inner.contains(e):
            continue
        a, b = (tuple(round(v, 3) for v in c) for c in e.coords)
        w = math.dist(a, b)
        graph.setdefault(a, []).append((b, w))
        graph.setdefault(b, []).append((a, w))
    if not graph:
        return None

    def farthest(src):
        dist, prev, heap = {src: 0}, {src: None}, [(0, src)]
        while heap:
            dd, u = heapq.heappop(heap)
            if dd > dist[u]:
                continue
            for v, w in graph[u]:
                if dd + w < dist.get(v, 1e18):
                    dist[v], prev[v] = dd + w, u
                    heapq.heappush(heap, (dd + w, v))
        end = max(dist, key=dist.get)
        path = [end]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])
        return end, path

    a, _ = farthest(next(iter(graph)))
    _, path = farthest(a)
    return LineString(path).simplify(0.5) if len(path) > 1 else None


def is_thin(poly, stroke):
    """A filled shape that stands for a stroke: about a stroke wide and much longer."""
    thickness = 2 * poly.area / poly.length
    return thickness < 1.2 * stroke and poly.length / 2 > 6 * thickness


def dedupe(lines, eps=6, min_len=40):
    """Drop stretches that retrace a longer stroke within eps units."""
    kept = []
    for line in sorted(lines, key=lambda g: -g.length):
        pieces = [line]
        for k in kept:
            zone = k.buffer(eps)
            nxt = []
            for p in pieces:
                if p.intersection(zone).length > min_len:
                    nxt += [
                        q for q in lines_of(p.difference(zone)) if q.length > 2 * eps
                    ]
                else:
                    nxt.append(p)
            pieces = nxt
        kept += pieces
    return kept


def snap_joins(lines, tol):
    """Trim stroke ends that overshoot a stroke they cross near the end, and extend ends that
    stop short of one, so joins meet on the centerlines."""
    lines = list(lines)
    for i in range(len(lines)):
        for at_start in (True, False):
            s = lines[i]
            if s.is_ring or s.length < 1e-6:
                continue
            end = Point(s.coords[0] if at_start else s.coords[-1])
            others = [o for j, o in enumerate(lines) if j != i and o.length > 0]
            if not others or min(end.distance(o) for o in others) < 0.5:
                continue
            # Overshoot: the nearest crossing within tol of this end.
            best = None
            for o in others:
                for pt in lines_of_points(s.intersection(o)):
                    along = s.project(pt)
                    tail = along if at_start else s.length - along
                    if 0.5 < tail <= tol and (best is None or tail < best[0]):
                        best = (tail, along)
            if best:
                along = best[1]
                cut = (
                    substring(s, along, s.length)
                    if at_start
                    else substring(s, 0, along)
                )
                if isinstance(cut, LineString) and cut.length > 0.5:
                    lines[i] = cut
                continue
            # Gap: extend onto the nearest stroke within tol.
            o = min(others, key=end.distance)
            if end.distance(o) <= tol:
                target = o.interpolate(o.project(end)).coords[0]
                coords = list(s.coords)
                lines[i] = LineString(
                    [target, *coords] if at_start else [*coords, target]
                )
    return lines


def lines_of_points(geom):
    if geom.is_empty:
        return []
    if isinstance(geom, Point):
        return [geom]
    if isinstance(geom, LineString):
        return [Point(geom.coords[0]), Point(geom.coords[-1])]
    return [p for part in geom.geoms for p in lines_of_points(part)]


def iosevka_glyphs(path, clean=True):
    """{char: (advance, [polyline])}: centerlines, skeletons of thin fills, and dot outlines."""
    with open(path) as f:
        data = json.load(f)
    stroke = data["metrics"]["stroke"]
    out = {}
    for g in data["glyphs"].values():
        lines, _, fills = resolve(g["tree"])
        rings = []
        for f in fills:
            for poly in getattr(f, "geoms", [f]):
                if poly.is_empty:
                    continue
                if (
                    clean
                    and is_thin(poly, stroke)
                    and (sk := skeleton(poly)) is not None
                ):
                    lines.append(sk)
                else:
                    rings.append(list(poly.exterior.coords))
        if clean and lines:
            lines = snap_joins(dedupe(lines), 1.5 * stroke)
        merged = linemerge(MultiLineString(lines)) if lines else None
        polys = [list(line.coords) for line in lines_of(merged)] if merged else []
        polys += rings
        for u in g["unicodes"]:
            out[chr(u)] = (g["advance"], polys)
    return data["metrics"], out


def svg_font_glyphs(path):
    """{char: (advance, [polyline])} from an SVG font of M/L paths, y up."""
    root = ET.parse(path).getroot()
    ns = {"s": "http://www.w3.org/2000/svg"}
    font = root.find(".//s:font", ns)
    default = float(font.get("horiz-adv-x"))
    out = {}
    for g in font.findall("s:glyph", ns):
        u = g.get("unicode")
        if not u or len(u) != 1:
            continue
        polys, nums, cmd = [], [], None
        for tok in re.findall(r"[MLC]|-?[\d.]+(?:e-?\d+)?", g.get("d", "")):
            if tok in "MLC":
                cmd = tok
                continue
            nums.append(float(tok))
            if cmd in "ML" and len(nums) == 2:
                if cmd == "M":
                    polys.append([])
                polys[-1].append(tuple(nums))
                nums, cmd = [], "L"
            elif cmd == "C" and len(nums) == 6:
                p0 = polys[-1][-1]
                c1, c2, p3 = nums[0:2], nums[2:4], nums[4:6]
                polys[-1] += flatten((p0, c1, c2, p3))[1:]
                nums = []
        out[u] = (float(g.get("horiz-adv-x", default)), polys)
    return out
