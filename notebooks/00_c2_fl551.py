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
#     display_name: c2g
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 00_c2 — Flash Eurobarometer 551: the demand-side layer
#
# Prepares FL551 for the manuscript's market-size and transfer-behaviour arguments (revision register
# **T33**, **CON-1**, **VAL-7**, **VAL-8**, **REP-9**). **National level, five countries (SK, CZ, HU,
# PL, AT), four tiers:**
#
# | tier | question(s) | role |
# |---|---|---|
# | 1 | `q1_1` × `q2.2` | population → rail-market conversion, by age band |
# | 2 | `q12`, `q13`, `q14` | connecting-rail behaviour; the T1 → T2 narrowing for the one-transfer layer |
# | 3 | `q3` | planning factors: **metric validity, feeds no calculation** |
# | 4 | `q8`–`q10` | multimodal scope boundary: **bounds the claim, does not enter the cascade** |
#
# Out of scope by design: `q4`–`q7` (environmental importance, greener-travel incentives, booking
# channel, online-booking barriers).
#
# Input is the frame `eb_fl551_load.ipynb` derives from the archive file (NUTS resolution,
# multi-response dummies, the Q2 routing flag); this notebook does **not** reload the microdata.
#
# | Field | Value |
# |---|---|
# | Study | Flash Eurobarometer 551, *Multimodal Digital Mobility Service* |
# | Requested by | DG MOVE |
# | Archive | GESIS ZA8901 v1.0.0, released 2025-04-14 |
# | DOI | 10.4232/1.14506 |
# | Fieldwork | 28 August – 4 September 2024 |
# | Mode | Web-based self-administered (CAWI), Ipsos European Public Affairs |
# | Sampling | **Non-probability: quota** |
# | n | 25,803 (the 25,805 in the press material is wrong) |
# | Variables | 214 described in the codebook |
# | Weights | `w1` national post-stratification; `w87` for EU-27 |
#
# **Provenance, as methods text.** The demand-side data are Flash Eurobarometer 551, *Multimodal
# Digital Mobility Service*, requested by the European Commission's Directorate-General for Mobility
# and Transport (DG MOVE) and distributed by GESIS as study ZA8901, version 1.0.0, released
# 14 April 2025 (doi:10.4232/1.14506). It is a mobility survey, not a tourism survey. Fieldwork ran
# from 28 August to 4 September 2024 as a web-based self-administered survey (CAWI) by Ipsos
# European Public Affairs, on a **non-probability quota sample** of 25,803 respondents aged 15 and
# over in the 27 member states. Country estimates use the post-stratification weight `w1`; EU-27
# benchmarks use `w87`. Because the sample is non-probability, every interval reported here is
# **nominal**: the design-effect-adjusted binomial half-width the estimate would have under random
# sampling, computed on Kish's effective sample size, which is the form the Commission itself
# publishes. It is not a margin of error (VAL-8, point 1).
#
# Not revisited here: **national only** (FL551's NUTS2 cells were rejected on power, VAL-8 point 3),
# and **never pooled with FL499** (ZA7807; different year, mode and class of sample).

# %% [markdown]
# ## Setup

# %%
import os, sys

# Run from the project root so every relative path ('data/...', 'traintran/...') resolves the
# same whether the notebook is launched from notebooks/ or from the root.
_here = os.path.abspath('')
if os.path.basename(_here) == 'notebooks':
    os.chdir(os.path.dirname(_here))
sys.path.insert(0, os.getcwd())
print('Working directory:', os.getcwd())

# %%
from pathlib import Path

import numpy as np
import pandas as pd

from traintran import eurobarometer as eb

EB_DIR = Path('data/eb')
FL551_PARQUET = EB_DIR / 'fl551.parquet'                       # from eb_fl551_load.ipynb
FL551_CODEBOOK = EB_DIR / 'fl551_codebook.csv'
FL551_MULTI = EB_DIR / 'fl551_multiresponse_long.parquet'
FL551_CROSSWALK = EB_DIR / 'fl551_region_nuts_crosswalk.csv'

STUDY = 'ZA8901 v1.0.0'
DOI = '10.4232/1.14506'
SOURCE = f'Flash Eurobarometer 551 (Multimodal Digital Mobility Service, DG MOVE), GESIS {STUDY}, doi:{DOI}'
SAMPLING = 'non-probability quota'
INTERVAL_TYPE = 'nominal'

STUDY_COUNTRIES = ['SK', 'CZ', 'HU', 'PL', 'AT']   # Slovakia first
W_COUNTRY = 'w1'    # national post-stratification weight
W_EU27 = 'w87'      # EU-27 aggregate weight; w1 is never used for a cross-country aggregate

for p in (FL551_PARQUET, FL551_CODEBOOK, FL551_MULTI, FL551_CROSSWALK):
    if not p.exists():
        raise FileNotFoundError(f'{p} missing -- run eb_fl551_load.ipynb first')
print(SOURCE)
print(f'sampling: {SAMPLING}; intervals: {INTERVAL_TYPE}')

# %% [markdown]
# ## 1. Load
#
# `fl551.parquet` holds the **214 codebook variables** plus the columns `eb_fl551_load.ipynb`
# derives. It is the **post-crosswalk** version: it carries `region_code`, `region_r_code`,
# `region_nuts_id` and `nuts0_id` … `nuts3_id`. (The register's T33 note that these outputs are
# "pre-NUTS and stale" is out of date; asserted below.)

# %%
fl551 = pd.read_parquet(FL551_PARQUET)
codebook = pd.read_csv(FL551_CODEBOOK)
crosswalk = pd.read_csv(FL551_CROSSWALK)
multi_items = (pd.read_parquet(FL551_MULTI, columns=['block', 'variable', 'item'])
                 .drop_duplicates(['variable']).set_index('variable')['item'])

derived = [c for c in fl551.columns if c not in set(codebook['variable'])]
print(f'fl551: {fl551.shape[0]:,} rows x {fl551.shape[1]} columns '
      f'= {len(codebook)} codebook variables + {len(derived)} derived by the loader')
print('derived:', derived)
print(f'crosswalk: {len(crosswalk)} region rows')

# %% [markdown]
# ## 2. Integrity checks
#
# Each must fail loudly if the input is not what this notebook was written against.
#
# - **25,803 rows, 236 columns**; the 214 codebook variables all present (the extra 22 are
#   loader-derived, so 214 is not asserted on the parquet).
# - Post-crosswalk: the NUTS columns exist.
# - Five-country n: **SK 1013, CZ 1003, HU 1001, PL 1009, AT 1009**.
# - `w1` non-null on every retained row; `w87` non-null on all 25,803.
# - `nuts3_id` is **null for all five countries**: region is asked at NUTS2, so the hierarchy climbs
#   by truncation and never descends.
# - `d1` (exact age) bounded 15–104; `d1r2` has six categories. **`d4`, `d4r1`, `d4r2` are the age when
#   full-time education stopped, not the respondent's age**; nothing is asserted about them.

# %%
assert fl551.shape == (25_803, 236), fl551.shape
assert len(codebook) == 214 and set(codebook['variable']) <= set(fl551.columns)
NUTS_COLS = ['region_code', 'region_r_code', 'region_nuts_id', 'nuts0_id', 'nuts1_id', 'nuts2_id', 'nuts3_id']
assert set(NUTS_COLS) <= set(fl551.columns), 'parquet is pre-crosswalk -- re-run eb_fl551_load.ipynb'

EXPECTED_N = {'SK': 1013, 'CZ': 1003, 'HU': 1001, 'PL': 1009, 'AT': 1009}
n_by = fl551['isocntry'].value_counts()
assert {c: int(n_by.get(c, 0)) for c in STUDY_COUNTRIES} == EXPECTED_N, n_by.reindex(STUDY_COUNTRIES)

sub = fl551['isocntry'].isin(STUDY_COUNTRIES)
assert fl551.loc[sub, W_COUNTRY].notna().all(), 'w1 missing on a retained row'
assert fl551[W_EU27].notna().all(), 'w87 missing'
assert fl551.loc[sub, 'nuts3_id'].isna().all(), 'nuts3_id populated: the NUTS2 survey region cannot descend'
assert fl551['d1'].between(15, 104).all() and fl551['d1'].min() == 15 and fl551['d1'].max() == 104
assert sorted(fl551['d1r2'].dropna().unique()) == [1, 2, 3, 4, 5, 6]
# d4 / d4r1 / d4r2 = age when full-time education stopped -- deliberately no assertion.

print('all integrity checks passed')
print(f"  {fl551.shape[0]:,} rows x {fl551.shape[1]} columns; post-crosswalk NUTS columns present")
print('  five-country n:', EXPECTED_N, '; nuts3_id null for all five; d1 in [15, 104]; d1r2 six bands')

# %% [markdown]
# ## 3. Analysis frames
#
# - `fl5`: the five study countries, weighted within country by `w1`.
# - `eu27`: all 27 member states, weighted by `w87`, used only for benchmark columns.

# %%
fl5 = fl551.loc[sub].copy()
eu27 = fl551.copy()

frame_summary = pd.DataFrame({
    'n': fl5.groupby('isocntry').size(),
    'n_eff': fl5.groupby('isocntry').apply(lambda g: eb.effective_n(g, W_COUNTRY), include_groups=False),
}).reindex(STUDY_COUNTRIES)
frame_summary.loc['EU-27 (w87)'] = [len(eu27), eb.effective_n(eu27, W_EU27)]
print(frame_summary.round(1).to_string())


