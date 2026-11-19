# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
#   kernelspec:
#     display_name: Python (traintranv2)
#     language: python
#     name: traintranv2
# ---

# %% [markdown]
# # 04c — Statistical models: distance decay, transfer penalty, frequency against distance and population
#
# The metric definitions §5–7, computed with full inference. Reviewer 1 (register STA-1 to STA-5, T17–T19, CF-12):
# the submitted manuscript reports correlations and regression coefficients that have **no computed source** in the
# legacy code (only `np.polyfit` chart labels), reads a regression intercept as the "average transfer overhead",
# and gives no uncertainty or diagnostics. Here every model reports n, coefficients with HC3 (heteroskedasticity-
# robust) standard errors and 95 % intervals, R², and diagnostics. Code: `traintranv2/nb04_models.py`.
#
# | § | model | output (`output/<city>/explore/`) |
# |---|---|---|
# | 1 | linear distance decay τ̄ = α + β r̄, per network, on route km and shortest-path km | `models_coef.csv`, `models_summary.csv` |
# | 2 | the transfer penalty as a model term (Δα), pooled and matched | same |
# | 3 | power-law forms (log–log) | same |
# | 3b | functional form: RESET of each form, the curvature probe, the primary form by a fixed rule | `specification_choice.csv` |
# | 4 | frequency against distance and population: correlations with intervals, pooled and within country | `correlations.csv` |
# | 5 | joint model log f = γ0 + γr log r + γP log P (+ country), country residuals | `country_residuals.csv` |
# | 5b | spatial autocorrelation of outcome and residuals; spatial lag / error check | `spatial_diagnostics.csv` |
# | 6 | zero-frequency LAUs: a two-part model | same as §1 |
# | 7 | audit: every coefficient the manuscript states, against the computed one | `claims_audit.csv` |
# | 8 | outputs, influential LAUs by name, and the written reading | `influential_observations.csv`, `README_models.md` |
#
# **Diagnostics on every fit:** Breusch–Pagan p (heteroskedasticity), RESET p (nonlinearity), residual skew,
# Cook's distance (influential LAUs, D > 4/n), Moran's I of the outcome and of the residuals on the k nearest LAUs
# (k = 3, 5, 8, 10; 999 permutations). **Distances** (decided in 04b): route km (operating) and shortest-path km
# (access); for frequency against distance the shortest path. Unit: LAU, inbound, headline runs.
#
# **Reviewer 1 asked us to "consider" seven things.** Each is reported **and** given a stated reading: a diagnostic
# that is computed but never read would hand the reviewer the evidence without the answer.
#
# | item | where it is answered |
# |---|---|
# | heteroskedasticity | HC3 on every OLS; Breusch–Pagan p per fit |
# | uncertainty | SE, 95 % interval and p per term; Fisher-z / bootstrap intervals on correlations |
# | zero / very low frequency | §6 two-part model |
# | country-level effects | §1–§5: country fixed effects **and** SEs clustered by country on every pooled foreign model; §4 within-country correlations |
# | nonlinearity | §3b: a primary form per model by a stated rule; §7: the audit failures read against it |
# | influential observations | §1 and §8: named, with leave-one-out changes and a top-5 refit |
# | spatial autocorrelation | §5b: outcome vs residual Moran's I across k; spatial lag / error check |

# %%
import os, sys

# Run from the project root so every relative path resolves the same from notebooks/ or the root.
_here = os.path.abspath('')
if os.path.basename(_here) == 'notebooks':
    os.chdir(os.path.dirname(_here))
sys.path.insert(0, os.getcwd())
print('Working directory:', os.getcwd())

# %%
import warnings
import numpy as np
import pandas as pd
import traintranv2  # noqa: F401  (PROJ data fix)
from traintranv2.config import default_config
from traintranv2 import nb02_connections as C
from traintranv2 import nb04_models as M
from traintranv2 import nb04_frame as FR  # noqa: F401  (registers the 04 schemas)
from traintranv2.nb01a_feeds import write_meta
from traintranv2.nb01b_stations import load_lau_subset

warnings.filterwarnings('ignore', category=RuntimeWarning)
cfg = default_config()
OUT = os.path.join(cfg.out_dir, 'explore')
lau = pd.read_csv(os.path.join(OUT, 'lau_table.csv'), dtype={'lau_gisco_id': str})
lau = lau[lau['headline'].astype(str).eq('True')].copy()
L = C.lau_with_city_units(load_lau_subset(cfg), cfg)          # the hub city and the other split city as one unit each
cent = L.set_index('GISCO_ID').geometry.to_crs('EPSG:3035').centroid
lau['x'] = lau['lau_gisco_id'].map(cent.x)
lau['y'] = lau['lau_gisco_id'].map(cent.y)
for c in ('time_mean_min', 'route_km_mean', 'rail_km_mean', 'f_per_day', 'population'):
    lau[f'log_{c}'] = np.log(lau[c].where(lau[c] > 0))
inb = lau[lau.direction == 'inbound']
NETS = ['domestic_direct', 'domestic_one_transfer', 'foreign_direct', 'foreign_one_transfer']
KS = M.MORAN_KS
coefs, summs, spatial, influential = [], [], [], []


def keep(coef, summ, extra, n_removed=0):
    """Collect one model: its coefficients, its summary row and (if computed) its outcome / residual Moran's I."""
    summ = dict(summ)
    summ.pop('_model', None)
    mk = summ.pop('moran_k', None)
    summ['n_removed'] = n_removed
    p = summ.get('moran_p', np.nan)
    summ['si_understated'] = bool(p < 0.05) if np.isfinite(p) else None
    coefs.append(coef.assign(**extra))
    summs.append({**summ, **extra})
    if mk:
        k5 = mk[5]
        spatial.append({**{k: extra[k] for k in ('network', 'family', 'distance', 'sample')}, 'n': summ['n'], 'k': 5,
                        'moran_i_y': k5[0], 'moran_p_y': k5[1], 'moran_i_resid': k5[2], 'moran_p_resid': k5[3],
                        'absorbed': k5[0] - k5[2],
                        'i_resid_min_k': min(v[2] for v in mk.values()), 'i_resid_max_k': max(v[2] for v in mk.values()),
                        'p_resid_max_k': max(v[3] for v in mk.values()),
                        'i_y_min_k': min(v[0] for v in mk.values()), 'i_y_max_k': max(v[0] for v in mk.values())})


def name_influential(m, slope, extra):
    t = M.influence_table(m, slope)
    influential.append(t.assign(**{k: extra[k] for k in ('network', 'family', 'distance', 'sample')}, n=int(m.nobs)))


def n_countries(d):
    return d['country'].nunique()


