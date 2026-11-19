"""
Notebook 04c -- the statistical models of the metric definitions (§5-7), with the inference Reviewer 1 asks for
(register STA-1 to STA-5, T17-T19, CF-12: "every r, R² and Eq. 8-10 has no computed source").

Every fit reports n, coefficients with heteroskedasticity-robust (HC3) standard errors and 95 % intervals, R², and
diagnostics: Breusch-Pagan (heteroskedasticity), Ramsey RESET (nonlinearity), skew of the residuals, Cook's distance
(influential observations), and Moran's I of the residuals on a k-nearest-neighbour graph of the LAUs (spatial
autocorrelation).

* ``fit``             -- OLS with HC3 and the diagnostics.
* ``correlations``    -- Pearson (Fisher-z interval) and Spearman (bootstrap interval) of two variables.
* ``transfer_penalty``-- the transfer effect as a model term (STA-1/2): pooled direct + one-transfer LAUs,
                         ``time = a + b*km + d*transfer + g*transfer*km``; and the matched version: LAUs with both,
                         ``time_1T - time_direct`` against ``km_1T - km_direct``.
* ``two_part``        -- zero-frequency LAUs (STA-4): a logit (binomial GLM) for being served among LAUs with a
                         station (pseudo-R² = 1 - deviance / null deviance), then the
                         frequency model on the served.

Answering the diagnostics, not only computing them (STA-4, ``additional_refactoring.md``):

* ``fit(groups=...)``  -- country effects: SEs clustered by country (country fixed effects are a ``C(country)`` term).
* ``curvature`` / ``choose_form`` -- nonlinearity: the quadratic shape probe, and the mechanical rule that picks a
                         primary functional form from the RESET tests.
* ``influence_table``  -- influential observations by name, with the leave-one-out change in every coefficient.
* ``moran_pair``       -- spatial autocorrelation of the outcome and of the residuals on one KNN graph per k (the
                         weights are built once and reused), so the structure absorbed by the covariates is measured.
* ``spatial_check``    -- spatial lag and spatial error models (spreg, maximum likelihood) as a check on whether the
                         OLS coefficients move.
"""

import numpy as np

AUDIT_CLAIMS = [
    # (network, quantity, stated value, where) -- the submitted manuscript, round 1
    ("domestic_direct", "decay slope (min/km)", 0.82, "§3.1.1, Fig. 5a"),
    ("domestic_direct", "decay intercept (min)", 10.1, "§3.1.1, Fig. 5a"),
    ("domestic_direct", "decay R2", 0.98, "§3.1.1, Fig. 5a"),
    ("domestic_direct", "r(log f, log distance)", -0.21, "§3.1.1, Fig. 5c"),
    ("domestic_direct", "r(log f, log population)", 0.09, "§3.1.1, Fig. 5c"),
    ("domestic_one_transfer", "log-log time slope", 0.70, "§3.1.2, Fig. 7a"),
    ("domestic_one_transfer", "log-log time R2", 0.90, "§3.1.2, Fig. 7a"),
    ("domestic_one_transfer", "r(log f, log distance)", -0.11, "§3.1.2, Fig. 7c"),
    ("domestic_one_transfer", "r(log f, log population)", 0.19, "§3.1.2, Fig. 7c"),
    ("foreign_direct", "decay slope (min/km)", 0.79, "§3.2.1, Fig. 12a"),
    ("foreign_direct", "decay intercept (min)", 37.0, "§3.2.1, Fig. 12a"),
    ("foreign_direct", "decay R2", 0.95, "§3.2.1, Fig. 12a"),
    ("foreign_direct", "trip-weighted efficiency (min/km)", 1.06, "§3.2.1, Fig. 12b"),
    ("foreign_direct", "r(log f, log distance)", -0.48, "§3.2.1, Fig. 12c"),
    ("foreign_direct", "r(log f, log population)", 0.20, "§3.2.1, Fig. 12c"),
    ("foreign_one_transfer", "decay slope (min/km)", 0.74, "§3.2.2, Fig. 14a"),
    ("foreign_one_transfer", "decay intercept (min)", 187.0, "§3.2.2, Fig. 14a (read as transfer overhead)"),
    ("foreign_one_transfer", "decay R2", 0.80, "§3.2.2, Fig. 14a"),
    ("foreign_one_transfer", "trip-weighted efficiency (min/km)", 1.38, "§3.2.2, Fig. 14b"),
    ("foreign_one_transfer", "r(log f, log distance)", -0.08, "§3.2.2, Fig. 14c"),
    ("foreign_one_transfer", "r(log f, log population)", -0.32, "§3.2.2, Fig. 14c"),
]


