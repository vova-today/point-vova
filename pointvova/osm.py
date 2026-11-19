"""Coastline from OpenStreetMap extracts (.osm.gz, as the API's /map call returns them).

In OpenStreetMap the coastline is the ways tagged natural=coastline, drawn along the high-water line.
A closed way is an island, down to single rocks.
"""
import gzip
import math
import xml.etree.ElementTree as ET

import numpy as np


def read_extract(path):
    """One extract -> ((west, south, east, north), {way id: [node ids]}, {node id: (lat, lon)}).

    The box is the extract's own <bounds>: the area that was asked for.
    """
    with gzip.open(path, "rb") as f:
        root = ET.parse(f).getroot()
    b = root.find("bounds")
    box = tuple(float(b.get(k)) for k in ("minlon", "minlat", "maxlon", "maxlat"))
    nodes = {int(n.get("id")): (float(n.get("lat")), float(n.get("lon"))) for n in root.iter("node")}
    ways = {}
    for w in root.iter("way"):
        if any(t.get("k") == "natural" and t.get("v") == "coastline" for t in w.iter("tag")):
            ways[int(w.get("id"))] = [int(nd.get("ref")) for nd in w.iter("nd")]
    return box, ways, nodes


def ring_area_m2(pts):
    """Area of a small closed ring of (lat, lon), on a local flat map. Good to a percent for a rock or an islet."""
    lat0, lon0 = pts[0]
    kx = 111320 * math.cos(math.radians(lat0))
    xy = [((lon - lon0) * kx, (lat - lat0) * 110574) for lat, lon in pts]
    return 0.5 * abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1])))


def coastline(paths, min_islet_m2=0.0):
    """Coastline vertices of all extracts, each node once.

    Closed ways smaller than min_islet_m2 are left out: that is how the result's dependence on small rocks is tested.
    Returns arrays with one row per vertex: 'lat', 'lon', 'way' and 'node' (OpenStreetMap ids), 'islet_m2' (the
    area of the vertex's way if it is closed, else 0); and 'boxes' (the extracts' bounds), 'ways', 'dropped'.
    """
    boxes, ways, nodes = [], {}, {}
    for path in paths:
        box, w, n = read_extract(path)
        boxes.append(box)
        ways.update(w)
        nodes.update(n)
    seen, rows, dropped = set(), [], 0
    for way_id in sorted(ways):
        refs = ways[way_id]
        closed = len(refs) > 3 and refs[0] == refs[-1]
        area = ring_area_m2([nodes[r] for r in refs[:-1]]) if closed else 0.0
        if closed and area < min_islet_m2:
            dropped += 1
            continue
        for r in refs:
            if r not in seen:
                seen.add(r)
                rows.append((nodes[r][0], nodes[r][1], way_id, r, area))
    lat, lon, way, node, area = (np.array(c) for c in zip(*rows))
    return {"lat": lat, "lon": lon, "way": way.astype(np.int64), "node": node.astype(np.int64), "islet_m2": area,
            "boxes": boxes, "ways": len(ways) - dropped, "dropped": dropped}
