# one_transfer_hubs.csv — Transfer hubs of the domestic one-transfer network: volume and exclusive catchment

- **Produced by:** notebooks/02b_domestic_one_transfer.ipynb
- **Generated:** 2026-11-17T11:49:53
- **One row is:** one transfer station in one direction
- **Rows:** 245
- **Feed:** ZSR_SK
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `T_key` | str | Transfer station. |
| `stop_name` | str | Station name. |
| `journeys_per_day` | float | One-transfer journeys per day through it (Slovak LAUs). |
| `n_lau` | int | Slovak LAUs reached through it. |
| `n_lau_only_hub` | int | LAUs without a direct train for which it is the only transfer station. |
| `pop_only_hub` | float | Their population end-2025. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