# %% [markdown]
# ## 4. Tier 1 — the population → rail-market conversion
#
# ### Variables and the routing gate
#
# - `q1_1`: how often the respondent travels regionally (50–300 km) and long-distance (300 km+)
#   **for leisure**: 1 monthly or more, 2 every 2–3 months, 3 once or twice a year, 4 once every few
#   years, 5 never, 998 don't know. (`q1_2` is the same for work.)
# - `q2.2`: **train**, within the set of modes used for those journeys in the past two years.
#
# **Routing:** `q2` is asked only of respondents who travel at least once every few years for leisure
# *or* work (`q1_1` or `q1_2` in 1–4); the archive codes the rest `9 = Inap.`, which the loader turns
# into NaN (`q2_base = 0`). A NaN is **not** "did not use the train"; it is "not asked".
#
# **The conversion is a joint on individuals**, never a product of marginals:
#
# `T1 = (q1_1 ∈ {1, 2, 3}) AND (q2.2 == 1)`
#
# The gate is reported so the reader sees where the base narrows. All intervals are **nominal**
# (non-probability quota sample).

# %%
def estimate(frame, col, weight=W_COUNTRY):
    p = eb.wshare(frame, col, weight)
    n_eff = eb.effective_n(frame, weight)
    hw = eb.ci95(p, n_eff)
    return {'pct': p, 'n': len(frame), 'n_eff': n_eff, 'hw_pp': hw, 'ci_low': p - hw, 'ci_high': p + hw}


def diff_ci(e1, e2):
    # e1 - e2 for independent cells, nominal 95 % interval and z.
    p1, n1, p2, n2 = e1['pct'] / 100, e1['n_eff'], e2['pct'] / 100, e2['n_eff']
    diff = 100 * (p1 - p2)
    se = 100 * np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return {'diff_pp': diff, 'ci_low': diff - 1.96 * se, 'ci_high': diff + 1.96 * se, 'z': diff / se,
            'significant': bool(abs(diff / se) >= 1.96)}


for f in (fl5, eu27):
    f['leisure_123'] = f['q1_1'].isin([1, 2, 3]).astype(int)
    f['asked_q2'] = f['q2.2'].notna().astype(int)
    f['T1'] = (f['q1_1'].isin([1, 2, 3]) & f['q2.2'].eq(1)).astype(int)
assert (fl5['T1'] == fl5['rail_traveller']).all(), "T1 differs from the loader's rail_traveller flag"

gate = pd.DataFrame({c: {
    'q1_1 in {1,2,3} %': eb.wshare(g, 'leisure_123'),
    'asked q2 %': eb.wshare(g, 'asked_q2'),
    'train among asked %': eb.wshare(g[g['asked_q2'] == 1].assign(t=lambda x: x['q2.2'].eq(1).astype(int)), 't'),
} for c, g in fl5.groupby('isocntry')}).T.reindex(STUDY_COUNTRIES)
print('The gate (w1, % of the 15+ sample unless stated):\n')
print(gate.round(1).to_string())

EXPECTED_GATE = {'SK': (87.3, 95.7, 56.8), 'CZ': (92.7, 97.5, 63.3), 'HU': (82.1, 94.2, 52.4),
                 'PL': (83.9, 96.5, 58.9), 'AT': (86.1, 93.5, 56.8)}
for c, exp in EXPECTED_GATE.items():
    assert np.allclose(gate.loc[c].values, exp, atol=0.1), (c, gate.loc[c].round(2).tolist())
print('\ngate shares match the expected values')

# %%
conv = {}
for c, g in fl5.groupby('isocntry'):
    nat, y, o = estimate(g, 'T1'), estimate(g[g['d1r2'] <= 5], 'T1'), estimate(g[g['d1r2'] == 6], 'T1')
    gr = diff_ci(o, y)
    conv[c] = {'r_national': nat['pct'], 'n': nat['n'], 'n_eff': nat['n_eff'], 'hw_pp': nat['hw_pp'],
               'ci_low': nat['ci_low'], 'ci_high': nat['ci_high'],
               'r_15_64': y['pct'], 'hw_15_64': y['hw_pp'], 'n_15_64': y['n'], 'n_eff_15_64': y['n_eff'],
               'r_65plus': o['pct'], 'hw_65plus': o['hw_pp'], 'n_65plus': o['n'], 'n_eff_65plus': o['n_eff'],
               'gradient_pp': gr['diff_pp'], 'gradient_ci_low': gr['ci_low'], 'gradient_ci_high': gr['ci_high'],
               'gradient_z': gr['z'], 'gradient_significant': gr['significant']}
conv = pd.DataFrame(conv).T.reindex(STUDY_COUNTRIES)
conv = conv.astype({k: float for k in conv.columns if k != 'gradient_significant'}).astype({'gradient_significant': bool})

print('T1 national (nominal 95 %):')
print(conv[['r_national', 'n', 'n_eff', 'hw_pp']].round(1).to_string())
print('\nT1 by band (nominal 95 %); gradient = 65+ minus 15-64:')
print(conv.assign(verdict=lambda x: np.where(x.gradient_significant, 'significant', 'not significant'))
          [['r_15_64', 'hw_15_64', 'n_eff_15_64', 'r_65plus', 'hw_65plus', 'n_eff_65plus',
            'gradient_pp', 'gradient_ci_low', 'gradient_ci_high', 'verdict']].round(1).to_string())

EXPECTED_T1 = {'SK': (50.3, 909), 'CZ': (59.4, 950), 'HU': (44.7, 905), 'PL': (50.8, 969), 'AT': (49.6, 931)}
EXPECTED_BANDS = {'SK': (50.7, 736, 48.8, 176, -1.9), 'CZ': (64.6, 710, 43.3, 241, -21.3),
                  'HU': (46.6, 686, 38.7, 219, -7.9), 'PL': (54.7, 756, 38.2, 214, -16.5),
                  'AT': (51.9, 697, 42.0, 238, -9.9)}
for c in STUDY_COUNTRIES:
    r = conv.loc[c]
    assert abs(r.r_national - EXPECTED_T1[c][0]) <= 0.1 and abs(r.n_eff - EXPECTED_T1[c][1]) <= 1, c
    y, ny, o, no, g = EXPECTED_BANDS[c]
    assert abs(r.r_15_64 - y) <= 0.1 and abs(r.n_eff_15_64 - ny) <= 1, (c, r.r_15_64, r.n_eff_15_64)
    assert abs(r.r_65plus - o) <= 0.1 and abs(r.n_eff_65plus - no) <= 1, (c, r.r_65plus, r.n_eff_65plus)
    assert abs(r.gradient_pp - g) <= 0.1, (c, r.gradient_pp)
assert conv['gradient_significant'].to_dict() == {'SK': False, 'CZ': True, 'HU': True, 'PL': True, 'AT': True}
print('\nT1 national and by band match the expected tables; SK gradient not significant, the other four significant')

# %%
# Six-band table: context for why two bands are coarse.
AGE6 = {1: '15-24', 2: '25-34', 3: '35-44', 4: '45-54', 5: '55-64', 6: '65+'}
age6 = pd.DataFrame({c: {AGE6[k]: eb.wshare(g[g['d1r2'] == k], 'T1') for k in AGE6}
                     for c, g in fl5.groupby('isocntry')}).T.reindex(STUDY_COUNTRIES)
age6_neff = pd.DataFrame({c: {AGE6[k]: eb.effective_n(g[g['d1r2'] == k]) for k in AGE6}
                          for c, g in fl5.groupby('isocntry')}).T.reindex(STUDY_COUNTRIES)
print('T1 by six age bands (%, nominal):\n')
print(age6.round(1).to_string())
EXPECTED_AGE6 = {'SK': [61.4, 52.2, 50.5, 49.6, 42.2, 48.8], 'CZ': [80.3, 68.9, 70.3, 56.8, 50.5, 43.3],
                 'HU': [63.7, 41.1, 43.9, 49.4, 36.9, 38.7], 'PL': [64.2, 58.3, 51.7, 54.8, 47.3, 38.2],
                 'AT': [55.8, 49.6, 52.9, 52.6, 49.5, 42.0]}
for c, exp in EXPECTED_AGE6.items():
    assert np.allclose(age6.loc[c].values, exp, atol=0.1), (c, age6.loc[c].round(2).tolist())
print('\nsix-band table matches')

# %% [markdown]
# ### Age bands and the municipal join
#
# The municipal population (`00_b1` … `00_b5`, attached to the LAU subset by
# `00_extract_base_data_eu` §2c) has three bands: 0–14, 15–64, 65+. `d1r2`'s six categories map onto
# them exactly: bands 1–5 are 15–64, band 6 is 65+, and 0–14 lies outside the survey frame. No
# interpolation.
#
# 1. **Denominator correction.** The survey samples ages 15 and over, so a rate applies to
#    `pop_15_64 + pop_65plus`, never to total population. With these bands that is exact per
#    municipality, replacing a national 13–16 % under-15 assumption (REP-9).
# 2. **Band-standardised conversion**, next to the flat one:
#
#    `market_m = pop_15_64_m · r_15_64[country] + pop_65plus_m · r_65plus[country]`
#
#    `market_flat_m = (pop_15_64_m + pop_65plus_m) · r_national[country]`
#
# Shown here over each country's **whole** municipal population, so the size of the standardisation
# effect is visible; the catchment-level branch is in §5.

