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
# # 00_c1 — Flash Eurobarometer 499: destination criteria, cultural offerings
#
# Prepares FL499 for the manuscript's product–market matching argument (revision register **CON-12**,
# with **LIT-4** and **T26** for the discussion; data access was **T34**). **National level, five
# countries (SK, CZ, HU, PL, AT), one item in focus:** `q4_total.1`, *cultural offerings*. The other
# nine substantive criteria are produced as ranking context, not as findings.
#
# Input is the frame `eb_fl499_load.ipynb` derives from the archive file (NUTS resolution,
# multi-response dummies, codebook); this notebook does **not** reload the microdata.
#
# | Field | Value |
# |---|---|
# | Study | Flash Eurobarometer 499, *Attitudes of Europeans towards tourism* |
# | Requested by | DG GROW |
# | Archive | GESIS ZA7807 v1.0.0 |
# | DOI | 10.4232/1.13878 |
# | Fieldwork | 18–28 October 2021 |
# | Mode | CATI, landline + mobile, random digit dialling |
# | Sampling | Probability |
# | n (published) | 25,714 |
# | Weight | `w1`, post-stratification |
#
# **Provenance, as methods text.** The data are Flash Eurobarometer 499, *Attitudes of Europeans
# towards tourism*, requested by the European Commission's Directorate-General for Internal Market,
# Industry, Entrepreneurship and SMEs (DG GROW) and distributed by GESIS as study ZA7807, version
# 1.0.0 (doi:10.4232/1.13878). Fieldwork ran from 18 to 28 October 2021 by computer-assisted
# telephone interviewing on landline and mobile numbers drawn by random digit dialling, a
# probability design. The published sample is 25,714 interviews; the archive file holds 25,711
# records in the 27 member states. Country estimates use the post-stratification weight `w1`;
# the EU-27 benchmark uses `w87`.
#
# Decisions taken outside this notebook and not revisited here:
#
# - **National only.** Regional (NUTS2) estimates were checked and rejected on power: of the five
#   countries only Slovakia has every NUTS2 cell above an effective n of 100, Poland has 13 of 17
#   below 50, and Podkarpackie, the Polish region bordering eastern Slovakia, has n_eff 28 (±17.3 pp).
# - **Cultural offerings only** enters the results; everything else is context.
# - **Never pooled with FL551** (ZA8901): different year, mode and class of sample.

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
FL499_PARQUET = EB_DIR / 'fl499.parquet'                       # from eb_fl499_load.ipynb
FL499_CODEBOOK = EB_DIR / 'fl499_codebook.csv'
FL499_MULTI = EB_DIR / 'fl499_multiresponse_long.parquet'

STUDY = 'ZA7807 v1.0.0'
DOI = '10.4232/1.13878'
SOURCE = f'Flash Eurobarometer 499, GESIS {STUDY}, doi:{DOI}'

STUDY_COUNTRIES = ['SK', 'CZ', 'HU', 'PL', 'AT']   # Slovakia first: the comparisons are against it
W_COUNTRY = 'w1'    # post-stratification weight, within a country
W_EU27 = 'w87'      # "WEIGHT EURO-28-UK": the EU-27 aggregate weight (not w1, not w14 = EU-25)

for p in (FL499_PARQUET, FL499_CODEBOOK, FL499_MULTI):
    if not p.exists():
        raise FileNotFoundError(f'{p} missing -- run eb_fl499_load.ipynb first')
print(SOURCE)

# %% [markdown]
# ## 1. Load
#
# `fl499.parquet` holds the **211 archive variables** plus the columns `eb_fl499_load.ipynb` derives
# (region/NUTS resolution, `seeks_*` flags, age groups). The codebook lists the 211 archive
# variables; the multi-response file supplies the official item labels of `Q4_Total`.

# %%
fl499 = pd.read_parquet(FL499_PARQUET)
codebook = pd.read_csv(FL499_CODEBOOK)
q4_items = (pd.read_parquet(FL499_MULTI, columns=['block', 'variable', 'item'])
              .query("block == 'q4_total'")[['variable', 'item']].drop_duplicates()
              .assign(pos=lambda x: x['variable'].str.split('.').str[1].astype(int))
              .sort_values('pos').reset_index(drop=True))

derived = [c for c in fl499.columns if c not in set(codebook['variable'])]
print(f'fl499: {fl499.shape[0]:,} rows x {fl499.shape[1]} columns '
      f'= {len(codebook)} archive variables + {len(derived)} derived by the loader')
print('derived:', derived)
print()
print(q4_items.to_string(index=False))

