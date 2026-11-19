# route_validation.csv — Route km between consecutive stations against the distance the feed publishes

- **Produced by:** notebooks/04b_distance_time_efficiency.ipynb
- **Generated:** 2026-11-17T11:39:18
- **One row is:** one consecutive station pair of the sampled trips of one feed
- **Rows:** 3,339
- **Built from:** 04a journeys / lau_table
- **Efficiency cut-off:** 5 km route

| column | type | description |
|---|---|---|
| `feed` | str | UKRZ_UA, BAHN_AT or DRAHY_CZ (feeds publishing shape_dist_traveled). |
| `a` | str | First station. |
| `b` | str | Next station. |
| `route_km` | float | Shortest track distance on the OSM graph (nb04_distance.pair_km). |
| `published_km` | float | The feed's shape_dist_traveled difference, km (median over the sampled trips). |
| `ratio` | float | route_km / published_km. |