# %%
import geopandas as gpd

LAU_SUBSET = Path('data/eu/ref-lau-2024-01m/subsetv4atua/LAU_RG_01M_2024_4326.geojson')
_cc = ', '.join(f"'{c}'" for c in STUDY_COUNTRIES)
lau_pop = gpd.read_file(LAU_SUBSET, where=f'CNTR_CODE IN ({_cc})', ignore_geometry=True)
need = ['POP_15_64_2025', 'POP_65PLUS_2025']
assert set(need) <= set(lau_pop.columns), 'LAU subset lacks POP_2025 bands -- run 00_extract_base_data_eu §2c'
assert lau_pop[need].notna().all().all()


def apply_conversion(pop, rates):
    # Flat and band-standardised market per municipality; rates in %, by CNTR_CODE.
    r = rates.reindex(pop['CNTR_CODE'])
    out = pop[['GISCO_ID', 'CNTR_CODE']].copy()
    out['pop_15plus'] = (pop['POP_15_64_2025'] + pop['POP_65PLUS_2025']).to_numpy()
    out['market_std'] = (pop['POP_15_64_2025'].to_numpy() * r['r_15_64'].to_numpy()
                         + pop['POP_65PLUS_2025'].to_numpy() * r['r_65plus'].to_numpy()) / 100
    out['market_flat'] = out['pop_15plus'] * r['r_national'].to_numpy() / 100
    return out


muni = apply_conversion(lau_pop, conv)
national_market = muni.groupby('CNTR_CODE')[['pop_15plus', 'market_flat', 'market_std']].sum().reindex(STUDY_COUNTRIES)
national_market['share_65plus_%'] = (100 * lau_pop.groupby('CNTR_CODE')['POP_65PLUS_2025'].sum()
                                     / national_market['pop_15plus'])
national_market['std / flat'] = national_market['market_std'] / national_market['market_flat']
print('National rail market, flat vs band-standardised (persons aged 15+):\n')
print(national_market.round({'pop_15plus': 0, 'market_flat': 0, 'market_std': 0,
                             'share_65plus_%': 1, 'std / flat': 4}).to_string())

dev = (national_market['std / flat'] - 1).abs()
assert (dev < 0.03).all(), dev
assert dev['SK'] < 0.005, dev['SK']
print(f"\nstandardisation moves the total by {100 * dev.min():.2f}-{100 * dev.max():.2f} %; Slovakia {100 * dev['SK']:.2f} %")

# %% [markdown]
# **Standardisation moves the total very little**: by 0.1–0.3 % of the flat total in the five
# countries, where the 65+ share of the 15+ population is 23–25 %, and by 0.06 % in Slovakia (the
# cell above asserts < 3 % everywhere and < 0.5 % for Slovakia). That is a **data-resolution finding, not a
# null result**. The steep part of the age gradient lies *inside* 15–64 (Czechia falls from 80.3 % at
# 15–24 to 50.5 % at 55–64 across the five working-age bands), where the municipal statistics give
# one band and the survey gives five. The binding constraint is the population data, not the survey.
#
# **Slovakia is the only one of the five with no detectable age gradient.** Its 65+ − 15–64
# difference (−1.9 pp, nominal 95 % interval −10.2 to +6.3) is not distinguishable from zero and is
# clearly shallower than Czechia's (−21.3) and Poland's (−16.5). The interval does not exclude a
# gradient of up to about −10 pp. Concessionary rail travel for pensioners is a candidate explanation,
# named here as a **hypothesis, not a conclusion**.
#
# **Uncertainty rule.** One country rate applies to every municipality, so the errors are perfectly
# correlated: the relative interval of a catchment total equals that of the rate,
# Var(Σ Nᵢ p̂) = (Σ Nᵢ)² · Var(p̂) (VAL-8, point 4). Age-standardising moves the point estimate; it
# does not narrow the interval.

# %%
# The uncertainty rule, shown: the relative half-width of a national total equals the rate's.
rel = pd.DataFrame({
    'market_flat': national_market['market_flat'],
    'half_width_persons': national_market['pop_15plus'] * conv['hw_pp'] / 100,
})
rel['relative_hw_total_%'] = 100 * rel['half_width_persons'] / rel['market_flat']
rel['relative_hw_rate_%'] = 100 * conv['hw_pp'] / conv['r_national']
assert np.allclose(rel['relative_hw_total_%'], rel['relative_hw_rate_%'])
print(rel.round(1).to_string())
print('\nrelative interval of the total == relative interval of the rate (nominal), in every country')

# %% [markdown]
# ## 5. Tier 2 — connecting-rail behaviour and the T1 → T2 narrowing
#
# The paper's unit of analysis, the time-feasible single-transfer itinerary, tested against
# reported behaviour. Nothing else in either survey touches it.
#
# ### Variables and their bases
#
# - `q12`: combined two or more rail legs run by **different operators** in the last two years:
#   1 every few months or more, different journeys · 2 every few months or more, same journey ·
#   3 once or twice a year · 4 less than once a year · **5 never, although I did travel by train** ·
#   **6 I did not travel by train in the last two years** · 998 don't know. The 5/6 split is kept.
# - `q13`: difficulty of the last such booking (1 very easy … 4 very difficult). **Base: `q12 ∈ {1,2,3,4}`.**
# - `q14.1`–`q14.10`: why never or rarely. **Base: `q12 ∈ {4,5}`**, stated wherever a Q14 figure appears.
#
# All intervals nominal (non-probability quota sample).

# %%
Q12_GE1, Q13_BASE, Q14_BASE = [1, 2, 3], [1, 2, 3, 4], [4, 5]

bases = pd.DataFrame({c: {
    'q13_base_n': int(g['q12'].isin(Q13_BASE).sum()),
    'q13_base_n_eff': eb.effective_n(g[g['q12'].isin(Q13_BASE)]),
    'q14_base_n': int(g['q12'].isin(Q14_BASE).sum()),
    'q14_base_n_eff': eb.effective_n(g[g['q12'].isin(Q14_BASE)]),
} for c, g in fl5.groupby('isocntry')}).T.reindex(STUDY_COUNTRIES)
bases['q14_hw_at_p50'] = [eb.ci95(50, n) for n in bases['q14_base_n_eff']]
print('Bases (nominal half-width at p = .5 for a Q14 share):\n')
print(bases.round(1).to_string())

EXPECTED_BASES = {'SK': (637, 574, 303, 271, 6.0), 'CZ': (665, 630, 233, 220, 6.6), 'HU': (505, 462, 315, 286, 5.8),
                  'PL': (608, 583, 271, 261, 6.1), 'AT': (569, 524, 328, 303, 5.6)}
for c, (n13, e13, n14, e14, hw) in EXPECTED_BASES.items():
    r = bases.loc[c]
    assert r.q13_base_n == n13 and abs(r.q13_base_n_eff - e13) <= 1, (c, r.q13_base_n, r.q13_base_n_eff)
    assert r.q14_base_n == n14 and abs(r.q14_base_n_eff - e14) <= 1, (c, r.q14_base_n, r.q14_base_n_eff)
    assert abs(r.q14_hw_at_p50 - hw) <= 0.1, (c, r.q14_hw_at_p50)
print('\nbase sizes match')

# %% [markdown]
# ### The narrowing, computed as a joint on individuals
#
# `T2 = T1 AND (q12 ∈ {1, 2, 3})`: a rail traveller (T1) who combined operators at least once or
# twice a year. "In T1, never connects" is the share of **all 15+ respondents** who are in T1 and
# answer `q12 ∈ {4, 5}`.

# %%
for f in (fl5, eu27):
    f['T2'] = (f['T1'].eq(1) & f['q12'].isin(Q12_GE1)).astype(int)
    f['T1_never_connects'] = (f['T1'].eq(1) & f['q12'].isin(Q14_BASE)).astype(int)
    f['q12_ge1'] = f['q12'].isin(Q12_GE1).astype(int)

Q12_CAT = {1: '>=1/yr', 2: '>=1/yr', 3: '>=1/yr', 4: '<1/yr', 5: 'never', 6: '"no train"', 998: 'DK'}
narrow, breakdown, marginal_check = {}, {}, {}
for c, g in fl5.groupby('isocntry'):
    t1, t2 = estimate(g, 'T1'), estimate(g, 'T2')
    narrow[c] = {'T1': t1['pct'], 'T2': t2['pct'], 'T2_hw': t2['hw_pp'], 'T2_ci_low': t2['ci_low'],
                 'T2_ci_high': t2['ci_high'], 'T2_n_eff': t2['n_eff'],
                 'T2_as_%_of_T1': 100 * t2['pct'] / t1['pct'],
                 'in_T1_never_connects_%': eb.wshare(g, 'T1_never_connects')}
    g1 = g[g['T1'] == 1]
    w = g1.groupby(g1['q12'].map(Q12_CAT))[W_COUNTRY].sum()
    breakdown[c] = (100 * w / g1[W_COUNTRY].sum()).to_dict()
    # Guard: the product of marginals is NOT the joint.
    marginal_check[c] = {'T2_joint': t2['pct'], 'T1_x_q12ge1_marginal': t1['pct'] * eb.wshare(g, 'q12_ge1') / 100}

