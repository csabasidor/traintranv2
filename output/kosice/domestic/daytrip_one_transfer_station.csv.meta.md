# daytrip_one_transfer_station.csv — Same-day visits to Košice by direct or one-transfer trains, per Slovak station

- **Produced by:** notebooks/02d_domestic_daytrip_one_transfer.ipynb
- **Generated:** 2026-11-17T11:28:30
- **One row is:** one Slovak station with at least one day-trip day
- **Rows:** 378
- **Feed:** ZSR_SK
- **Rule:** arrive <= 11:00, dwell >= 360 min, depart >= 17:00, back <= 23:59

| column | type | description |
|---|---|---|
| `station_key` | str | Station (01b catalog). |
| `stop_name` | str | Station name. |
| `lau_gisco_id` | str | LAU of the station (01b). |
| `lau_name_national` | str | LAU name. |
| `nuts3_id` | str | NUTS3 region. |
| `degurba` | str | Degree of urbanisation of the LAU (1 city, 2 town / suburb, 3 rural). |
| `n_daytrip_days` | int | Days of the window on which a same-day visit to Košice is possible (rule in the notebook / config). |
| `daytrip_share` | float | n_daytrip_days / window_days. |
| `rail_km` | float | Shortest track distance from the Košice station (01c). |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
