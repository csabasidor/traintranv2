# market_potential_exp.csv — Market potential, exponential form by half-life: effective population

- **Produced by:** notebooks/05_market_potential.ipynb (nb05_market_potential.exponential)
- **Generated:** 2026-11-17T11:40:39
- **One row is:** one country x service level x mass level x half-life
- **Rows:** 225
- **Inputs:** explore/lau_table.csv, data/eb/fl551_*_national.csv, NUTS subset PPS 2023

| column | type | description |
|---|---|---|
| `country` | str | Origin country. |
| `service_level` | str | direct, onehop (no direct train) or direct_or_onehop. |
| `mass` | str | M1 population catchment (15+), M2 rail-travelling population, M3 connecting-adjusted. |
| `half_life_min` | int | Half-life h, minutes (the grid is the sensitivity analysis). |
| `effective_population` | float | Σ M · 2^(-t/h): population-equivalents at zero journey time. |
| `catchment` | float | Σ M. |
| `geography_ratio` | float | effective_population / catchment. |
| `share_national_rail_market` | float | effective_population / M2 of the whole country (M2, M3). |
| `low` | float | At the rates' nominal lower bounds. |
| `high` | float | At the upper bounds. |
| `source` | str | Flash Eurobarometer 551 (GESIS ZA8901 v1.0.0) and the traintranv2 02-04 outputs. |
| `sampling` | str | non-probability quota (FL551). |
| `interval_type` | str | nominal: an FL551 interval is a design-effect-adjusted binomial half-width, not a margin of error. |
| `rate_is_upper_bound` | bool | True: the FL551 rate overstates the rail-market share (fewer non-travellers than a probability sample, FL499 dx1). |
| `generated_at` | str | When the file was written. |