narrow = pd.DataFrame(narrow).T.reindex(STUDY_COUNTRIES).astype(float)
breakdown = pd.DataFrame(breakdown).T.reindex(STUDY_COUNTRIES)[['>=1/yr', '<1/yr', 'never', '"no train"', 'DK']]
marginal_check = pd.DataFrame(marginal_check).T.reindex(STUDY_COUNTRIES)
print(narrow[['T1', 'T2', 'T2_hw', 'T2_as_%_of_T1', 'in_T1_never_connects_%']].round(1).to_string())
print('\nQ12 within the T1 group (row %):\n')
print(breakdown.round(1).to_string())

EXPECTED_NARROW = {'SK': (50.3, 29.9, 3.0, 59.4, 16.4), 'CZ': (59.4, 40.8, 3.1, 68.6, 14.3),
                   'HU': (44.7, 21.3, 2.7, 47.7, 17.9), 'PL': (50.8, 31.5, 2.9, 61.9, 13.8),
                   'AT': (49.6, 26.3, 2.8, 53.1, 20.3)}
EXPECTED_BREAKDOWN = {'SK': [59.4, 16.6, 16.0, 1.4, 6.5], 'CZ': [68.6, 14.2, 9.8, 2.7, 4.7],
                      'HU': [47.7, 12.9, 27.1, 4.7, 7.6], 'PL': [61.9, 17.0, 10.1, 2.6, 8.3],
                      'AT': [53.1, 18.1, 22.8, 2.1, 4.0]}
for c in STUDY_COUNTRIES:
    assert np.allclose(narrow.loc[c, ['T1', 'T2', 'T2_hw', 'T2_as_%_of_T1', 'in_T1_never_connects_%']].values,
                       EXPECTED_NARROW[c], atol=0.1), (c, narrow.loc[c].round(2).to_dict())
    assert np.allclose(breakdown.loc[c].values, EXPECTED_BREAKDOWN[c], atol=0.1), (c, breakdown.loc[c].round(2).tolist())
assert (narrow['T2'] < narrow['T1']).all()
assert (abs(marginal_check['T2_joint'] - marginal_check['T1_x_q12ge1_marginal']) > 0.5).all(), marginal_check
print('\nnarrowing and Q12 breakdown match; the joint differs from the product of marginals in every country:')
print(marginal_check.round(1).to_string())

# %% [markdown]
# ### One check before banding Tier 2
#
# Banding is safe in Tier 1 (65+ n_eff 176–241). It may not survive the extra conditioning of T2,
# so the 65+ cell *inside* T2 is measured first; below an effective n of 100, T2 is reported
# unbanded.

# %%
t2_65 = pd.Series({c: eb.effective_n(g[(g['T2'] == 1) & (g['d1r2'] == 6)]) for c, g in fl5.groupby('isocntry')}
                  ).reindex(STUDY_COUNTRIES)
print('n_eff of the 65+ cell inside T2:', t2_65.round(0).astype(int).to_dict())
T2_BANDED = bool((t2_65 >= 100).all())
print('-> T2 reported', 'by band' if T2_BANDED else
      'UNBANDED: the 65+ cell inside T2 is below n_eff 100 in every country, too thin for a band rate')

# %% [markdown]
# ### The branched cascade — the T2 discount applies to the single-transfer layer only
#
# A traveller reaching Košice **directly** never needs to connect, so the cascade branches instead of
# applying one blended factor:
#
# ```
# direct catchment       × T1                 -> addressable direct market
# one-transfer catchment × T1 × (T2 | T1)     -> addressable connecting market
# ```
#
# Catchments come from the pipeline run in `output/ke/`: `distance_decay_rail_foreign_direct.csv`
# (LAUs with a direct train to Košice) and `distance_decay_rail_foreign_onehop.csv` (reachable with one
# transfer); the one-transfer layer is one-hop **minus** direct. T1 is applied band-standardised to
# each LAU's 15+ population (§4). **Poland and Austria have no direct connection**, so their whole
# catchment sits behind a transfer and takes the full discount. **Czechia and Hungary** have direct
# lines, so only their one-transfer extension does. Ukrainian LAUs in the direct file are outside
# FL551 and are listed, not converted. The domestic (SK) catchment is grouped by station in the
# pipeline output, not by LAU, so it is not branched here.

# %%
OUT_KE = Path('output/ke')
_rd = lambda f: pd.read_csv(OUT_KE / f, encoding='utf-8-sig', usecols=['euc_lau_code', 'country'])
direct = _rd('distance_decay_rail_foreign_direct.csv').drop_duplicates('euc_lau_code')
onehop = _rd('distance_decay_rail_foreign_onehop.csv').drop_duplicates('euc_lau_code')
one_transfer = onehop[~onehop['euc_lau_code'].isin(direct['euc_lau_code'])]
outside = direct[~direct['country'].isin(STUDY_COUNTRIES)]
print('LAUs outside FL551 (not converted):', outside['euc_lau_code'].tolist())

layers = pd.concat([direct[direct['country'].isin(STUDY_COUNTRIES)].assign(layer='direct'),
                    one_transfer.assign(layer='one_transfer')], ignore_index=True)
layers = layers.merge(muni, left_on='euc_lau_code', right_on='GISCO_ID', how='left')
unmatched = layers[layers['GISCO_ID'].isna()]
print(f'catchment LAUs: {len(layers)}; without a 2025 population in the LAU subset: {len(unmatched)}',
      unmatched['euc_lau_code'].tolist())
layers = layers.dropna(subset=['GISCO_ID'])

t2_given_t1 = narrow['T2_as_%_of_T1'] / 100                      # (T2 | T1), by country
layers['discount'] = np.where(layers['layer'] == 'one_transfer', layers['country'].map(t2_given_t1), 1.0)
layers['addressable'] = layers['market_std'] * layers['discount']

cascade = (layers.groupby(['country', 'layer'])
           .agg(laus=('GISCO_ID', 'size'), pop_15plus=('pop_15plus', 'sum'),
                rail_market_T1=('market_std', 'sum'), addressable=('addressable', 'sum'))
           .reset_index())
cascade['factor_applied'] = np.where(cascade['layer'] == 'direct', 'T1',
                                     'T1 x (T2|T1) = ' + cascade['country'].map(t2_given_t1).round(3).astype(str))
print('\nBranched cascade (persons aged 15+; nominal intervals as the rates):\n')
print(cascade.round(0).to_string(index=False))

assert set(cascade.loc[cascade['layer'] == 'direct', 'country']) == {'CZ', 'HU'}, 'direct layer should be CZ, HU only'
assert not ((cascade['country'].isin(['PL', 'AT'])) & (cascade['layer'] == 'direct')).any()
assert (layers.loc[layers['layer'] == 'direct', 'discount'] == 1).all()

# %% [markdown]
# ### Two findings
#
# **The countries that most need a transfer are not the ones most habituated to transferring.**
# Hungary has a direct line and the lowest connecting share of its rail market (T2 as 47.7 % of T1);
# Czechia has a direct line and the highest (68.6 %); Austria has no direct connection and sits at
# 53.1 %.
#
# **The internal inconsistency, sized rather than hidden.** 1.4–4.7 % of the T1 group answer Q12 as
# "did not travel by train in the last two years" although they report train use in Q2. Both questions
# cover two years, so this is a **recall inconsistency**, reported as a measurement-quality
# observation.
#
# ### Q14 — what it can and cannot say
#
# **Q14's reasons are reasons for not combining rail operators in general, not reasons for not
# visiting Košice.** They corroborate that the constraints the pipeline computes are ones travellers
# hit; they do not measure how often any constraint binds for this destination. Base: `q12 ∈ {4, 5}`.
#
# | reason | pipeline counterpart |
# |---|---|
# | `q14.4` no suitable combination | feasibility |
# | `q14.6` journey too long | journey time |
# | `q14.5` stranded on a missed connection | transfer window and gateway dependence |
# | `q14.3` did not know where to search | information availability |
# | `q14.8` could not buy all tickets in one place | operator fragmentation |
# | `q14.1` not needed | a direct connection sufficed |

# %%
print('"no train" share inside T1 (%):', breakdown['"no train"'].round(1).to_dict())
assert breakdown['"no train"'].between(1.4 - 0.05, 4.7 + 0.05).all()

Q14 = [f'q14.{k}' for k in range(1, 11)]
PIPELINE_MAP = {'q14.4': 'feasibility', 'q14.6': 'journey time', 'q14.5': 'transfer window / gateway dependence',
                'q14.3': 'information availability', 'q14.8': 'operator fragmentation', 'q14.1': 'direct connection sufficed'}
rows = []
for c, g in fl5.groupby('isocntry'):
    b = g[g['q12'].isin(Q14_BASE)]
    for k in Q14:
        e = estimate(b, k)
        rows.append({'isocntry': c, 'reason_id': k, 'reason': multi_items[k], 'pipeline_counterpart': PIPELINE_MAP.get(k, ''),
                     'base': 'q12 in {4,5}', 'base_n': e['n'], 'base_n_eff': e['n_eff'],
                     'share_pct': e['pct'], 'ci_low': e['ci_low'], 'ci_high': e['ci_high']})
