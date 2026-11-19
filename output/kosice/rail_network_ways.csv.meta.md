# rail_network_ways.csv — The OSM ways that form the rail network (after type filter, de-duplication, clip)

- **Produced by:** notebooks/01c_rail_network.ipynb, sections 2-3
- **Generated:** 2026-11-17T11:23:15
- **One row is:** one OSM way (clipped part) used in the graph; rebuild the network from the gpkg with this list
- **Rows:** 297,248
- **OSM extraction date:** 2026-05-28T08:42:21.097Z
- **gpkg sha256:** 965df123e363e68c6f32afede42ceb3195bda6394859896a574daca25917ab70

| column | type | description |
|---|---|---|
| `osm_id` | str | OSM way id. |
| `railway` | str | railway= value (rail, narrow_gauge, or light_rail for the TEŽ). |
| `ref` | str | OSM ref (e.g. 112D for the TEŽ), where tagged. |
| `name` | str | OSM name, where tagged. |
| `length_km` | float | Length inside the study area, km (EPSG:3035). |
