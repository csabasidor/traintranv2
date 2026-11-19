# feed_quality.csv — Per country run and direction: legs, duplicates and itineraries behind the foreign results (REP-4)

- **Produced by:** notebooks/03b_foreign_one_transfer.ipynb
- **Generated:** 2026-11-17T11:31:46
- **One row is:** one country run x direction
- **Rows:** 12
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `first_legs` | int | ZSR legs between the hub and a station (first legs). |
| `second_legs` | int | Second legs (all feeds of the run) after removing cross-feed copies. |
| `duplicates_dropped` | int | Second legs dropped as another feed's copy of the same train. |
| `same_train_dropped` | int | Itineraries dropped as a transfer onto the same train (both directions of the run). |
| `itineraries` | int | One-transfer itineraries to / from stations of the country. |
| `itineraries_next_day` | int | Of them, connections across midnight (PIP-6). |
| `transfer_stations` | int | Transfer stations used. |
| `second_leg_feeds` | str | Itineraries by the second train's feed, 'feed: n' joined by '; '. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
