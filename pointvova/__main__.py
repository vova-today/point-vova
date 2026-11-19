"""Compute Point Vova and every number in the README, and write results/.

    python -m pointvova [path/to/gshhs_f.b]        default: data/gshhg/gshhs_f.b

Steps: the coarse search (scan.py), the result and its variants (solve.py), the check against coastline segments
(edges.py), the comparison with Barnes (straightline.py), the summary and the map file. Stops if any check fails
or the result is not the expected one.
"""
import glob
import json
import os
import sys

from geographiclib.geodesic import Geodesic

from . import edges, export, scan, straightline
from .solve import load_coast, solve

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OSM = {day: sorted(glob.glob(os.path.join(ROOT, "data", "osm", day, "*.osm.gz"))) for day in ("2026-11-11", "2017-04-26")}
OUT = os.path.join(ROOT, "results")
# The result as first computed on 11 November 2026. The article rounds it to 24.1852 N, 43.3709 W, 2,033.9 km.
EXPECTED = (24.185247, -43.370870, 2033.896)
# Barnes (2019), doi:10.1080/17538947.2019.1576786, Table 3, as printed. Used for comparison only.
BARNES_OSM = (24.1851, -43.3704, 2033.8849)
BARNES_GSHHG = (24.1923, -43.3728, 2033.5187)
VARIANTS = [  # file name, label, OpenStreetMap near the pole as of, islets below this left out (m2), sphere?
    ("point-vova", "OpenStreetMap of 11 November 2026 near the pole, WGS84 (the result)", "2026-11-11", 0, False),
    ("no-islets-under-500-m2", "the same without islets under 500 m2", "2026-11-11", 500, False),
    ("no-islets-under-1000-m2", "the same without islets under 1,000 m2", "2026-11-11", 1000, False),
    ("no-islets-under-5000-m2", "the same without islets under 5,000 m2", "2026-11-11", 5000, False),
    ("no-islets-under-10000-m2", "the same without islets under 10,000 m2", "2026-11-11", 10000, False),
    ("sphere", "the same on a sphere", "2026-11-11", 0, True),
    ("osm-2017-04-26", "OpenStreetMap of 26 April 2017 near the pole, WGS84", "2017-04-26", 0, False),
    ("gshhg-only", "GSHHG alone, WGS84", None, 0, False),
    ("gshhg-only-sphere", "GSHHG alone, sphere", None, 0, True),
]


def metres(a, b):
    return Geodesic.WGS84.Inverse(a[0], a[1], b[0], b[1])["s12"]


def save(name, data):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=1) + "\n")


