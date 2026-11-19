# lau_table.csv — Per LAU: the metric-definition aggregates of the four networks

- **Produced by:** notebooks/04a_service_patterns.ipynb (nb04_frame.lau_table)
- **Generated:** 2026-11-17T12:07:28
- **One row is:** one LAU x direction x network x run with at least one journey
- **Rows:** 4,868
- **Built from:** 02a, 02b, 03a, 03b outputs

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `run` | str | SK (domestic, ZSR_SK window) or the foreign country run (CZ, HU, AT, PL, UA; PL:PL_IC = sensitivity). |
| `headline` | bool | False only for single-feed sensitivity runs (PL:PL_IC). |
| `direction` | str | inbound (to Košice) or outbound (from Košice). |
| `lau_gisco_id` | str | LAU (abroad: from the national feed's station, 03a). |
| `window_days` | int | W: days in the window. |
| `n_journeys` | int | |I|: distinct journeys. |
| `run_days` | int | R: their run days summed. |
| `time_mean_min` | float | Mean journey time (spec §1). |
| `time_median_min` | float | Median journey time. |
| `time_min_min` | float | Shortest journey time. |
| `wait_median_min` | float | Median transfer wait (one transfer). |
| `route_km_mean` | float | Mean route km over the journeys. |
| `rail_km_mean` | float | Mean shortest-path km of the stations used (spec §2). |
| `geo_km_mean` | float | Mean geodesic km of the stations used. |
| `n_stations` | int | Stations of the LAU used. |
| `has_direct` | bool | A direct train exists in this direction. |
| `service_days` | int | Days with at least one journey. |
| `f_per_day` | float | f = R / W: journeys per day (spec §4). |
| `mean_days_per_journey` | float | R / |I|; must be <= W. |
| `lau_name` | str | LAU name (national). |
| `country` | str | Country of the LAU. |
| `nuts2_id` | str | NUTS2 region (UA: oblast). |
| `nuts3_id` | str | NUTS3 region (empty for UA). |
| `degurba` | float | Degree of urbanisation (1 city, 2 town / suburb, 3 rural). |
| `population` | float | Population: end-2025 where available, else 2024 (UA). |
| `pop_year` | int | Year of that population figure. |
| `pop_15plus` | float | Population aged 15+ (15-64 + 65+, end-2025); empty where not available (UA). |
