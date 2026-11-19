"""Tests for traintranv2.nb04_models on synthetic data with known parameters."""
import numpy as np
import pandas as pd

from traintranv2 import nb04_models as M


def _decay(n=300, a=20.0, b=0.8, seed=1):
    rng = np.random.default_rng(seed)
    km = rng.uniform(10, 500, n)
    return pd.DataFrame({"km": km, "t": a + b * km + rng.normal(0, 10, n),
                         "x": rng.uniform(0, 100, n), "y": rng.uniform(0, 100, n)})


def test_fit_recovers_intercept_and_slope_within_their_intervals():
    coef, s, _ = M.fit(_decay(), "t", ["km"], label="d")
    c = coef.set_index("term")
    assert c.loc["Intercept", "ci_low"] <= 20 <= c.loc["Intercept", "ci_high"]
    assert c.loc["km", "ci_low"] <= 0.8 <= c.loc["km", "ci_high"]
    assert s["n"] == 300 and s["r2"] > 0.9 and "bp_p" in s and "reset_p" in s and np.isfinite(s["moran_i"])


def test_reset_flags_nonlinearity():
    d = _decay()
    d["t"] = 0.002 * d["km"] ** 2 + np.random.default_rng(2).normal(0, 5, len(d))
    _, s, _ = M.fit(d, "t", ["km"])
    assert s["reset_p"] < 0.01


def test_transfer_penalty_is_the_intercept_difference_not_the_intercept():
    rng = np.random.default_rng(3)
    km = rng.uniform(20, 400, 200)
    direct = pd.DataFrame({"lau_gisco_id": [f"L{i}" for i in range(200)], "route_km_mean": km,
                           "time_mean_min": 15 + 0.8 * km + rng.normal(0, 5, 200)})
    one = direct.assign(route_km_mean=km * 1.1,
                        time_mean_min=15 + 60 + 0.8 * km * 1.1 + rng.normal(0, 5, 200))     # +60 min transfer
    coef, summ = M.transfer_penalty(direct, one, xy_cols=())
    c = coef[coef.model == "pooled"].set_index("term")
    assert c.loc["transfer", "ci_low"] <= 60 <= c.loc["transfer", "ci_high"]           # Δα = 60, not α = 75
    m = coef[coef.model == "matched"].set_index("term")
    assert m.loc["Intercept", "ci_low"] <= 60 <= m.loc["Intercept", "ci_high"]


def test_correlations_intervals_contain_the_estimates():
    rng = np.random.default_rng(4)
    a = rng.normal(size=500)
    r = M.correlations(a, 0.5 * a + rng.normal(size=500), n_boot=300)
    assert r["pearson_low"] < r["pearson_r"] < r["pearson_high"] and 0.3 < r["pearson_r"] < 0.6
    assert r["spearman_low"] < r["spearman_rho"] < r["spearman_high"]


def test_moran_detects_spatial_clustering():
    xs, ys = np.meshgrid(np.arange(15), np.arange(15))
    xy = np.c_[xs.ravel(), ys.ravel()]
    clustered = (xy[:, 0] > 7).astype(float) + np.random.default_rng(5).normal(0, 0.1, len(xy))
    i, p = M._moran(clustered, xy)
    assert i > 0.5 and p < 0.01


def test_clustered_errors_keep_the_estimate_and_change_the_interval():
    d = _decay(n=300).assign(country=np.repeat(list("ABCDE"), 60))
    rng = np.random.default_rng(7)
    d["t"] = d["t"] + d["country"].map({k: rng.normal(0, 40) for k in "ABCDE"})        # a shared shock per country
    c0, s0, _ = M.fit(d, "t", ["km"])
    c1, s1, _ = M.fit(d, "t", ["km"], groups="country")
    a, b = c0.set_index("term").loc["km"], c1.set_index("term").loc["km"]
    assert np.isclose(a.coef, b.coef) and not np.isclose(a.se, b.se)
    assert s0["cov_type"] == "HC3" and s1["cov_type"].startswith("cluster by country (5 clusters)")


def test_choose_form_rule():
    assert M.choose_form(0.20, 0.50)[0] == "linear"                  # linear passes: linear, whatever log-log does
    assert M.choose_form(1e-6, 0.30)[0] == "log-log"                 # linear rejects, log-log passes
    assert M.choose_form(1e-6, 1e-4)[0] == "linear, caveat"          # both reject
    assert M.choose_form(1e-6, np.nan)[0] == "linear, caveat"        # no log-log form


def test_choose_form_picks_loglog_on_a_power_law():
    rng = np.random.default_rng(8)
    d = pd.DataFrame({"km": rng.uniform(5, 800, 400)})
    d["t"] = 3 * d.km ** 0.6 * np.exp(rng.normal(0, 0.05, 400))      # a power law: curved in levels, straight in logs
    d["lt"], d["lkm"] = np.log(d.t), np.log(d.km)
    _, lin, _ = M.fit(d, "t", ["km"], xy_cols=())
    _, log, _ = M.fit(d, "lt", ["lkm"], xy_cols=())
    assert lin["reset_p"] < M.FORM_ALPHA <= log["reset_p"]
    assert M.choose_form(lin["reset_p"], log["reset_p"])[0] == "log-log"


def test_moran_pair_absorbed_structure():
    xs, ys = np.meshgrid(np.arange(15), np.arange(15))
    xy = np.c_[xs.ravel(), ys.ravel()].astype(float)
    rng = np.random.default_rng(9)
    x = (xy[:, 0] > 7).astype(float)                                 # a clustered covariate
    y = 3 * x + rng.normal(0, 0.3, len(x))                           # the outcome clusters only through x
    resid = y - 3 * x
    res = M.moran_pair(y, resid, xy, ks=(5,))
    i_y, _, i_r, _ = res[5]
    assert i_y > 0.5 and abs(i_r) < 0.15 and (i_y - i_r) > 0.4       # the covariate absorbed the structure
    i_old, p_old = M._moran(resid, xy)                               # same seed, same graph: the residual test is unchanged
    assert np.isclose(i_old, i_r) and np.isclose(p_old, res[5][3])


def test_influence_table_names_the_outlier_and_its_leave_one_out_change():
    d = _decay(n=100).assign(lau_gisco_id=[f"L{i}" for i in range(100)], lau_name=[f"n{i}" for i in range(100)],
                             country="SK", population=1000.0)
    d.loc[0, ["km", "t"]] = [2000.0, 50.0]                           # far away and far too fast: high leverage, off the line
    _, _, m = M.fit(d, "t", ["km"], xy_cols=())
    t = M.influence_table(m, "km")
    assert t.iloc[0]["lau_gisco_id"] == "L0" and t.iloc[0]["above_1"]
    _, _, m2 = M.fit(d.iloc[1:], "t", ["km"], xy_cols=())
    assert np.isclose(t.iloc[0]["d_slope"], m.params["km"] - m2.params["km"])


def test_two_part_logit_on_served():
    rng = np.random.default_rng(6)
    d = pd.DataFrame({"log_pop": rng.normal(8, 1, 400)})
    d["served"] = (rng.uniform(size=400) < 1 / (1 + np.exp(-(d.log_pop - 8) * 2))).astype(int)
    coef, s = M.two_part(d, "served", ["log_pop"], "t")
    assert coef.set_index("term").loc["log_pop", "coef"] > 0 and s["n_served"] == d.served.sum()