# %% [markdown]
# ## 2. Integrity checks
#
# Each must fail loudly if the input is not what this notebook was written against.
#
# - 25,711 rows; the **211 archive variables** all present (the codebook); 27 countries in `isocntry`.
# - Five-country subset: **SK 1000, CZ 1000, HU 1001, PL 1019, AT 1012**.
# - `w1` non-null on every retained row; `w87` non-null on all 25,711 rows across the 27 countries,
#   summing to 25,713.2 (`w14` is EU-25 and covers only 24 countries: not used).
# - `q4_total.1` … `q4_total.12` exist and contain only {0, 1} after coercion.
# - `d1` (exact age) is bounded 15–102. **`d4`, `d4r1`, `d4r2` are the age when full-time education
#   stopped, not the respondent's age**; nothing is asserted about them and they are not used as age.

# %%
Q4_TOTAL = [f'q4_total.{k}' for k in range(1, 13)]

assert len(fl499) == 25_711, len(fl499)
assert len(codebook) == 211 and codebook['variable'].is_unique, len(codebook)
assert set(codebook['variable']) <= set(fl499.columns), set(codebook['variable']) - set(fl499.columns)
assert fl499['isocntry'].nunique() == 27, fl499['isocntry'].nunique()

EXPECTED_N = {'SK': 1000, 'CZ': 1000, 'HU': 1001, 'PL': 1019, 'AT': 1012}
n_by = fl499['isocntry'].value_counts()
assert {c: int(n_by.get(c, 0)) for c in STUDY_COUNTRIES} == EXPECTED_N, n_by.reindex(STUDY_COUNTRIES)

sub = fl499['isocntry'].isin(STUDY_COUNTRIES)
assert fl499.loc[sub, W_COUNTRY].notna().all(), 'w1 missing on a retained row'
assert fl499[W_EU27].notna().all() and fl499.loc[fl499[W_EU27].notna(), 'isocntry'].nunique() == 27
assert abs(fl499[W_EU27].sum() - 25_713.2) < 0.05, fl499[W_EU27].sum()
assert fl499.loc[fl499['w14'].notna(), 'isocntry'].nunique() == 24   # why w14 is not the EU-27 weight

missing_q4 = [c for c in Q4_TOTAL if c not in fl499.columns]
assert not missing_q4, missing_q4
for c in Q4_TOTAL:
    vals = set(pd.to_numeric(fl499[c], errors='raise').dropna().unique())
    assert vals <= {0, 1}, (c, vals)
    assert fl499[c].notna().all(), (c, 'has missing values')

assert fl499['d1'].between(15, 102).all() and fl499['d1'].min() == 15 and fl499['d1'].max() == 102
# d4 / d4r1 / d4r2 = age when full-time education stopped -- deliberately no assertion.

assert q4_items['pos'].tolist() == list(range(1, 13)) and q4_items['variable'].tolist() == Q4_TOTAL

print('all integrity checks passed')
print(f"  rows {len(fl499):,}; archive variables {len(codebook)}; countries {fl499['isocntry'].nunique()}")
print('  five-country n:', EXPECTED_N)
print(f"  w87: {fl499[W_EU27].notna().sum():,} rows, sum {fl499[W_EU27].sum():,.1f}; d1 in [15, 102]")

# %% [markdown]
# ## 3. Analysis frames
#
# - `fl5` — the five study countries, weighted within country by `w1`.
# - `eu27` — all 27 member states, weighted by `w87`, kept only for the EU-27 benchmark column (§3a).
#   `w1` is never used for a cross-country aggregate.

# %%
Q4_SUBSTANTIVE = [f'q4_total.{k}' for k in range(1, 11)]   # 1-10; 11 = something else, 12 = don't know
keep = ['uniqid', 'isocntry', W_COUNTRY, W_EU27, 'd1', 'nuts1_id', 'nuts2_id', *Q4_TOTAL]

fl5 = fl499.loc[sub, keep].copy()
fl5[Q4_TOTAL] = fl5[Q4_TOTAL].astype(int)
eu27 = fl499[keep].copy()
eu27[Q4_TOTAL] = eu27[Q4_TOTAL].astype(int)

frame_summary = pd.DataFrame({
    'n': fl5.groupby('isocntry').size(),
    'sum_w1': fl5.groupby('isocntry')[W_COUNTRY].sum(),
    'n_eff': fl5.groupby('isocntry').apply(lambda g: eb.effective_n(g, W_COUNTRY), include_groups=False),
}).reindex(STUDY_COUNTRIES)
frame_summary.loc['EU-27 (w87)'] = [len(eu27), eu27[W_EU27].sum(), eb.effective_n(eu27, W_EU27)]
print(frame_summary.round(1).to_string())


