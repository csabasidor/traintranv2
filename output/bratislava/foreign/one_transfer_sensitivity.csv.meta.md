# one_transfer_sensitivity.csv — Sensitivity of the foreign one-transfer results: transfer window and city transfers

- **Produced by:** notebooks/03b_foreign_one_transfer.ipynb
- **Generated:** 2026-11-17T11:59:40
- **One row is:** one variant x country run x direction
- **Rows:** 80
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `variant` | str | window (transfer-window grid, VAL-2) or city_transfer (any two stations of one LAU, PIP-17). |
| `min_connect_min` | int | Minimum transfer, minutes. |
| `max_connect_min` | int | Maximum transfer, minutes. |
| `is_base` | bool | The headline settings. |
| `n_lau_one_transfer` | int | LAUs with a one-transfer journey. |
| `n_lau_newly_reached` | int | LAUs with a one-transfer journey and no direct train. |
| `pop_newly_reached` | float | Their population. |
| `journeys_per_day` | float | Journeys per day over all LAUs of the country (distinct per LAU, summed). |
| `single_hub_share` | float | Share of newly reached LAUs depending on one transfer station (hubs_for_90 = 1). |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
