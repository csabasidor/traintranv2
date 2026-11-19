# one_transfer_lau.csv — One-transfer connections to / from Košice per foreign LAU, with gateway dependence

- **Produced by:** notebooks/03b_foreign_one_transfer.ipynb
- **Generated:** 2026-11-17T11:59:40
- **One row is:** one foreign LAU in one direction with at least one one-transfer journey
- **Rows:** 3,547
- **Transfer window:** 10-90 min
- **Pairing:** dated

| column | type | description |
|---|---|---|
| `country` | str | Destination country (CZ, HU, AT, PL, UA). |
| `run` | str | Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC). |
| `lau_gisco_id` | str | LAU of the station (01b). |
| `lau_name_national` | str | LAU name. |
| `nuts3_id` | str | NUTS3 region (empty for UA). |
| `degurba` | str | Degree of urbanisation of the LAU (1 city, 2 town / suburb, 3 rural). |
| `population` | float | LAU population: end-2025 where available, else 2024 (UA). |
| `pop_year` | int | Year of that population figure. |
| `direction` | str | inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored. |
| `n_journeys` | int | Distinct one-transfer journeys (first train + second train) serving the unit in this direction; a pair calling at several stations of one LAU counts once for the LAU. |
| `journeys_per_day` | float | Sum of those journeys' run days / window_days. |
| `service_days` | int | Days with at least one such journey. |
| `service_share` | float | service_days / window_days. |
| `min_time_min` | float | Shortest door-to-door time (first departure to final arrival, incl. the wait), minutes. |
| `median_time_min` | float | Median journey time over the distinct journeys, minutes. |
| `n_first_legs` | int | Distinct first trains behind the journeys (inbound: departures from the unit; outbound: departures from the hub). |
| `n_second_legs` | int | Distinct second trains behind the journeys. |
| `n_shared_leg` | int | Journeys sharing their first or second train with another journey to the same unit (transfer alternatives on one physical train). |
| `n_hubs` | int | Transfer stations used. |
| `median_wait_min` | float | Median wait at the transfer station, minutes. |
| `has_direct` | bool | The LAU also has a direct ZSR train in this direction. |
| `main_hub` | str | Transfer station carrying the largest share of the LAU's journeys per day. |
| `main_hub_share` | float | That share. |
| `hubs_for_90` | int | Fewest transfer stations carrying 90 % of the LAU's journeys per day (1 = depends on one gateway). |
| `window_start` | str | First day of the analysis window (ISO date). |
| `window_end` | str | Last day of the window. |
| `window_days` | int | Days in the window; per-day figures divide by this. |
