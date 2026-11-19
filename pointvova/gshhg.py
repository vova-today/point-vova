"""Read GSHHG binary shorelines (gshhs_*.b).

Each polygon is a 44-byte big-endian header of 11 int32 (id, n, flag, ...) followed by n (lon, lat) pairs in
microdegrees. The level is the low byte of the flag:
1 land, 2 lake, 3 island in a lake, 4 pond, 5 Antarctic ice front, 6 Antarctic grounding line.
"""
import functools

import numpy as np

SHORE_LEVELS = (1, 5, 6)  # what the sea touches


def read(path):
    """The shoreline polygons as [{'lat', 'lon'}], longitudes in -180..180."""
    raw = open(path, "rb").read()
    pos, out = 0, []
    while pos < len(raw):
        head = np.frombuffer(raw, ">i4", 11, pos)
        n, level = int(head[1]), int(head[2]) & 255
        if level in SHORE_LEVELS:
            pts = np.frombuffer(raw, ">i4", 2 * n, pos + 44).reshape(n, 2) * 1e-6
            lon = pts[:, 0].copy()
            lon[lon > 180] -= 360
            out.append({"lat": pts[:, 1].copy(), "lon": lon})
        pos += 44 + 8 * n
    return out


@functools.lru_cache(maxsize=1)
def vertices(path):
    """Every shoreline vertex of the file as two arrays (lat, lon). Read once; do not write into them."""
    polys = read(path)
    return np.concatenate([p["lat"] for p in polys]), np.concatenate([p["lon"] for p in polys])
