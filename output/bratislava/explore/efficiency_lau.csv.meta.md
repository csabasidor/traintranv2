# efficiency_lau.csv — Journey efficiency per LAU (spec §3, route km), with the network mean and both aggregations

- **Produced by:** notebooks/04b_distance_time_efficiency.ipynb
- **Generated:** 2026-11-17T12:11:05
- **One row is:** one LAU x direction x network x run with mean route km above the cut-off
- **Rows:** 4,541
- **Built from:** 04a journeys / lau_table
- **Efficiency cut-off:** 5 km route

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `run` | str | SK (domestic, ZSR_SK window) or the foreign country run (CZ, HU, AT, PL, UA; PL:PL_IC = sensitivity). |
| `direction` | str | inbound (to Košice) or outbound (from Košice). |
| `lau_gisco_id` | str | LAU (abroad: from the national feed's station, 03a). |
| `lau_name` | str | LAU name (national). |
| `country` | str | Country of the LAU. |
| `degurba` | float | Degree of urbanisation (1 city, 2 town / suburb, 3 rural). |
| `population` | float | Population: end-2025 where available, else 2024 (UA). |
| `f_per_day` | float | Journeys per day. |
| `time_mean_min` | float | Mean journey time, minutes. |
| `route_km_mean` | float | Mean route km. |
| `rail_km_mean` | float | Mean shortest-path km. |
| `geo_km_mean` | float | Mean straight-line km. |
| `e_route` | float | e = mean time / mean route km, min per km. |
| `e_rail` | float | The same on shortest-path km. |
| `e_geo` | float | The same on straight-line km. |
| `e_network` | float | Trip-weighted network mean of e_route (weights f_per_day). |
| `delta` | float | e_route - e_network (signed difference). |
| `delta_hat` | float | e_route / e_network (ratio). |
| `e_mean_of_ratios` | float | Mean over the journeys of time / route km. |
| `rom_mor` | float | e_route / e_mean_of_ratios. |
| `n_stations` | int | Stations of the LAU used. |
| `window_days` | int | Days in the window. |
