# direction_asymmetry.csv — Inbound against outbound per LAU

- **Produced by:** notebooks/04a_service_patterns.ipynb
- **Generated:** 2026-11-17T11:35:50
- **One row is:** one LAU x network x run
- **Rows:** 1,489
- **Built from:** 02a, 02b, 03a, 03b outputs

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `run` | str | SK (domestic, ZSR_SK window) or the foreign country run (CZ, HU, AT, PL, UA; PL:PL_IC = sensitivity). |
| `lau_gisco_id` | str | LAU (abroad: from the national feed's station, 03a). |
| `f_inbound` | float | Journeys per day to Košice. |
| `f_outbound` | float | Journeys per day from Košice. |
| `time_inbound` | float | Median journey time inbound, minutes. |
| `time_outbound` | float | Median journey time outbound, minutes. |
| `f_diff` | float | f_inbound - f_outbound. |
| `time_diff` | float | time_inbound - time_outbound. |
| `population` | float | Population: end-2025 where available, else 2024 (UA). |
