# station_tags_review.csv — Review list: in-scope stations whose LAU name check stayed unresolved (all feeds)

- **Produced by:** notebooks/01b_stations_tag_match.ipynb, section 4
- **Generated:** 2026-11-15T13:51:30
- **One row is:** one station with lau_match_method = unresolved inside the six study countries
- **Rows:** 0
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `feed_key` | str | Feed of the station. |
| `station_key` | str | Station id (see station_tags). |
| `stop_name` | str | Station name. |
| `stop_ids` | str | Member stop_ids; use one of them with feed_key in lau_manual_matches_v2.csv. |
| `nuts_rg_01_country_id` | str | Country of the polygon LAU. |
| `lau_gisco_id` | str | LAU the station was kept in (its polygon). |
| `lau_name_national` | str | That LAU's national name. |
| `lau_name_score` | float | Best name similarity to that LAU (national / Latin). |
| `candidates` | str | Up to three nearby LAUs (within lau_neighbor_radius_km, measured in lau_metric_crs) with their best name score, 'name [GISCO_ID] score', separated by ' | '. |
| `gisco_id` | str | Empty; the reviewer's chosen LAU. |
| `note` | str | Empty; the reviewer's note. |