print({n: int((inb.network == n).sum()) for n in NETS})
print('countries per foreign network:', {n: sorted(inb.loc[inb.network == n, 'country'].unique()) for n in NETS if n.startswith('foreign')})

# %% [markdown]
# ## 1. Linear distance decay
#
# τ̄_ℓ = α + β r̄_ℓ per network (spec §5): α in minutes, β in minutes per km (60 / β the line-haul speed). On route km
# (the distance travelled) and shortest-path km (the separation). α is the predicted time at zero distance under the
# model — **not** a transfer penalty (§2 estimates that).
#
# Beside each headline fit:
# * **Country effects (foreign networks).** Fixed effects `C(country)` absorb each country's level; that variant tests
#   whether the slope holds within countries. Clustering the SEs by country tests whether the LAUs are independent;
#   it moves only the interval. Clustering is applied only where there are at least five countries
#   (`M.MIN_CLUSTERS`); with fewer, cluster-robust SEs are meaningless. Even five clusters is thin, so the clustered
#   interval is a check reported beside HC3, not a replacement for it. **The domestic networks are one country:** a
#   country term cannot be identified there, so they stay pooled.
# * **Influence.** LAUs with Cook's D > 4/n are named (§8, `influential_observations.csv`), with the leave-one-out
#   change in intercept and slope. A refit **without the five most influential LAUs** is the sensitivity the
#   reviewer's "influential large cities" actually asks for: population is only a proxy for influence. The refit
#   **without LAUs above 100,000 inhabitants** stays, with `n_removed` stating what it removed. Influential LAUs are
#   **never dropped from the headline models**: they are real municipalities with real service.

# %%
for net in NETS:
    d = inb[inb.network == net]
    for dist in ('route_km_mean', 'rail_km_mean'):
        ex = {'network': net, 'family': 'decay', 'distance': dist[:-8]}
        c, s, m = M.fit(d, 'time_mean_min', [dist], label=f'decay {dist[:-8]}', moran_ks=KS)
        keep(c, s, {**ex, 'sample': 'all'})
        name_influential(m, dist, {**ex, 'sample': 'all'})
        n_all = s['n']
        small = d[d.population < 100_000]
        if len(small) > 5 and len(small) < len(d):
            c, s, ms = M.fit(small, 'time_mean_min', [dist], label=f'decay {dist[:-8]} without cities', moran_ks=KS)
            keep(c, s, {**ex, 'sample': 'pop < 100k'}, n_removed=n_all - s['n'])
            name_influential(ms, dist, {**ex, 'sample': 'pop < 100k'})
        top5 = M.influence_table(m, dist, threshold=-1).head(5)['lau_gisco_id']
        c, s, mt = M.fit(d[~d.lau_gisco_id.isin(top5)], 'time_mean_min', [dist], label=f'decay {dist[:-8]} excl. top-5',
                         moran_ks=KS)
        keep(c, s, {**ex, 'sample': 'excl. top-5 influential'}, n_removed=n_all - s['n'])
        name_influential(mt, dist, {**ex, 'sample': 'excl. top-5 influential'})
        if net.startswith('foreign') and n_countries(d) > 1:
            c, s, mc = M.fit(d, 'time_mean_min', [dist, 'C(country)'], label=f'decay {dist[:-8]} + country', moran_ks=KS)
            keep(c, s, {**ex, 'sample': 'country effects'})
            name_influential(mc, dist, {**ex, 'sample': 'country effects'})
            if n_countries(d) >= M.MIN_CLUSTERS:
                c, s, _ = M.fit(d, 'time_mean_min', [dist], label=f'decay {dist[:-8]} clustered', groups='country', moran_ks=KS)
                keep(c, s, {**ex, 'sample': 'clustered'})
co, su = pd.concat(coefs), pd.DataFrame(summs)
dec = co[(co.family == 'decay') & co.term.isin(['route_km_mean', 'rail_km_mean'])]
dec = dec.merge(su[['network', 'family', 'distance', 'sample', 'n', 'n_removed', 'r2', 'reset_p', 'max_cooks', 'moran_i']],
                on=['network', 'family', 'distance', 'sample'])
dec['linear_form_ok'] = dec['reset_p'] >= M.FORM_ALPHA
display(dec[['network', 'distance', 'sample', 'n', 'n_removed', 'coef', 'ci_low', 'ci_high', 'r2', 'reset_p',
             'linear_form_ok', 'max_cooks', 'moran_i']].round(4))

# %%
# How much do country effects, clustering and the influential LAUs move the slope?  (foreign networks)
base = dec[dec['sample'] == 'all'].set_index(['network', 'distance'])
rows = []
for (net, dist), b in base.iterrows():
    for smp in ('country effects', 'clustered', 'excl. top-5 influential', 'pop < 100k'):
        r = dec[(dec.network == net) & (dec.distance == dist) & (dec['sample'] == smp)]
        if len(r):
            r = r.iloc[0]
            rows.append({'network': net, 'distance': dist, 'variant': smp, 'slope_all': b.coef,
                         'all_low': b.ci_low, 'all_high': b.ci_high, 'slope_variant': r.coef,
                         'var_low': r.ci_low, 'var_high': r.ci_high, 'n_removed': r.n_removed,
                         'moved_outside_all_ci': not (b.ci_low <= r.coef <= b.ci_high)})
moves = pd.DataFrame(rows)
display(moves.round(4))
print('Reading:')
for _, r in moves[moves.variant.isin(['country effects', 'clustered'])].iterrows():
    print(f"  {r.network} {r.distance}: {r.variant} -> slope {r.slope_variant:.3f} [{r.var_low:.3f}, {r.var_high:.3f}] "
          f"vs pooled {r.slope_all:.3f} [{r.all_low:.3f}, {r.all_high:.3f}]"
          + ('  ** moves outside the pooled interval **' if r.moved_outside_all_ci else ''))
dom = moves[(moves.variant == 'pop < 100k') & moves.network.str.startswith('domestic')]
for _, r in dom.iterrows():
    print(f"  {r.network} {r.distance}: the pop < 100k refit removes {int(r.n_removed)} LAU(s), "
          f"so it says nothing about large cities; the top-5 refit is the informative one")

# %%
# The observations that move a fit on their own (Cook's D > 1), by name
big = pd.concat(influential, ignore_index=True)
gt1 = big[big.above_1]
print(f'{len(big):,} LAU x model rows with Cook\'s D > 4/n; {len(gt1)} with D > 1')
display(gt1[['network', 'family', 'distance', 'sample', 'lau_gisco_id', 'lau_name', 'country', 'population', 'cooks_d',
             'actual', 'fitted', 'd_intercept', 'd_slope']].round(3))