# %% [markdown]
# ## 4. The cultural-offerings estimate
#
# ### Q4's structure, and which variable is the input
#
# *"When you choose a destination to visit, which of the following are most important?"* is asked in
# two steps, giving three variable families:
#
# | family | content | used |
# |---|---|---|
# | `q4a` | the **first** choice only, single response, 1–11 | no |
# | `q4b.1` … `q4b.12` | the follow-up (*"And then?"*), dummies; `9 = Inap. (not 1-11 in q4a)` | no |
# | `q4_total.1` … `q4_total.12` | **the combined set, 0/1** | **yes** |
#
# Positions 1–10 are the **ten** substantive criteria; 11 is *something else*, 12 *don't know*.
# (The register's T34 says "all seven Q4_Total criteria"; there are ten.)
#
# ### Estimator
#
# Per country, the `w1`-weighted share of `q4_total.1`, with the retained `n`, the Kish effective
# sample size `n_eff = (Σw)² / Σw²`, and the 95 % half-width `1.96 · √(p(1−p)/n_eff)`.
#
# FL499 is a **probability** sample, so these intervals are **design-warranted**, not nominal. The
# public file has no PSU, stratum or cluster variables, only the post-stratification weight, so the
# design effect is approximated by the weighting effect (Kish), which is what `n_eff` does. Region
# codes 997/998/999 (997 = disclosure control, "re-identification potential") would be excluded from
# any regional cut; this section is national and touches no region variable.

# %%
def estimate(frame, col, weight):
    p = eb.wshare(frame, col, weight)
    n_eff = eb.effective_n(frame, weight)
    hw = eb.ci95(p, n_eff)
    return {'share_pct': p, 'n': len(frame), 'n_eff': n_eff, 'hw_pp': hw,
            'ci_low': p - hw, 'ci_high': p + hw}


CULTURE = 'q4_total.1'
culture = pd.DataFrame({c: estimate(g, CULTURE, W_COUNTRY) for c, g in fl5.groupby('isocntry')}).T
culture = culture.reindex(STUDY_COUNTRIES).astype(float)
culture['n'] = culture['n'].astype(int)

# Rank of cultural offerings among the ten substantive criteria, within each country.
_shares = pd.DataFrame({c: {k: eb.wshare(g, k, W_COUNTRY) for k in Q4_SUBSTANTIVE}
                        for c, g in fl5.groupby('isocntry')})
culture['rank_of_10'] = _shares.rank(ascending=False, method='min').loc[CULTURE].reindex(STUDY_COUNTRIES).astype(int)

show = culture.assign(interval=lambda x: [f'[{a:.1f}, {b:.1f}]' for a, b in zip(x.ci_low, x.ci_high)])
print(show[['share_pct', 'n', 'n_eff', 'hw_pp', 'interval', 'rank_of_10']].round(1).to_string())

# %%
# Assert against the expected table: share within 0.1 pp, n_eff within 1, ranks exact.
EXPECTED_CULTURE = {'SK': (44.7, 710), 'CZ': (52.6, 730), 'HU': (50.2, 767), 'PL': (42.5, 734), 'AT': (31.4, 826)}
EXPECTED_RANK = {'SK': 3, 'CZ': 1, 'HU': 1, 'PL': 1, 'AT': 4}
for c, (share, n_eff) in EXPECTED_CULTURE.items():
    assert abs(culture.at[c, 'share_pct'] - share) <= 0.1, (c, culture.at[c, 'share_pct'], share)
    assert abs(culture.at[c, 'n_eff'] - n_eff) <= 1, (c, culture.at[c, 'n_eff'], n_eff)
assert culture['rank_of_10'].to_dict() == EXPECTED_RANK, culture['rank_of_10'].to_dict()
print('cultural offerings: shares, n_eff and ranks match the expected table')


# %% [markdown]
# ### Differences against Slovakia
#
# Independent samples, so `SE = √(p₁(1−p₁)/n_eff₁ + p₂(1−p₂)/n_eff₂)`, CI = diff ± 1.96·SE,
# `z = diff / SE`. Verdict: |z| < 1.96 **not significant**; 1.96 ≤ |z| < 2.58 **significant,
# marginally** (p < 0.05, not p < 0.01); |z| ≥ 2.58 **significant**. A non-significant difference is
# reported as no detectable difference, not as a difference.

