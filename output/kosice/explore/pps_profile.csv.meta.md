# pps_profile.csv — Purchasing power of the catchment against its country (a characteristic, not a weight)

- **Produced by:** notebooks/05_market_potential.ipynb (nb05_market_potential.pps_profile)
- **Generated:** 2026-11-17T11:40:39
- **One row is:** one country x service level (UA not included: no PPS)
- **Rows:** 13
- **Inputs:** explore/lau_table.csv, data/eb/fl551_*_national.csv, NUTS subset PPS 2023

| column | type | description |
|---|---|---|
| `country` | str | Origin country. |
| `service_level` | str | direct, onehop (no direct train) or direct_or_onehop. |
| `pps_level` | str | NUTS3. |
| `n_lau` | int | LAUs. |
| `pps_catchment_popweighted` | float | Population(15+)-weighted mean PPS of the catchment. |
| `pps_country_popweighted` | float | Population-weighted mean PPS of the whole country. |
| `catchment_vs_country` | float | Ratio of the two (> 1: the reachable population is in richer regions). |
| `source` | str | Flash Eurobarometer 551 (GESIS ZA8901 v1.0.0) and the traintranv2 02-04 outputs. |
| `sampling` | str | non-probability quota (FL551). |
| `interval_type` | str | nominal: an FL551 interval is a design-effect-adjusted binomial half-width, not a margin of error. |
| `rate_is_upper_bound` | bool | True: the FL551 rate overstates the rail-market share (fewer non-travellers than a probability sample, FL499 dx1). |
| `generated_at` | str | When the file was written. |
