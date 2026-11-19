# station_group_manual.csv — Reviewed cross-feed station pairs (input)

- **Produced by:** hand-maintained from station_group_review.csv
- **Generated:** 2026-11-17T11:19:56
- **One row is:** one reviewed pair
- **Rows:** 32
- **Domestic feed:** ZSR_SK

| column | type | description |
|---|---|---|
| `a` | str | station_key of one station. |
| `a_name` | str | Its name (for readability). |
| `b` | str | station_key of the other station. |
| `b_name` | str | Its name (for readability). |
| `decision` | str | accept (link: same physical station) or reject (remove any direct link); empty rows are ignored. |
| `note` | str | Reason of the decision. |
