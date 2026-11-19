"""Check the result against the coastline's segments, not only its vertices.

The solver measures to vertices. Land is the line between them, and a point inside a segment can be nearer than
both of its ends. This check measures the point's distance to every segment near the circle.

A segment of length L whose ends are d1 and d2 from the point cannot come nearer than (d1 + d2 - L) / 2
(the triangle inequality). Segments that could reach within half a metre of the circle are searched along
their whole length.
"""
import numpy as np
from geographiclib.geodesic import Geodesic

from . import gshhg, osm
from .solve import MARGIN_KM, sph_km

G = Geodesic.WGS84


def segments(gshhg_path, osm_paths, point, reach_km):
    """Coastline segments with an end within reach_km of the point, as the solver's coastline has them:
    OpenStreetMap ways whole, GSHHG outside the OpenStreetMap extracts' bounds."""
    seen, out, boxes = set(), [], []

    def add(a, b):
        key = (min(a, b), max(a, b))
        if key not in seen:
            seen.add(key)
            out.append((a, b))

    for path in osm_paths:
        box, ways, nodes = osm.read_extract(path)
        boxes.append(box)
        for refs in ways.values():
            pts = [nodes[r] for r in refs]
            for a, b in zip(pts, pts[1:]):
                add(a, b)
    for poly in gshhg.read(gshhg_path):
        lat, lon = poly["lat"], poly["lon"]
        for i in np.flatnonzero(sph_km(point[0], point[1], lat, lon) < reach_km + 60):
            j = (i + 1) % len(lat)
            a, b = (float(lat[i]), float(lon[i])), (float(lat[j]), float(lon[j]))
            if not any(w <= q[1] <= e and s <= q[0] <= n for q in (a, b) for w, s, e, n in boxes):
                add(a, b)
    ends = np.array([[a[0], a[1], b[0], b[1]] for a, b in out])
    near = np.minimum(sph_km(point[0], point[1], ends[:, 0], ends[:, 1]),
                      sph_km(point[0], point[1], ends[:, 2], ends[:, 3])) < reach_km
    return [seg for seg, keep in zip(out, near) if keep]


def nearest_on(point, a, b):
    """Least distance from the point to the geodesic from a to b, and where along it (0 at a, 1 at b)."""
    line = G.InverseLine(a[0], a[1], b[0], b[1])

    def at(t):
        q = line.Position(line.s13 * t)
        return G.Inverse(point[0], point[1], q["lat2"], q["lon2"])["s12"]

    lo, hi = 0.0, 1.0
    for _ in range(60):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if at(m1) < at(m2):
            hi = m2
        else:
            lo = m1
    t = (lo + hi) / 2
    return at(t), t


def check(run, gshhg_path, osm_paths):
    point, radius = (run["lat"], run["lon"]), run["km"] * 1000
    segs = segments(gshhg_path, osm_paths, point, run["km"] + MARGIN_KM)
    searched, longest, clearance, inner = 0, 0.0, float("inf"), 0
    for a, b in segs:
        d1 = G.Inverse(point[0], point[1], a[0], a[1])["s12"]
        d2 = G.Inverse(point[0], point[1], b[0], b[1])["s12"]
        length = G.Inverse(a[0], a[1], b[0], b[1])["s12"]
        longest = max(longest, length)
        if (d1 + d2 - length) / 2 > radius + 0.5:
            continue
        searched += 1
        least, t = nearest_on(point, a, b)
        clearance = min(clearance, least - radius)
        inner += 1e-6 < t < 1 - 1e-6
    return {
        "segments_near_the_circle": len(segs),
        "segments_searched_along_their_length": searched,
        "of_them_nearest_at_an_inner_point": int(inner),
        "nearest_segment_minus_radius_mm": clearance * 1000,
        "circle_is_empty_of_segments": clearance > -1e-3,
        "longest_segment_near_the_circle_m": longest,
    }
