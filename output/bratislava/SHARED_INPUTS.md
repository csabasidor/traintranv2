# Shared inputs of the Bratislava run

Copied from `output\kosice` on 2026-11-17T14:04:23 by `nb01a_feeds.shared_inputs`. These products of notebooks 01a / 01b do not depend on the destination (feeds, analysis windows, station catalog, LAU tags, cross-feed station groups), so they are identical for every destination. The timetable cache (`timetable/`, keyed by feed and window) is copied too. 01c and everything after it are run for this destination.

| file | sha256 (first 16) |
|---|---|
| `windows.json` | `d40852d882a045df` |
| `feed_roles.csv` | `f8a59d541d53fc7d` |
| `feed_monthly_trains.csv` | `4aeaac82bd197887` |
| `feed_stop_tags.parquet` | `50d8d1b6f4b1584b` |
| `station_tags.csv` | `313ec96047b88fed` |
| `station_tags_review.csv` | `17571ce4bc2cec33` |
| `station_feed_matches.csv` | `937fcefe84662469` |
| `station_feed_review.csv` | `c57824d985ff16b9` |
| `station_group_links.csv` | `8df213f52c1a0741` |
| `station_group_conflicts.csv` | `20971580f12f856b` |
| `station_group_review.csv` | `c05a34c201089a48` |
