# rail_network_length.csv — Rail network length per country: track-km and line-km

- **Produced by:** notebooks/01c_rail_network.ipynb, section 3b
- **Generated:** 2026-11-17T11:48:12
- **One row is:** one country (inside its border), plus the six together
- **Rows:** 7
- **OSM extraction date:** 2026-05-28T08:42:21.097Z
- **gpkg sha256:** 965df123e363e68c6f32afede42ceb3195bda6394859896a574daca25917ab70

| column | type | description |
|---|---|---|
| `region` | str | Country code, or 'all six'. |
| `track_km` | float | Summed length of the kept OSM ways inside the country: every mapped track counts (a double-track line about twice). |
| `line_km` | float | Line length, parallel tracks counted once: (A30 - A15) / (2 x 15 m) from 15 m and 30 m flat-ended buffers (nb01c_rail_network.track_and_line_km). |
| `track_per_line` | float | track_km / line_km: about 1 for single-track networks, up to 2+ for multi-track. |