# %%
def diff_vs(a, b, est=culture):
    p1, n1 = est.at[a, 'share_pct'] / 100, est.at[a, 'n_eff']
    p2, n2 = est.at[b, 'share_pct'] / 100, est.at[b, 'n_eff']
    diff = 100 * (p1 - p2)
    se = 100 * np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    z = diff / se
    verdict = ('not significant' if abs(z) < 1.96 else
               'significant, marginally' if abs(z) < 2.58 else 'significant')
    return {'diff_pp': diff, 'ci_low': diff - 1.96 * se, 'ci_high': diff + 1.96 * se, 'z': z, 'verdict': verdict}


vs_sk = pd.DataFrame({f'{c} - SK': diff_vs(c, 'SK') for c in STUDY_COUNTRIES if c != 'SK'}).T
vs_sk[['diff_pp', 'ci_low', 'ci_high', 'z']] = vs_sk[['diff_pp', 'ci_low', 'ci_high', 'z']].astype(float)
print(vs_sk.assign(ci=lambda x: [f'[{a:+.1f}, {b:+.1f}]' for a, b in zip(x.ci_low, x.ci_high)])
           [['diff_pp', 'ci', 'z', 'verdict']].round(2).to_string())

EXPECTED_VS_SK = {'CZ - SK': (8.0, 3.03, 'significant'), 'HU - SK': (5.6, 2.14, 'significant, marginally'),
                  'PL - SK': (-2.2, -0.84, 'not significant'), 'AT - SK': (-13.2, -5.37, 'significant')}
for k, (diff, z, verdict) in EXPECTED_VS_SK.items():
    assert abs(vs_sk.at[k, 'diff_pp'] - diff) <= 0.1 and abs(vs_sk.at[k, 'z'] - z) <= 0.02, (k, vs_sk.loc[k].to_dict())
    assert vs_sk.at[k, 'verdict'] == verdict, (k, vs_sk.at[k, 'verdict'])
assert vs_sk.at['PL - SK', 'ci_low'] < 0 < vs_sk.at['PL - SK', 'ci_high']
print('\ndifferences against SK match the expected table; PL - SK is not significant '
      '(its interval contains 0): no detectable difference')

# %% [markdown]
# ## 5. Ranking context and the response-style diagnostic
#
# Two pieces whose job is to stop the cultural figure being over-read.
#
# ### 5a. The full criterion matrix — **context, not findings**
#
# Ten substantive criteria × five countries (`w1`), plus an EU-27 column weighted with `w87`, ordered
# by the EU-27 column. **Only the cultural-offerings row is carried into the manuscript's results.**

# %%
CRITERION_SHORT = {
    'q4_total.1': 'Cultural offerings', 'q4_total.2': 'Natural environment',
    'q4_total.3': 'Activities available', 'q4_total.4': 'Price of overall trip',
    'q4_total.5': 'Accessibility for all', 'q4_total.6': 'Eco-friendly practices',
    'q4_total.7': 'Reachable by low-impact transport', 'q4_total.8': 'Sustainability certification',
    'q4_total.9': 'Local population involved', 'q4_total.10': 'Health/safety information',
}
assert list(CRITERION_SHORT) == Q4_SUBSTANTIVE

matrix = pd.DataFrame({c: {k: eb.wshare(g, k, W_COUNTRY) for k in Q4_SUBSTANTIVE}
                       for c, g in fl5.groupby('isocntry')})[STUDY_COUNTRIES]
matrix['EU-27'] = [eb.wshare(eu27, k, W_EU27) for k in matrix.index]
matrix = matrix.sort_values('EU-27', ascending=False)
matrix.index = matrix.index.map(CRITERION_SHORT)
print('CONTEXT, NOT FINDINGS -- % naming each criterion (w1 by country, w87 for EU-27)\n')
print(matrix.round(1).to_string())

EXPECTED_MATRIX = {
    'Cultural offerings':                [44.7, 52.6, 50.2, 42.5, 31.4, 43.7],
    'Price of overall trip':             [46.3, 40.7, 45.5, 39.7, 31.8, 42.9],
    'Natural environment':               [60.6, 30.4, 43.0, 37.7, 40.6, 42.6],
    'Activities available':              [29.3, 41.9, 29.0, 36.7, 33.9, 30.1],
    'Accessibility for all':             [34.7, 39.0, 30.0, 37.5, 11.9, 23.9],
    'Health/safety information':         [16.4, 22.0, 23.8, 16.9, 22.7, 20.1],
    'Eco-friendly practices':            [15.1, 11.2, 12.3,  8.8, 19.9, 14.6],
    'Reachable by low-impact transport': [16.0, 12.4, 10.4, 12.6, 15.4, 14.0],
    'Local population involved':         [22.1, 10.7, 12.3, 13.3, 19.1, 13.4],
    'Sustainability certification':      [10.5,  8.6, 12.5, 11.4, 11.4, 10.6],
}
assert list(matrix.index) == list(EXPECTED_MATRIX), list(matrix.index)
assert (abs(matrix.values - np.array(list(EXPECTED_MATRIX.values()))) <= 0.1).all(), 'matrix differs'
print('\nmatrix matches the expected table (within 0.1 pp), EU-27 order included')


