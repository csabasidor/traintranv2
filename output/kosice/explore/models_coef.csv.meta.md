# models_coef.csv — Coefficients of the 04c models, with HC3 standard errors and 95 % intervals

- **Produced by:** notebooks/04c_models.ipynb (nb04_models)
- **Generated:** 2026-11-17T14:10:46
- **One row is:** one term of one model
- **Rows:** 255
- **Unit:** LAU, inbound, headline runs
- **Errors:** HC3 (OLS); cluster-robust by country (sample "clustered", >= 5 countries); HC1 (logit); ML (spatial models)

| column | type | description |
|---|---|---|
| `network` | str | Network (or domestic / foreign for the transfer models). |
| `family` | str | decay, transfer, power, joint or two_part. |
| `distance` | str | route (route km) or rail (shortest-path km). |
| `sample` | str | Sample or variant: all, pop < 100k, excl. top-5 influential, pooled, matched, country effects (C(country) fixed effects), clustered (SEs clustered by country), spatial lag / spatial error (ML, check on the OLS fit) ... |
| `model` | str | Model label. |
| `term` | str | Model term (rho / lambda: the spatial parameter). |
| `coef` | float | Estimate. |
| `se` | float | Standard error: HC3 (OLS), cluster-robust by country (sample 'clustered'), HC1 (logit), ML asymptotic (spatial lag / error). |
| `ci_low` | float | 95 % interval, low. |
| `ci_high` | float | 95 % interval, high. |
| `p` | float | p-value. |
