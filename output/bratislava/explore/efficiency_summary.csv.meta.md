# efficiency_summary.csv — Network efficiency: trip-weighted mean and median, by cut-off and by distance

- **Produced by:** notebooks/04b_distance_time_efficiency.ipynb
- **Generated:** 2026-11-17T12:11:05
- **One row is:** one network x direction x cut-off x distance
- **Rows:** 48
- **Built from:** 04a journeys / lau_table
- **Efficiency cut-off:** 5 km route

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `direction` | str | inbound (to Košice) or outbound (from Košice). |
| `cutoff_km` | int | LAUs with mean route km above this are included. |
| `distance` | str | route, rail or geo. |
| `n_lau` | int | LAUs included. |
| `e_weighted` | float | Trip-weighted mean efficiency, min per km. |
| `e_median` | float | Median over the LAUs. |
| `speed_weighted_kmh` | float | 60 / e_weighted. |
