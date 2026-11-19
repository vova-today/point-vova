"""Refine and verify a pole of inaccessibility: the sea point whose nearest land is as far as it can be.

At such a point the nearest land lies at the same distance in three places (the point is the centre of the largest
circle that fits in the sea, and the circle touches land three times). The solver:

1. takes a starting point near the pole (the best cell of the coarse search, scan.py);
2. finds the nearest coastline vertex of each of the three nearest shores (shores more than 300 km apart);
3. moves the point by Newton's method until the three geodesic distances are equal;
4. repeats 2 and 3 until nothing moves (the nearest vertices can change as the point moves);
5. checks that no other vertex is nearer, and that the three shores surround the point (no gap between their
   directions reaches 180 degrees), so every move brings one of them closer.

Distances are geodesics on the WGS84 ellipsoid (GeographicLib, Karney 2013). Spherical distances are used only to
choose which vertices to measure exactly, with a margin wider than the two can differ by.
"""
import math

import numpy as np
from geographiclib.geodesic import Geodesic

from . import gshhg, osm

SPHERE_M = 6371008.8  # mean Earth radius
RADIUS_KM = 2400.0  # coastline farther than this from the start is not loaded
SLACK_KM = 25.0  # vertices this close to a shore's spherical minimum are measured exactly
MARGIN_KM = 30.0  # the final check measures exactly every vertex within the result + this (spherical)
SHORE_SEP_KM = 300.0  # two contact points nearer than this are the same shore
NEXT_LAND_SEP_KM = 100.0  # "the next land": the nearest vertex at least this far from all three contacts


def sph_km(lat0, lon0, lat, lon):
    """Great-circle distance on the mean sphere, km. For preselection only."""
    a, b = math.radians(lat0), math.radians(lon0)
    la, lo = np.radians(lat), np.radians(lon)
    c = math.sin(a) * np.sin(la) + math.cos(a) * np.cos(la) * np.cos(lo - b)
    return np.arccos(np.clip(c, -1, 1)) * SPHERE_M / 1000


