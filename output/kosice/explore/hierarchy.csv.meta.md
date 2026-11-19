# hierarchy.csv — Distinct journeys recounted per NUTS3, NUTS2 and country (never summed from LAUs)

- **Produced by:** notebooks/04a_service_patterns.ipynb (nb04_patterns.recount)
- **Generated:** 2026-11-17T11:35:50
- **One row is:** one region x level x direction x network x run
- **Rows:** 321
- **Built from:** 02a, 02b, 03a, 03b outputs

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `run` | str | SK (domestic, ZSR_SK window) or the foreign country run (CZ, HU, AT, PL, UA; PL:PL_IC = sensitivity). |
| `direction` | str | inbound (to Košice) or outbound (from Košice). |
| `level` | str | nuts3 / nuts2 / country. |
| `region` | str | Region id. |
| `n_journeys` | int | Distinct journeys serving the region. |
| `run_days` | int | Their run days. |
| `window_days` | int | Days in the window. |
| `n_lau` | int | LAUs of the region reached. |
| `f_per_day` | float | Journeys per day for the region. |