for _, r in gt1.iterrows():
    print(f"  {r.network} {r.family} {r.distance}: {r.lau_name} ({r.lau_gisco_id}, {int(r.population):,} inh.) "
          f"D = {r.cooks_d:.2f}; without it the slope changes by {-r.d_slope:+.4f}, the intercept by {-r.d_intercept:+.2f}")

# %% [markdown]
# ## 2. The transfer penalty, as a model term
#
# Reviewer 1: compare matched direct and one-transfer journeys controlling for distance, or include transfer status in
# a pooled model. Both, within the domestic and the foreign networks:
# * **pooled** — direct and one-transfer LAUs together, `τ̄ = α + β r̄ + δ·transfer + γ·transfer·r̄`; δ = Δα, the
#   difference in intercepts (spec §5), γ the difference in slopes;
# * **matched** — LAUs with both a direct and a one-transfer journey: `Δτ = a + b·Δr`; a is the extra time of the
#   transfer at equal distance; the mean and median Δτ the raw difference.
#
# The **foreign** Δα is reported three ways: pooled as before, with **country fixed effects** (Δα net of each
# country's level), and with **SEs clustered by country**. If the point estimate moves once country is absorbed, that
# is a finding about the pooled value, not a correction to bury. Set beside the observed transfer waits (STA-2;
# 02b / 03b).

# %%
pen = []
for scope in ('domestic', 'foreign'):
    dd, oo = inb[inb.network == f'{scope}_direct'], inb[inb.network == f'{scope}_one_transfer']
    for dist in ('route_km_mean', 'rail_km_mean'):
        ex = {'network': scope, 'family': 'transfer', 'distance': dist[:-8]}
        c, ss = M.transfer_penalty(dd, oo, km=dist, moran_ks=KS)
        name_influential(ss[0]['_model'], dist, {**ex, 'sample': 'pooled'})
        for s_ in ss:
            keep(c[c.model == s_['model']], s_, {**ex, 'sample': s_['model']})
        tr = c[(c.model == 'pooled') & (c.term == 'transfer')].iloc[0]
        mi = c[(c.model == 'matched') & (c.term == 'Intercept')].iloc[0]
        pen.append({'scope': scope, 'distance': dist[:-8], 'variant': 'pooled', 'delta_alpha': tr.coef,
                    'da_low': tr.ci_low, 'da_high': tr.ci_high, 'matched_extra': mi.coef, 'me_low': mi.ci_low,
                    'me_high': mi.ci_high, 'matched_n': ss[1]['n'], 'matched_median_dtime': ss[1]['median_d_time'],
                    'median_wait_min': oo['wait_median_min'].median()})
        if scope == 'foreign':
            both = pd.concat([dd, oo])
            for variant in ('country effects', 'clustered'):
                if variant == 'clustered' and n_countries(both) < M.MIN_CLUSTERS:
                    continue
                c2, s2 = M.transfer_penalty(dd, oo, km=dist, variant=variant, moran_ks=KS)
                if variant == 'country effects':        # clustered = the pooled fit, same Cook's D: not repeated
                    name_influential(s2[0]['_model'], dist, {**ex, 'sample': variant})
                keep(c2, s2[0], {**ex, 'sample': variant})
                t2 = c2[c2.term == 'transfer'].iloc[0]
                pen.append({'scope': scope, 'distance': dist[:-8], 'variant': variant, 'delta_alpha': t2.coef,
                            'da_low': t2.ci_low, 'da_high': t2.ci_high})
pen = pd.DataFrame(pen)
display(pen.round(1))
fp = pen[(pen.scope == 'foreign') & (pen.distance == 'route')].set_index('variant')
print('Reading (foreign, route km):')
for v in fp.index:
    print(f"  {v:<15} Δα = {fp.at[v, 'delta_alpha']:.1f} min [{fp.at[v, 'da_low']:.1f}, {fp.at[v, 'da_high']:.1f}]")
if 'country effects' in fp.index:
    moved = not (fp.at['pooled', 'da_low'] <= fp.at['country effects', 'delta_alpha'] <= fp.at['pooled', 'da_high'])
    print('  the country-effects Δα', 'lies OUTSIDE' if moved else 'lies inside', 'the pooled interval')

# %% [markdown]
# ## 3. Power-law forms
#
# The log–log forms of the chart grids (spec §5): log τ̄ = a + b log r̄ (b: time elasticity of distance) and
# log f = c + d log r̄ (d: frequency decay exponent), with the same inference; for the foreign networks also with
# country effects and clustered SEs (`distance` tells the two apart: route = time, rail = frequency).

# %%
for net in NETS:
    d = inb[inb.network == net]
    for y, xv, dist, smp, lab in (('log_time_mean_min', 'log_route_km_mean', 'route', 'time', 'log time ~ log route km'),
                                  ('log_f_per_day', 'log_rail_km_mean', 'rail', 'frequency', 'log f ~ log rail km')):
        ex = {'network': net, 'family': 'power', 'distance': dist}
        c, s, m = M.fit(d, y, [xv], label=lab, moran_ks=KS)
        keep(c, s, {**ex, 'sample': smp})
        name_influential(m, xv, {**ex, 'sample': smp})
        if net.startswith('foreign') and n_countries(d) > 1:
            c, s, mc = M.fit(d, y, [xv, 'C(country)'], label=lab + ' + country', moran_ks=KS)
            keep(c, s, {**ex, 'sample': 'country effects'})
            name_influential(mc, xv, {**ex, 'sample': 'country effects'})
            if n_countries(d) >= M.MIN_CLUSTERS:
                c, s, _ = M.fit(d, y, [xv], label=lab + ' clustered', groups='country', moran_ks=KS)
                keep(c, s, {**ex, 'sample': 'clustered'})
co, su = pd.concat(coefs), pd.DataFrame(summs)
x = co[(co.family == 'power') & co.term.isin(['log_route_km_mean', 'log_rail_km_mean'])]
x = x.merge(su[su.family == 'power'][['network', 'distance', 'sample', 'n', 'r2', 'reset_p', 'resid_skew', 'moran_i']],
            on=['network', 'distance', 'sample'])
x['loglog_form_ok'] = x['reset_p'] >= M.FORM_ALPHA
display(x[['network', 'distance', 'sample', 'n', 'coef', 'ci_low', 'ci_high', 'r2', 'reset_p', 'loglog_form_ok',
           'resid_skew', 'moran_i']].round(4))

# %% [markdown]
# ### Residual skew
#
# Reviewer 1's premise was skew in the *variables* (population, frequency), which the log transforms address. What
# remains is skew in the *residuals* of some fits, listed below. **What follows from it:** the HC3 intervals rely on
# large-sample (asymptotic) theory and remain valid; intervals based on normal residuals would not be, and **no
# normal-theory interval is reported anywhere** in these outputs.

