# influential_observations.csv — Influential LAUs by name: every LAU with Cook's distance > 4/n in a headline model

- **Produced by:** notebooks/04c_models.ipynb (nb04_models.influence_table)
- **Generated:** 2026-11-17T14:13:59
- **One row is:** one LAU x model
- **Rows:** 1,958
- **Unit:** LAU, inbound, headline runs
- **Errors:** HC3 (OLS); cluster-robust by country (sample "clustered", >= 5 countries); HC1 (logit); ML (spatial models)

| column | type | description |
|---|---|---|
| `network` | str | Network. |
| `family` | str | Model family. |
| `distance` | str | route or rail. |
| `sample` | str | The headline sample of the model. |
| `n` | int | Observations of the model. |
| `lau_gisco_id` | str | LAU. |
| `lau_name` | str | LAU name. |
| `country` | str | Country. |
| `population` | float | Population. |
| `cooks_d` | float | Cook's distance (no interval exists for it). |
| `fitted` | float | Fitted value of the outcome. |
| `actual` | float | Observed value. |
| `d_intercept` | float | Leave-one-out change in the intercept (all LAUs minus without this one). |
| `d_slope` | float | Leave-one-out change in the distance coefficient. |
| `above_1` | bool | Cook's D > 1: this LAU moves the fit on its own. |
