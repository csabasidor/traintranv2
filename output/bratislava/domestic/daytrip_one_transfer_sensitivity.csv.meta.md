# daytrip_one_transfer_sensitivity.csv — Dwell-time sensitivity of same-day visits by direct or one-transfer trains (Reviewer 1, VAL-3)

- **Produced by:** notebooks/02d_domestic_daytrip_one_transfer.ipynb
- **Generated:** 2026-11-17T11:50:15
- **One row is:** one minimum dwell in Košice
- **Rows:** 3
- **Feed:** ZSR_SK
- **Rule:** arrive <= 11:00, dwell >= 360 min, depart >= 17:00, back <= 23:59

| column | type | description |
|---|---|---|
| `dwell_min` | int | Minimum time in Košice between arrival and return departure, minutes. |
| `is_base` | bool | The configuration of the main results. |
| `n_lau_any` | int | LAUs with >= 1 day-trip day. |
| `pop_any` | float | Their population. |
| `n_lau_50` | int | LAUs with day trips on >= 50 % of days. |
| `pop_50` | float | Their population. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
