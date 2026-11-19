# station_tags.csv — Station catalog of all six feeds with LAU / NUTS / DEGURBA / population tags and cross-feed groups

- **Produced by:** notebooks/01b_stations_tag_match.ipynb, sections 3, 4 and 6
- **Generated:** 2026-11-15T13:51:30
- **One row is:** one station of one feed: platforms merged into their GTFS parent station; stops without a parent merged by the domestic rule (same norm_name within 2 km)
- **Rows:** 9,614
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `feed_key` | str | Feed the station comes from (ZSR_SK = domestic; DRAHY_CZ, MAV_HU, BAHN_AT, PL_IC, PL_REG, UKRZ_UA = foreign). |
| `station_key` | str | Stable station id: <feed_key>:<parent stop_id, or the first member stop_id>. |
| `stop_name` | str | Station name in that feed (the parent's name where there is one). |
| `stop_lat` | float | Latitude (WGS84): the parent's point, else the first member stop's. |
| `stop_lon` | float | Longitude (WGS84). |
| `stop_ids` | str | Semicolon-joined boarding stop_ids (platforms) of the station in that feed; trips reference these. Join key together with feed_key. |
| `n_member_stops` | int | Number of boarding stops merged into the station. |
| `dedup_method` | str | parent (platforms of one GTFS parent station), name_2km (stops with the same norm_name within 2 km), single. |
| `in_trips` | bool | True if at least one member stop is used by a trip (stop_times.txt). |
| `uic_code` | str | 7-digit UIC station code where the feed carries it (ZSR_SK, UKRZ_UA stop_ids; DRAHY_CZ country prefix + national number from its parent id: CZ 54, SK 56, PL 51, AT 81, DE 80); empty for MAV_HU, BAHN_AT, PL_IC, PL_REG. |
| `in_scope` | bool | True if the point lies in a LAU of the six study countries (CZ, SK, AT, HU, PL, UA). |
| `lau_name_score` | float | Name similarity (0-1, SequenceMatcher on norm_name) between the station name and the chosen LAU's national or Latin name, whichever is higher; 1.0 for manual corrections. |
| `lau_match_method` | str | How the LAU was chosen: contains_primary / fuzzy_primary (polygon LAU confirmed by name), contains_neighbor / fuzzy_neighbor (moved to a LAU within lau_neighbor_radius_km whose name fits better), unresolved (polygon LAU kept, name does not fit: review), polygon_accepted (station in a lau_polygon_only_countries country, PL / AT / UA / CZ / HU: the polygon LAU is taken without a name check), manual, ua_fallback. |
| `lau_name_in_polygon` | bool | True if the station lies in the LAU polygon and the names contain each other (method contains_primary). |
| `lau_tag_source` | str | Which step decided the LAU: polygon, name_neighbor, manual, ua_fallback, outside (no LAU in scope). |
| `nuts_rg_01_country_id` | str | Country code of the LAU (CNTR_CODE); '??' outside the study area. |
| `nuts_rg_01_country_name` | str | Country name (NUTS 2024 level 0, NAME_LATN). |
| `nuts_rg_01_region_id` | str | NUTS 2024 level-2 region of the LAU (UA: oblast code UA01...). |
| `nuts_rg_01_region_name` | str | Name of that NUTS2 region / oblast. |
| `nuts3_id` | str | NUTS 2024 level-3 region of the LAU ('??' for UA: GISCO has no UA level 3). |
| `nuts3_name` | str | Name of that NUTS3 region. |
| `lau_gisco_id` | str | GISCO_ID of the chosen LAU in the LAU 2024 subset (EU: <CC>_<LAU code>; UA: hromada pcode). |
| `lau_code` | str | National LAU code of the chosen LAU (text; leading zeros kept). |
| `lau_name_national` | str | LAU name, national spelling (LAU_NAME_NATIONAL). |
| `lau_name_latin` | str | LAU name, Latin spelling (LAU_NAME_LATIN). |
| `degurba` | int | Degree of urbanisation of the LAU: 1 city, 2 town/suburb, 3 rural (DEGURBA 2021; UA from GHSL). |
| `lau_pop_2024` | float | LAU population from GISCO LAU 2024 (POP_2024; UA hromadas: 1 Jan 2022). |
| `lau_area_km2` | float | LAU area in km2 (AREA_KM2). |
| `nuts2_id` | str | NUTS2 code of the LAU (same as nuts_rg_01_region_id). |
| `lau_pop_2025` | float | LAU population at end-2025 from the national statistical office (00_b* notebooks); empty for UA. |
| `lau_pop_15_64_2025` | float | Of which aged 15-64, end-2025. |
| `lau_pop_65plus_2025` | float | Of which aged 65 and over, end-2025. |
| `station_group_id` | str | Cross-feed identity: the same physical station in several feeds shares this id (G: + smallest station_key of the group). |
| `group_n_feeds` | int | Number of feeds the station's group spans (1 = only this feed). |
| `link_tiers` | str | How the group was linked: code (same UIC code), place (same LAU, within match_auto_max_km, names match), match (accepted foreign match), manual (reviewed pair in station_group_manual.csv); semicolon-joined, empty for single-feed groups. |