# %%
su = pd.DataFrame(summs)
sk = su[su.resid_skew.abs() > 2][['network', 'family', 'distance', 'sample', 'n', 'resid_skew']]
print(f'{len(sk)} fits with |residual skew| > 2:')
display(sk.round(2))

# %% [markdown]
# ## 3b. Functional form: answering RESET instead of only running it
#
# RESET is computed on every fit. Where it rejects linearity, reporting the linear slope anyway would use a
# diagnostic for appearance. So, per network × model × distance:
# * **Curvature probe:** km² is added to the linear form, and its coefficient, interval and sign are reported
#   (+ the gradient steepens with distance, − it flattens). It is a shape check, not a proposed model.
# * **Primary form by a fixed rule** (`M.choose_form`, RESET level 0.01), applied mechanically:
#   - linear passes → **linear** is primary;
#   - linear rejects and log–log passes → **log–log** is primary, and linear is reported as sensitivity;
#   - both reject → the linear coefficient is reported **with a caveat**: it is a descriptive average gradient, not
#     a structural parameter.

# %%
spec = []
for net in NETS:
    d = inb[inb.network == net]
    for dist in ('route_km_mean', 'rail_km_mean'):
        lin = su[(su.network == net) & (su.family == 'decay') & (su.distance == dist[:-8]) & (su['sample'] == 'all')].iloc[0]
        _, ls, _ = M.fit(d, 'log_time_mean_min', [f'log_{dist}'], xy_cols=())
        cv = M.curvature(d, 'time_mean_min', dist)
        form, rule = M.choose_form(lin.reset_p, ls['reset_p'])
        spec.append({'network': net, 'family': 'decay', 'distance': dist[:-8], 'n': int(lin.n), 'reset_linear': lin.reset_p,
                     'reset_loglog': ls['reset_p'], 'r2_linear': lin.r2, 'r2_loglog': ls['r2'], **{k: cv[k] for k in
                     ('quad_coef', 'quad_low', 'quad_high', 'quad_p')}, 'rule': rule, 'primary_form': form})
    # frequency against distance: linear f ~ rail km vs the log-log of §3
    _, fs, _ = M.fit(d, 'f_per_day', ['rail_km_mean'], xy_cols=())
    pw = su[(su.network == net) & (su.family == 'power') & (su['sample'] == 'frequency')].iloc[0]
    cv = M.curvature(d, 'f_per_day', 'rail_km_mean')
    form, rule = M.choose_form(fs['reset_p'], pw.reset_p)
    spec.append({'network': net, 'family': 'frequency', 'distance': 'rail', 'n': fs['n'], 'reset_linear': fs['reset_p'],
                 'reset_loglog': pw.reset_p, 'r2_linear': fs['r2'], 'r2_loglog': pw.r2,
                 **{k: cv[k] for k in ('quad_coef', 'quad_low', 'quad_high', 'quad_p')}, 'rule': rule, 'primary_form': form})
    # joint: f ~ rail km + population vs the log-log joint of §5 (fitted there; refitted here without Moran)
    _, js, _ = M.fit(d, 'f_per_day', ['rail_km_mean', 'population'], xy_cols=())
    _, jl, _ = M.fit(d, 'log_f_per_day', ['log_rail_km_mean', 'log_population'], xy_cols=())
    cv = M.curvature(d, 'f_per_day', 'rail_km_mean', extra=('population',))
    form, rule = M.choose_form(js['reset_p'], jl['reset_p'])
    spec.append({'network': net, 'family': 'joint', 'distance': 'rail', 'n': js['n'], 'reset_linear': js['reset_p'],
                 'reset_loglog': jl['reset_p'], 'r2_linear': js['r2'], 'r2_loglog': jl['r2'],
                 **{k: cv[k] for k in ('quad_coef', 'quad_low', 'quad_high', 'quad_p')}, 'rule': rule, 'primary_form': form})
for scope in ('domestic', 'foreign'):
    p_ = pd.concat([inb[inb.network == f'{scope}_direct'].assign(transfer=0),
                    inb[inb.network == f'{scope}_one_transfer'].assign(transfer=1)], ignore_index=True)
    for dist in ('route_km_mean', 'rail_km_mean'):
        lin = su[(su.network == scope) & (su.family == 'transfer') & (su.distance == dist[:-8]) & (su['sample'] == 'pooled')].iloc[0]
        cv = M.curvature(p_, 'time_mean_min', dist, extra=('transfer', f'transfer:{dist}'))
        form, rule = M.choose_form(lin.reset_p, np.nan)
        spec.append({'network': scope, 'family': 'transfer', 'distance': dist[:-8], 'n': int(lin.n),
                     'reset_linear': lin.reset_p, 'reset_loglog': np.nan, 'r2_linear': lin.r2, 'r2_loglog': np.nan,
                     **{k: cv[k] for k in ('quad_coef', 'quad_low', 'quad_high', 'quad_p')}, 'rule': rule, 'primary_form': form})
spec = pd.DataFrame(spec)
display(spec[['network', 'family', 'distance', 'n', 'reset_linear', 'reset_loglog', 'r2_linear', 'r2_loglog',
              'quad_coef', 'quad_low', 'quad_high', 'primary_form']].round(6))
print(spec.primary_form.value_counts().to_string())
print('\nModels whose linear coefficient is reported only with the caveat (both forms rejected):')
for _, r in spec[spec.primary_form == 'linear, caveat'].iterrows():
    shape = 'steepens' if r.quad_coef > 0 else 'flattens'
    sig = 'significant' if not (r.quad_low <= 0 <= r.quad_high) else 'not significant'
    print(f"  {r.network} {r.family} {r.distance}: linear RESET p = {r.reset_linear:.1e}"
          + (f", log-log p = {r.reset_loglog:.1e}" if np.isfinite(r.reset_loglog) else '')
          + f"; the gradient {shape} with distance (km² term {sig})")

# %% [markdown]
# ## 4. Frequency against distance and against population
#
# Pearson r on logs (Fisher-z interval) and Spearman ρ (bootstrap interval, 2,000 draws), per network (spec §6). For
# the foreign networks also **within each country**. A correlation pooled across five countries can show a sign that
# no single country shows (Simpson's paradox), so each within-country sign is compared with the pooled one.

# %%
cors = []
for net in NETS:
    d = inb[inb.network == net]
    for var in ('log_rail_km_mean', 'log_population'):
        w = var.replace('log_', '').replace('_mean', '')
        pooled = M.correlations(d['log_f_per_day'], d[var])
        rows_c = []
        if net.startswith('foreign'):
            for ctry, g in d.groupby('country'):
                r = M.correlations(g['log_f_per_day'], g[var])
                if 'pearson_r' in r:
                    rows_c.append({'network': net, 'with': w, 'country': ctry, **r,
                                   'sign_differs_from_pooled': bool(np.sign(r['pearson_r']) != np.sign(pooled['pearson_r']))})
            signs = [np.sign(r['pearson_r']) for r in rows_c]
            majority = np.sign(sum(signs)) if signs else 0
            flag = bool(majority != 0 and np.sign(pooled['pearson_r']) != majority)
        else:
            flag = None
        cors.append({'network': net, 'with': w, 'country': 'pooled', **pooled, 'sign_differs_from_pooled': flag})
        cors.extend(rows_c)
