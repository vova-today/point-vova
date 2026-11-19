# Data

## OpenStreetMap extracts: `osm/2026-11-11/`

Six boxes downloaded from the OpenStreetMap API on 11 November 2026 with

```
https://api.openstreetmap.org/api/0.6/map?bbox=WEST,SOUTH,EAST,NORTH
```

and gzipped, otherwise untouched. They hold everything mapped in the box. The calculation reads only the ways tagged `natural=coastline`. The boxes cover the coasts that face the point, not whole islands. Outside them the coastline is GSHHG.

| File | West, south, east, north | What |
|---|---|---|
| `floresSW.osm.gz` | -31.30, 39.35, -31.18, 39.45 | Flores, Azores: the south-west, with the rock off Ponta dos Ilhéus |
| `floresNW.osm.gz` | -31.30, 39.45, -31.18, 39.53 | Flores, Azores: the north-west |
| `santoantao.osm.gz` | -25.37, 16.98, -25.25, 17.15 | the west coast of Santo Antão, Cape Verde |
| `desirade.osm.gz` | -61.15, 16.28, -60.98, 16.36 | La Désirade, Guadeloupe |
| `petiteterre.osm.gz` | -61.14, 16.15, -61.08, 16.19 | Îles de la Petite-Terre, Guadeloupe |
| `barbuda.osm.gz` | -61.80, 17.55, -61.72, 17.72 | the east of Barbuda |

Flores is in two files because the API returns at most 50,000 nodes per request.

© OpenStreetMap contributors, Open Database License 1.0: https://www.openstreetmap.org/copyright

## OpenStreetMap as it was: `osm/2017-04-26/`

The coastline of the same six boxes as it stood on 26 April 2017 at 08:54 UTC. That is the date of the land polygons file Barnes (2019) used. Downloaded on 19 November 2026 from the Overpass API (`https://overpass-api.de/api/interpreter`), one query per box:

```
[out:xml][timeout:300][date:"2017-04-26T08:54:00Z"];
way[natural=coastline](SOUTH,WEST,NORTH,EAST);
(._;>;);
out meta;
```

These files hold only the coastline ways and their nodes, with each element's edit date. The newest edit in them is of 30 March 2017.

One line was added to each file: the `<bounds>` element with the box that was asked for. The API's files have it, Overpass's do not, and the code reads the box from it. Otherwise the files are as downloaded, gzipped.

© OpenStreetMap contributors, Open Database License 1.0.

## GSHHG: `gshhg/`, not included

Global Self-consistent, Hierarchical, High-resolution Geography Database, version 2.3.7 (Wessel and Smith), LGPL.

- Download: https://www.soest.hawaii.edu/pwessel/gshhg/ (`gshhg-bin-2.3.7.zip`, 119 MB)
- File used: `gshhs_f.b` (full resolution), 95,809,336 bytes. Put it in `data/gshhg/`.
- SHA-256: `af9215d58ebc525b2d09654a89959829f09e6edc457f3666759cded37be4ecf6`

Levels read: 1 (land), 5 and 6 (Antarctica). Lakes are left out.
