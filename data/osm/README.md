# OpenStreetMap rail network (`data/osm/`)

The OSM rail network is too large for the repository (234 MB), so it is hosted separately. Download it into `data/osm/`. The pipeline expects it at the path set in `traintranv2/config.py` (`osm_railways_gpkg`).

| File | Size | SHA-256 (first 12) | Contents | Used for |
|---|---:|---|---|---|
| [v4_railways.gpkg](https://cases.idoaba.eu/traintranv2/data/osm/v4_railways.gpkg) | 233.7 MB | `965df123e363` | GeoPackage, layer `railways`, EPSG:4326: OSM railway ways extracted from the country dumps of the study area and its neighbours (extent 9.6–40.3° E, 44.5–55.4° N), 440,511 rows | Notebook 01c: the routed rail graph that gives shortest-path rail km and route km along the called stations |

The full SHA-256, the row counts by `railway` tag, the columns and the extraction date are recorded in `v4_railways.manifest.json` in this folder. That file is in the repository.

## What the pipeline uses

The layer contains every `railway=*` way, including abandoned, disused, tram and platform features. Notebook 01c keeps only:
- `railway=rail` (299,518 rows) and `railway=narrow_gauge` (6,877);
- `light_rail` ways with OSM `ref=112D`, or with the 1000 mm gauge inside Slovakia: the Tatra Electric Railway (TEŽ), run by ŽSR / ZSSK.

The file has 16,873 duplicate rows: ways that appear in more than one country dump. Notebook 01c removes them by `osm_id`.

## Setup

```bash
cd data/osm
curl -LO https://cases.idoaba.eu/traintranv2/data/osm/v4_railways.gpkg
sha256sum v4_railways.gpkg   # expect 965df123e363e68c6f32afede42ceb3195bda6394859896a574daca25917ab70
```

## Extraction date

The layer was written on 2026-05-28 (`gpkg_contents.last_change`). The country dumps' own dates are not recorded in the file, so this is the latest possible date of the OSM data, not its exact date.

## Source and licence

© OpenStreetMap contributors. Available under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Redistributing this extract is allowed under the ODbL, provided the attribution is kept and the file stays under the same licence.

