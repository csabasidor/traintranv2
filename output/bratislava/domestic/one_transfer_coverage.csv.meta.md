# one_transfer_coverage.csv — Slovak LAUs and population reached directly and with one transfer, with denominators

- **Produced by:** notebooks/02b_domestic_one_transfer.ipynb
- **Generated:** 2026-11-17T11:49:53
- **One row is:** one group of LAUs in one direction
- **Rows:** 12
- **Feed:** ZSR_SK
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `group` | str | all_lau (all Slovak LAUs except the hub's), with_station, direct, one_transfer (any one-transfer journey), newly_reached (one transfer, no direct train), direct_or_one_transfer. |
| `n_lau` | int | LAUs in the group. |
| `population` | float | Population end-2025. |
| `share_lau` | float | n_lau / all_lau. |
| `share_population` | float | population / all_lau. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