# %% [markdown]
# ### 5b. The censoring diagnostic — a methods result in its own right
#
# Q4 admits at most **four** mentions (one in `q4a`, up to three more in `q4b`). Countries differ
# sharply in how many of the four slots they fill, and in a CATI design run by national fieldwork
# agencies that cannot be separated from differences in interviewer probing. Mentions are counted
# over the ten substantive criteria; the cap is verified from the data, not assumed.

# %%
def mention_profile(frame, weight):
    m = frame[Q4_SUBSTANTIVE].sum(axis=1)
    w = frame[weight]
    share = lambda mask: 100 * w[mask].sum() / w.sum()
    return {'max_mentions': int(m.max()), 'n_at_5_plus': int((m >= 5).sum()),
            'le2_pct': share(m <= 2), 'exactly2_pct': share(m == 2), 'cap4_pct': share(m == 4),
            'mean_mentions': float(np.average(m, weights=w))}


mentions = pd.DataFrame({c: mention_profile(g, W_COUNTRY) for c, g in fl5.groupby('isocntry')}).T.reindex(STUDY_COUNTRIES)
mentions.loc['EU-27'] = mention_profile(eu27, W_EU27)
mentions = mentions.astype({'max_mentions': int, 'n_at_5_plus': int})

# The cap, programmatically: 4 in every country, nobody at 5+.
assert (mentions['max_mentions'] == 4).all() and (mentions['n_at_5_plus'] == 0).all(), mentions[['max_mentions', 'n_at_5_plus']]
print('cap verified: max 4 mentions in every country (and EU-27), 0 respondents at 5 or more\n')
print(mentions[['le2_pct', 'cap4_pct', 'mean_mentions', 'exactly2_pct']].round(2).to_string())

EXPECTED_MENTIONS = {'SK': (32.2, 42.3, 2.96), 'CZ': (41.6, 29.3, 2.70), 'HU': (44.2, 30.6, 2.69),
                     'PL': (49.7, 26.4, 2.57), 'AT': (62.1, 10.3, 2.38)}
for c, (le2, cap4, mean) in EXPECTED_MENTIONS.items():
    r = mentions.loc[c]
    assert abs(r.le2_pct - le2) <= 0.1 and abs(r.cap4_pct - cap4) <= 0.1 and abs(r.mean_mentions - mean) <= 0.005, (c, r.to_dict())
assert abs(mentions.at['EU-27', 'mean_mentions'] - 2.56) <= 0.005
assert abs(mentions.at['AT', 'exactly2_pct'] - 53.7) <= 0.1
print(f"\nmatches the expected table; {mentions.at['AT', 'exactly2_pct']:.1f} % of Austrians name exactly two and stop")

# %% [markdown]
# **Consequence.** Normalising each criterion to its share of *all mentions* (share ÷ mean mentions)
# changes cross-country orderings on low-prevalence items. Low-impact transport becomes SK 5.4,
# CZ 4.6, HU 3.9, PL 4.9, **AT 6.5**, which reverses SK against AT (raw: SK 16.0 > AT 15.4). So a
# cross-country comparison of the *level* of an individual criterion is not supported by this
# instrument.

# %%
share_of_mentions = matrix[STUDY_COUNTRIES] / mentions.loc[STUDY_COUNTRIES, 'mean_mentions']
lit = 'Reachable by low-impact transport'
print('raw share (%):        ', matrix.loc[lit, STUDY_COUNTRIES].round(1).to_dict())
print('share of mentions (%):', share_of_mentions.loc[lit].round(1).to_dict())

# Expected values were computed from rounded inputs; HU is 10.35 / 2.69 = 3.85 unrounded (3.9 from
# 10.4 / 2.69), hence the 0.06 tolerance. The claim itself -- the SK/AT reversal -- is asserted exactly below.
EXPECTED_SOM = {'SK': 5.4, 'CZ': 4.6, 'HU': 3.9, 'PL': 4.9, 'AT': 6.5}
assert all(abs(share_of_mentions.at[lit, c] - v) <= 0.06 for c, v in EXPECTED_SOM.items()), share_of_mentions.loc[lit]
assert matrix.at[lit, 'SK'] > matrix.at[lit, 'AT'] and share_of_mentions.at[lit, 'SK'] < share_of_mentions.at[lit, 'AT']
print('\nreproduced: SK > AT on raw shares, SK < AT on share-of-mentions -- the ordering reverses')

