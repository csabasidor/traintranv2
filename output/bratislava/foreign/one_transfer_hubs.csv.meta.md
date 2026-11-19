# one_transfer_hubs.csv — Transfer stations (gateways) of the foreign one-transfer journeys

- **Produced by:** notebooks/03b_foreign_one_transfer.ipynb
- **Generated:** 2026-11-17T11:59:40
- **One row is:** one transfer station in one direction in one country run
- **Rows:** 344
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `T_key` | str | Transfer station. |
| `stop_name` | str | Station name. |
| `journeys_per_day` | float | Journeys per day through it (to / from LAUs of the country). |
| `n_lau` | int | LAUs reached through it. |
| `n_lau_only_hub` | int | LAUs without a direct train for which it is the only transfer station. |
| `pop_only_hub` | float | Their population. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
