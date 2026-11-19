# models_summary.csv — Fit statistics and diagnostics of the 04c models

- **Produced by:** notebooks/04c_models.ipynb (nb04_models)
- **Generated:** 2026-11-17T14:13:59
- **One row is:** one model
- **Rows:** 83
- **Unit:** LAU, inbound, headline runs
- **Errors:** HC3 (OLS); cluster-robust by country (sample "clustered", >= 5 countries); HC1 (logit); ML (spatial models)

| column | type | description |
|---|---|---|
| `network` | str | Network. |
| `family` | str | Model family. |
| `distance` | str | route or rail. |
| `sample` | str | Sample or variant. |
| `model` | str | Model label. |
| `n` | int | Observations (LAUs). |
| `r2` | float | R²; pseudo-R² (1 - deviance / null deviance) for the two-part logit, ML pseudo-R² for the spatial models. A two-part pseudo-R² near 0 (Košice foreign_one_transfer: 0.048) means that part explains almost nothing; it is never presented as if it did. |
| `adj_r2` | float | Adjusted R² (OLS only). |
| `bp_p` | float | Breusch-Pagan p (heteroskedasticity). |
| `reset_p` | float | Ramsey RESET p (nonlinearity); see specification_choice.csv for what follows. |
| `resid_skew` | float | Skew of the residuals (HC3 intervals stay valid; no normal-theory interval is reported). |
| `n_influential` | float | LAUs with Cook's distance > 4/n (named in influential_observations.csv). |
| `max_cooks` | float | Largest Cook's distance (no interval exists for it). |
| `moran_i` | float | Moran's I of the residuals (5 nearest LAUs, row-standardised); the outcome's I and the k sweep are in spatial_diagnostics.csv. |
| `moran_p` | float | Its pseudo p-value (999 permutations; 0.001 is the floor). |
| `n_served` | float | Served LAUs (two-part logit only; empty for every other family by design). |
| `mean_d_time` | float | Matched transfer model only (empty elsewhere by design): mean one-transfer minus direct time, minutes. |
| `median_d_time` | float | Matched transfer model only: the median of that difference. |
| `cov_type` | str | Standard errors: HC3, cluster by country (with the number of clusters), HC1 (logit), ML. |
| `n_removed` | float | Observations removed against the full fit (pop < 100k, excl. top-5 influential); 0 for full fits. The domestic pop < 100k refit removes one LAU and establishes nothing. |
| `si_understated` | object | True where the residuals are spatially autocorrelated (Moran p < 0.05): the intervals understate the uncertainty; empty where not tested. |