MORAN_KS = (3, 5, 8, 10)      # neighbour counts for the k sweep; k = 5 is the reported graph
FORM_ALPHA = 0.01             # RESET level at which a functional form is rejected (specification rule)
MIN_CLUSTERS = 5              # fewer countries than this: country fixed effects only, no clustered SEs


def _weights(xy, k: int):
    """Row-standardised k-nearest-neighbour weights of the points ``xy`` (None if too few points)."""
    from libpysal.weights import KNN
    if len(xy) <= k + 1:
        return None
    w = KNN.from_array(np.asarray(xy, dtype=float), k=k)
    w.transform = "r"
    return w


def _moran_w(values, w, seed: int = 0):
    """Moran's I on prebuilt weights; (I, pseudo p from 999 permutations). The seed is reset before every call, so
    each test draws the same permutations whatever ran before it."""
    from esda.moran import Moran
    if w is None:
        return np.nan, np.nan
    np.random.seed(seed)                       # esda draws its permutations from numpy's global generator
    m = Moran(np.asarray(values, dtype=float), w, permutations=999)
    return float(m.I), float(m.p_sim)


def _moran(resid, xy, k: int = 5, seed: int = 0):
    """Moran's I of residuals on a k-nearest-neighbour graph (row-standardised); (I, pseudo p from 999 permutations)."""
    return _moran_w(resid, _weights(xy, k), seed)


def moran_pair(y_values, resid, xy, ks=MORAN_KS, seed: int = 0):
    """Moran's I of the outcome and of the residuals on the same graph, for each k (weights built once per k).

    High I in the outcome and much lower I in the residuals: the covariates absorbed the spatial (corridor)
    structure; high I in both: they did not. Returns {k: (I_y, p_y, I_resid, p_resid)}.
    """
    out = {}
    for k in ks:
        w = _weights(xy, k)
        out[k] = (*_moran_w(y_values, w, seed), *_moran_w(resid, w, seed))
    return out


def fit(df, y: str, x: list, xy_cols=("x", "y"), label: str = "", groups: str = None, moran_ks=None):
    """OLS of ``y`` on ``x`` (column names; categorical as 'C(col)') with HC3; returns (coef table, summary dict, model).

    ``groups``: a column to cluster the standard errors by (country); the point estimates are those of OLS, only the
    interval changes. With few clusters (here at most five countries) the cluster-robust asymptotics are thin: it is
    a check on independence, reported beside HC3, not a replacement for it.
    ``moran_ks``: also compute Moran's I of ``y`` and of the residuals for these k (``summary['moran_k']``).
    """
    import pandas as pd
    import statsmodels.formula.api as smf
    from statsmodels.stats.diagnostic import het_breuschpagan, linear_reset
    from scipy.stats import skew

    used = {v[2:-1] if v.startswith("C(") else v for term in x for v in term.split(":")}
    d = df.dropna(subset=[y] + sorted(used) + ([groups] if groups else [])).copy()
    formula = f"{y} ~ " + " + ".join(x)
    if groups:
        codes = pd.factorize(d[groups])[0]
        m = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": codes})
    else:
        m = smf.ols(formula, data=d).fit(cov_type="HC3")
    ci = m.conf_int()
    coef = pd.DataFrame({"model": label, "term": m.params.index, "coef": m.params.values, "se": m.bse.values,
                         "ci_low": ci[0].values, "ci_high": ci[1].values, "p": m.pvalues.values})
    infl = m.get_influence().cooks_distance[0]
    n = int(m.nobs)
    out = {"model": label, "n": n, "r2": m.rsquared, "adj_r2": m.rsquared_adj,
           "bp_p": float(het_breuschpagan(m.resid, m.model.exog)[1]) if m.model.exog.shape[1] > 1 else np.nan,
           "reset_p": np.nan, "resid_skew": float(skew(m.resid)),
           "n_influential": int((infl > 4 / n).sum()), "max_cooks": float(infl.max())}
    try:
        out["reset_p"] = float(linear_reset(m, power=2, use_f=True).pvalue)
    except Exception:
        pass
    out["cov_type"] = f"cluster by {groups} ({len(set(d[groups]))} clusters)" if groups else "HC3"
    if xy_cols and all(c in d for c in xy_cols):
        xy = d[list(xy_cols)].to_numpy()
        out["moran_i"], out["moran_p"] = _moran(m.resid, xy)
        if moran_ks:
            out["moran_k"] = moran_pair(d[y].to_numpy(), m.resid.to_numpy(), xy, ks=moran_ks)
    return coef, out, m


