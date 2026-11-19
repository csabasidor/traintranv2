# station_feed_manual.csv — Reviewed foreign-match decisions (input)

- **Produced by:** hand-maintained; seeded by notebooks/01b_stations_tag_match.ipynb, section 5
- **Generated:** 2026-11-17T11:19:56
- **One row is:** one reviewed station x feed decision
- **Rows:** 16
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `station_name` | str | Station name (for readability). |
| `station_stop_id` | str | One ZSR_SK stop_id of the station (the key). |
| `feed_key` | str | National feed. |
| `feed_stop_id` | str | The accepted (or rejected) stop_id in that feed; an accepted stop is expanded to its catalog station (parent + the member stops trains use). |
| `feed_stop_name` | str | Its name (for readability). |
| `decision` | str | accept or reject; empty rows are ignored. |
| `note` | str | Reason / source of the decision. |
