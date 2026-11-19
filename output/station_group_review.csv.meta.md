# station_group_review.csv — Review queue: close stations of different feeds in one LAU whose names do not match

- **Produced by:** notebooks/01b_stations_tag_match.ipynb, section 6
- **Generated:** 2026-11-17T11:19:56
- **One row is:** one pair of stations (different feeds, same LAU, within match_auto_max_km) left in different groups
- **Rows:** 0
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `a` | str | station_key of one station. |
| `a_feed` | str | Its feed. |
| `a_name` | str | Its name. |
| `b` | str | station_key of the other station. |
| `b_feed` | str | Its feed. |
| `b_name` | str | Its name. |
| `lau_gisco_id` | str | The shared LAU. |
| `distance_km` | float | Distance between the two stations, km. |
| `decision` | str | Empty; accept (same station) / reject, when copied into data/manual/station_group_manual.csv. |
| `note` | str | Empty; reviewer's note. |
