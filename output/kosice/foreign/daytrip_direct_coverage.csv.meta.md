# daytrip_direct_coverage.csv — Foreign LAUs and population with same-day visits to Košice (direct), with denominators

- **Produced by:** notebooks/03c_foreign_daytrip_direct.ipynb
- **Generated:** 2026-11-17T11:31:56
- **One row is:** one group of LAUs of one country
- **Rows:** 30
- **Rule:** arrive <= 11:00, dwell >= 360 min, depart >= 17:00, back <= 23:59

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `group` | str | all_lau, served (an option in both directions), daytrip_any (>= 1 day), daytrip_50 / daytrip_90 (on >= 50 % / 90 % of the window's days). |
| `n_lau` | int | LAUs in the group. |
| `population` | float | LAU population: end-2025 where available, else 2024 (UA). |
| `share_lau` | float | n_lau / n_lau of all_lau. |
| `share_population` | float | population / population of all_lau. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
