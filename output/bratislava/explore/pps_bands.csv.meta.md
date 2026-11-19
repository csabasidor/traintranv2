# pps_bands.csv — Catchment and rail market by national PPS quartile

- **Produced by:** notebooks/05_market_potential.ipynb (nb05_market_potential.pps_profile)
- **Generated:** 2026-11-17T12:13:01
- **One row is:** one country x service level x PPS quartile
- **Rows:** 60
- **Inputs:** explore/lau_table.csv, data/eb/fl551_*_national.csv, NUTS subset PPS 2023

| column | type | description |
|---|---|---|
| `country` | str | Origin country. |
| `service_level` | str | direct, onehop (no direct train) or direct_or_onehop. |
| `pps_level` | str | NUTS3. |
| `pps_band` | str | Q1 (poorest) .. Q4: national quartiles of NUTS3 PPS, population-weighted over the LAUs. |
| `M1` | float | Population catchment (15+). |
| `M2` | float | Rail-travelling population. |
| `M3` | float | Connecting-adjusted. |
| `n_lau` | int | LAUs. |
| `source` | str | Flash Eurobarometer 551 (GESIS ZA8901 v1.0.0) and the traintranv2 02-04 outputs. |
| `sampling` | str | non-probability quota (FL551). |
| `interval_type` | str | nominal: an FL551 interval is a design-effect-adjusted binomial half-width, not a margin of error. |
| `rate_is_upper_bound` | bool | True: the FL551 rate overstates the rail-market share (fewer non-travellers than a probability sample, FL499 dx1). |
| `generated_at` | str | When the file was written. |