q14 = pd.DataFrame(rows)
print('\nQ14 reasons, % of the base q12 in {4,5} (nominal):\n')
print(q14.pivot(index='reason_id', columns='isocntry', values='share_pct')[STUDY_COUNTRIES]
         .reindex(Q14).assign(pipeline=lambda x: x.index.map(lambda k: PIPELINE_MAP.get(k, '')))
         .rename(index=lambda k: f'{k} {multi_items[k][:45]}').round(1).to_string())

# %% [markdown]
# ## 6. Tier 3 — planning factors as metric validity
#
# > **This tier feeds no calculation.** It is evidence about which computed quantities travellers
# > weigh, not an input to any of them; nothing here is multiplied by a population.
#
# `q3.1`–`q3.12`, *"Which are the most important factors for you when planning a regional or
# long-distance journey? You can select **up to three** factors"* (a tighter cap than FL499's four).
# Eleven substantive factors: 1 departure/arrival time · 2 total travel duration · 3 cost ·
# **4 number of connections** · 5 easy access to terminals incl. reduced mobility · 6 passenger rights
# on delays, cancellations or missed connections · 7 comfort · 8 environmental impact · **9 ease of
# finding travel options** · 10 ease of booking tickets · 11 other. (12 = don't know.)
#
# Raw shares are the headline; the comparison that survives normalisation is the within-country rank
# (the FL499 censoring argument, `00_c1_prep_fl499` §5b). Intervals nominal.

# %%
Q3 = [f'q3.{k}' for k in range(1, 12)]          # 1-11 substantive (11 = other); 12 = don't know

planning = pd.DataFrame({c: {k: eb.wshare(g, k) for k in Q3} for c, g in fl5.groupby('isocntry')})[STUDY_COUNTRIES]
planning['EU-27'] = [eb.wshare(eu27, k, W_EU27) for k in Q3]
planning.insert(0, 'factor', [multi_items[k] for k in Q3])
print('Planning factors, % naming (w1 by country, w87 for EU-27) -- METRIC VALIDITY, feeds no calculation\n')
print(planning.round(1).to_string())

EXPECTED_Q3 = {'q3.2': [47.7, 54.2, 46.2, 51.7, 46.0, 47.1], 'q3.4': [22.6, 18.6, 18.8, 21.1, 20.6, 13.9],
               'q3.9': [14.9, 22.2, 17.5, 17.8, 14.3, 16.5], 'q3.10': [10.7, 13.5, 11.4, 17.5, 12.9, 16.4],
               'q3.6': [5.9, 4.4, 6.0, 4.9, 8.2, 7.7]}
for k, exp in EXPECTED_Q3.items():
    got = planning.loc[k, STUDY_COUNTRIES + ['EU-27']].astype(float).values
    assert np.allclose(got, exp, atol=0.1), (k, got.round(2))
print('\nthe five checked rows match within 0.1 pp')


# %%
# The cap of three, programmatically; then mentions per respondent against it.
def q3_mentions(frame, weight):
    m = frame[Q3].sum(axis=1)
    w = frame[weight]
    dist = {f'{k}_mentions_%': 100 * w[m == k].sum() / w.sum() for k in range(0, 4)}
    return {'max_mentions': int(m.max()), 'n_above_3': int((m > 3).sum()),
            'mentions_per_respondent': float(np.average(m, weights=w)), **dist}


q3_cap = pd.DataFrame({c: q3_mentions(g, W_COUNTRY) for c, g in fl5.groupby('isocntry')}).T.reindex(STUDY_COUNTRIES)
q3_cap.loc['EU-27'] = q3_mentions(eu27, W_EU27)
assert (q3_cap['max_mentions'] == 3).all() and (q3_cap['n_above_3'] == 0).all(), q3_cap[['max_mentions', 'n_above_3']]
print('cap verified: at most 3 factors in every country and the EU-27, nobody above 3\n')
print(q3_cap.drop(columns=['max_mentions', 'n_above_3']).round(2).to_string())

ranks = planning[STUDY_COUNTRIES].astype(float).rank(ascending=False, method='min').astype(int)
ranks.index = [f'{k} {multi_items[k][:28]}' for k in ranks.index]
print('\nwithin-country rank (1 = most named):\n')
print(ranks.to_string())

# Duration is the top factor only in SK and CZ; cost (q3.3) leads in HU, PL, AT and the EU-27.
# What holds in all five is that duration is the top NON-COST factor (rank 1 or 2 overall).
non_cost = [k for k in Q3 if k != 'q3.3']
assert (planning.loc['q3.2', STUDY_COUNTRIES].astype(float)
        == planning.loc[non_cost, STUDY_COUNTRIES].astype(float).max()).all(), 'duration is not the top non-cost factor'
assert ranks.iloc[1].le(2).all()
top = planning.loc[Q3, STUDY_COUNTRIES + ['EU-27']].astype(float).idxmax()
print('\ntop factor overall:', {c: multi_items[k] for c, k in top.items()})
assert (planning.loc['q3.4', STUDY_COUNTRIES].astype(float) > planning.at['q3.4', 'EU-27']).all()

# %% [markdown]
# ### Three readings
#
# - **Total travel duration is the top non-cost factor in all five countries** (46.0–54.2 %, asserted
#   above): first overall in Slovakia and Czechia, second behind **cost** in Hungary, Poland and
#   Austria (cost 59.9–62.7 %, also first in the EU-27 at 60.7 %). That validates mean journey time
#   as the paper's primary *quality* measure. Fares are outside GTFS and outside this paper, which
#   is a limitation to state, not a reason to read duration as the single top criterion.
# - **Number of connections runs 18.6–22.6 %, above the EU-27's 13.9 % in all five**. The
#   direct-versus-one-transfer axis is therefore validated, and as a *regional* pattern rather than a
#   Slovak peculiarity.
# - **Connections (~20 %) against passenger rights for missed connections (4.4–8.2 %):** travellers
#   weigh *how many* connections far more than *what happens if one fails*. Gateway dependence is
#   therefore framed as a **planning friction, not a reliability risk**.
#
# Censoring caution, as for FL499: with at most three choices, countries that fill fewer slots show
# lower raw shares across the board. Raw shares are the headline because they have a population
# referent and match the Commission's tables. The ranking above is the comparison that survives
# normalisation.

# %% [markdown]
# ## 7. Tier 4 — the multimodal scope boundary
#
# > **Tier 4 bounds the claim and does not enter the cascade.** Nothing here is multiplied by a
# > population.
#
# - `q8_1`: how often the respondent **combined different collective modes** (e.g. flight + rail,
#   rail + coach); `q8_2`: **combined different operators within one mode**. Both on the Q12-style
#   frequency scale (1–2 every few months or more, 3 once or twice a year, 4 less than once a year,
#   5 never, 998 DK).
# - `q9_1` / `q9_2`: difficulty of booking each (1 very easy … 4 very difficult, 998 DK). Bases
#   `q8_1 ∈ {1,2,3,4}` and `q8_2 ∈ {1,2,3,4}`.
# - `q10.1`–`q10.8`: which mode pairs were combined; base `q8_1 ∈ {1,2,3,4}`. **`q10.4` = train and
#   bus/coach**, the planned coach extension.
#
# No expected values were pre-computed for this tier, so **bases come first**, every cell prints its
# base and n_eff beside it, and a cell with **n_eff < 100 is suppressed** with the reason stated.
# All intervals nominal.

# %%
MIN_N_EFF = 100
COMBINED = [1, 2, 3, 4]


def cell(frame, col, base_label):
    # A share on its base, suppressed (NaN + reason) below MIN_N_EFF.
    e = estimate(frame, col)
    ok = e['n_eff'] >= MIN_N_EFF
    return {'base': base_label, 'base_n': e['n'], 'base_n_eff': e['n_eff'],
            'share_pct': e['pct'] if ok else np.nan, 'ci_low': e['ci_low'] if ok else np.nan,
            'ci_high': e['ci_high'] if ok else np.nan,
            'suppressed': '' if ok else f'n_eff {e["n_eff"]:.0f} < {MIN_N_EFF}'}


for f in (fl5,):
    f['comb_modes'] = f['q8_1'].isin(COMBINED).astype(int)
    f['comb_operators'] = f['q8_2'].isin(COMBINED).astype(int)
    f['comb_any'] = (f['comb_modes'] | f['comb_operators']).astype(int)
    f['comb_modes_only'] = (f['comb_modes'] & ~f['comb_operators'].astype(bool)).astype(int)
    f['q9_1_difficult'] = f['q9_1'].isin([3, 4]).astype(int)
    f['q9_2_difficult'] = f['q9_2'].isin([3, 4]).astype(int)

base_rows = []
for c, g in fl5.groupby('isocntry'):
    for lab, mask in [('q8_1 in {1,2,3,4}', g['comb_modes'] == 1), ('q8_2 in {1,2,3,4}', g['comb_operators'] == 1),
                      ('q8_1 or q8_2 in {1,2,3,4}', g['comb_any'] == 1)]:
        b = g[mask]
        base_rows.append({'isocntry': c, 'base': lab, 'n': len(b), 'n_eff': eb.effective_n(b)})