# %% [markdown]
# **Defence.** Within a country, share-of-mentions is the raw share divided by one constant (that
# country's mean mentions), a monotone transformation, so the **ranking of the ten criteria is
# invariant**. The cell below fails if the two orderings differ in any country. This is why the
# paper states its claim as a **rank**, and why raw shares are the headline: they have a population
# referent, carry a binomial interval, and match the Commission's published tables.

# %%
for c in STUDY_COUNTRIES:
    raw_order = matrix[c].sort_values(ascending=False, kind='mergesort').index.tolist()
    som_order = share_of_mentions[c].sort_values(ascending=False, kind='mergesort').index.tolist()
    assert raw_order == som_order, f'{c}: orderings differ\n{raw_order}\n{som_order}'
print('within-country orderings of the ten criteria are identical under raw shares and '
      'share-of-mentions in all five countries')
print(pd.DataFrame({c: matrix[c].rank(ascending=False, method='min').astype(int) for c in STUDY_COUNTRIES})
        .loc[['Cultural offerings', 'Natural environment', 'Price of overall trip']].to_string())

# %% [markdown]
# ## 5c. The criteria by region (T38, CON-12)
#
# CON-12 asks whether FL499 can show what travellers seek **in the regions the network reaches**, rather than as a
# national average. The criteria are read per region, with the same rules as FL551 §7c:
#
# * NUTS2 in SK, CZ, HU, AT; Poland collapsed to its seven NUTS1 macroregions.
# * Respondents without a disclosed region (codes 997–999, no `nuts2_id`) are excluded.
# * A Wald test that a country's regions share one share, plus the top − bottom pair with a Bonferroni critical z.
#   `regional_contrast_supported` requires both.
#
# FL499 is a probability sample, so the intervals are design-warranted (weighting effect only; no PSU / strata in
# the public file).

# %%
from scipy import stats

REGION_LEVEL = {c: 'nuts2_id' for c in STUDY_COUNTRIES} | {'PL': 'nuts1_id'}
reg_rows, test_rows = [], []
for c in STUDY_COUNTRIES:
    lvl = REGION_LEVEL[c]
    g_c = fl5[(fl5.isocntry == c) & fl5[lvl].notna()]
    for k in Q4_SUBSTANTIVE:
        nat = estimate(fl5[fl5.isocntry == c], k, W_COUNTRY)
        cells = {r: estimate(g, k, W_COUNTRY) for r, g in g_c.groupby(lvl)}
        for r, e in cells.items():
            reg_rows.append({'isocntry': c, 'level': 'NUTS1 macroregion' if lvl == 'nuts1_id' else 'NUTS2',
                             'region_id': r, 'criterion_id': k, 'criterion_label': CRITERION_SHORT[k],
                             'share_pct': e['share_pct'], 'n': e['n'], 'n_eff': e['n_eff'], 'hw_pp': e['hw_pp'],
                             'ci_low': e['ci_low'], 'ci_high': e['ci_high'], 'national_pct': nat['share_pct'],
                             'underpowered': bool(e['hw_pp'] > 10)})
        p = np.array([e['share_pct'] / 100 for e in cells.values()])
        n = np.array([e['n_eff'] for e in cells.values()])
        pbar = (p * n).sum() / n.sum()
        chi2 = float((n * (p - pbar) ** 2).sum() / (pbar * (1 - pbar))) if 0 < pbar < 1 else 0.0
        p_wald = float(stats.chi2.sf(chi2, len(cells) - 1))
        top, bot = max(cells, key=lambda r: cells[r]['share_pct']), min(cells, key=lambda r: cells[r]['share_pct'])
        p1, n1, p2, n2 = cells[top]['share_pct'] / 100, cells[top]['n_eff'], cells[bot]['share_pct'] / 100, cells[bot]['n_eff']
        se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
        z = (p1 - p2) / se if se else 0.0
        z_adj = float(stats.norm.ppf(1 - 0.025 / (len(cells) * (len(cells) - 1) / 2)))
        test_rows.append({'isocntry': c, 'criterion_id': k, 'criterion_label': CRITERION_SHORT[k],
                          'n_regions': len(cells), 'wald_chi2': chi2, 'p_equal_shares': p_wald,
                          'top_region': top, 'top_pct': 100 * p1, 'bottom_region': bot, 'bottom_pct': 100 * p2,
                          'top_minus_bottom_pp': 100 * (p1 - p2), 'tb_z': z, 'tb_z_bonferroni': z_adj,
                          'regional_contrast_supported': bool(p_wald < 0.05 and abs(z) >= z_adj)})