def influence_table(m, slope_term: str, id_cols=("lau_gisco_id", "lau_name", "country", "population"),
                    threshold=None):
    """The observations of a fitted OLS ``m`` with Cook's D above ``threshold`` (default 4/n), by name.

    Columns: the id columns, cooks_d, fitted, actual, d_intercept / d_slope = the leave-one-out change in the
    intercept and in ``slope_term`` (estimate with all observations minus the estimate without this one), above_1
    (Cook's D > 1: one observation moves the fit on its own). Sorted by Cook's D, largest first.
    """
    inf = m.get_influence()
    cooks = inf.cooks_distance[0]
    n = int(m.nobs)
    thr = 4 / n if threshold is None else threshold
    d = m.model.data.frame.loc[m.model.data.row_labels]
    out = d[[c for c in id_cols if c in d]].copy()
    out["cooks_d"] = cooks
    out["fitted"] = np.asarray(m.fittedvalues)
    out["actual"] = np.asarray(m.model.endog)
    loo = np.asarray(m.params)[None, :] - np.asarray(inf.params_not_obsi)     # leave-one-out change per term
    terms = list(m.params.index)
    out["d_intercept"] = loo[:, terms.index("Intercept")]
    out["d_slope"] = loo[:, terms.index(slope_term)]
    out = out[out["cooks_d"] > thr].sort_values("cooks_d", ascending=False)
    out["above_1"] = out["cooks_d"] > 1
    return out.reset_index(drop=True)


def curvature(df, y: str, x: str, xy_cols=("x", "y"), label: str = "", extra=()):
    """The quadratic shape probe: ``y ~ x + x² (+ extra)``. Returns (coefficient of x², its 95 % interval, p, R², n).

    A shape check, not a proposed model: the sign says whether the gradient steepens (+) or flattens (-) with x.
    """
    d = df.assign(**{f"{x}_sq": df[x] ** 2})
    c, s, _ = fit(d, y, [x, f"{x}_sq", *extra], xy_cols=(), label=label)
    r = c.set_index("term").loc[f"{x}_sq"]
    return {"quad_coef": float(r.coef), "quad_low": float(r.ci_low), "quad_high": float(r.ci_high),
            "quad_p": float(r.p), "quad_r2": s["r2"], "n": s["n"]}


def choose_form(reset_linear: float, reset_loglog: float, alpha: float = FORM_ALPHA):
    """The primary functional form by a fixed rule (applied mechanically, never case by case).

    linear RESET passes (p >= alpha)                 -> 'linear'
    linear rejects, log-log passes                   -> 'log-log' (linear reported as sensitivity)
    both reject (or no log-log form exists)          -> 'linear, caveat': the linear coefficient is a descriptive
                                                        average gradient, not a structural parameter
    Returns (primary_form, rule).
    """
    lin_ok = np.isfinite(reset_linear) and reset_linear >= alpha
    log_ok = np.isfinite(reset_loglog) and reset_loglog >= alpha
    if lin_ok:
        return "linear", f"linear RESET p >= {alpha}"
    if log_ok:
        return "log-log", f"linear RESET p < {alpha}, log-log RESET p >= {alpha}"
    if not np.isfinite(reset_loglog):
        return "linear, caveat", f"linear RESET p < {alpha}, no log-log form"
    return "linear, caveat", f"both RESET p < {alpha}"


def spatial_check(df, y: str, x: list, xy_cols=("x", "y"), k: int = 5):
    """Spatial lag and spatial error models (spreg, maximum likelihood) on the KNN graph of the OLS diagnostics.

    A check on whether the OLS coefficients move once spatial dependence is modelled, not a replacement for OLS.
    Returns a coefficient table: model ('spatial lag' / 'spatial error'), term (incl. 'rho' / 'lambda'), coef, se,
    95 % interval (z), p; and a summary per model (n, pseudo-R², the spatial parameter).
    """
    import pandas as pd
    from scipy.stats import norm
    import spreg
    d = df.dropna(subset=[y, *x, *xy_cols])
    w = _weights(d[list(xy_cols)].to_numpy(), k)
    if w is None:
        return pd.DataFrame(), []
    Y = d[[y]].to_numpy(dtype=float)
    X = d[list(x)].to_numpy(dtype=float)
    rows, summ = [], []
    for name, cls, sp in (("spatial lag", spreg.ML_Lag, "rho"), ("spatial error", spreg.ML_Error, "lambda")):
        import contextlib, io, warnings
        with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
            warnings.simplefilter("ignore")              # spreg prints its class name; scipy warns on the optimiser
            r = cls(Y, X, w=w, name_y=y, name_x=list(x), method="full")
        b = np.asarray(r.betas).ravel()
        se = np.sqrt(np.diag(np.asarray(r.vm)))
        # spreg names: CONSTANT, the x columns, then W_<y> (lag) or lambda (error)
        names = ["Intercept" if t == "CONSTANT" else sp if t.startswith(("W_", "lambda")) else t for t in r.name_x]
        z = norm.ppf(0.975)
        for t, bb, ss in zip(names, b, se):
            p = float(2 * (1 - norm.cdf(abs(bb / ss)))) if ss > 0 else np.nan
            rows.append({"model": name, "term": t, "coef": float(bb), "se": float(ss),
                         "ci_low": float(bb - z * ss), "ci_high": float(bb + z * ss), "p": p})
        summ.append({"model": name, "n": int(r.n), "r2": float(r.pr2), "spatial_param": sp,
                     "spatial_value": float(b[names.index(sp)])})
    return pd.DataFrame(rows), summ