tier4_bases = pd.DataFrame(base_rows).pivot(index='isocntry', columns='base', values=['n', 'n_eff']).reindex(STUDY_COUNTRIES)
print('Tier 4 bases (before any share):\n')
print(tier4_bases.round(0).astype(int).to_string())
print('\nall bases at n_eff >=', MIN_N_EFF, ':', bool((tier4_bases['n_eff'] >= MIN_N_EFF).all().all()))

# %%
rows = []
for c, g in fl5.groupby('isocntry'):
    allr = 'all 15+'
    rows += [{'isocntry': c, 'measure': 'combined modes (q8_1 1-4)', **cell(g, 'comb_modes', allr)},
             {'isocntry': c, 'measure': 'combined operators, one mode (q8_2 1-4)', **cell(g, 'comb_operators', allr)},
             {'isocntry': c, 'measure': 'combined anything (q8_1 or q8_2 1-4)', **cell(g, 'comb_any', allr)}]
    anyb = g[g['comb_any'] == 1]
    rows += [{'isocntry': c, 'measure': 'multimodal share of combiners (q8_1 1-4)', **cell(anyb, 'comb_modes', 'q8_1 or q8_2 in {1,2,3,4}')},
             {'isocntry': c, 'measure': 'modes only, never operators', **cell(anyb, 'comb_modes_only', 'q8_1 or q8_2 in {1,2,3,4}')}]
    rows += [{'isocntry': c, 'measure': 'q9_1 booking difficult, combining modes (3-4)',
              **cell(g[g['comb_modes'] == 1], 'q9_1_difficult', 'q8_1 in {1,2,3,4}')},
             {'isocntry': c, 'measure': 'q9_2 booking difficult, combining operators (3-4)',
              **cell(g[g['comb_operators'] == 1], 'q9_2_difficult', 'q8_2 in {1,2,3,4}')}]
    b10 = g[g['comb_modes'] == 1]
    for k in range(1, 9):
        rows.append({'isocntry': c, 'measure': f'q10.{k} {multi_items[f"q10.{k}"]}', **cell(b10, f'q10.{k}', 'q8_1 in {1,2,3,4}')})
multimodal = pd.DataFrame(rows)

show = multimodal.assign(v=lambda x: [f'{s:5.1f} [{a:.1f}, {b:.1f}]  base {bb}, n {n}, n_eff {ne:.0f}' if not sp
                                       else f'suppressed ({sp}); base {bb}, n_eff {ne:.0f}'
                                       for s, a, b, bb, n, ne, sp in zip(x.share_pct, x.ci_low, x.ci_high, x.base,
                                                                         x.base_n, x.base_n_eff, x.suppressed)])
for c in STUDY_COUNTRIES:
    print(f'--- {c}')
    print(show.loc[show.isocntry == c, ['measure', 'v']].to_string(index=False, header=False))
print('\nsuppressed cells:', int((multimodal['suppressed'] != '').sum()))

# %%
pv = lambda m: multimodal[multimodal.measure == m].set_index('isocntry')['share_pct'].reindex(STUDY_COUNTRIES)
summary4 = pd.DataFrame({
    'combined modes %': pv('combined modes (q8_1 1-4)'),
    'combined operators %': pv('combined operators, one mode (q8_2 1-4)'),
    'multimodal share of combiners %': pv('multimodal share of combiners (q8_1 1-4)'),
    'train + bus/coach (q10.4) % of mode-combiners': pv(f'q10.4 {multi_items["q10.4"]}'),
    'difficult: modes (q9_1) %': pv('q9_1 booking difficult, combining modes (3-4)'),
    'difficult: operators (q9_2) %': pv('q9_2 booking difficult, combining operators (3-4)'),
})
summary4['harder'] = np.where(summary4['difficult: modes (q9_1) %'] > summary4['difficult: operators (q9_2) %'],
                              'modes', 'operators')
print('Tier 4 headline (nominal; each figure on its own base, see above):\n')
print(summary4.round(1).to_string())

# %% [markdown]
# **Reading.** Tier 4 turns the rail-only scope into a number instead of a caveat. A rail-only
# connectivity measure understates real reachability by the share of combining that is multimodal
# (row *multimodal share of combiners*); `q10.4` sizes the planned rail + coach extension among
# those who combine modes. `q9_1` against `q9_2` says whether the harder booking problem is combining
# **modes** or combining **operators**. Both groups overlap (a respondent can answer both), so the two
# difficulty shares are compared descriptively, not tested as independent samples. None of this
# enters the cascade.
#
# What the numbers say, measured here: 71–79 % of the 15+ sample combined modes in the last two
# years; among everyone who combined anything, **93–97 % combined modes**, and 10–15 % combined
# modes but never operators. So combining is overwhelmingly multimodal, and a rail-only measure sees
# only part of how people actually reach a destination: that is the size of the boundary. Rail +
# coach (`q10.4`) is the most frequent mode pair among mode-combiners (47–65 %), which sizes the coach
# extension. **Neither booking problem is clearly harder:** 28–39 % find each difficult; operators
# are rated harder by 5–7 pp in Slovakia and Czechia, and the two are within 3 pp elsewhere (Hungary
# leans towards modes).

# %% [markdown]
# ## 7b. Two checks on the survey layer
#
# **(a) Is the rail-market rate an upper bound? (VAL-7)** FL551 is a non-probability quota panel. If it holds fewer
# people who never travel than a probability sample of the same countries, its rate overstates the rail market. The
# probability benchmark is FL499 (GESIS ZA7807, CATI / RDD, probability): `dx1`, "Before the COVID-19 pandemic, how
# frequently did you travel for leisure or work?" (code 4 = never). FL551: `q1_1`, leisure travel of 50 km or more
# (code 5 = never). The wordings differ, and in a known direction: `dx1` counts **any** trip, leisure **or work**, of
# any length, so its "never" should be the **smaller** share. If FL551's "never" is smaller still, the panel holds too
# few non-travellers, and the comparison is conservative. Intervals: nominal for FL551, design-warranted for FL499
# (both on the Kish effective n; "don't know" left out of both bases).
#
# **(b) T40: is FL551's regional composition right in Slovakia? (VAL-8 point 2)** The Slovak NUTS2 shares of the
# respondents, unweighted and `w1`-weighted, against the NUTS2 population aged 15+ aggregated from the LAU layer, as
# was done for Czechia and Austria (weighting moved their mean absolute deviation from 0.66 to 0.17 pp and from 0.38
# to 0.08 pp).

# %%
fl499 = pd.read_parquet(EB_DIR / 'fl499.parquet')
ub = []
for c in STUDY_COUNTRIES:
    a = fl5[(fl5.isocntry == c) & fl5['q1_1'].isin([1, 2, 3, 4, 5])].assign(never=lambda d: (d['q1_1'] == 5).astype(float))
    b = fl499[(fl499.isocntry == c) & fl499['dx1'].isin([1, 2, 3, 4])].assign(never=lambda d: (d['dx1'] == 4).astype(float))
    pa, pb = eb.wshare(a, 'never', W_COUNTRY), eb.wshare(b, 'never', 'w1')
    na, nb = eb.effective_n(a, W_COUNTRY), eb.effective_n(b, 'w1')
    ha, hb = eb.ci95(pa, na), eb.ci95(pb, nb)
    ub.append({'isocntry': c, 'fl551_never_pct': pa, 'fl551_hw_pp': ha, 'fl551_n_eff': na,
               'fl499_never_pct': pb, 'fl499_hw_pp': hb, 'fl499_n_eff': nb, 'difference_pp': pa - pb,
               'fl551_fewer_never': pa < pb, 'intervals_separate': (pa + ha) < (pb - hb),
               'fl551_question': 'q1_1 leisure, 50 km or more; 5 = never',
               'fl499_question': 'dx1 leisure or work, any distance, before COVID-19; 4 = never'})
upper_bound_out = pd.DataFrame(ub)
print(upper_bound_out[['isocntry', 'fl551_never_pct', 'fl551_hw_pp', 'fl499_never_pct', 'fl499_hw_pp', 'difference_pp',
                       'fl551_fewer_never', 'intervals_separate']].round(2).to_string(index=False))
ALL_FEWER = bool(upper_bound_out['fl551_fewer_never'].all())
print('the FL551 panel holds fewer never-travellers than the probability sample in all five countries:', ALL_FEWER,
      '-> the rail-market rate is labelled an upper bound' if ALL_FEWER else '-> the upper-bound label must be revised')

import geopandas as gpd
lau_pop = gpd.read_file(LAU_SUBSET, ignore_geometry=True)
lau_pop = lau_pop[lau_pop['CNTR_CODE'] == 'SK']
pop15 = (lau_pop['POP_15_64_2025'].fillna(0) + lau_pop['POP_65PLUS_2025'].fillna(0)).groupby(lau_pop['NUTS2_ID']).sum()
sk = fl5[(fl5.isocntry == 'SK') & fl5['nuts2_id'].notna()]
t40 = pd.DataFrame({'population_15plus_pct': 100 * pop15 / pop15.sum(),
                    'sample_unweighted_pct': 100 * sk['nuts2_id'].value_counts(normalize=True),
                    'sample_w1_pct': 100 * sk.groupby('nuts2_id')[W_COUNTRY].sum() / sk[W_COUNTRY].sum()})