regional_out = pd.DataFrame(reg_rows)
regional_tests_out = pd.DataFrame(test_rows)
print('Criteria with a supported regional contrast:')
sup = regional_tests_out[regional_tests_out.regional_contrast_supported]
print(sup[['isocntry', 'criterion_label', 'p_equal_shares', 'top_region', 'top_pct', 'bottom_region', 'bottom_pct']]
      .round(3).to_string(index=False) if len(sup) else '  none')
print(f"\nWald p < 0.05 in {int((regional_tests_out.p_equal_shares < 0.05).sum())} of {len(regional_tests_out)} "
      f"country x criterion tests (about {0.05 * len(regional_tests_out):.1f} expected by chance)")
print('\nSlovakia, by NUTS2 (share ± half-width):')
print(regional_out[regional_out.isocntry == 'SK']
      .assign(cell=lambda d: d.share_pct.round(1).astype(str) + ' ± ' + d.hw_pp.round(1).astype(str))
      .pivot(index='criterion_label', columns='region_id', values='cell').to_string())

# %% [markdown]
# **Reading (this run).** The regions add nothing that survives testing:
#
# * Only 3 of the 50 country × criterion Wald tests reach p < 0.05, about the 2.5 chance alone would give.
# * The one contrast that passes both tests (cultural offerings, Budapest HU11 59 % against Dél-Dunántúl HU23 37 %,
#   Wald p = 0.044) is one of 50 and does not survive a correction across them.
# * In Slovakia every criterion's four regional shares lie inside each other's intervals.
#
# CON-12 is therefore answered **nationally**: what travellers seek is read at country level, and the regional
# table goes to the supplement as evidence that the regions the network reaches do not differ from their country.

# %% [markdown]
# ## 6. Exports
#
# Written to `data/eb/`, every file with a `source` (ZA7807 v1.0.0 and its DOI) and a `generated_at`
# column, using `traintran.output._write`, the metadata convention of the pipeline outputs. The
# precision travels with each number instead of living in a footnote.
#
# | file | content |
# |---|---|
# | `fl499_cultural_national.csv` | one row per country: `isocntry`, `share_pct`, `n`, `n_eff`, `ci_low`, `ci_high`, `rank_of_10`, `mentions_per_respondent` |
# | `fl499_criteria_matrix_national.csv` | §5a in long form: `isocntry`, `criterion_id`, `criterion_label`, `share_pct`, `n_eff`, `ci_low`, `ci_high`, `weight`; EU-27 rows have `isocntry = EU27`, `weight = w87` |
# | `fl499_mention_counts.csv` | §5b: share giving ≤ 2, exactly 2, the cap of 4, mean mentions, max mentions |
# | `fl499_criteria_regional.csv` | §5c: the ten criteria per NUTS2 (PL: NUTS1 macroregion) with n, n_eff, interval, national share, `underpowered` |
# | `fl499_criteria_regional_tests.csv` | §5c: per country and criterion, the Wald test and the Bonferroni top − bottom contrast |

# %%
import datetime as dt
from traintran.output import _write

EXPORT_META = {'source': SOURCE, 'generated_at': dt.datetime.now().isoformat(timespec='seconds')}

cultural_out = (culture.reset_index(names='isocntry')
                [['isocntry', 'share_pct', 'n', 'n_eff', 'ci_low', 'ci_high', 'rank_of_10']]
                .assign(mentions_per_respondent=lambda x: x['isocntry'].map(mentions['mean_mentions'])))

rows = []
for cc, frame, weight in [*[(c, fl5[fl5.isocntry == c], W_COUNTRY) for c in STUDY_COUNTRIES],
                          ('EU27', eu27, W_EU27)]:
    for k in Q4_SUBSTANTIVE:
        e = estimate(frame, k, weight)
        rows.append({'isocntry': cc, 'criterion_id': k, 'criterion_label': CRITERION_SHORT[k],
                     'criterion_item': q4_items.set_index('variable').at[k, 'item'],
                     'share_pct': e['share_pct'], 'n_eff': e['n_eff'],
                     'ci_low': e['ci_low'], 'ci_high': e['ci_high'], 'weight': weight})
