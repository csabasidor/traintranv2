# market_potential_contour.csv — Market potential, contour form: catchment within a journey time τ

- **Produced by:** notebooks/05_market_potential.ipynb (nb05_market_potential.contour)
- **Generated:** 2026-11-17T11:40:39
- **One row is:** one country x service level x mass level x τ (empty τ = the whole catchment)
- **Rows:** 360
- **Inputs:** explore/lau_table.csv, data/eb/fl551_*_national.csv, NUTS subset PPS 2023

| column | type | description |
|---|---|---|
| `country` | str | Origin country. |
| `service_level` | str | direct, onehop (no direct train) or direct_or_onehop. |
| `mass` | str | M1 population catchment (15+), M2 rail-travelling population, M3 connecting-adjusted. |
| `tau_min` | float | Journey-time limit, minutes. |
| `value` | float | Σ M over LAUs with mean journey time <= τ. |
| `total` | float | Σ M of the whole catchment. |
| `n_lau` | int | LAUs counted. |
| `low` | float | At the rates' nominal lower bounds (M2 / M3). |
| `high` | float | At the upper bounds. |
| `share_of_catchment` | float | value / total. |
| `source` | str | Flash Eurobarometer 551 (GESIS ZA8901 v1.0.0) and the traintranv2 02-04 outputs. |
| `sampling` | str | non-probability quota (FL551). |
| `interval_type` | str | nominal: an FL551 interval is a design-effect-adjusted binomial half-width, not a margin of error. |
| `rate_is_upper_bound` | bool | True: the FL551 rate overstates the rail-market share (fewer non-travellers than a probability sample, FL499 dx1). |
| `generated_at` | str | When the file was written. |
