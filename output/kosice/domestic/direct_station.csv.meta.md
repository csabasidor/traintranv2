# direct_station.csv — Direct connections to / from Košice per Slovak station

- **Produced by:** notebooks/02a_domestic_direct.ipynb
- **Generated:** 2026-11-17T11:26:56
- **One row is:** one Slovak station in one direction, with at least one direct trip
- **Rows:** 230
- **Feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `station_key` | str | Station (01b catalog). |
| `stop_name` | str | Station name. |
| `lau_gisco_id` | str | LAU of the station (01b). |
| `lau_name_national` | str | LAU name. |
| `nuts3_id` | str | NUTS3 region. |
| `degurba` | str | Degree of urbanisation of the LAU (1 city, 2 town / suburb, 3 rural). |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `n_journeys` | int | Distinct trips (direct) serving the unit in this direction; a train calling at several stations of one LAU counts once for the LAU. |
| `journeys_per_day` | float | Sum of those trips' run days in the window / window_days: average trains per day. |
| `service_days` | int | Days of the window with at least one such trip. |
| `service_share` | float | service_days / window_days. |
| `min_time_min` | float | Shortest ride between the hub and the unit, minutes. |
| `median_time_min` | float | Median ride over the distinct trips, minutes. |
| `rail_km` | float | Shortest track distance from the Košice station (01c). |
| `geo_km` | float | Geodesic distance from the Košice station (01c). |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