def correlations(a, b, n_boot: int = 2000, seed: int = 0):
    """Pearson r with a Fisher-z 95 % interval and Spearman rho with a bootstrap 95 % interval."""
    from scipy.stats import pearsonr, spearmanr
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = len(a)
    if n < 4:
        return {"n": n}
    r = pearsonr(a, b)
    z, s = np.arctanh(r.statistic), 1 / np.sqrt(n - 3)
    rs = spearmanr(a, b).statistic
    rng = np.random.default_rng(seed)
    boots = [spearmanr(a[i], b[i]).statistic for i in (rng.integers(0, n, n) for _ in range(n_boot))]
    return {"n": n, "pearson_r": r.statistic, "pearson_low": np.tanh(z - 1.96 * s), "pearson_high": np.tanh(z + 1.96 * s),
            "pearson_p": r.pvalue, "spearman_rho": rs, "spearman_low": np.nanpercentile(boots, 2.5),
            "spearman_high": np.nanpercentile(boots, 97.5)}


def transfer_penalty(direct, one, km: str = "route_km_mean", time: str = "time_mean_min", xy_cols=("x", "y"),
                     variant: str = "pooled", moran_ks=None):
    """Transfer effect on journey time, net of distance (STA-1 / STA-2).

    pooled: LAU rows of both networks, ``time ~ km + transfer + transfer:km`` -- the transfer coefficient is the
    difference in intercepts (Δα), the interaction the difference in slopes.
    matched: LAUs with both a direct and a one-transfer journey -- ``Δtime ~ Δkm``; the intercept is the extra
    time of the transfer at equal distance, the mean Δtime the raw difference.

    ``variant`` (pooled model only; the matched model is returned only for 'pooled'):
    'pooled' as above; 'country effects' adds ``C(country)`` (Δα net of each country's level);
    'clustered' keeps the pooled point estimate and clusters the SEs by country.
    """
    import pandas as pd
    p = pd.concat([direct.assign(transfer=0), one.assign(transfer=1)], ignore_index=True)
    if variant == "country effects":
        coef, summ, mv = fit(p, time, [km, "transfer", f"transfer:{km}", "C(country)"], xy_cols, variant,
                             moran_ks=moran_ks)
        summ["_model"] = mv
        return coef, [summ]
    if variant == "clustered":
        coef, summ, mv = fit(p, time, [km, "transfer", f"transfer:{km}"], xy_cols, variant, groups="country",
                             moran_ks=moran_ks)
        summ["_model"] = mv
        return coef, [summ]
    coef, summ, mp = fit(p, time, [km, "transfer", f"transfer:{km}"], xy_cols, "pooled", moran_ks=moran_ks)
    summ["_model"] = mp                         # the fitted pooled model, for the influence table (popped by callers)
    keys = ["lau_gisco_id"]
    m = direct[keys + [km, time]].merge(one[keys + [km, time]], on=keys, suffixes=("_d", "_t"))
    m["d_time"], m["d_km"] = m[f"{time}_t"] - m[f"{time}_d"], m[f"{km}_t"] - m[f"{km}_d"]
    mc, ms, _ = fit(m, "d_time", ["d_km"], (), "matched")
    ms["mean_d_time"], ms["median_d_time"] = float(m["d_time"].mean()), float(m["d_time"].median())
    return pd.concat([coef, mc], ignore_index=True), [summ, ms]


def two_part(cand, served_col: str, x: list, label: str):
    """Logit P(served) among LAUs with a station, as a separate part of a two-part model (STA-4: zero frequency)."""
    import pandas as pd
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    d = cand.dropna(subset=x + [served_col])
    # binomial GLM (= logit), fitted by IRLS with robust errors
    m = smf.glm(f"{served_col} ~ " + " + ".join(x), data=d, family=sm.families.Binomial()).fit(cov_type="HC1")
    ci = m.conf_int()
    coef = pd.DataFrame({"model": label, "term": m.params.index, "coef": m.params.values, "se": m.bse.values,
                         "ci_low": ci[0].values, "ci_high": ci[1].values, "p": m.pvalues.values})
    return coef, {"model": label, "n": int(m.nobs), "r2": float(1 - m.deviance / m.null_deviance),
                  "n_served": int(d[served_col].sum())}
