# daytrip_direct_lau.csv — Same-day visits to Košice per foreign LAU (direct)

- **Produced by:** notebooks/03c_foreign_daytrip_direct.ipynb
- **Generated:** 2026-11-17T11:59:54
- **One row is:** one foreign LAU with at least one day-trip day, in one country run
- **Rows:** 23
- **Rule:** arrive <= 11:00, dwell >= 360 min, depart >= 17:00, back <= 23:59

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
| `n_daytrip_days` | int | Days of the window on which a same-day visit to Košice is possible (rule in the notebook / config). |
| `daytrip_share` | float | n_daytrip_days / window_days. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