cors = pd.DataFrame(cors)
display(cors[['network', 'with', 'country', 'n', 'pearson_r', 'pearson_low', 'pearson_high', 'spearman_rho',
              'sign_differs_from_pooled']].round(3))
print('Pooled correlations whose sign differs from the majority of the within-country signs:')
print(cors[(cors.country == 'pooled') & (cors.sign_differs_from_pooled == True)][['network', 'with', 'pearson_r']].to_string(index=False) or '  none')

# %% [markdown]
# ## 5. Joint model and country residuals
#
# log f = γ0 + γr log r̄ + γP log P (spec §6): distance decay net of size (γr) and the demand elasticity (γP). For the
# foreign networks also with country effects, with SEs clustered by country, and the mean residual per country ε̄_c with
# e^ε̄_c as a multiplier on the expected frequency (spec §7).

# %%
resid = []
for net in NETS:
    d = inb[inb.network == net].copy()
    ex = {'network': net, 'family': 'joint', 'distance': 'rail'}
    c, s, m = M.fit(d, 'log_f_per_day', ['log_rail_km_mean', 'log_population'], label='joint', moran_ks=KS)
    keep(c, s, {**ex, 'sample': 'no country effects'})
    name_influential(m, 'log_rail_km_mean', {**ex, 'sample': 'no country effects'})
    dd = d.dropna(subset=['log_f_per_day', 'log_rail_km_mean', 'log_population']).assign(resid=m.resid)
    for ctry, g in dd.groupby('country'):
        resid.append({'network': net, 'country': ctry, 'n': len(g), 'mean_resid': g['resid'].mean(),
                      'multiplier': float(np.exp(g['resid'].mean()))})
    if net.startswith('foreign') and d['country'].nunique() > 1:
        c, s, mc = M.fit(d, 'log_f_per_day', ['log_rail_km_mean', 'log_population', 'C(country)'], label='joint + country',
                         moran_ks=KS)
        keep(c, s, {**ex, 'sample': 'country effects'})
        name_influential(mc, 'log_rail_km_mean', {**ex, 'sample': 'country effects'})
        if n_countries(d) >= M.MIN_CLUSTERS:
            c, s, _ = M.fit(d, 'log_f_per_day', ['log_rail_km_mean', 'log_population'], label='joint clustered',
                            groups='country', moran_ks=KS)
            keep(c, s, {**ex, 'sample': 'clustered'})
co, su = pd.concat(coefs), pd.DataFrame(summs)
x = co[(co.family == 'joint') & co.term.isin(['log_rail_km_mean', 'log_population'])]
display(x.pivot_table(index=['network', 'sample'], columns='term', values=['coef', 'ci_low', 'ci_high']).round(3))
display(su[su.family == 'joint'][['network', 'sample', 'n', 'r2', 'cov_type', 'bp_p', 'reset_p', 'moran_i', 'moran_p']].round(3))
resid = pd.DataFrame(resid)
display(resid.round(3))

# %% [markdown]
# ## 5b. Spatial autocorrelation: what the residual clustering means
#
# Moran's I of the residuals was already computed (k = 5, 999 permutations). On its own it can't distinguish two
# things:
# * **structure in the outcome**, which is expected: LAUs on the same line share the same trains, so service is a
#   corridor phenomenon;
# * **structure the model failed to absorb**, which is the problem: it makes the intervals too narrow.
#
# So Moran's I is computed for the **outcome** and the **residuals** on the same graph. `absorbed = I_y − I_resid` is
# what the covariates explained. All this is repeated for k = 3, 5, 8 and 10, because a result that holds across k
# can't be blamed on one arbitrary graph. p = 0.001 is the floor of 999 permutations.
#
# **A spatial model as a check, not a headline:** for the decay and joint specifications, spatial lag and spatial error
# models (maximum likelihood, the same 5-nearest-LAU graph). In the **error** model the covariate coefficients are
# directly comparable with OLS. In the **lag** model a coefficient is the direct effect only; the total effect is
# β / (1 − ρ), shown alongside.

# %%
sd = pd.DataFrame(spatial)
display(sd[['network', 'family', 'distance', 'sample', 'n', 'moran_i_y', 'moran_i_resid', 'absorbed', 'moran_p_resid',
            'i_resid_min_k', 'i_resid_max_k', 'p_resid_max_k']].round(3))
head = sd[sd['sample'].isin(['all', 'pooled', 'time', 'frequency', 'no country effects'])]
print(f"headline fits: {len(head)}; residual Moran p < 0.05 at k = 5 in {int((head.moran_p_resid < 0.05).sum())}; "
      f"significant at every k in {int((head.p_resid_max_k < 0.05).sum())}")
print(f"outcome I {head.moran_i_y.min():.2f}–{head.moran_i_y.max():.2f}; residual I {head.moran_i_resid.min():.2f}–"
      f"{head.moran_i_resid.max():.2f}; share of the outcome's I absorbed by the covariates: median "
      f"{(head.absorbed / head.moran_i_y).median():.0%}")

# %%
sp_rows = []
for net in NETS:
    d = inb[inb.network == net]
    for fam, y, xs, ols_sample, dist in (('decay', 'time_mean_min', ['route_km_mean'], 'all', 'route'),
                                         ('joint', 'log_f_per_day', ['log_rail_km_mean', 'log_population'], 'no country effects', 'rail')):
        c, sm = M.spatial_check(d, y, xs)
        if c.empty:
            continue
        for s_ in sm:
            ex = {'network': net, 'family': fam, 'distance': dist, 'sample': s_['model']}
            keep(c[c.model == s_['model']].drop(columns='model').assign(model=s_['model']),
                 {'model': s_['model'], 'n': s_['n'], 'r2': s_['r2'], 'cov_type': 'ML'}, ex)
        ols = co[(co.network == net) & (co.family == fam) & (co['sample'] == ols_sample) & (co.distance == dist)].set_index('term')
        sp_ = c.set_index(['model', 'term'])
        rho = sp_.loc[('spatial lag', 'rho'), 'coef']
        for t in xs:
            sp_rows.append({'network': net, 'family': fam, 'term': t,
                            'ols': ols.at[t, 'coef'], 'ols_low': ols.at[t, 'ci_low'], 'ols_high': ols.at[t, 'ci_high'],
                            'error_model': sp_.loc[('spatial error', t), 'coef'],
                            'err_low': sp_.loc[('spatial error', t), 'ci_low'], 'err_high': sp_.loc[('spatial error', t), 'ci_high'],
                            'lambda': sp_.loc[('spatial error', 'lambda'), 'coef'],
                            'lag_direct': sp_.loc[('spatial lag', t), 'coef'], 'rho': rho,
                            'lag_total': sp_.loc[('spatial lag', t), 'coef'] / (1 - rho)})
