# correlations.csv — Correlations of log frequency with log distance and log population, with intervals

- **Produced by:** notebooks/04c_models.ipynb
- **Generated:** 2026-11-17T14:13:59
- **One row is:** one network x variable x country (pooled, and within each country for the foreign networks)
- **Rows:** 26
- **Unit:** LAU, inbound, headline runs
- **Errors:** HC3 (OLS); cluster-robust by country (sample "clustered", >= 5 countries); HC1 (logit); ML (spatial models)

| column | type | description |
|---|---|---|
| `network` | str | Network. |
| `with` | str | rail_km (shortest path) or population. |
| `country` | str | pooled, or the country of a within-country correlation. |
| `n` | int | LAUs. |
| `pearson_r` | float | Pearson r on logs. |
| `pearson_low` | float | Fisher-z 95 % interval, low. |
| `pearson_high` | float | Fisher-z 95 % interval, high. |
| `pearson_p` | float | p-value. |
| `spearman_rho` | float | Spearman rank correlation. |
| `spearman_low` | float | Bootstrap 95 % interval, low. |
| `spearman_high` | float | Bootstrap 95 % interval, high. |
| `sign_differs_from_pooled` | object | Country rows: the within-country Pearson r has the opposite sign of the pooled one. Pooled rows: the pooled sign differs from the majority of the within-country signs (Simpson's paradox check). Empty for the single-country domestic networks. |
