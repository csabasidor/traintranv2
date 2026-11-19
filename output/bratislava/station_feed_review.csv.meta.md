# station_feed_review.csv — Review queue: foreign matches outside the automatic rule

- **Produced by:** notebooks/01b_stations_tag_match.ipynb, section 5
- **Generated:** 2026-11-15T13:51:30
- **One row is:** one station x feed with status review
- **Rows:** 0
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `station_name` | str | Station name in the ZSR_SK feed. |
| `station_stop_ids` | str | ZSR_SK stop_ids of the station; copy one into station_feed_manual.station_stop_id. |
| `country` | str | Country of the station. |
| `feed_key` | str | National feed searched. |
| `reason` | str | Why it needs review (see station_feed_matches.reason). |
| `match_type` | str | Name tier of the best hit, or none. |
| `score` | float | Name similarity of the best hit. |
| `feed_stop_id` | str | Best name hit in the feed (may be empty). |
| `feed_stop_name` | str | Its name. |
| `feed_station_name` | str | Station the best hit belongs to. |
| `match_distance_km` | float | Distance to the best hit, km. |
| `same_lau` | bool | True if the best hit is in the same LAU. |
| `alternatives` | str | Position candidates: up to three feed stations within match_candidate_km, same LAU first, with stop_id, distance and LAU. |
| `suggested_feed_stop_id` | str | The first position candidate's stop_id. |
| `decision` | str | Empty; to be filled when copied into data/manual/station_feed_manual.csv (accept / reject). |
| `note` | str | Empty; reviewer's note. |
