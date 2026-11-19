# cross_feed_duplicates.csv — Trains present in two feeds: the copy dropped and the leg kept (PIP-8)

- **Produced by:** notebooks/03b_foreign_one_transfer.ipynb
- **Generated:** 2026-11-17T11:31:46
- **One row is:** one dropped second leg (station-group pair of one trip) and the leg it duplicates
- **Rows:** 7,010
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `drop_feed` | str | Feed of the dropped copy (usually ZSR_SK). |
| `drop_trip` | str | Its trip_id. |
| `keep_feed` | str | Feed of the kept leg (the destination country's feed). |
| `keep_trip` | str | Its trip_id. |
| `from_group` | str | Departure station group. |
| `to_group` | str | Arrival station group. |
| `d_dep_s` | int | Departure difference kept - dropped, seconds (|.| <= 120). |
| `d_arr_s` | int | Arrival difference kept - dropped, seconds (|.| <= 120). |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
