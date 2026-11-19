# degurba_corners.csv — DEGURBA sensitivity: rail market under city / town / rural propensity ratios (corners)

- **Produced by:** notebooks/05_market_potential.ipynb (nb05_market_potential.degurba_corners)
- **Generated:** 2026-11-17T11:40:39
- **One row is:** one country x corner
- **Rows:** 18
- **Inputs:** explore/lau_table.csv, data/eb/fl551_*_national.csv, NUTS subset PPS 2023

| column | type | description |
|---|---|---|
| `country` | str | Origin country. |
| `ratio_city` | float | Propensity ratio for cities (DEGURBA 1). |
| `ratio_town` | float | For towns and suburbs (2). |
| `ratio_rural` | float | For rural areas (3). |
| `mass` | str | M1 population catchment (15+), M2 rail-travelling population, M3 connecting-adjusted. |
| `value` | float | The mass under the ratios (renormalised to the catchment mix). |
| `base` | float | Uniform-rate value. |
| `source` | str | Flash Eurobarometer 551 (GESIS ZA8901 v1.0.0) and the traintranv2 02-04 outputs. |
| `sampling` | str | non-probability quota (FL551). |
| `interval_type` | str | nominal: an FL551 interval is a design-effect-adjusted binomial half-width, not a margin of error. |
| `rate_is_upper_bound` | bool | True: the FL551 rate overstates the rail-market share (fewer non-travellers than a probability sample, FL499 dx1). |
| `generated_at` | str | When the file was written. |
