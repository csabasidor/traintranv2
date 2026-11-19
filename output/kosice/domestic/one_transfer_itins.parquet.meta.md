# one_transfer_itins.parquet — One-transfer itineraries between the Košice hub and every station of the domestic feed

- **Produced by:** notebooks/02b_domestic_one_transfer.ipynb
- **Generated:** 2026-11-17T11:28:07
- **One row is:** one itinerary (first train + second train, paired at one transfer station) with the dates both run
- **Rows:** 124,593
- **window_start:** 2025-12-14
- **window_end:** 2026-12-12
- **window_days:** 364
- **Feed:** ZSR_SK
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `station_key` | str | Origin (inbound) or destination (outbound) station. |
| `group` | str | Its station_group_id. |
| `T` | str | station_group_id of the transfer station. |
| `T_key` | str | Transfer station. |
| `leg1_feed` | str | Feed of the first train. |
| `leg1_trip` | str | trip_id of the first train. |
| `leg2_feed` | str | Feed of the second train. |
| `leg2_trip` | str | trip_id of the second train. |
| `start_s` | int | Departure of the first train (seconds of the service day, no wrap). |
| `t_arr_s` | int | Arrival at the transfer station. |
| `t_dep_s` | int | Departure from it. |
| `end_s` | int | Arrival of the second train. |
| `ride_s` | int | Time on board (total - wait), seconds. |
| `wait_s` | int | Wait at the transfer station, seconds. |
| `total_s` | int | end_s - start_s, seconds. |
| `next_day` | bool | True if the second train leaves after midnight on the next service date (times then run past 24:00 on the first train's clock; PIP-6). |
| `n_days` | int | Days both trains run (bitmask AND). |
| `mask` | str | Those days, '0'/'1' per window day. |
| `has_direct` | bool | True if the station also has a direct train in this direction (02a). |
| `nuts_rg_01_country_id` | str | Country of the station. |
| `lau_gisco_id` | str | LAU of the station. |