t40['dev_unweighted_pp'] = t40['sample_unweighted_pct'] - t40['population_15plus_pct']
t40['dev_w1_pp'] = t40['sample_w1_pct'] - t40['population_15plus_pct']
print(t40.round(2).to_string())
print(f"mean |deviation|: unweighted {t40['dev_unweighted_pp'].abs().mean():.2f} pp -> w1 {t40['dev_w1_pp'].abs().mean():.2f} pp; "
      f"max {t40['dev_unweighted_pp'].abs().max():.2f} -> {t40['dev_w1_pp'].abs().max():.2f} pp  (CZ 0.66 -> 0.17, AT 0.38 -> 0.08)")
t40_out = t40.reset_index(names='nuts2_id')

# %% [markdown]
# ## 7c. Regional estimates with intervals (T38; VAL-8 point 3, CON-12)
#
# The paper quotes regional figures (Slovak NUTS2 rail-market rates; Észak-Magyarország; the regions where "number
# of connections" is named most often). Each gets its nominal 95 % interval and effective n here, and each country is
# tested for whether its regions differ at all, before any regional reading is written.
#
# * **Unit:** NUTS2 in SK, CZ, HU, AT. **Poland is collapsed to its seven NUTS1 macroregions** (`nuts1_id`): at
#   NUTS2 its smallest cell has an effective n of 16 and a half-width of ±24 pp (VAL-8).
# * **Quantities:** T1, the rail-market rate (§4), and `q3.4`, "number of connections" among the planning factors
#   (§6).
# * **Flags:** a cell is `underpowered` when its half-width exceeds 10 pp.
# * **Tests per country:**
#   * a Wald test that all regions share one rate (χ² on the effective n, df = regions − 1);
#   * top against bottom region (`diff_ci`), with a Bonferroni critical z over all region pairs, because the two are
#     chosen after looking. `regional_contrast_supported` requires both tests. An ordering is never written as a
#     ranking.
#
# Intervals are nominal (quota sample) and, as everywhere here, a lower bound on the real uncertainty
# (`eb.ci95`).

# %%
from scipy import stats

REGION_LEVEL = {c: 'nuts2_id' for c in STUDY_COUNTRIES} | {'PL': 'nuts1_id'}
UNDERPOWERED_HW = 10.0
REG_VARS = {'T1': 'rail market (T1)', 'q3.4': multi_items['q3.4']}
nuts_names = gpd.read_file('data/eu/ref-nuts-2024-01m/subsetv4atua/NUTS_RG_01M_2024_4326_LEVL_2.geojson',
                           ignore_geometry=True)[['NUTS_ID', 'NAME_LATN']]
nuts1_names = gpd.read_file('data/eu/ref-nuts-2024-01m/subsetv4atua/NUTS_RG_01M_2024_4326_LEVL_1.geojson',
                            ignore_geometry=True)[['NUTS_ID', 'NAME_LATN']]
region_name = pd.concat([nuts_names, nuts1_names]).drop_duplicates('NUTS_ID').set_index('NUTS_ID')['NAME_LATN']

reg_rows, test_rows = [], []
for c in STUDY_COUNTRIES:
    lvl = REGION_LEVEL[c]
    g_c = fl5[(fl5.isocntry == c) & fl5[lvl].notna()]
    for var, label in REG_VARS.items():
        nat = estimate(fl5[fl5.isocntry == c], var)
        cells = {r: estimate(g, var) for r, g in g_c.groupby(lvl)}
        for r, e in cells.items():
            reg_rows.append({'isocntry': c, 'level': 'NUTS1 macroregion' if lvl == 'nuts1_id' else 'NUTS2',
                             'region_id': r, 'region_name': region_name.get(r, ''), 'variable': var, 'label': label,
                             'pct': e['pct'], 'n': e['n'], 'n_eff': e['n_eff'], 'hw_pp': e['hw_pp'],
                             'ci_low': e['ci_low'], 'ci_high': e['ci_high'], 'national_pct': nat['pct'],
                             'diff_from_national_pp': e['pct'] - nat['pct'],
                             'underpowered': bool(e['hw_pp'] > UNDERPOWERED_HW)})
        p = np.array([e['pct'] / 100 for e in cells.values()])
        n = np.array([e['n_eff'] for e in cells.values()])
        pbar = (p * n).sum() / n.sum()
        chi2 = float((n * (p - pbar) ** 2).sum() / (pbar * (1 - pbar)))
        top = max(cells, key=lambda r: cells[r]['pct'])
        bot = min(cells, key=lambda r: cells[r]['pct'])
        tb = diff_ci(cells[top], cells[bot])
        # the top and bottom of k regions are picked after looking: Bonferroni over the k(k-1)/2 pairs
        m_pairs = len(cells) * (len(cells) - 1) / 2
        z_adj = float(stats.norm.ppf(1 - 0.025 / m_pairs))
        p_wald = float(stats.chi2.sf(chi2, len(cells) - 1))
        test_rows.append({'isocntry': c, 'variable': var, 'label': label, 'n_regions': len(cells),
                          'wald_chi2': chi2, 'df': len(cells) - 1, 'p_equal_rates': p_wald,
                          'top_region': top, 'top_pct': cells[top]['pct'], 'bottom_region': bot,
                          'bottom_pct': cells[bot]['pct'], 'top_minus_bottom_pp': tb['diff_pp'],
                          'tb_ci_low': tb['ci_low'], 'tb_ci_high': tb['ci_high'], 'tb_z': tb['z'],
                          'tb_z_bonferroni': z_adj,
                          # supported only if the regions differ at all AND the pair survives the correction
                          'regional_contrast_supported': bool(p_wald < 0.05 and abs(tb['z']) >= z_adj),
                          'n_underpowered': int(sum(cells[r]['hw_pp'] > UNDERPOWERED_HW for r in cells))})
regional_out = pd.DataFrame(reg_rows)
regional_tests_out = pd.DataFrame(test_rows)

# the Slovak regional table published in the register (VAL-8) and its SK04 - SK02 test
sk_t1 = regional_out[(regional_out.isocntry == 'SK') & (regional_out.variable == 'T1')].set_index('region_id')
for r, (pct, neff, hw) in {'SK01': (51.1, 122, 8.9), 'SK02': (45.0, 285, 5.8), 'SK03': (53.5, 237, 6.4),
                           'SK04': (53.1, 261, 6.1)}.items():
    assert abs(sk_t1.at[r, 'pct'] - pct) <= 0.1 and abs(sk_t1.at[r, 'n_eff'] - neff) <= 1 and abs(sk_t1.at[r, 'hw_pp'] - hw) <= 0.1, r
sk42 = diff_ci(estimate(fl5[(fl5.isocntry == 'SK') & (fl5.nuts2_id == 'SK04')], 'T1'),
               estimate(fl5[(fl5.isocntry == 'SK') & (fl5.nuts2_id == 'SK02')], 'T1'))
assert abs(sk42['diff_pp'] - 8.0) <= 0.1 and not sk42['significant']
print(f"SK04 - SK02 = {sk42['diff_pp']:.1f} pp [{sk42['ci_low']:.1f}, {sk42['ci_high']:.1f}], z = {sk42['z']:.2f}: not significant (as registered)")

print('\nRegional cells (nominal 95 %):')
print(regional_out.assign(cell=lambda d: d.pct.round(1).astype(str) + ' ± ' + d.hw_pp.round(1).astype(str))
      .pivot_table(index=['isocntry', 'region_id', 'region_name'], columns='variable', values='cell', aggfunc='first')
      .to_string())
print('\nDo the regions differ? (Wald test of one common rate; top vs bottom region)')
print(regional_tests_out[['isocntry', 'variable', 'n_regions', 'p_equal_rates', 'top_region', 'top_pct', 'bottom_region',
                          'bottom_pct', 'top_minus_bottom_pp', 'tb_z', 'tb_z_bonferroni', 'regional_contrast_supported',
                          'n_underpowered']].round(3).to_string(index=False))
print('\nregional contrast supported anywhere:', bool(regional_tests_out['regional_contrast_supported'].any()))
hu31 = regional_out[(regional_out.region_id == 'HU31') & (regional_out.variable == 'T1')].iloc[0]
print(f"Észak-Magyarország T1 = {hu31.pct:.1f} ± {hu31.hw_pp:.1f} (national {hu31.national_pct:.1f}): "
      f"{'inside' if hu31.ci_low <= hu31.national_pct <= hu31.ci_high else 'outside'} the interval")

# %% [markdown]
# ### What the regional figures can carry
#
# Read the table above before writing any regional sentence:
#
# * A country whose `p_equal_rates` ≥ 0.05 has **no detectable regional difference**. Its regional figures are
#   reported only as point estimates with intervals, never compared with each other.
# * Where the regions do differ, only the **top–bottom pair** can be a contrast, and only when
#   `regional_contrast_supported`. An ordering of the regions in between is not supported, so it is **never written
#   as a ranking**. The register's Q3 ordering (SK03, Podkarpackie, Észak-Magyarország and SK04 at the top) falls
#   under this rule. Podkarpackie is now inside the PL8 macroregion.
# * **Result (this run): no country shows a regional difference in either quantity.** All `p_equal_rates` are
#   ≥ 0.05. The uncorrected top–bottom gaps (e.g. AT T1 33 pp, CZ 20 pp) are what picking extremes out of 7–9
#   cells produces, and none survives both tests. The paper therefore uses **national rates only**. Regional cells
#   go to a supplementary table with their intervals.
# * `underpowered` cells (half-width over 10 pp) are not quoted in the text at all.

