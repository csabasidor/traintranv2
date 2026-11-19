# direct_coverage.csv — Slovak LAUs and population reached by a direct train to / from Košice, with denominators

- **Produced by:** notebooks/02a_domestic_direct.ipynb
- **Generated:** 2026-11-17T11:48:33
- **One row is:** one group of LAUs (all, with a station, served directly) in one direction
- **Rows:** 6
- **Feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `group` | str | all_lau (every Slovak LAU except the hub's), with_station (LAUs with a station of the domestic catalog), direct (LAUs with a direct trip). |
| `n_lau` | int | LAUs in the group. |
| `population` | float | Their population end-2025. |
| `share_lau` | float | n_lau / n_lau of all_lau. |
| `share_population` | float | population / population of all_lau. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
