# cascade.csv — The Slovak cascade: residents -> with a connection -> same-day return -> rail travellers, against the legacy figures

- **Produced by:** notebooks/05_market_potential.ipynb
- **Generated:** 2026-11-17T11:40:39
- **One row is:** one step
- **Rows:** 5
- **Inputs:** explore/lau_table.csv, data/eb/fl551_*_national.csv, NUTS subset PPS 2023

| column | type | description |
|---|---|---|
| `step` | str | Step. |
| `base` | str | Population base (total or 15+). |
| `new` | float | This run. |
| `legacy` | float | The register's legacy figure. |
| `new_share_of_residents` | float | new / residents. |
| `legacy_share` | float | legacy / legacy residents. |
| `source` | str | Flash Eurobarometer 551 (GESIS ZA8901 v1.0.0) and the traintranv2 02-04 outputs. |
| `sampling` | str | non-probability quota (FL551). |
| `interval_type` | str | nominal: an FL551 interval is a design-effect-adjusted binomial half-width, not a margin of error. |
| `rate_is_upper_bound` | bool | True: the FL551 rate overstates the rail-market share (fewer non-travellers than a probability sample, FL499 dx1). |
| `generated_at` | str | When the file was written. |
