# direct_lau.csv — Direct connections to / from Košice per foreign LAU

- **Produced by:** notebooks/03a_foreign_direct.ipynb
- **Generated:** 2026-11-17T11:50:26
- **One row is:** one foreign LAU in one direction with at least one direct ZSR trip, in one country run
- **Rows:** 175
- **Runs:** CZ; HU; UA; PL; PL:PL_IC; AT

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `lau_gisco_id` | str | LAU of the station (01b). |
| `lau_name_national` | str | LAU name. |
| `nuts3_id` | str | NUTS3 region (empty for UA). |
| `degurba` | str | Degree of urbanisation of the LAU (1 city, 2 town / suburb, 3 rural). |
| `population` | float | LAU population: end-2025 where available, else 2024 (UA). |
| `pop_year` | int | Year of that population figure. |
| `n_stations` | int | Stations of the LAU with a direct trip in this direction. |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `n_journeys` | int | Distinct trips (direct) serving the unit in this direction; a train calling at several stations of one LAU counts once for the LAU. |
| `journeys_per_day` | float | Sum of those trips' run days in the window / window_days: average trains per day. |
| `service_days` | int | Days of the window with at least one such trip. |
| `service_share` | float | service_days / window_days. |
| `min_time_min` | float | Shortest ride between the hub and the unit, minutes. |
| `median_time_min` | float | Median ride over the distinct trips, minutes. |
| `journeys_per_day_364` | float | The same on ZSR_SK's full window (364 days), for reference. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
