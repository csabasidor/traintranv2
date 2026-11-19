# station_group_links.csv — Cross-feed links between stations (and rejected code links)

- **Produced by:** notebooks/01b_stations_tag_match.ipynb, section 6
- **Generated:** 2026-11-17T11:19:56
- **One row is:** one link between two stations of different feeds
- **Rows:** 1,217
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `a` | str | station_key of one station. |
| `b` | str | station_key of the other. |
| `tier` | str | code / place / match / manual (see station_tags.link_tiers); in the conflicts file: code links rejected for distance. |
| `distance_km` | float | Distance between the two stations, km. |
| `uic_code` | str | The shared UIC code (code tier). |
