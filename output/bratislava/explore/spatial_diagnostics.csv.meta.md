# spatial_diagnostics.csv — Spatial autocorrelation of the outcome and of the residuals, per model, on the LAU KNN graph

- **Produced by:** notebooks/04c_models.ipynb (nb04_models.moran_pair)
- **Generated:** 2026-11-17T14:13:59
- **One row is:** one model
- **Rows:** 59
- **Unit:** LAU, inbound, headline runs
- **Errors:** HC3 (OLS); cluster-robust by country (sample "clustered", >= 5 countries); HC1 (logit); ML (spatial models)

| column | type | description |
|---|---|---|
| `network` | str | Network. |
| `family` | str | Model family. |
| `distance` | str | route or rail. |
| `sample` | str | Sample or variant. |
| `n` | int | LAUs. |
| `k` | int | Neighbours of the reported graph (5). |
| `moran_i_y` | float | Moran's I of the outcome. |
| `moran_p_y` | float | Its pseudo p (999 permutations; floor 0.001). |
| `moran_i_resid` | float | Moran's I of the residuals. |
| `moran_p_resid` | float | Its pseudo p. |
| `absorbed` | float | moran_i_y - moran_i_resid: the spatial structure the covariates absorbed. |
| `i_resid_min_k` | float | Smallest residual I over k = 3, 5, 8, 10. |
| `i_resid_max_k` | float | Largest residual I over k = 3, 5, 8, 10. |
| `p_resid_max_k` | float | Largest residual pseudo p over those k. |
| `i_y_min_k` | float | Smallest outcome I over those k. |
| `i_y_max_k` | float | Largest outcome I over those k. |
