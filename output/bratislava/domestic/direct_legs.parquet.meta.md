# direct_legs.parquet — Direct trains between the Košice hub and every station of the domestic feed (both directions)

- **Produced by:** notebooks/02a_domestic_direct.ipynb
- **Generated:** 2026-11-17T11:48:33
- **One row is:** one trip between the hub and one station, in one direction (the trip's shortest hub - station ride)
- **Rows:** 8,133
- **window_start:** 2025-12-14
- **window_end:** 2026-12-12
- **window_days:** 364
- **Feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `feed_key` | str | Feed of the trip (ZSR_SK). |
| `trip_id` | str | GTFS trip_id. |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `station_key` | str | Station (01b catalog). |
| `group` | str | station_group_id of the station (01b). |
| `hub_key` | str | Hub station of the trip: the last hub call before the station (outbound) or the first after it (inbound). |
| `dep_s` | int | Departure, seconds of the service day (hub outbound, station inbound); not wrapped at 24:00. |
| `arr_s` | int | Arrival, seconds of the service day (station outbound, hub inbound). |
| `ride_s` | int | arr_s - dep_s, seconds. |
| `route_type` | str | GTFS route_type of the trip (extended types: 100 long distance, 102 / 103 express / interregional, 105 sleeper, 106 regional). |
| `n_days` | int | Days of the window the trip runs (calendar + calendar_dates). |
| `mask` | str | Run dates as '0'/'1' per window day, day 0 first. |
| `stop_name` | str | Station name. |
| `nuts_rg_01_country_id` | str | Country of the station's LAU (domestic analysis = SK; other countries are in 03a). |
| `lau_gisco_id` | str | LAU of the station (01b). |
