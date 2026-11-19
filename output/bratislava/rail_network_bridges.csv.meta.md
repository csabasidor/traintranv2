# rail_network_bridges.csv — Cut-off pieces of the rail network that carry stations, and whether a construction bridge joined them

- **Produced by:** notebooks/01c_rail_network.ipynb, section 5b
- **Generated:** 2026-11-17T11:48:12
- **One row is:** one connected component with snapped stations that did not reach the Košice station after gap joins and station links
- **Rows:** 15
- **OSM extraction date:** 2026-05-28T08:42:21.097Z
- **gpkg sha256:** 965df123e363e68c6f32afede42ceb3195bda6394859896a574daca25917ab70

| column | type | description |
|---|---|---|
| `component_id` | int | Component id before bridging (this run's numbering). |
| `stations` | str | Up to six station names on it. |
| `n_stations` | int | Stations (all feeds) snapped onto it. |
| `bridged` | bool | True if a path over track + rail_bridge_types within rail_bridge_max_km joined it to the main network. |
| `bridge_km` | float | Length of the added path, km. |
| `construction_km` | float | Of which over railway=construction (lines under reconstruction in OSM), km. |
| `note` | str | Rule applied, or why no bridge was found. |
