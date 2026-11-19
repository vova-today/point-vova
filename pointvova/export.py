"""The result as a map file: the point, the three places where its circle touches land, the radii and the circle.

Lines are geodesics on WGS84, and the three shores are vertices of the circle.
"""
import json

from geographiclib.geodesic import Geodesic

G = Geodesic.WGS84


def write(run, path):
    lat0, lon0, radius = run["lat"], run["lon"], run["km"] * 1000
    shores = sorted(run["shores"], key=lambda sh: sh["azimuth"])
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon0, lat0]},
              "properties": {"name": "Point Vova", "name:ru": "Точка Вовы",
                             "description": "Atlantic pole of inaccessibility",
                             "distance_to_land_km": round(run["km"], 3), "ellipsoid": run["ellipsoid"]}}]
    for sh in shores:
        props = {k: sh[k] for k in ("source", "osm_way", "osm_node", "islet_m2") if k in sh}
        props.update(name="Contact", azimuth_from_point=round(sh["azimuth"], 3), km=round(sh["km"], 3))
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [sh["lon"], sh["lat"]]},
                      "properties": props})
        line = G.InverseLine(lat0, lon0, sh["lat"], sh["lon"])
        steps = (line.Position(line.s13 * i / 120) for i in range(121))
        feats.append({"type": "Feature", "properties": {"name": "Radius"},
                      "geometry": {"type": "LineString", "coordinates": [[q["lon2"], q["lat2"]] for q in steps]}})
    # every quarter of a degree, plus the three shores' own directions
    bearings = sorted({k / 4 for k in range(1440)} | {sh["azimuth"] for sh in shores})
    rim = [[d["lon2"], d["lat2"]] for d in (G.Direct(lat0, lon0, b, radius) for b in bearings + bearings[:1])]
    feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": rim},
                  "properties": {"name": "The largest circle without land", "radius_km": round(run["km"], 3)}})
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False)
        f.write("\n")
