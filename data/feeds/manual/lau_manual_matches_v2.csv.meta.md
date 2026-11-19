# lau_manual_matches_v2.csv — Manual LAU corrections, re-keyed to the ZSR_SK stop_id (input)

- **Produced by:** converted once from data/manual/lau_manual_matches.csv by notebooks/01b_stations_tag_match.ipynb, section 2; then hand-maintained
- **Generated:** 2026-11-17T11:19:56
- **One row is:** one reviewed station -> LAU correction
- **Rows:** 392
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `feed_key` | str | Feed of the station (the converted legacy rows are ZSR_SK). |
| `stop_id` | str | Feed stop_id the correction applies to (any member stop of a station). |
| `stop_name` | str | Station name (from the legacy catalog). |
| `gisco_id` | str | LAU to assign (GISCO_ID in the LAU 2024 subset). |
| `note` | str | Reviewer's note from the original review. |
| `conversion` | str | Only ok / ok_near rows are applied. ok (same name, <= 100 m), ok_near (<= 1 km), unmatched / unmatched_far (no such stop in the current feed), dropped_out_of_scope (DE/CH), ua_review (old hard-coded UA id), gisco_not_in_subset. |
| `legacy_station_id` | str | The old run-specific S000nn id the row was keyed on. |
| `match_distance_km` | float | Distance between the legacy station and the matched feed stop, km. |
