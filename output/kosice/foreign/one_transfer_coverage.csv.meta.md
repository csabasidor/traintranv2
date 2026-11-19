# one_transfer_coverage.csv — Foreign LAUs and population reached with one transfer, with denominators

- **Produced by:** notebooks/03b_foreign_one_transfer.ipynb
- **Generated:** 2026-11-17T11:31:46
- **One row is:** one group of LAUs of one country in one direction
- **Rows:** 72
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `group` | str | all_lau (every LAU of the country), with_station (LAUs with a station of the run's feeds), direct (a direct ZSR train), one_transfer (a journey with one change), newly_reached (one transfer and no direct train), direct_or_one_transfer. |
| `n_lau` | int | LAUs in the group. |
| `population` | float | LAU population: end-2025 where available, else 2024 (UA). |
| `share_lau` | float | n_lau / n_lau of all_lau. |
| `share_population` | float | population / population of all_lau. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
