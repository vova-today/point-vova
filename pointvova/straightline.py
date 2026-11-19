"""The point a straight-line nearest-neighbour search arrives at, for comparison with Barnes (2019).

Barnes (2019, section 2.6) puts the coastline points in Cartesian 3-space, finds a point's nearest neighbour
there, and then measures the distance to that neighbour along the ellipsoid. On an ellipsoid the nearest point
by straight line, through the Earth, is not always the nearest along the surface.

A search that maximises "the distance along the surface to the straight-line nearest neighbour" ends where the
three shores are equally far by straight line. The value it reports there is the largest of the three surface
distances. The real distance to land at that point is the smallest of them.

This module finds that point for a coastline whose pole and three shores are already known.
"""
import math

import numpy as np
from geographiclib.geodesic import Geodesic

from .solve import contacts, sph_km

G = Geodesic.WGS84
A, F = 6378137.0, 1 / 298.257223563  # WGS84
SHORE_KM = 60.0  # a shore is every vertex this close to its contact


def cartesian(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    e2 = F * (2 - F)
    n = A / np.sqrt(1 - e2 * np.sin(la) ** 2)
    return np.stack([n * np.cos(la) * np.cos(lo), n * np.cos(la) * np.sin(lo), n * (1 - e2) * np.sin(la)], -1)


def point(coast, pole):
    """coast: the coastline (solve.load_coast); pole: its result (solve.solve)."""
    xyz = cartesian(coast["lat"], coast["lon"])
    shores = [np.flatnonzero(sph_km(s["lat"], s["lon"], coast["lat"], coast["lon"]) < SHORE_KM) for s in pole["shores"]]

    def nearest(p):  # per shore: (straight-line metres to its nearest vertex, azimuth, surface metres to that vertex)
        here = cartesian(np.array(p[0]), np.array(p[1]))
        out = []
        for idx in shores:
            d = np.linalg.norm(xyz[idx] - here, axis=1)
            i = idx[int(np.argmin(d))]
            g = G.Inverse(p[0], p[1], coast["lat"][i], coast["lon"][i])
            out.append((float(d.min()), g["azi1"], g["s12"]))
        return out

    p = (pole["lat"], pole["lon"])
    for _ in range(60):
        act = nearest(p)
        az = np.radians([a[1] for a in act])
        system = np.column_stack([-np.cos(az), -np.sin(az), -np.ones(3)])
        north, east, _ = np.linalg.solve(system, -np.array([a[0] for a in act]))
        moved = math.hypot(north, east)
        g = G.Direct(p[0], p[1], math.degrees(math.atan2(east, north)), moved)
        p = (g["lat2"], g["lon2"])
        if moved < 1e-4:
            break
    act = nearest(p)
    straight = [a[0] for a in act]
    # the three shores are the nearest land by straight line too: no other vertex is nearer
    assert np.linalg.norm(xyz - cartesian(np.array(p[0]), np.array(p[1])), axis=1).min() > min(straight) - 1e-3
    return {
        "lat": p[0], "lon": p[1],
        "straight_line_km": min(straight) / 1000,
        "spread_between_straight_lines_mm": (max(straight) - min(straight)) * 1000,
        "surface_km_to_the_three_shores": sorted(a[2] / 1000 for a in act),
        "largest_surface_km": max(a[2] for a in act) / 1000,
        "distance_to_land_km": min(c[0] for c in contacts(p, coast, G)) / 1000,
        "pole_of_this_coastline": {"lat": pole["lat"], "lon": pole["lon"], "km": pole["km"]},
    }
