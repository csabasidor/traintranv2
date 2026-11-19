# daytrip_direct_sensitivity.csv — Dwell-time sensitivity of foreign same-day visits (direct)

- **Produced by:** notebooks/03c_foreign_daytrip_direct.ipynb
- **Generated:** 2026-11-17T11:31:56
- **One row is:** one minimum dwell x country run
- **Rows:** 18
- **Rule:** arrive <= 11:00, dwell >= 360 min, depart >= 17:00, back <= 23:59

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `dwell_min` | int | Minimum time in Košice, minutes. |
| `is_base` | bool | The configured dwell. |
| `n_lau_any` | int | LAUs with >= 1 day-trip day. |
| `pop_any` | float | Their population. |
| `n_lau_50` | int | LAUs with day trips on >= 50 % of days. |
| `pop_50` | float | Their population. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