def main():
    gshhg_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "gshhg", "gshhs_f.b")
    assert all(len(paths) == 6 for paths in OSM.values()), "expected six OpenStreetMap extracts per date in data/osm"
    os.makedirs(os.path.join(OUT, "runs"), exist_ok=True)

    # 1. Where to start: this project's own coarse search. Barnes's points are not an input.
    found = scan.search(gshhg_path)
    save("scan.json", found)
    start = (found[0]["lat"], found[0]["lon"])

    # 2. The result and its variants.
    runs, coasts = {}, {}
    for name, label, day, min_m2, sphere in VARIANTS:
        key = (day, min_m2)
        if key not in coasts:
            coasts[key] = load_coast(gshhg_path, OSM[day] if day else (), start, min_m2)
        r = runs[name] = solve(coasts[key], start, sphere)
        assert r["circle_is_empty"] and r["is_local_maximum"], name
        save("point-vova.json" if name == "point-vova" else os.path.join("runs", name + ".json"), r)
    result = runs["point-vova"]
    here = (result["lat"], result["lon"])
    off = metres(here, EXPECTED)
    assert off < 1 and abs(result["km"] - EXPECTED[2]) < 0.001, f"not the expected point: {off:.2f} m away"

    # 3. The same result against segments instead of vertices.
    seg = edges.check(result, gshhg_path, OSM["2026-11-11"])
    assert seg["circle_is_empty_of_segments"] and not seg["of_them_nearest_at_an_inner_point"], seg
    save("edges.json", seg)

    # 4. Barnes's point: the coastline of his date, and the point his nearest-neighbour search arrives at on it.
    old = runs["osm-2017-04-26"]
    there = (old["lat"], old["lon"])
    line = straightline.point(coasts[("2017-04-26", 0)], old)
    save("straight-line-2017.json", line)

    # 5. The summary and the map file.
    lines = [f"Coarse search: {found[0]['km']} km from land at {start[0]}, {start[1]}; "
             f"second best {found[1]['km']} km at {found[1]['lat']}, {found[1]['lon']}. "
             f"The start is {metres(start, here) / 1000:.1f} km from the result.",
             "",
             "| Variant | Latitude | Longitude | Distance to land, km | Away from the result, m |",
             "|---|---|---|---|---|"]
    for name, label, *_ in VARIANTS:
        r = runs[name]
        lines.append(f"| {label} | {r['lat']:.6f} | {r['lon']:.6f} | {r['km']:.4f} | {metres(here, (r['lat'], r['lon'])):.0f} |")
    for label, (lat, lon, km) in (("Barnes 2019, OpenStreetMap", BARNES_OSM), ("Barnes 2019, GSHHG 2.3.6", BARNES_GSHHG)):
        lines.append(f"| {label} | {lat:.4f} | {lon:.4f} | {km:.4f} | {metres(here, (lat, lon)):.0f} |")
    gshhg_run = (runs["gshhg-only"]["lat"], runs["gshhg-only"]["lon"])
    nxt, far = result["next_land"], result["nearest_gshhg_vertex"]
    lines += ["", "Shores, by bearing from the point:"]
    by_bearing = lambda run: sorted(run["shores"], key=lambda sh: sh["azimuth"])
    for sh, was in zip(by_bearing(result), by_bearing(old)):
        islet = f", a closed way of {sh['islet_m2']} m2" if "islet_m2" in sh else ""
        moved = metres((sh["lat"], sh["lon"]), (was["lat"], was["lon"]))
        since = "the same node as in 2017" if sh["osm_node"] == was["osm_node"] else f"{moved:.0f} m from the 2017 contact"
        lines.append(f"- {sh['azimuth']:.1f} deg: {sh['lat']:.7f}, {sh['lon']:.7f}, {sh['km']:.4f} km, OpenStreetMap way "
                     f"{sh['osm_way']}, node {sh['osm_node']}{islet}; "
                     f"1 m of this shore moves the point {sh['point_moves_m_per_m']:.2f} m; {since}")
    lines += [
        "",
        f"Iterations: {result['iterations']}. Spread between the three distances: {result['spread_between_shores_mm']:.1e} mm.",
        f"Gaps between the bearings: {', '.join(f'{g:.0f}' for g in sorted(result['azimuth_gaps_deg']))} deg.",
        f"Next land after the three shores: {nxt['lat']:.4f}, {nxt['lon']:.4f}, "
        f"{nxt['km']:.1f} km ({nxt['km'] - result['km']:.1f} km farther).",
        f"Nearest coastline taken from GSHHG: {far['lat']:.4f}, {far['lon']:.4f}, "
        f"{far['km']:.1f} km ({far['km'] - result['km']:.1f} km farther).",
        f"Coastline vertices: {result['coastline']['gshhg_world']:,} in GSHHG, {result['coastline']['osm']:,} from "
        f"OpenStreetMap; measured exactly in the final check: {result['vertices_measured_exactly_in_check']:,}.",
        f"Coastline segments near the circle: {seg['segments_near_the_circle']:,}; "
        f"searched along their length: {seg['segments_searched_along_their_length']}; "
        f"nearest at an inner point: {seg['of_them_nearest_at_an_inner_point']}; "
        f"longest: {seg['longest_segment_near_the_circle_m']:.0f} m.",
        "",
        "Barnes (2019):",
        f"- GSHHG alone against his GSHHG point: {metres(gshhg_run, BARNES_GSHHG[:2]):.0f} m apart.",
        f"- The result against his OpenStreetMap point: {metres(here, BARNES_OSM[:2]):.1f} m apart.",
        f"- The pole of the 2017 coastline: {old['lat']:.6f}, {old['lon']:.6f}, {old['km']:.4f} km. "
        f"{metres(there, here):.1f} m from the result, {metres(there, BARNES_OSM[:2]):.1f} m from his point; "
        f"his printed distance is {(BARNES_OSM[2] - old['km']) * 1000:.1f} m longer.",
        f"- The straight-line point of the 2017 coastline: {line['lat']:.6f}, {line['lon']:.6f}. "
        f"{metres((line['lat'], line['lon']), BARNES_OSM[:2]):.1f} m from his point. "
        f"Largest surface distance to a shore there: {line['largest_surface_km']:.4f} km "
        f"({(line['largest_surface_km'] - BARNES_OSM[2]) * 1000:+.1f} m against his printed distance). "
        f"Real distance to land there: {line['distance_to_land_km']:.4f} km, "
        f"{(old['km'] - line['distance_to_land_km']) * 1000:.1f} m less than at the pole of that coastline.",
    ]
    with open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    export.write(result, os.path.join(OUT, "point-vova.geojson"))
    print("\n".join(lines))


main()