spc = pd.DataFrame(sp_rows)
spc['error_inside_ols_ci'] = (spc.error_model >= spc.ols_low) & (spc.error_model <= spc.ols_high)
spc['ols_inside_error_ci'] = (spc.ols >= spc.err_low) & (spc.ols <= spc.err_high)
display(spc.round(4))
print('Reading:')
for _, r in spc.iterrows():
    rel = (r.error_model - r.ols) / abs(r.ols) if r.ols else np.nan
    print(f"  {r.network} {r.family} {r.term}: OLS {r.ols:.4f} [{r.ols_low:.4f}, {r.ols_high:.4f}] -> spatial error "
          f"{r.error_model:.4f} [{r.err_low:.4f}, {r.err_high:.4f}] ({rel:+.0%}), λ = {r['lambda']:.2f}; "
          f"lag total {r.lag_total:.4f} (ρ = {r.rho:.2f})"
          + ('' if r.ols_inside_error_ci else '  ** OLS outside the spatial-error interval **'))

# %% [markdown]
# ## 6. LAUs without service: a two-part model
#
# The frequency models above see only served LAUs. Among the LAUs **with a station** (01b), the first part asks which
# are served at all: a logit on log shortest-path km of the LAU's nearest station to the hub and log population. The
# frequency models of §5 are the second part (STA-4: zero frequency handled, not dropped). A pseudo-R² near zero
# means that part explains almost nothing. It is flagged below, and never presented as if it explained something.

# %%
tags = pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str)
tags = C.tags_with_city_units(tags, cfg, L)
snap = pd.read_csv(os.path.join(cfg.out_dir, 'station_rail_snap.csv'), dtype={'station_key': str})
pop, _ = __import__('traintranv2.nb03_foreign', fromlist=['x']).lau_population(L)
st = tags[['station_key', 'feed_key', 'lau_gisco_id', 'nuts_rg_01_country_id']].merge(snap[['station_key', 'rail_km']], on='station_key')
hub_lau = C.hub_city_laus(cfg)
for scope, ctry in [('domestic', ['SK']), ('foreign', ['CZ', 'HU', 'AT', 'PL', 'UA'])]:
    s_ = st[st.nuts_rg_01_country_id.isin(ctry) & ~st.lau_gisco_id.isin(hub_lau)]
    cand = s_.groupby('lau_gisco_id')['rail_km'].min().rename('rail_km').reset_index()
    cand['log_rail_km'] = np.log(cand['rail_km'].where(cand['rail_km'] > 0))
    cand['log_population'] = np.log(cand['lau_gisco_id'].map(pop))
    for kind in ('direct', 'one_transfer'):
        served = set(inb.loc[inb.network == f'{scope}_{kind}', 'lau_gisco_id'])
        if kind == 'one_transfer':
            served |= set(inb.loc[inb.network == f'{scope}_direct', 'lau_gisco_id'])
        cand['served'] = cand['lau_gisco_id'].isin(served).astype(int)
        c, s = M.two_part(cand, 'served', ['log_rail_km', 'log_population'], f'served ({kind})')
        keep(c, {**s, 'cov_type': 'HC1'}, {'network': f'{scope}_{kind}', 'family': 'two_part', 'distance': 'rail',
                                           'sample': 'LAUs with a station'})
co, su = pd.concat(coefs), pd.DataFrame(summs)
display(co[co.family == 'two_part'][['network', 'term', 'coef', 'ci_low', 'ci_high', 'p']].round(3))
tp = su[su.family == 'two_part'][['network', 'n', 'n_served', 'r2']]
display(tp)
for _, r in tp[tp.r2 < 0.1].iterrows():
    print(f"  {r.network}: pseudo-R² = {r.r2:.3f}: distance and population explain almost nothing about which LAUs are "
          f"served; this part is reported as uninformative, not as a finding")

# %% [markdown]
# ## 7. Audit of the manuscript's coefficients (STA-5)
#
# Every coefficient the submitted manuscript states, against the value computed here **with the manuscript's own
# definition** (decay and correlations on shortest-path km, inbound, LAU level, the 2026 windows and feeds of this
# run) and its 95 % interval. `within_ci`: the stated value lies inside the computed interval.
#
# **`form_rejected`:** the specification behind each quantity, and whether RESET rejects it (p < 0.01).
# * decay slope, intercept and R² → the linear decay on shortest-path km;
# * log–log time → log time ~ log shortest-path km;
# * r(log f, log distance) → log f ~ log distance;
# * r(log f, log population) → log f ~ log population;
# * trip-weighted efficiency comes from no model, so it has none.
#
# The cross-tabulation tests the reading "the audit failures sit where the functional form is rejected". It is
# printed whichever way it comes out.

# %%
def get(net, family, sample, term, distance='rail', what='coef'):
    r = co[(co.network == net) & (co.family == family) & (co['sample'] == sample) & (co.term == term) & (co.distance == distance)]
    return r.iloc[0][what] if len(r) else np.nan


def basis_reset(net, qty):
    d = inb[inb.network == net]
    if qty.startswith('decay'):
        r = su[(su.network == net) & (su.family == 'decay') & (su['sample'] == 'all') & (su.distance == 'rail')]
        return 'time ~ rail km (linear)', float(r.reset_p.iloc[0])
    if qty.startswith('log-log time'):
        return 'log time ~ log rail km', M.fit(d.assign(lr=np.log(d.rail_km_mean)), 'log_time_mean_min', ['lr'], xy_cols=())[1]['reset_p']
    if 'log distance' in qty:
        return 'log f ~ log rail km', M.fit(d, 'log_f_per_day', ['log_rail_km_mean'], xy_cols=())[1]['reset_p']
    if 'log population' in qty:
        return 'log f ~ log population', M.fit(d, 'log_f_per_day', ['log_population'], xy_cols=())[1]['reset_p']
    return '', np.nan


