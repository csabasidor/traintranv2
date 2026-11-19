# feed_table.csv — The seven GTFS feeds: size, coverage in time, exceptions (REP-4)

- **Produced by:** notebooks/04e_feed_completeness.ipynb (nb04_feeds.feed_table)
- **Generated:** 2026-11-17T12:12:49
- **One row is:** one feed
- **Rows:** 7
- **Runs:** headline country runs (03)

| column | type | description |
|---|---|---|
| `feed_key` | str | Feed. |
| `file` | str | File in data/feeds/. |
| `bytes` | int | File size. |
| `agencies` | int | agency.txt rows. |
| `routes` | int | routes.txt rows. |
| `trips` | int | trips.txt rows. |
| `stops` | int | stops.txt rows. |
| `stations` | int | Stations in the 01b catalog. |
| `route_types` | str | GTFS route_type values present. |
| `calendar_dates_added` | int | calendar_dates rows adding a service day (exception_type 1). |
| `calendar_dates_removed` | int | Rows removing one (exception_type 2): holidays, cancellations. |
| `service_start` | str | First day of the feed's calendar. |
| `service_end` | str | Last day. |
| `window_start` | str | Analysis window start (01a). |
| `window_end` | str | Window end. |
| `window_days` | int | Window length. |
| `role` | str | domestic / foreign. |
