# direct_coverage.csv — Foreign LAUs and population reached by a direct ZSR train to / from Košice, with denominators

- **Produced by:** notebooks/03a_foreign_direct.ipynb
- **Generated:** 2026-11-17T11:28:42
- **One row is:** one group of LAUs of one country in one direction
- **Rows:** 36
- **Runs:** CZ; HU; UA; PL; PL:PL_IC; AT

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `group` | str | all_lau (every LAU of the country), with_station (LAUs with a station of the run's feeds), direct. |
| `n_lau` | int | LAUs in the group. |
| `population` | float | LAU population: end-2025 where available, else 2024 (UA). |
| `share_lau` | float | n_lau / n_lau of all_lau. |
| `share_population` | float | population / population of all_lau. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