audit = []
pooled_cors = cors[cors.country == 'pooled']
for net, qty, stated, where in M.AUDIT_CLAIMS:
    lo = hi = np.nan
    if qty.startswith('decay slope'):
        v, lo, hi = (get(net, 'decay', 'all', 'rail_km_mean', what=w) for w in ('coef', 'ci_low', 'ci_high'))
    elif qty.startswith('decay intercept'):
        v, lo, hi = (get(net, 'decay', 'all', 'Intercept', what=w) for w in ('coef', 'ci_low', 'ci_high'))
    elif qty == 'decay R2':
        v = su[(su.network == net) & (su.family == 'decay') & (su['sample'] == 'all') & (su.distance == 'rail')]['r2'].iloc[0]
    elif qty == 'log-log time slope':
        d = inb[inb.network == net]
        c, s, _ = M.fit(d.assign(lr=np.log(d.rail_km_mean)), 'log_time_mean_min', ['lr'])
        r = c[c.term == 'lr'].iloc[0]
        v, lo, hi = r.coef, r.ci_low, r.ci_high
    elif qty == 'log-log time R2':
        d = inb[inb.network == net]
        v = M.fit(d.assign(lr=np.log(d.rail_km_mean)), 'log_time_mean_min', ['lr'])[1]['r2']
    elif qty.startswith('trip-weighted efficiency'):
        d = inb[(inb.network == net) & (inb.rail_km_mean > 5)]
        v = np.average(d.time_mean_min / d.rail_km_mean, weights=d.f_per_day)
    elif qty.startswith('r(log f'):
        w = 'rail_km' if 'distance' in qty else 'population'
        r = pooled_cors[(pooled_cors.network == net) & (pooled_cors['with'] == w)].iloc[0]
        v, lo, hi = r.pearson_r, r.pearson_low, r.pearson_high
    basis, rp = basis_reset(net, qty)
    audit.append({'network': net, 'quantity': qty, 'stated': stated, 'computed': v, 'ci_low': lo, 'ci_high': hi,
                  'within_ci': bool(lo <= stated <= hi) if np.isfinite(lo) else None, 'where': where,
                  'form_basis': basis, 'form_reset_p': rp,
                  'form_rejected': bool(rp < M.FORM_ALPHA) if np.isfinite(rp) else None})
audit = pd.DataFrame(audit)
display(audit.round(4))
print('within_ci against form_rejected (quantities with an interval and a specification):')
ct = audit[audit.within_ci.notna() & audit.form_rejected.notna()]
display(pd.crosstab(ct.within_ci.map({True: 'within CI', False: 'outside CI'}),
                    ct.form_rejected.map({True: 'form rejected', False: 'form not rejected'})))
fails = audit[audit.within_ci == False]
print(f"{len(fails)} audit failures; their specification rejected in {int((fails.form_rejected == True).sum())}:")
for _, r in fails.iterrows():
    print(f"  {r.network} {r.quantity}: stated {r.stated}, computed {r.computed:.3f} [{r.ci_low:.3f}, {r.ci_high:.3f}]; "
          f"{r.form_basis} RESET p = {r.form_reset_p:.1e} -> {'rejected' if r.form_rejected else 'not rejected'}")

# %% [markdown]
# ## 8. Outputs and the written reading
#
# Every CSV carries its `.meta.md`. `README_models.md` states, in words and for this run, the four decisions:
# * fixed effects vs clustering;
# * the primary functional form;
# * the treatment of influential LAUs;
# * what the spatial result means for the intervals.
#
# The manuscript draws on that file.

# %%
co = pd.concat(coefs, ignore_index=True)[['network', 'family', 'distance', 'sample', 'model', 'term', 'coef', 'se',
                                          'ci_low', 'ci_high', 'p']]
su = pd.DataFrame(summs)
for c in ('adj_r2', 'bp_p', 'reset_p', 'resid_skew', 'n_influential', 'max_cooks', 'moran_i', 'moran_p', 'n_served',
          'mean_d_time', 'median_d_time', 'cov_type'):
    if c not in su:
        su[c] = np.nan
su = su[['network', 'family', 'distance', 'sample', 'model', 'n', 'r2', 'adj_r2', 'bp_p', 'reset_p', 'resid_skew',
         'n_influential', 'max_cooks', 'moran_i', 'moran_p', 'n_served', 'mean_d_time', 'median_d_time',
         'cov_type', 'n_removed', 'si_understated']]
infl = pd.concat(influential, ignore_index=True)[['network', 'family', 'distance', 'sample', 'n', 'lau_gisco_id',
                                                  'lau_name', 'country', 'population', 'cooks_d', 'fitted', 'actual',
                                                  'd_intercept', 'd_slope', 'above_1']]
cors = cors[['network', 'with', 'country', 'n', 'pearson_r', 'pearson_low', 'pearson_high', 'pearson_p', 'spearman_rho',
             'spearman_low', 'spearman_high', 'sign_differs_from_pooled']]
sd = pd.DataFrame(spatial)[['network', 'family', 'distance', 'sample', 'n', 'k', 'moran_i_y', 'moran_p_y', 'moran_i_resid',
                            'moran_p_resid', 'absorbed', 'i_resid_min_k', 'i_resid_max_k', 'p_resid_max_k', 'i_y_min_k', 'i_y_max_k']]
spec = spec[['network', 'family', 'distance', 'n', 'reset_linear', 'reset_loglog', 'r2_linear', 'r2_loglog', 'quad_coef',
             'quad_low', 'quad_high', 'quad_p', 'rule', 'primary_form']]
errors = 'HC3 (OLS); cluster-robust by country (sample "clustered", >= 5 countries); HC1 (logit); ML (spatial models)'
for name, key, frame in [('models_coef.csv', 'explore_models_coef', co), ('models_summary.csv', 'explore_models_summary', su),
                         ('correlations.csv', 'explore_correlations', cors), ('country_residuals.csv', 'explore_country_residuals', resid),
                         ('claims_audit.csv', 'explore_claims_audit', audit),
                         ('specification_choice.csv', 'explore_specification_choice', spec),
                         ('influential_observations.csv', 'explore_influential_observations', infl),
                         ('spatial_diagnostics.csv', 'explore_spatial_diagnostics', sd)]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Unit': 'LAU, inbound, headline runs', 'Errors': errors})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')

