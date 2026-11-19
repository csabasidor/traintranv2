# route_types.csv — Services behind the journeys, by GTFS route_type (PIP-9)

- **Produced by:** notebooks/04a_service_patterns.ipynb
- **Generated:** 2026-11-17T11:35:50
- **One row is:** one network x run x route_type (or route_type pair for one transfer)
- **Rows:** 87
- **Built from:** 02a, 02b, 03a, 03b outputs

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `run` | str | SK (domestic, ZSR_SK window) or the foreign country run (CZ, HU, AT, PL, UA; PL:PL_IC = sensitivity). |
| `route_types` | str | route_type of the train (direct) or 'first > second' (one transfer); 100 long distance, 102/103 express / interregional, 105 sleeper, 106 regional, 2 rail. |
| `journeys` | int | Distinct journeys (both directions). |
| `run_days` | int | Their run days. |
| `seasonal_only` | float | Of them, journeys running in one season only; empty where the window does not span all four seasons (PL). |
