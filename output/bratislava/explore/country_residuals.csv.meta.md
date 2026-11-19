# country_residuals.csv — Mean residual of the joint frequency model per country (spec §7)

- **Produced by:** notebooks/04c_models.ipynb
- **Generated:** 2026-11-17T14:13:59
- **One row is:** one network x country
- **Rows:** 11
- **Unit:** LAU, inbound, headline runs
- **Errors:** HC3 (OLS); cluster-robust by country (sample "clustered", >= 5 countries); HC1 (logit); ML (spatial models)

| column | type | description |
|---|---|---|
| `network` | str | Network. |
| `country` | str | Country. |
| `n` | int | LAUs. |
| `mean_resid` | float | Mean log-scale residual. |
| `multiplier` | float | exp(mean residual): served this many times as often as size and distance predict. |
