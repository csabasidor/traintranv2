# one_transfer_sensitivity.csv — Transfer-window sensitivity of the domestic one-transfer network (Reviewer 1, VAL-2)

- **Produced by:** notebooks/02b_domestic_one_transfer.ipynb
- **Generated:** 2026-11-17T11:49:53
- **One row is:** one (min, max) transfer window in one direction
- **Rows:** 14
- **Feed:** ZSR_SK
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `min_connect_min` | int | Shortest allowed wait, minutes. |
| `max_connect_min` | int | Longest allowed wait, minutes. |
| `is_base` | bool | The configuration of the main results. |
| `n_lau_newly_reached` | int | LAUs reached with one transfer and no direct train. |
| `pop_newly_reached` | float | Their population end-2025. |
| `journeys_per_day_median` | float | Median journeys per day over those LAUs. |
| `median_time_min` | float | Median of the LAUs' median journey time, minutes. |
| `single_hub_share` | float | Share of those LAUs where one hub carries >= 90 % of the journeys. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
