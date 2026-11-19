# daytrip_direct_station.csv — Same-day visits to Košice from foreign stations (direct)

- **Produced by:** notebooks/03c_foreign_daytrip_direct.ipynb
- **Generated:** 2026-11-17T11:31:56
- **One row is:** one foreign station with at least one day-trip day, in one country run
- **Rows:** 10
- **Rule:** arrive <= 11:00, dwell >= 360 min, depart >= 17:00, back <= 23:59

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `station_key` | str | Station (01b catalog). |
| `stop_name` | str | Station name. |
| `lau_gisco_id` | str | LAU of the station (01b). |
| `lau_name_national` | str | LAU name. |
| `nuts3_id` | str | NUTS3 region. |
| `degurba` | str | Degree of urbanisation of the LAU (1 city, 2 town / suburb, 3 rural). |
| `n_daytrip_days` | int | Days of the window on which a same-day visit to Košice is possible (rule in the notebook / config). |
| `daytrip_share` | float | n_daytrip_days / window_days. |
| `rail_km` | float | Shortest track distance from Košice (01c). |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
