# detour_summary.csv — Detour factors per network: route / straight line, shortest path / straight line, route / shortest path

- **Produced by:** notebooks/04b_distance_time_efficiency.ipynb
- **Generated:** 2026-11-17T11:39:18
- **One row is:** one network x ratio
- **Rows:** 12
- **Built from:** 04a journeys / lau_table
- **Efficiency cut-off:** 5 km route

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `ratio` | str | route_geo, rail_geo (spec §2 delta) or route_rail. |
| `n` | int | Journeys. |
| `p5` | float | 5th percentile over the journeys. |
| `p25` | float | 25th percentile over the journeys. |
| `p50` | float | 50th percentile over the journeys. |
| `p75` | float | 75th percentile over the journeys. |
| `p95` | float | 95th percentile over the journeys. |
