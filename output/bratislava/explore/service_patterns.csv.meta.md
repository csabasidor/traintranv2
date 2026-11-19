# service_patterns.csv — Journeys per day by weekday, month and season, per LAU (REP-8, CF-20)

- **Produced by:** notebooks/04a_service_patterns.ipynb (nb04_patterns.lau_patterns)
- **Generated:** 2026-11-17T12:07:28
- **One row is:** one LAU x direction x network x run
- **Rows:** 4,868
- **Built from:** 02a, 02b, 03a, 03b outputs

| column | type | description |
|---|---|---|
| `network` | str | domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer. |
| `run` | str | SK (domestic, ZSR_SK window) or the foreign country run (CZ, HU, AT, PL, UA; PL:PL_IC = sensitivity). |
| `direction` | str | inbound (to Košice) or outbound (from Košice). |
| `lau_gisco_id` | str | LAU (abroad: from the national feed's station, 03a). |
| `all` | float | Journeys per day on every day (run days in the slice / days of the slice in the window; empty if the window has none). |
| `weekday` | float | Journeys per day on Mon-Fri (run days in the slice / days of the slice in the window; empty if the window has none). |
| `weekend` | float | Journeys per day on Sat-Sun (run days in the slice / days of the slice in the window; empty if the window has none). |
| `mon` | float | Journeys per day on Mon (run days in the slice / days of the slice in the window; empty if the window has none). |
| `tue` | float | Journeys per day on Tue (run days in the slice / days of the slice in the window; empty if the window has none). |
| `wed` | float | Journeys per day on Wed (run days in the slice / days of the slice in the window; empty if the window has none). |
| `thu` | float | Journeys per day on Thu (run days in the slice / days of the slice in the window; empty if the window has none). |
| `fri` | float | Journeys per day on Fri (run days in the slice / days of the slice in the window; empty if the window has none). |
| `sat` | float | Journeys per day on Sat (run days in the slice / days of the slice in the window; empty if the window has none). |
| `sun` | float | Journeys per day on Sun (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m03` | float | Journeys per day on month 3 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m04` | float | Journeys per day on month 4 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m05` | float | Journeys per day on month 5 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m06` | float | Journeys per day on month 6 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m07` | float | Journeys per day on month 7 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m08` | float | Journeys per day on month 8 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m09` | float | Journeys per day on month 9 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m10` | float | Journeys per day on month 10 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m11` | float | Journeys per day on month 11 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m12` | float | Journeys per day on month 12 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `DJF` | float | Journeys per day on Dec-Feb (run days in the slice / days of the slice in the window; empty if the window has none). |
| `MAM` | float | Journeys per day on Mar-May (run days in the slice / days of the slice in the window; empty if the window has none). |
| `JJA` | float | Journeys per day on Jun-Aug (run days in the slice / days of the slice in the window; empty if the window has none). |
| `SON` | float | Journeys per day on Sep-Nov (run days in the slice / days of the slice in the window; empty if the window has none). |
| `pattern` | str | every_day (all seven weekdays served), weekday_only, weekend_only, partial. |
| `m01` | float | Journeys per day on month 1 (run days in the slice / days of the slice in the window; empty if the window has none). |
| `m02` | float | Journeys per day on month 2 (run days in the slice / days of the slice in the window; empty if the window has none). |
