# validation_sample.csv — Stratified sample of computed inbound journeys to check against the operators' planners (VAL-1)

- **Produced by:** notebooks/07_validation_sample.ipynb (nb07_validation.sample)
- **Generated:** 2026-11-17T12:19:15
- **One row is:** one sampled journey (one per LAU within a stratum)
- **Rows:** 73
- **Seed:** 20261116
- **Dates:** 2026-11-17 .. 2026-12-12

| column | type | description |
|---|---|---|
| `sample_id` | str | V001 ... |
| `stratum` | str | '<run> direct' / '<run> one transfer' per country / feed run; cross-feed transfer; across midnight. |
| `kind` | str | direct or one transfer. |
| `country` | str | Origin country. |
| `run` | str | Country / feed run (PL:PL_IC = PKP-IC feed). |
| `feed` | str | Feed of the train (direct) or of the two trains (one transfer). |
| `date` | str | Calendar date of the departure, between 2026-11-17 and 2026-12-12 (a GTFS time past 24:00 moves to the next day). |
| `date_basis` | str | feed = a run date in the feed; projected = the feed's window ended before 2026-11-17 (HU, PL), so the first date on the weekday the journey ran on in >= 80 % of cases. |
| `projected_from` | str | For projected rows: the last run date in the feed on that weekday. |
| `origin` | str | Origin station. |
| `destination` | str | Košice. |
| `planner` | str | Planner to query. |
| `departure` | str | Computed departure, clock time on that date. |
| `arrival` | str | Computed arrival at Košice; (+1) = the day after the departure. |
| `transfer_station` | str | Transfer station (one transfer). |
| `transfer_arrival` | str | Arrival there. |
| `transfer_departure` | str | Departure from there. |
| `trains` | str | Train numbers (and headsigns) as the feeds publish them. |
| `journey_min` | int | Computed journey time, minutes. |
