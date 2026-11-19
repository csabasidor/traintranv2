# feed_effect.csv — What each national feed adds: LAUs and population reached with ZSR_SK alone against ZSR_SK + the national feed

- **Produced by:** notebooks/04e_feed_completeness.ipynb (nb04_feeds.feed_effect)
- **Generated:** 2026-11-17T12:12:49
- **One row is:** one country x variant x direction (headline runs)
- **Rows:** 20
- **Runs:** headline country runs (03)

| column | type | description |
|---|---|---|
| `country` | str | Destination country. |
| `variant` | str | ZSR_SK alone, or ZSR_SK + national feed (the headline of 03). |
| `direction` | str | inbound / outbound. |
| `n_lau` | int | LAUs reached directly or with one transfer. |
| `population` | float | Their population. |
| `n_lau_newly_reached` | int | Of them, reached only with a transfer. |
| `window_days` | int | Days in the country window. |
| `added_lau` | int | LAUs added over ZSR_SK alone: the national feed's contribution. |
| `added_population` | float | Population added. |