# %% [markdown]
# ## 8. Exports
#
# Written to `data/eb/` with `traintran.output._write`; every file carries `source` (ZA8901 v1.0.0 +
# DOI), `sampling = "non-probability quota"`, `interval_type = "nominal"` and `generated_at`.
#
# | file | content |
# |---|---|
# | `fl551_conversion_national.csv` | per country: `r_national`, `r_15_64`, `r_65plus` with n, n_eff and intervals per cell, and the 65+ − 15–64 gradient. **The file the catchment pipeline joins to.** |
# | `fl551_conversion_age6.csv` | T1 by the six survey age bands: context for the resolution limit |
# | `fl551_connecting_national.csv` | T1, T2, T2/T1, the within-T1 Q12 breakdown, the q13/q14 bases, and the joint vs product-of-marginals pair |
# | `fl551_q14_reasons.csv` | the ten Q14 reasons by country, base `q12 in {4,5}` named in a column |
# | `fl551_planning_factors.csv` | the eleven Q3 factors × five countries + EU-27, `mentions_per_respondent`, `role = "metric_validity"` |
# | `fl551_multimodal.csv` | Tier 4, each cell with its base, n_eff and suppression flag |
# | `fl551_upper_bound_check.csv` | §7b (a): never-travellers in FL551 (quota) against FL499 `dx1` (probability), per country, with intervals |
# | `fl551_sk_regional_weighting.csv` | §7b (b), T40: Slovak NUTS2 shares of the sample (unweighted, `w1`) against the population 15+ |
# | `fl551_regional.csv` | §7c, T38: T1 and `q3.4` per NUTS2 (PL: NUTS1 macroregion) with n, n_eff, interval, difference from national, `underpowered` |
# | `fl551_regional_tests.csv` | §7c: per country and variable, the Wald test of one common rate and the top − bottom contrast |

# %%
import datetime as dt
from traintran.output import _write

EXPORT_META = {'source': SOURCE, 'sampling': SAMPLING, 'interval_type': INTERVAL_TYPE,
               'generated_at': dt.datetime.now().isoformat(timespec='seconds')}

band_ci = {}
for c, g in fl5.groupby('isocntry'):
    y, o = estimate(g[g['d1r2'] <= 5], 'T1'), estimate(g[g['d1r2'] == 6], 'T1')
    band_ci[c] = {'ci_low_15_64': y['ci_low'], 'ci_high_15_64': y['ci_high'],
                  'ci_low_65plus': o['ci_low'], 'ci_high_65plus': o['ci_high']}
conversion_out = (conv.join(pd.DataFrame(band_ci).T)
                  .reset_index(names='isocntry')
                  [['isocntry', 'r_national', 'r_15_64', 'r_65plus', 'n', 'n_eff', 'n_15_64', 'n_eff_15_64',
                    'n_65plus', 'n_eff_65plus', 'ci_low', 'ci_high', 'ci_low_15_64', 'ci_high_15_64',
                    'ci_low_65plus', 'ci_high_65plus', 'gradient_pp', 'gradient_ci_low', 'gradient_ci_high',
                    'gradient_significant']])

age6_rows = []
for c, g in fl5.groupby('isocntry'):
    for k, lab in AGE6.items():
        e = estimate(g[g['d1r2'] == k], 'T1')
        age6_rows.append({'isocntry': c, 'age_band': lab, 'd1r2': k, 'pct': e['pct'], 'n': e['n'],
                          'n_eff': e['n_eff'], 'ci_low': e['ci_low'], 'ci_high': e['ci_high']})
age6_out = pd.DataFrame(age6_rows)

connecting_out = (narrow.join(breakdown.add_prefix('q12_in_T1_').rename(columns=lambda s: s.replace('"', '')
                                                                        .replace('>=1/yr', 'ge1_per_yr')
                                                                        .replace('<1/yr', 'lt1_per_yr').replace(' ', '_')))
                  .join(bases).join(marginal_check.rename(columns={'T1_x_q12ge1_marginal': 'T2_product_of_marginals'}))
                  .reset_index(names='isocntry')
                  .rename(columns={'T2_ci_low': 'ci_low', 'T2_ci_high': 'ci_high', 'T2_as_%_of_T1': 'T2_pct_of_T1',
                                   'in_T1_never_connects_%': 'in_T1_never_connects_pct'}))
connecting_out['T2_over_T1'] = connecting_out['T2'] / connecting_out['T1']
connecting_out['t2_banded'] = T2_BANDED

planning_rows = []
for cc, frame, weight in [*[(c, fl5[fl5.isocntry == c], W_COUNTRY) for c in STUDY_COUNTRIES], ('EU27', eu27, W_EU27)]:
    mpr = q3_cap.at['EU-27' if cc == 'EU27' else cc, 'mentions_per_respondent']
    for k in Q3:
        e = estimate(frame, k, weight)
        planning_rows.append({'isocntry': cc, 'factor_id': k, 'factor': multi_items[k], 'share_pct': e['pct'],
                              'n_eff': e['n_eff'], 'ci_low': e['ci_low'], 'ci_high': e['ci_high'],
                              'mentions_per_respondent': mpr, 'weight': weight, 'role': 'metric_validity'})
planning_out = pd.DataFrame(planning_rows)

exports = {'fl551_conversion_national.csv': conversion_out, 'fl551_conversion_age6.csv': age6_out,
           'fl551_connecting_national.csv': connecting_out, 'fl551_q14_reasons.csv': q14,
           'fl551_planning_factors.csv': planning_out, 'fl551_multimodal.csv': multimodal,
           'fl551_upper_bound_check.csv': upper_bound_out, 'fl551_sk_regional_weighting.csv': t40_out,
           'fl551_regional.csv': regional_out, 'fl551_regional_tests.csv': regional_tests_out}
assert len(conversion_out) == len(connecting_out) == 5 and len(planning_out) == 66
for name, frame in exports.items():
    _write(frame, str(EB_DIR / name), EXPORT_META)
    print(f'[wrote] {EB_DIR / name}  ({len(frame)} rows x {frame.shape[1] + len(EXPORT_META)} cols)')
conversion_out[['isocntry', 'r_national', 'r_15_64', 'r_65plus', 'gradient_pp', 'gradient_significant']].round(2)

# %% [markdown]
# ## 9. Methods text
#
# *Demand-side survey.* Market size and transfer behaviour are estimated from Flash Eurobarometer
# 551, *Multimodal Digital Mobility Service* (GESIS ZA8901 v1.0.0, released 14 April 2025,
# doi:10.4232/1.14506), requested by DG MOVE. It is a mobility survey, not a tourism survey.
# Fieldwork ran from 28 August to 4 September 2024 as a web-based self-administered survey by Ipsos
# European Public Affairs on a **non-probability quota sample** (n = 25,803). Estimates use the national
# post-stratification weight `w1`, and EU-27 benchmarks use `w87`. Because the sample is not a
# probability sample, the intervals we report are **nominal**: the design-effect-adjusted binomial
# half-widths, on Kish's effective sample size, that the estimates would have under random
# sampling. This is the form the Commission publishes; it is not a margin of error.
#
# *Conversion.* The rail market is the share of the 15+ population who travel 50 km or more for
# leisure at least once or twice a year (`q1_1` 1–3) **and** used a train for such journeys in the
# past two years (`q2.2`). It is computed as a joint on individuals, never as a product of marginal
# shares. Mode use is asked only of respondents who travel at least once every few years for
# leisure or work; respondents outside that gate count as not converted, not as "did not use the
# train". The survey's six age bands map exactly onto the municipal bands 15–64 and 65+, and the rate
# applies to the population aged 15 and over in each municipality, not to total population. Applying
# separate 15–64 and 65+ rates changes national totals by less than 0.4 %, because the steep age
# gradient lies within 15–64 (Czechia: 80 % at 15–24, 51 % at 55–64), where the municipal statistics
# have a single band. Slovakia shows no detectable gradient between 15–64 and 65+ (−1.9 pp, nominal
# 95 % interval −10.2 to +6.3), whereas the other four do. Because one national rate applies to
# every municipality, the relative interval of any catchment total equals that of the rate.
#
# *Transfers.* The connecting-rail rate (T2) restricts the rail market to those who combined trains of
# different operators at least once or twice a year in the past two years (`q12` 1–3). The cascade
# branches. Municipalities with a direct train to Košice take the rail-market rate alone, while those
# reachable only with one transfer also take T2 as a share of T1. Poland and Austria have no direct
# connection, so their whole catchment is in the transfer layer; Czechia and Hungary have direct lines,
# so only their one-transfer extension is. The reasons for not combining operators (`q14`, asked of
# those who did so less than once a year or never, `q12` 4–5) are reasons concerning rail journeys in
# general, not reasons for not travelling to Košice. They show that the constraints the model computes
# are ones travellers meet; they do not measure how often any constraint binds for this destination.
#
# All estimates are national. FL551 is never pooled with Flash Eurobarometer 499: the two differ in
# year, mode and class of sample. Planning factors (`q3`) serve only as evidence of metric validity,
# and multimodal combining (`q8`–`q10`) bounds the scope of a rail-only measure; neither is
# multiplied by a population.
