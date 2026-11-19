# direct_legs.parquet — Direct ZSR_SK trains between the Košice hub and stations abroad, per destination-country window

- **Produced by:** notebooks/03a_foreign_direct.ipynb
- **Generated:** 2026-11-17T11:50:26
- **One row is:** one trip between the hub and one foreign station, in one direction, in one country run
- **Rows:** 1,677
- **Runs:** CZ; HU; UA; PL; PL:PL_IC; AT

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
| `lau_gisco_id` | str | LAU of the station (01b). |
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
