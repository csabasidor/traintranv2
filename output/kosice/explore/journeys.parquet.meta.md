# journeys.parquet — Distinct journeys per LAU of the four networks (domestic / foreign x direct / one transfer)

- **Produced by:** notebooks/04a_service_patterns.ipynb (nb04_frame.journeys)
- **Generated:** 2026-11-17T11:35:50
- **One row is:** one distinct journey (direct trip, or first + second train) x LAU x direction x run; the shortest ride if it calls at several stations of the LAU
- **Rows:** 109,769
- **Built from:** 02a, 02b, 03a, 03b outputs

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `run` | str | SK (domestic, ZSR_SK window) or the foreign country run (CZ, HU, AT, PL, UA; PL:PL_IC = sensitivity). |
| `headline` | bool | False only for single-feed sensitivity runs (PL:PL_IC). |
| `country` | str | Country of the station. |
| `window_days` | int | Days in the run window. |
| `direction` | str | inbound (to Košice) or outbound (from Košice). |
| `lau_gisco_id` | str | LAU (abroad: from the national feed's station, 03a). |
| `station_key` | str | Station of the LAU the journey uses. |
| `journey` | str | feed|trip (direct) or feed|leg1>feed|leg2 (one transfer). |
| `n_days` | int | Run days in the window (both legs, on one transfer). |
| `mask` | str | Run dates, '0'/'1' per window day. |
| `route_km` | float | Track km along the stations the train(s) call at (nb04_distance). |
| `has_direct` | bool | The station / LAU also has a direct train in this direction. |
| `rail_km` | float | Shortest track path Košice - station (01c). |
| `geo_km` | float | Geodesic Košice - station (01c). |
| `time_min` | float | Journey time: ride (direct) or first departure to final arrival incl. the wait, minutes. |
| `wait_min` | float | Wait at the transfer station, minutes (empty for direct). |
