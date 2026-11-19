# claims_audit.csv — Every coefficient the submitted manuscript states, against the computed value (STA-5)

- **Produced by:** notebooks/04c_models.ipynb
- **Generated:** 2026-11-17T14:13:59
- **One row is:** one stated quantity
- **Rows:** 21
- **Unit:** LAU, inbound, headline runs
- **Errors:** HC3 (OLS); cluster-robust by country (sample "clustered", >= 5 countries); HC1 (logit); ML (spatial models)

| column | type | description |
|---|---|---|
| `network` | str | Network. |
| `quantity` | str | What the manuscript states. |
| `stated` | float | The stated value. |
| `computed` | float | Computed here with the manuscript's definition (shortest-path km, inbound, LAU). |
| `ci_low` | float | 95 % interval, low (where defined). |
| `ci_high` | float | 95 % interval, high. |
| `within_ci` | object | The stated value lies inside the computed interval (empty where no interval). |
| `where` | str | Section / figure of the submitted manuscript. |
| `form_basis` | str | The specification behind the quantity (whose RESET decides form_rejected); empty for quantities that come from no model (trip-weighted efficiency). |
| `form_reset_p` | float | RESET p of that specification. |
| `form_rejected` | object | True where that specification is rejected (RESET p < 0.01). |
