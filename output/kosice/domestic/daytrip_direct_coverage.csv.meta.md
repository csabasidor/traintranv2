# daytrip_direct_coverage.csv — Slovak LAUs and population with a same-day visit to Košice by direct trains, with denominators

- **Produced by:** notebooks/02c_domestic_daytrip_direct.ipynb
- **Generated:** 2026-11-17T11:28:18
- **One row is:** one group of LAUs
- **Rows:** 5
- **Feed:** ZSR_SK
- **Rule:** arrive <= 11:00, dwell >= 360 min, depart >= 17:00, back <= 23:59

| column | type | description |
|---|---|---|
| `group` | str | all_lau (except the hub's), served (a train both ways), daytrip_any (>= 1 day), daytrip_50 (>= 50 % of days), daytrip_90 (>= 90 % of days). |
| `n_lau` | int | LAUs in the group. |
| `population` | float | Population end-2025. |
| `share_lau` | float | n_lau / all_lau. |
| `share_population` | float | population / all_lau. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
