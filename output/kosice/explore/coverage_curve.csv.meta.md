# coverage_curve.csv — LAUs and population with at least k journeys per day (CON-8)

- **Produced by:** notebooks/04a_service_patterns.ipynb (nb04_patterns.coverage_curve)
- **Generated:** 2026-11-17T11:35:50
- **One row is:** one threshold x country x direction x network x run
- **Rows:** 80
- **Built from:** 02a, 02b, 03a, 03b outputs

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `run` | str | SK (domestic, ZSR_SK window) or the foreign country run (CZ, HU, AT, PL, UA; PL:PL_IC = sensitivity). |
| `direction` | str | inbound (to Košice) or outbound (from Košice). |
| `country` | str | Country of the LAU. |
| `min_per_day` | int | Threshold k (0 = any journey). |
| `n_lau` | int | LAUs with f >= k. |
| `population` | float | Their population. |