matrix_out = pd.DataFrame(rows)

mention_out = (mentions.reset_index(names='isocntry').replace({'isocntry': {'EU-27': 'EU27'}})
               .assign(weight=lambda x: np.where(x['isocntry'] == 'EU27', W_EU27, W_COUNTRY)))

# The exports must say what the notebook asserted above.
assert len(cultural_out) == 5 and len(matrix_out) == 60
assert np.allclose(matrix_out.query("isocntry == 'EU27'").set_index('criterion_label')['share_pct']
                   .reindex(matrix.index), matrix['EU-27'])

for name, frame in [('fl499_cultural_national.csv', cultural_out),
                    ('fl499_criteria_matrix_national.csv', matrix_out),
                    ('fl499_mention_counts.csv', mention_out),
                    ('fl499_criteria_regional.csv', regional_out),
                    ('fl499_criteria_regional_tests.csv', regional_tests_out)]:
    _write(frame, str(EB_DIR / name), EXPORT_META)
    print(f'[wrote] {EB_DIR / name}  ({len(frame)} rows)')
cultural_out.round(2)

# %% [markdown]
# ## 7. Methods text
#
# *Destination criteria.* Product–market matching is assessed with Flash Eurobarometer 499,
# *Attitudes of Europeans towards tourism* (GESIS ZA7807 v1.0.0, doi:10.4232/1.13878), fielded
# 18–28 October 2021 by computer-assisted telephone interviews on landline and mobile numbers drawn
# by random digit dialling. Because FL499 is a probability sample, its confidence intervals are
# design-warranted. The public file carries no primary sampling unit, stratum or cluster identifiers,
# only the post-stratification weight `w1`; we therefore approximate the design effect by the
# weighting effect and compute 95 % intervals on Kish's effective sample size,
# n_eff = (Σw)²/Σw². Country estimates use `w1`; the EU-27 benchmark uses the cross-national weight
# `w87`.
#
# Question 4 asks which aspects are most important when choosing a destination. Respondents give a
# first choice and may add further choices, up to **four mentions in total**; we use the combined
# indicator (`Q4_Total`) over its ten substantive criteria. The cap matters: the share of respondents
# who stop at two or fewer mentions ranges from 32 % in Slovakia to 62 % in Austria, and only 10 % of
# Austrians reach the cap against 42 % of Slovaks. In a telephone survey run by national fieldwork
# agencies this cannot be separated from differences in interviewer probing. Normalising to each
# criterion's share of all mentions does not remove the problem: it reorders countries on
# low-prevalence items (for low-impact transport it reverses Slovakia and Austria). We therefore do
# not compare the *level* of a single criterion across countries as a substantive finding. We report
# raw shares, which have a population referent, a binomial interval and match the Commission's
# published tables, and we state the result as a **within-country rank**, which is identical under
# raw shares and share-of-mentions because dividing by a country's mean number of mentions is
# monotone.
#
# All estimates are national. Regional (NUTS 2) estimates were examined and rejected on power: only
# Slovakia has every region above an effective sample of 100, 13 of Poland's 17 regions fall below
# 50, and Podkarpackie, the region bordering eastern Slovakia, has an effective sample of 28, giving
# ±17.3 percentage points. FL499 is never pooled with Flash Eurobarometer 551. The two differ in year
# (2021 vs 2024), mode (telephone vs online) and class of sample (probability vs non-probability
# quota), so they enter the analysis as separate, independent sources.
#
# **Finding.** Cultural offerings is the top destination criterion in Czechia (52.6 %, ±3.6 pp),
# Hungary (50.2 %, ±3.5 pp) and Poland (42.5 %, ±3.6 pp). It is significantly higher in Czechia
# (+8.0 pp) and Hungary (+5.6 pp) than in Slovakia itself (44.7 %, ±3.7 pp, ranked third), and
# Poland does not differ detectably from Slovakia. Slovaks rank the natural environment first, at
# 60.6 %. Košice is a cultural, urban destination, so its product is better matched to the
# cross-border markets than to its own domestic market. This closes the first of the two
# redistribution preconditions the introduction opens and does not measure (CON-12), and it pairs
# with the connectivity analysis: those markets want what the destination offers, and the binding
# constraint is the connection.
#
# *Scope.* No share here is converted into a population count. FL499 measures which criteria people
# rank highly. It names no destination, does not distinguish rail from other low-impact modes, and
# carries no competitive context, so no share can be multiplied by a population to give a market
# size. That conversion is FL551's job (Q1_1 × Q2); realised demand is the occupancy data's.
