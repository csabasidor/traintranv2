# rail_network_added_edges.csv — Edges added to the OSM rail network by cleaning and station snapping

- **Produced by:** notebooks/01c_rail_network.ipynb, sections 4-5
- **Generated:** 2026-11-17T11:23:15
- **One row is:** one added edge
- **Rows:** 106,313
- **OSM extraction date:** 2026-05-28T08:42:21.097Z
- **gpkg sha256:** 965df123e363e68c6f32afede42ceb3195bda6394859896a574daca25917ab70

| column | type | description |
|---|---|---|
| `kind` | str | gap_join (dead end -> another component within rail_gap_join_m), snap (station -> its nearest track), station_link (station -> another component within rail_station_link_m: gauge breaks), bridge (segment of the shortest path joining a cut-off piece with stations to the main network over track + rail_bridge_types, see rail_network_bridges.csv). |
| `a_lon` | float | Longitude of one end. |
| `a_lat` | float | Latitude of one end. |
| `b_lon` | float | Longitude of the other end. |
| `b_lat` | float | Latitude of the other end. |
| `length_m` | float | Edge length, m. |