def load_coast(gshhg_path, osm_paths, start, min_islet_m2=0.0):
    """Coastline vertices within RADIUS_KM of start.

    GSHHG everywhere; inside the bounds of each OpenStreetMap extract, GSHHG's vertices are replaced by
    OpenStreetMap's. Returns arrays 'lat', 'lon', 'way', 'node', 'islet_m2' (the last three are 0 for GSHHG
    vertices) and 'info' (counts).
    """
    lat, lon = gshhg.vertices(gshhg_path)
    extra = {k: np.zeros(len(lat)) for k in ("way", "node", "islet_m2")}
    info = {"gshhg_world": len(lat), "osm": 0, "osm_ways": 0, "osm_islets_dropped": 0}
    if osm_paths:
        o = osm.coastline(osm_paths, min_islet_m2)
        inside = np.zeros(len(lat), bool)
        for w, s, e, n in o["boxes"]:
            inside |= (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
        lat, lon = np.concatenate([lat[~inside], o["lat"]]), np.concatenate([lon[~inside], o["lon"]])
        extra = {k: np.concatenate([v[~inside], o[k]]) for k, v in extra.items()}
        info.update(osm=len(o["lat"]), osm_ways=o["ways"], osm_islets_dropped=o["dropped"])
    near = sph_km(start[0], start[1], lat, lon) < RADIUS_KM
    info["within_radius"] = int(near.sum())
    coast = {"lat": lat[near], "lon": lon[near], "info": info}
    coast.update({k: v[near] for k, v in extra.items()})
    return coast


def _nearest(p, coast, geod, d, mask):
    """The exactly nearest vertex among those the mask allows: (metres, azimuth at p, index)."""
    idx = np.flatnonzero(mask & (d < d[mask].min() + SLACK_KM))
    best = None
    for i in idx:
        g = geod.Inverse(p[0], p[1], coast["lat"][i], coast["lon"][i])
        if best is None or g["s12"] < best[0]:
            best = (g["s12"], g["azi1"], int(i))
    return best


def contacts(p, coast, geod):
    """The nearest vertex of each of the three nearest shores, nearest first."""
    d = sph_km(p[0], p[1], coast["lat"], coast["lon"])
    free = np.ones(len(d), bool)
    out = []
    for _ in range(3):
        hit = _nearest(p, coast, geod, d, free)
        out.append(hit)
        free &= sph_km(coast["lat"][hit[2]], coast["lon"][hit[2]], coast["lat"], coast["lon"]) > SHORE_SEP_KM
    return out


def _system(act):
    """Moving the point by (north, east) metres changes distance k by -(cos az_k * north + sin az_k * east)."""
    az = np.radians([a[1] for a in act])
    return np.column_stack([-np.cos(az), -np.sin(az), -np.ones(3)])


def solve(coast, start, sphere=False):
    geod = Geodesic(SPHERE_M, 0) if sphere else Geodesic.WGS84
    p = tuple(start)
    for iteration in range(1, 61):
        act = contacts(p, coast, geod)
        north, east, _ = np.linalg.solve(_system(act), -np.array([a[0] for a in act]))
        moved = math.hypot(north, east)
        g = geod.Direct(p[0], p[1], math.degrees(math.atan2(east, north)), moved)
        p = (g["lat2"], g["lon2"])
        if moved < 1e-5:
            break
    act = contacts(p, coast, geod)
    radius_m = min(a[0] for a in act)

    # no vertex anywhere is nearer than the three contacts
    d = sph_km(p[0], p[1], coast["lat"], coast["lon"])
    ring = np.flatnonzero(d < radius_m / 1000 + MARGIN_KM)
    nearest_m = min(geod.Inverse(p[0], p[1], coast["lat"][i], coast["lon"][i])["s12"] for i in ring)

    # the three shores surround the point
    az = sorted(a[1] % 360 for a in act)
    gaps = [(az[(k + 1) % 3] - az[k]) % 360 for k in range(3)]

    # the next land: nearest vertex away from the three contacts
    free = np.ones(len(d), bool)
    for a in act:
        free &= sph_km(coast["lat"][a[2]], coast["lon"][a[2]], coast["lat"], coast["lon"]) > NEXT_LAND_SEP_KM
    next_land = _nearest(p, coast, geod, d, free)

    # the nearest coastline that is GSHHG's, not OpenStreetMap's
    nearest_gshhg = _nearest(p, coast, geod, d, coast["way"] == 0)

    # how far the point moves, and how much the radius grows, when shore k is 1 m farther away
    J = -np.linalg.inv(_system(act))

    def vertex(a):
        i = a[2]
        v = {"lat": float(coast["lat"][i]), "lon": float(coast["lon"][i]), "km": a[0] / 1000, "azimuth": a[1] % 360,
             "source": "OpenStreetMap" if coast["way"][i] else "GSHHG"}
        if coast["way"][i]:
            v.update(osm_way=int(coast["way"][i]), osm_node=int(coast["node"][i]))
        if coast["islet_m2"][i]:
            v["islet_m2"] = round(float(coast["islet_m2"][i]))
        return v

    shores = [vertex(a) for a in act]
    for k, v in enumerate(shores):
        v["point_moves_m_per_m"] = math.hypot(J[0, k], J[1, k])
        v["radius_grows_m_per_m"] = float(J[2, k])
    return {
        "lat": p[0], "lon": p[1], "km": radius_m / 1000,
        "ellipsoid": "sphere, R = 6371008.8 m" if sphere else "WGS84",
        "start": list(start),
        "iterations": iteration,
        "shores": shores,
        "spread_between_shores_mm": (max(a[0] for a in act) - radius_m) * 1000,
        "azimuth_gaps_deg": gaps,
        "is_local_maximum": max(gaps) < 180,
        "nearest_vertex_km": nearest_m / 1000,
        "circle_is_empty": nearest_m > radius_m - 1e-3,
        "vertices_measured_exactly_in_check": int(len(ring)),
        "next_land": vertex(next_land),
        "nearest_gshhg_vertex": vertex(nearest_gshhg),
        "coastline": dict(coast["info"]),
    }
