# rail_network_components.csv — Connected components of the cleaned OSM rail network

- **Produced by:** notebooks/01c_rail_network.ipynb, section 4
- **Generated:** 2026-11-17T11:23:14
- **One row is:** one connected component after gap joins and station links, longest first
- **Rows:** 1,198
- **OSM extraction date:** 2026-05-28T08:42:21.097Z
- **gpkg sha256:** 965df123e363e68c6f32afede42ceb3195bda6394859896a574daca25917ab70

| column | type | description |
|---|---|---|
| `component_id` | int | Component id (as in station_rail_snap.component_id). |
| `length_km` | float | Track length (+ gap joins), km. |
| `n_nodes` | int | Graph nodes in the component. |
| `n_stations` | int | Stations snapped onto it. |
| `has_hub` | bool | True for the component holding the Košice station. |
| `centre_lon` | float | Mean longitude of its nodes (for mapping). |
| `centre_lat` | float | Mean latitude of its nodes. |