# %%
# README_models.md: the reading of this run, generated from the numbers above
fpen = pen[(pen.scope == 'foreign') & (pen.distance == 'route')].set_index('variant')
dpen = pen[(pen.scope == 'domestic') & (pen.distance == 'route') & (pen.variant == 'pooled')].iloc[0]
caveat = spec[spec.primary_form == 'linear, caveat']
loglog = spec[spec.primary_form == 'log-log']
xt = pd.crosstab(ct.within_ci, ct.form_rejected)
n_fail = len(fails)
n_fail_rej = int((fails.form_rejected == True).sum())
n_pass_rej = int(((audit.within_ci == True) & (audit.form_rejected == True)).sum())
lines = [
    f"# Model diagnostics — what each one concluded ({cfg.hub_label} run)", "",
    f"Generated by `notebooks/04c_models.ipynb`. Every number below comes from the CSVs in this folder.", "",
    "## The four decisions", "",
    "### 1. Country effects: fixed effects and clustering, and what each does",
    "- **Country fixed effects** (`C(country)`, sample `country effects`) move the **point estimate**: does the "
    "relationship hold once each country's level is absorbed?",
    f"- **Clustered SEs** (sample `clustered`) move only the **interval**. They are applied where a model pools at least "
    f"{M.MIN_CLUSTERS} countries; with that few clusters the cluster-robust asymptotics are thin, so they are a check "
    "beside HC3, not a replacement.",
    "- **Domestic models** are one country, so they stay pooled: a country term cannot be identified.",
    "- **Foreign transfer penalty Δα, route km:** "
    + "; ".join(f"{v} {fpen.at[v, 'delta_alpha']:.1f} min [{fpen.at[v, 'da_low']:.1f}, {fpen.at[v, 'da_high']:.1f}]" for v in fpen.index)
    + f". Domestic pooled: {dpen.delta_alpha:.1f} [{dpen.da_low:.1f}, {dpen.da_high:.1f}].",
    "- **Pooled correlations:** "
    + (f"{int((cors.country.eq('pooled') & cors.sign_differs_from_pooled.eq(True)).sum())} pooled correlation(s) "
       "have a sign that differs from most of the within-country ones (Simpson's paradox); see `correlations.csv`."),
    "",
    "### 2. Functional form: a primary form per model, by a fixed rule",
    "- **The rule** (RESET level 0.01): linear passes → linear; linear rejects and log–log passes → log–log; both "
    "reject → the linear coefficient is reported as a descriptive average gradient, with a caveat.",
    f"- **Result:** {len(spec) - len(caveat) - len(loglog)} of {len(spec)} models keep linear, {len(loglog)} switch to "
    f"log–log, and {len(caveat)} carry the caveat: "
    + ", ".join(f"{r.network} {r.family} {r.distance}" for _, r in caveat.iterrows()) + ".",
    *((["- **The audit** compares the submitted manuscript's Košice coefficients with this run; it applies to the "
        "Košice destination only, so it is not read here."]) if cfg.legacy_dir is None else [
    f"- **The audit, read against it:** {n_fail} of the stated coefficients fall outside their interval. The "
    f"specification behind {n_fail_rej} of them is rejected by RESET, while {n_pass_rej} of the claims within their "
    f"interval also rest on a rejected form.",
    "",
    "  | | form rejected | form not rejected |",
    "  |---|---|---|",
    f"  | outside the interval | {n_fail_rej} | {n_fail - n_fail_rej} |",
    f"  | within the interval | {n_pass_rej} | {int(((audit.within_ci == True) & (audit.form_rejected == False)).sum())} |",
    "",
    "  " + ("So the failures do **not** all sit where the form is rejected: the functional form explains only part of "
            "the audit failures." if n_fail_rej < n_fail else
            "So every failure sits where the form is rejected: the submitted slopes were read off a rejected form."),
    ]),
    "",
    "### 3. Influential observations: named, never dropped from the headline models",
    f"- **Named:** {len(infl):,} LAU × model rows with Cook's D > 4/n are listed in `influential_observations.csv`, "
    f"{int(infl.above_1.sum())} of them with D > 1: "
    + (", ".join(f"{r.lau_name} ({r.network} {r.family} {r.distance}, {r['sample']}, D = {r.cooks_d:.2f}, "
                 f"{int(r.population):,} inh.)" for _, r in infl[infl.above_1].iterrows()) or "none") + ".",
    (f"- **Large cities?** Of the {infl[infl.above_1].lau_gisco_id.nunique()} distinct LAUs with D > 1, "
     f"{infl[infl.above_1 & (infl.population >= 100_000)].lau_gisco_id.nunique()} have 100,000 inhabitants or more, so "
     "population is only a partial proxy for influence; the top-5 refit removes the influential LAUs themselves."
     if infl.above_1.any() else
     "- **Large cities?** No LAU has Cook's D > 1 in any model: no single municipality, large or small, moves a fit "
     "on its own."),
    "- **Sensitivity:** the refit without the five most influential LAUs is reported beside every decay fit "
    "(`excl. top-5 influential`, `n_removed`).",
    "- **The large-city refit (pop < 100k):** it removes "
    + ", ".join(f"{r.network} {r.distance}: {int(r.n_removed)}" for _, r in moves[moves.variant == 'pop < 100k'].iterrows())
    + " LAUs. Domestically that is a single LAU, so it establishes nothing there.",
    "",
    "### 4. Spatial autocorrelation: what it means for the intervals",
    f"- **Size:** residual Moran's I is significant (p < 0.05, k = 5) in {int((head.moran_p_resid < 0.05).sum())} of "
    f"{len(head)} headline fits, and significant at every k (3, 5, 8, 10) in {int((head.p_resid_max_k < 0.05).sum())}.",
    f"- **Outcome vs residuals:** the outcome's I is {head.moran_i_y.min():.2f}–{head.moran_i_y.max():.2f} and the "
    f"residuals' {head.moran_i_resid.min():.2f}–{head.moran_i_resid.max():.2f}; the covariates absorb a median "
    f"{(head.absorbed / head.moran_i_y).median():.0%} of the outcome's spatial structure. The remainder is corridor "
    "structure: LAUs on one line share the same trains.",
    "- **Spatial check (decay and joint models):** spatial-error coefficients against OLS: "
    + "; ".join(f"{r.network} {r.family} {r.term}: OLS {r.ols:.4f} → {r.error_model:.4f} (λ = {r['lambda']:.2f})"
                for _, r in spc.iterrows()) + ".",
    f"  The OLS coefficient lies inside the spatial-error interval in {int(spc.ols_inside_error_ci.sum())} of {len(spc)} cases.",
    "- **Reading:** the OLS coefficients are reported as the estimates. Their HC3 intervals are **too narrow** where "
    "`si_understated` is true in `models_summary.csv`, and should be read as lower bounds on the uncertainty. Where "
    "the spatial-error coefficient differs from OLS, both are reported.",
    "",
    "## Already answered before this run",
    "- heteroskedasticity: HC3 throughout, Breusch–Pagan p per fit;",
    "- uncertainty: SE, 95 % interval and p per term;",
    "- zero frequency: the two-part model, "
    + "; ".join(f"{r.network} pseudo-R² {r.r2:.3f}" for _, r in tp.iterrows())
    + " (a value near 0 means that part explains almost nothing).",
    f"- residual skew: {len(sk)} fits have |skew| > 2; the HC3 intervals stay valid and no normal-theory interval is reported.",
]
rp = os.path.join(OUT, 'README_models.md')
open(rp, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print(f'[wrote] {rp}')
print('\n'.join(lines))
