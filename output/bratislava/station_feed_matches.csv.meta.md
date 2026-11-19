# station_feed_matches.csv — Foreign-station matches: domestic stations located in CZ/HU/AT/PL/UA found in their national feed

- **Produced by:** notebooks/01b_stations_tag_match.ipynb, section 5
- **Generated:** 2026-11-15T13:51:30
- **One row is:** accepted matches: one row per stop of the matched foreign catalog station -- its GTFS parent and the member stops trains use (best_match = 1); review / rejected / unmatched: one row per station x feed (best_match = 0)
- **Rows:** 890
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `station_id` | str | Run-specific station id (see station_tags.stop_id). |
| `station_name` | str | Station name in the ZSR_SK feed. |
| `station_stop_ids` | str | ';'-joined ZSR_SK stop_ids of the station (stable key). |
| `country` | str | Country the station is tagged in (decides which feed is searched). |
| `feed_key` | str | National feed searched. |
| `status` | str | auto (name or UIC code + same LAU + within match_auto_max_km), manual (reviewed accept), rejected (reviewed reject), review (not used downstream until decided). |
| `reason` | str | Why a row is in review: different_lau, too_far, name_below_threshold, no_coordinates (';'-joined, for a name hit), position_candidate (no name hit, but a station of the feed within match_candidate_km), no_name_match (nothing nearby either); the reviewer's note for manual / rejected. |
| `match_type` | str | Name tier of the hit: exact (normalised names equal), core (equal after dropping generic station words: Bahnhof, Bhf., pályaudvar, stacja kolejowa, železniční stanice, stanica, the CZ request flag z), code (same UIC code), sequence (fuzzy, SequenceMatcher ratio), manual, none. |
| `score` | float | Name similarity of the hit (1.0 for exact and manual). |
| `feed_stop_id` | str | Matched stop_id in the national feed. |
| `feed_stop_name` | str | Its stop_name. |
| `feed_station_name` | str | Name of the foreign catalog station the stop belongs to (station_tags.stop_name of that feed). |
| `feed_stop_lat` | float | Its latitude. |
| `feed_stop_lon` | float | Its longitude. |
| `feed_location_type` | str | Its GTFS location_type. |
| `feed_parent_station` | str | Its GTFS parent_station. |
| `match_distance_km` | float | Haversine distance between the domestic station and the best hit, km. |
| `same_lau` | bool | True if the hit's station lies in the same LAU as the domestic station (both from station_tags). |
| `station_lat` | float | Latitude of the domestic station. |
| `station_lon` | float | Longitude of the domestic station. |
| `station_gisco_id` | str | LAU (GISCO_ID) of the domestic station (from station_tags). |
| `feed_gisco_id` | str | LAU (GISCO_ID) of the hit's station (from station_tags). |
| `alternatives` | str | For review rows: position candidates -- up to three stations of the feed within match_candidate_km, same LAU first, 'name [stop_id] distance km, same LAU | LAU <id>', ' | '-separated. |
| `suggested_feed_stop_id` | str | For review rows: the first position candidate's stop_id (copy into station_feed_manual.feed_stop_id to accept it). |
| `best_match` | int | 1 = accepted (auto / manual), read by the foreign extraction; 0 = not used. |
