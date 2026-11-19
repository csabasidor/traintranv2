# dedup_radius.csv — Stations formed by the same-name merge rule at several radii (VAL-4)

- **Produced by:** notebooks/04e_feed_completeness.ipynb (nb04_feeds.dedup_radius)
- **Generated:** 2026-11-17T11:40:27
- **One row is:** one feed x radius
- **Rows:** 12
- **Runs:** headline country runs (03)

| column | type | description |
|---|---|---|
| `feed_key` | str | Feed without parent stations. |
| `radius_km` | float | Merge radius (01b uses 2 km). |
| `stops` | int | Boarding stops. |
| `stations` | int | Stations formed. |
| `merged_groups` | int | Stations formed from more than one stop. |
