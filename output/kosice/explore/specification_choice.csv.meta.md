# specification_choice.csv — Functional form per network and model: RESET of each form, the curvature probe, and the primary form

- **Produced by:** notebooks/04c_models.ipynb (nb04_models.curvature / choose_form)
- **Generated:** 2026-11-17T14:10:46
- **One row is:** one network x family x distance
- **Rows:** 20
- **Unit:** LAU, inbound, headline runs
- **Errors:** HC3 (OLS); cluster-robust by country (sample "clustered", >= 5 countries); HC1 (logit); ML (spatial models)

| column | type | description |
|---|---|---|
| `network` | str | Network (domestic / foreign for the transfer model). |
| `family` | str | decay (time ~ km), frequency (f ~ km), joint (f ~ km + population), transfer (pooled). |
| `distance` | str | route or rail. |
| `n` | int | LAUs. |
| `reset_linear` | float | RESET p of the linear form. |
| `reset_loglog` | float | RESET p of the log-log form (empty where none exists). |
| `r2_linear` | float | R² of the linear form. |
| `r2_loglog` | float | R² of the log-log form. |
| `quad_coef` | float | Coefficient of km² added to the linear form: + the gradient steepens with distance, - it flattens (a shape probe, not a proposed model). |
| `quad_low` | float | Its 95 % interval, low (HC3). |
| `quad_high` | float | Its 95 % interval, high. |
| `quad_p` | float | Its p-value. |
| `rule` | str | The rule that fired (RESET level 0.01). |
| `primary_form` | str | linear | log-log | linear, caveat (a descriptive average gradient, not a structural parameter). |
