# feed_roles.csv — Feeds and their role in the analysis

- **Produced by:** notebooks/01a_feeds_download.ipynb
- **Generated:** 2026-11-17T11:18:35
- **One row is:** one GTFS feed
- **Rows:** 7
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `feed_key` | str | Feed key used throughout the pipeline. |
| `country` | str | Country of the feed's operator / data origin. |
| `role` | str | domestic (analysed on its full calendar) or foreign (analysed on its overlap with the domestic feed). |
| `file` | str | File in data/feeds/. |
| `present` | bool | True if the file is on disk. |
| `provider` | str | Who distributes the GTFS (e.g. Transitious). |
| `data_origin` | str | Who produces the underlying data. |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the analysis window. |
| `window_days` | int | Length of the window in days. |
| `window_basis` | str | How the window was set: the service span (first to last day with >= window_min_share of the median daily trains) for the domestic feed, its overlap with the domestic one for a foreign feed. |
| `snapshot` | str | Note when an older snapshot is used on purpose (HU, UA). |
