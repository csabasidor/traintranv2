# one_transfer_itins.parquet — One-transfer itineraries between the Košice hub and stations abroad (ZSR first leg)

- **Produced by:** notebooks/03b_foreign_one_transfer.ipynb
- **Generated:** 2026-11-17T11:31:46
- **One row is:** one itinerary (ZSR train + ZSR or national train, paired at one transfer station) with the dates both run
- **Rows:** 72,346
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
| `lau_gisco_id` | str | LAU of the station abroad (from the national feed's station of its group, 03a). |
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `has_direct` | bool | The station also has a direct ZSR train in this direction. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
