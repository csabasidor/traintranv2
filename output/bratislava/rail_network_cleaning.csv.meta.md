# rail_network_cleaning.csv — OSM rail network: every filtering and cleaning step with counts

- **Produced by:** notebooks/01c_rail_network.ipynb, sections 2-5
- **Generated:** 2026-11-17T11:48:11
- **One row is:** one step of the build, in order
- **Rows:** 9
- **OSM extraction date:** 2026-05-28T08:42:21.097Z
- **gpkg sha256:** 965df123e363e68c6f32afede42ceb3195bda6394859896a574daca25917ab70

| column | type | description |
|---|---|---|
| `step` | str | What was done. |
| `ways` | float | OSM ways after the step (ways steps only). |
| `km` | float | Track length after the step, km (where measured). |
| `nodes` | float | Graph nodes after the step (graph steps only). |
| `components` | float | Connected components after the step (graph steps only). |
| `added_edges` | float | Edges the step added (gap joins, station snaps / links). |
| `note` | str | Rule and parameters of the step. |
