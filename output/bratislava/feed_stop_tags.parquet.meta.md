# feed_stop_tags.parquet — Polygon check of every stop of every feed

- **Produced by:** notebooks/01b_stations_tag_match.ipynb, section 1
- **Generated:** 2026-11-15T13:51:30
- **One row is:** one stop (stops.txt row, deduplicated on stop_id) of one feed
- **Rows:** 33,681
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `feed_key` | str | Feed key (ZSR_SK, DRAHY_CZ, MAV_HU, BAHN_AT, PL_IC, PL_REG, UKRZ_UA). |
| `stop_id` | str | stop_id in that feed. |
| `stop_name` | str | stop_name in that feed. |
| `stop_lat` | float | Latitude (WGS84); empty if the feed gives none. |
| `stop_lon` | float | Longitude (WGS84). |
| `location_type` | str | GTFS location_type (1 = station / parent, empty or 0 = stop / platform). |
| `parent_station` | str | GTFS parent_station (the station a platform belongs to). |
| `GISCO_ID` | str | LAU polygon containing the stop (point in polygon, no name check); empty outside the subset. |
| `CNTR_CODE` | str | Country of that LAU. |
| `LAU_CODE` | str | National LAU code of that LAU. |
| `NUTS2_ID` | str | NUTS2 region (UA: oblast). |
| `NUTS3_ID` | str | NUTS3 region (empty for UA). |
| `DGURBA` | int | Degree of urbanisation of the LAU (1 city, 2 town/suburb, 3 rural). |
| `in_scope` | bool | True if inside a LAU of the six study countries. |
