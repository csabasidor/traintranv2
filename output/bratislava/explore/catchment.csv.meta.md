# catchment.csv — Municipal catchment of Košice (inbound) with its three mass levels

- **Produced by:** notebooks/05_market_potential.ipynb (nb05_catchment)
- **Generated:** 2026-11-17T12:13:01
- **One row is:** one LAU (Bratislava one unit; the city of Košice excluded) reachable inbound on the headline runs
- **Rows:** 2,059
- **Inputs:** explore/lau_table.csv, data/eb/fl551_*_national.csv, NUTS subset PPS 2023

| column | type | description |
|---|---|---|
| `lau_code` | str | LAU (or city unit) id. |
| `lau_name` | str | Name. |
| `country` | str | Origin country. |
| `nuts2_id` | str | NUTS2. |
| `nuts3_id` | str | NUTS3. |
| `dgurba` | float | Degree of urbanisation. |
| `service_level` | str | direct (any direct train) or onehop; exclusive. |
| `network` | str | The 04 network the figures come from. |
| `run` | str | Country run (03). |
| `journey_time_min` | float | Mean journey time of the service level, minutes. |
| `rail_km` | float | Mean shortest-path km. |
| `route_km` | float | Mean route km. |
| `trips_per_day` | float | Journeys per day. |
| `pop_0_14` | float | Population 0-14 (outside both surveys; reported only). |
| `pop_15_64` | float | Population 15-64. |
| `pop_65plus` | float | Population 65+. |
| `pop_total` | float | Total population (UA: 2024). |
| `pop_15_plus` | float | 15-64 + 65+: the only base for rates. |
| `pps_value` | float | NUTS3 PPS per inhabitant (2023). |
| `pps_level` | str | NUTS3, or UA_no_PPS. |
| `pps_year` | float | Year of the PPS value. |
| `in_inner_ring` | bool | Rail distance < 50 km: below FL551's distance floor, not converted. |
| `in_survey` | bool | The country is in FL551 (not UA). |
| `M1` | float | Population catchment: pop_15_plus. |
| `M2` | float | Rail-travelling population: age-banded FL551 rates (beyond 50 km). |
| `M2_low` | float | M2 at the rates' nominal lower bounds. |
| `M2_high` | float | M2 at the upper bounds. |
| `M2_flat` | float | M2 with the flat national rate (for comparison). |
| `M3` | float | Connecting-adjusted: M2 (direct) or M2 x (T2|T1) (onehop). |
| `M3_low` | float | M3 at the nominal lower bounds. |
| `M3_high` | float | M3 at the upper bounds. |
| `source` | str | Flash Eurobarometer 551 (GESIS ZA8901 v1.0.0) and the traintranv2 02-04 outputs. |
| `sampling` | str | non-probability quota (FL551). |
| `interval_type` | str | nominal: an FL551 interval is a design-effect-adjusted binomial half-width, not a margin of error. |
| `rate_is_upper_bound` | bool | True: the FL551 rate overstates the rail-market share (fewer non-travellers than a probability sample, FL499 dx1). |
| `generated_at` | str | When the file was written. |
