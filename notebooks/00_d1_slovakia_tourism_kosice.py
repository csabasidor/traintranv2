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
# # 00_d1 — Košice tourism 2025 (ŠÚ SR DATAcube)
#
# Two cubes of the Statistical Office of the Slovak Republic, for the **city of Košice** (`SK0422_0425`,
# okresy Košice I–IV), **2025**, via the public DATAcube API
# (<https://statdata.statistics.sk/public/api/dc/swagger-ui/index.html>):
#
# | cube | title | selection |
# |---|---|---|
# | `cr3805qr` | *Návštevnosť, tržby a kapacity UZ – SR, kraje, okresy, obce (13 ukazovateľov)* — occupancy, turnover and capacity of accommodation establishments | `e_nuts15` = SK0422_0425 (city total); quarters 1–4 + the year (`1. - 4. Q.`); all 13 indicators |
# | `cr3804mr` | *Návštevnosť UZ – okresy (krajiny)* — occupancy of accommodation establishments by country of origin | `e_nuts14` = SK0422_0425; months 1–12 + the year (`1. - 12.`); origins VISIT_TOTAL, VISIT_DOM, VISIT_FOR, AT, CZ, HU, PL, UA; all 3 indicators |
#
# **API calls** (18 in total, each cached in `…/sk/tourism/api/` and skipped if present):
#
# 1. `GET /public/{cube}/info` — the cube's dimensions and their ids (2 calls);
# 2. `GET /public/{dimensionId}/{cube}/dimensionItemsInCube` — each dimension's items with codes and SK / EN
#    names (6 + 8 calls);
# 3. `GET /opendata/cube/dataset/{cube}/rows/{…}/columns/{…}/context/{…}?lang=SK&type=CSV` — the data, **one call
#    per cube**: several dimensions are stacked in `rows` (`dimA,ASC,…~dimB,ASC,all`).
#
# The data CSV carries **Slovak labels, not codes**; they are mapped back to codes through the item lists, and
# every label must map. Outputs go to `data/eu/ref-national-statistical-offices/sk/tourism/`, each CSV with a
# `.meta.md` data dictionary.

# %%
import os, sys

# Run from the project root so every relative path resolves the same from notebooks/ or the root.
_here = os.path.abspath('')
if os.path.basename(_here) == 'notebooks':
    os.chdir(os.path.dirname(_here))
sys.path.insert(0, os.getcwd())
print('Working directory:', os.getcwd())

# %%
import datetime as dt
import io
import json
import time
from pathlib import Path

import pandas as pd
import requests

API = 'https://statdata.statistics.sk/public/api/dc'
AREA = 'SK0422_0425'          # Košice (okresy Košice I-IV)
YEAR = '2025'
ORIGINS = ['VISIT_TOTAL', 'VISIT_DOM', 'VISIT_FOR', 'AT', 'CZ', 'HU', 'PL', 'UA']
PAUSE_S = 1.5

OUT_DIR = Path('data/eu/ref-national-statistical-offices/sk/tourism')
API_DIR = OUT_DIR / 'api'
API_DIR.mkdir(parents=True, exist_ok=True)

# One data call per cube: rows / columns / context of the opendata dataset endpoint.
SELECTION = {
    'cr3805qr': dict(rows='e_indic,ASC,all~e_unit,ASC,all',
                     columns='e_quarter,ASC,all',
                     context=f'e_nuts15,ASC,{AREA}~e_nuts14,ASC,{AREA}~e_year,ASC,{YEAR}'),
    'cr3804mr': dict(rows=f"e_geo-visit,ASC,{','.join(ORIGINS)}~e_indic,ASC,all~e_unit,ASC,all",
                     columns='e_month,ASC,all',
                     context=f'e_nuts14,ASC,{AREA}~e_year,ASC,{YEAR}'),
}
http = requests.Session()
n_fetched = 0


def get(url, tries=4, timeout=180):
    global n_fetched
    for k in range(tries):
        try:
            r = http.get(url, timeout=timeout)
            r.raise_for_status()
            n_fetched += 1
            time.sleep(PAUSE_S)
            return r
        except requests.RequestException as e:
            if k == tries - 1:
                raise
            wait = 5 * 2 ** k
            print(f'  retry in {wait}s after {type(e).__name__}: {e}')
            time.sleep(wait)


def cached(name, url, as_json=True):
    p = API_DIR / name
    if not p.exists():
        p.write_bytes(get(url).content)
        print('[fetched]', p)
    text = p.read_text(encoding='utf-8')
    return json.loads(text) if as_json else text


def data_url(cube):
    s = SELECTION[cube]
    return (f"{API}/opendata/cube/dataset/{cube}/rows/{s['rows']}/columns/{s['columns']}"
            f"/context/{s['context']}?lang=SK&type=CSV")


for c in SELECTION:
    print(c, '->', data_url(c))

# %% [markdown]
# ## 1. Cube metadata: dimensions and items
#
# Every requested code must exist in its dimension.

# %%
META = {}
for cube in SELECTION:
    info = cached(f'{cube}_info.json', f'{API}/public/{cube}/info')
    items = {}
    for d in info['dimensions']:
        lst = cached(f"{cube}_items_{d['acronym']}.json", f"{API}/public/{d['id']}/{cube}/dimensionItemsInCube")
        items[d['acronym']] = pd.DataFrame([{'code': x['acronym'], 'name_sk': (x.get('nameSk') or '').strip(),
                                             'name_en': (x.get('nameEn') or '').strip()} for x in lst])
    META[cube] = {'info': info, 'items': items}
    print(f"{cube}: {info['nameEn']}\n   ({info['nameSk'].strip()}); last data change {info['lastDataChange']}")
    display(pd.DataFrame([{'dimension': d['acronym'], 'name': d.get('nameEn', ''), 'items': len(items[d['acronym']])}
                          for d in info['dimensions']]))

need = {'cr3805qr': {'e_nuts15': [AREA], 'e_nuts14': [AREA], 'e_year': [YEAR]},
        'cr3804mr': {'e_nuts14': [AREA], 'e_year': [YEAR], 'e_geo-visit': ORIGINS}}
for cube, dims in need.items():
    for dim, codes in dims.items():
        miss = set(codes) - set(META[cube]['items'][dim]['code'])
        assert not miss, f'{cube}.{dim}: {miss} not in the cube'
AREA_NAME = META['cr3804mr']['items']['e_nuts14'].set_index('code').loc[AREA, 'name_sk']
print(f'all requested codes exist; {AREA} = {AREA_NAME}')
display(META['cr3804mr']['items']['e_geo-visit'].query('code in @ORIGINS'))
display(META['cr3805qr']['items']['e_indic'])


# %%
def label_to_code(cube, dim, labels):
    """Map the data CSV's Slovak labels of one dimension back to item codes; every label must map."""
    it = META[cube]['items'][dim]
    assert it['name_sk'].is_unique, f'{cube}.{dim}: Slovak names are not unique'
    m = it.set_index('name_sk')['code']
    out = labels.str.strip().map(m)
    bad = sorted(set(labels[out.isna()]))
    assert not bad, f'{cube}.{dim}: labels without a code: {bad}'
    return out


def names(cube, dim):
    return META[cube]['items'][dim].set_index('code')


def fetch_data(cube):
    text = cached(f'{cube}_{YEAR}_{AREA}.csv', data_url(cube), as_json=False)
    return pd.read_csv(io.StringIO(text), dtype=str)


# %% [markdown]
# ## 2. `cr3805qr` — accommodation capacity, turnover, prices, occupancy (quarters)
#
# Quarter labels become `Q1`…`Q4` and `YEAR` (`1. - 4. Q.`). Checks: the 13 × 5 values are all there (missing
# ones listed); for **flows** (turnover, U_CR_0014–0016) Q1 + … + Q4 equals the year. Stocks (capacity),
# averages (prices, rooms / beds per day) and rates (occupancy) are not additive and are only reported.

# %%
cube = 'cr3805qr'
raw = fetch_data(cube)
assert list(raw.columns) == ['e_quarter', 'e_indic', 'e_unit', 'hodnota'], list(raw.columns)
QMAP = {'1. Q.': 'Q1', '2. Q.': 'Q2', '3. Q.': 'Q3', '4. Q.': 'Q4', '1. - 4. Q.': 'YEAR'}
ind = names(cube, 'e_indic')
acc = pd.DataFrame({
    'cube': cube, 'nuts_code': AREA, 'nuts_name': AREA_NAME, 'year': int(YEAR),
    'period': label_to_code(cube, 'e_quarter', raw['e_quarter']).map(QMAP),
    'period_label': raw['e_quarter'],
    'indic_code': label_to_code(cube, 'e_indic', raw['e_indic']),
    'unit_code': label_to_code(cube, 'e_unit', raw['e_unit']),
    'value': pd.to_numeric(raw['hodnota'], errors='coerce'),
})
acc.insert(7, 'indic_name_sk', acc['indic_code'].map(ind['name_sk']))
acc.insert(8, 'indic_name_en', acc['indic_code'].map(ind['name_en']))
acc = acc.sort_values(['indic_code', 'period']).reset_index(drop=True)
assert acc['period'].notna().all() and not acc.duplicated(['indic_code', 'period']).any()

full = pd.MultiIndex.from_product([ind.index, list(QMAP.values())], names=['indic_code', 'period'])
missing = full.difference(acc.dropna(subset=['value']).set_index(['indic_code', 'period']).index)
print(f'{len(acc)} rows, {acc.value.notna().sum()} values of {len(full)} expected; missing: {list(missing) or "none"}')

wide_acc = acc.pivot(index=['indic_code', 'indic_name_en', 'unit_code'], columns='period', values='value')[list(QMAP.values())]
FLOWS = ['U_CR_0014', 'U_CR_0015', 'U_CR_0016']
chk = wide_acc.reset_index().set_index('indic_code').loc[[f for f in FLOWS if f in wide_acc.index.get_level_values(0)]]
chk = chk.assign(sum_q=chk[['Q1', 'Q2', 'Q3', 'Q4']].sum(axis=1))
chk['diff'] = chk['sum_q'] - chk['YEAR']
display(chk[['indic_name_en', 'Q1', 'Q2', 'Q3', 'Q4', 'sum_q', 'YEAR', 'diff']])
assert (chk['diff'].abs() <= chk['YEAR'].abs() * 0.005 + 1).all(), 'turnover quarters do not add up to the year'
print('turnover: Q1..Q4 add up to the year (within rounding)')

# %% [markdown]
# ## 3. `cr3804mr` — visitors by country of origin (months)
#
# Month labels become `M01`…`M12` and `YEAR` (`1. - 12.`). Checks: 8 origins × 3 indicators × 13 periods = 312
# values; **VISIT_TOTAL = VISIT_DOM + VISIT_FOR** (visitors and nights, every period); **months 1–12 add up to
# the year**; average nights ≈ nights / visitors.

# %%
cube = 'cr3804mr'
raw = fetch_data(cube)
assert list(raw.columns) == ['e_month', 'e_geo-visit', 'e_indic', 'e_unit', 'hodnota'], list(raw.columns)
MMAP = {f'{m}.': f'M{m:02d}' for m in range(1, 13)} | {'1. - 12.': 'YEAR'}
ind = names(cube, 'e_indic')
geo = names(cube, 'e_geo-visit')
vis = pd.DataFrame({
    'cube': cube, 'nuts_code': AREA, 'nuts_name': AREA_NAME, 'year': int(YEAR),
    'period': label_to_code(cube, 'e_month', raw['e_month']).map(MMAP),
    'period_label': raw['e_month'],
    'origin_code': label_to_code(cube, 'e_geo-visit', raw['e_geo-visit']),
    'indic_code': label_to_code(cube, 'e_indic', raw['e_indic']),
    'unit_code': label_to_code(cube, 'e_unit', raw['e_unit']),
    'value': pd.to_numeric(raw['hodnota'], errors='coerce'),
})
vis.insert(7, 'origin_name_sk', vis['origin_code'].map(geo['name_sk']))
vis.insert(8, 'origin_name_en', vis['origin_code'].map(geo['name_en']))
vis.insert(10, 'indic_name_sk', vis['indic_code'].map(ind['name_sk']))
vis.insert(11, 'indic_name_en', vis['indic_code'].map(ind['name_en']))
vis['origin_code'] = pd.Categorical(vis['origin_code'], ORIGINS, ordered=True)
vis = vis.sort_values(['indic_code', 'origin_code', 'period']).reset_index(drop=True)
vis['origin_code'] = vis['origin_code'].astype(str)
assert vis['period'].notna().all() and not vis.duplicated(['origin_code', 'indic_code', 'period']).any()
assert set(vis.origin_code) == set(ORIGINS), set(ORIGINS) - set(vis.origin_code)
print(f'{len(vis)} rows (expected {len(ORIGINS) * 3 * 13}), {vis.value.notna().sum()} values')

VISITORS, NIGHTS, AVG = 'U_CR_0005', 'U_CR_0008', 'U_CR_0011'
cube_v = vis.pivot_table(index=['indic_code', 'period'], columns='origin_code', values='value')
for ic in (VISITORS, NIGHTS):
    t = cube_v.loc[ic]
    d = t['VISIT_TOTAL'] - t['VISIT_DOM'] - t['VISIT_FOR']
    assert (d.abs() < 0.5).all(), f'{ic}: total != domestic + foreign in {list(d[d.abs() >= 0.5].index)}'
    m = t.drop(index='YEAR').sum() - t.loc['YEAR']
    print(f'{ic}: total = domestic + foreign in every period; months - year by origin: {m.round(1).to_dict()}')
    assert (m.abs() <= t.loc['YEAR'].abs() * 0.005 + 1).all(), f'{ic}: months do not add up to the year'
ratio = (cube_v.loc[NIGHTS] / cube_v.loc[VISITORS]).round(1)
off = (ratio - cube_v.loc[AVG]).abs()
print(f'average nights = nights / visitors: max difference {off.max().max():.2f}')
assert (off <= 0.051).all().all()

# %% [markdown]
# ## 4. Overview

# %%
display(wide_acc)
v = cube_v.loc[VISITORS][ORIGINS].astype('int64')
n = cube_v.loc[NIGHTS][ORIGINS].astype('int64')
print('visitors by origin and month:'); display(v)
print('nights by origin and month:'); display(n)
share = (v[['AT', 'CZ', 'HU', 'PL', 'UA']].div(v['VISIT_FOR'], axis=0) * 100).round(1)
share['five_countries'] = share.sum(axis=1)
print('share of foreign visitors (%):'); display(share)

# %% [markdown]
# ## 4b. Occupancy rate and market shares (%), 2025
#
# **(a) Net occupancy rate** of permanent bed places (`U_CR_0020`) and of bedrooms (`U_CR_0021`), in %, from
# `cr3805qr`, shown per quarter and as the office's annual figure. Two averages of the quarters are set beside it:
# * the **plain mean** of the four quarters;
# * the **capacity-weighted mean**: each quarter weighted by its available bed places (or rooms) per day
#   (`U_CR_0023`, `U_CR_0022`) × its days.
#
# The annual rate is a ratio (nights over available bed-nights), not an average of rates. So the weighted mean
# should reproduce the official annual figure; the plain mean may not.
#
# **(b) Market shares** of each origin, in %, from `cr3804mr`: visitors and nights, as a share of **all** guests and
# of **foreign** guests. Two versions:
# * **annual**: the year's totals; each month counts with its demand, so this is the figure to report;
# * **monthly average**: the plain mean of the 12 monthly shares; it gives a quiet month the same weight as a busy one.
#
# **(c) Contribution to the occupancy rate:** each origin's nights / (available permanent bed places per day × 365)
# × 100, in **percentage points** of the annual bed-place occupancy rate. Over all guests this rebuilds the official
# annual rate, which is checked below.

# %%
DAYS_Q = pd.Series({f'Q{q}': (pd.Timestamp(f'{YEAR}-{3 * q - 2:02d}-01') + pd.offsets.QuarterEnd(0)).dayofyear
                    - (pd.Timestamp(f'{YEAR}-{3 * q - 2:02d}-01').dayofyear - 1) for q in range(1, 5)})
DAYS_YEAR = 366 if pd.Timestamp(f'{YEAR}-12-31').dayofyear == 366 else 365
qa = wide_acc.reset_index().set_index('indic_code')
occ_rows = []
for rate, cap, what in (('U_CR_0020', 'U_CR_0023', 'permanent bed places'), ('U_CR_0021', 'U_CR_0022', 'bedrooms')):
    r, c = qa.loc[rate], qa.loc[cap]
    q = ['Q1', 'Q2', 'Q3', 'Q4']
    w = c[q].astype(float) * DAYS_Q[q].values                       # available bed- (room-) days per quarter
    occ_rows.append({'measure': f'net occupancy rate of {what}', 'indic_code': rate,
                     **{k: float(r[k]) for k in q}, 'official_year': float(r['YEAR']),
                     'plain_mean_q': float(r[q].astype(float).mean()),
                     'weighted_mean_q': float((r[q].astype(float) * w).sum() / w.sum())})
occ = pd.DataFrame(occ_rows)
print('(a) net occupancy rate, %:')
display(occ.round(2))
off = (occ.weighted_mean_q - occ.official_year).abs().max()
print(f'capacity-weighted mean of the quarters vs the official annual rate: max difference {off:.2f} pp')

# %%
yv, yn = v.loc['YEAR'], n.loc['YEAR']
ORIG5 = ['AT', 'CZ', 'HU', 'PL', 'UA']
months = [f'M{m:02d}' for m in range(1, 13)]
beds_per_day = float(qa.loc['U_CR_0023', 'YEAR'])                 # available permanent bed places per day, year
bed_nights = beds_per_day * DAYS_YEAR
share_rows = []
for o in ['VISIT_TOTAL', 'VISIT_DOM', 'VISIT_FOR', *ORIG5]:
    share_rows.append({
        'origin_code': o, 'origin_name_en': geo.loc[o, 'name_en'],
        'visitors': int(yv[o]), 'nights': int(yn[o]), 'avg_nights': round(yn[o] / yv[o], 2),
        'share_total_visitors_pct': 100 * yv[o] / yv['VISIT_TOTAL'],
        'share_total_nights_pct': 100 * yn[o] / yn['VISIT_TOTAL'],
        'share_foreign_visitors_pct': 100 * yv[o] / yv['VISIT_FOR'] if o in ORIG5 else None,
        'share_foreign_nights_pct': 100 * yn[o] / yn['VISIT_FOR'] if o in ORIG5 else None,
        'monthly_mean_share_total_visitors_pct': float((100 * v.loc[months, o] / v.loc[months, 'VISIT_TOTAL']).mean()),
        'monthly_mean_share_foreign_visitors_pct': (float((100 * v.loc[months, o] / v.loc[months, 'VISIT_FOR']).mean())
                                                    if o in ORIG5 else None),
        'occupancy_contribution_pp': 100 * yn[o] / bed_nights,
    })
shares = pd.DataFrame(share_rows)
five = shares[shares.origin_code.isin(ORIG5)]
shares = pd.concat([shares, pd.DataFrame([{
    'origin_code': 'FIVE', 'origin_name_en': 'AT + CZ + HU + PL + UA',
    'visitors': int(five.visitors.sum()), 'nights': int(five.nights.sum()),
    'avg_nights': round(five.nights.sum() / five.visitors.sum(), 2),
    **{c: five[c].sum() for c in ('share_total_visitors_pct', 'share_total_nights_pct', 'share_foreign_visitors_pct',
                                  'share_foreign_nights_pct', 'monthly_mean_share_total_visitors_pct',
                                  'monthly_mean_share_foreign_visitors_pct', 'occupancy_contribution_pp')}}])],
    ignore_index=True)
shares.insert(0, 'year', int(YEAR))
print(f'(b, c) market shares and contribution to the occupancy rate, {YEAR} '
      f'({beds_per_day:,.0f} permanent bed places per day x {DAYS_YEAR} days = {bed_nights:,.0f} bed-nights):')
display(shares.round(2))
rebuilt = float(shares.loc[shares.origin_code == 'VISIT_TOTAL', 'occupancy_contribution_pp'].iloc[0])
official = float(occ.loc[occ.indic_code == 'U_CR_0020', 'official_year'].iloc[0])
print(f'all guests: {rebuilt:.2f} pp rebuilt from nights / bed-nights vs the official {official:.1f} % '
      f'(difference {rebuilt - official:+.2f} pp)')
assert abs(rebuilt - official) < 0.1, 'nights / available bed-nights does not rebuild the official occupancy rate'
print(f"the five study countries: {five.share_total_visitors_pct.sum():.1f} % of all guests, "
      f"{five.share_foreign_visitors_pct.sum():.1f} % of foreign guests, "
      f"{five.occupancy_contribution_pp.sum():.2f} pp of the {official:.1f} % bed-place occupancy rate")

# %% [markdown]
# ## 5. Outputs and data dictionaries

# %%
COMMON = {
    'cube': 'DATAcube cube id.',
    'nuts_code': 'Territory code (SK0422_0425 = Košice, okresy Košice I-IV).',
    'nuts_name': 'Territory name.',
    'year': 'Reference year.',
    'period_label': 'Period label as the cube gives it.',
    'indic_code': 'Indicator code (U_CR_…).',
    'indic_name_sk': 'Indicator name, Slovak.',
    'indic_name_en': 'Indicator name, English.',
    'unit_code': 'Unit (UNIT_NR number, UNIT_PERS persons, UNIT_EUR euro, UNIT_VPC percent).',
    'value': 'Value; empty if the cube has none (e.g. confidential).',
}
OUTS = {
    'kosice_accommodation_2025_quarterly.csv': ('cr3805qr', acc, 'one indicator in one period (quarter or year)', {
        **COMMON, 'period': 'Q1..Q4, or YEAR for the whole year (1. - 4. Q.).'}),
    'kosice_visitors_origin_2025_monthly.csv': ('cr3804mr', vis, 'one indicator for one country of origin in one period (month or year)', {
        **COMMON, 'period': 'M01..M12, or YEAR for the whole year (1. - 12.).',
        'origin_code': 'Country of origin: VISIT_TOTAL all visitors, VISIT_DOM domestic, VISIT_FOR foreign, or an ISO country code.',
        'origin_name_sk': 'Origin name, Slovak.', 'origin_name_en': 'Origin name, English.'}),
    'kosice_occupancy_rate_2025.csv': ('cr3805qr', occ, 'one occupancy-rate indicator: quarters, the official year, two averages', {
        'measure': 'Net occupancy rate of permanent bed places or of bedrooms.',
        'indic_code': 'Indicator code (U_CR_0020 bed places, U_CR_0021 bedrooms).',
        'Q1': 'Q1 rate, %.', 'Q2': 'Q2 rate, %.', 'Q3': 'Q3 rate, %.', 'Q4': 'Q4 rate, %.',
        'official_year': 'The office\'s annual rate, % (1. - 4. Q.): the figure to report.',
        'plain_mean_q': 'Plain mean of the four quarterly rates, % (a check, not the annual rate).',
        'weighted_mean_q': 'Mean of the quarters weighted by available bed places (rooms) per day x days, %; '
                           'reproduces the annual rate.'}),
    'kosice_market_shares_2025.csv': ('cr3804mr', shares, 'one country of origin (or total / domestic / foreign / the five '
                                      'study countries) in 2025; capacity from cr3805qr', {
        'year': 'Reference year.',
        'origin_code': 'VISIT_TOTAL, VISIT_DOM, VISIT_FOR, an ISO country code, or FIVE = AT + CZ + HU + PL + UA.',
        'origin_name_en': 'Origin name, English.',
        'visitors': 'Visitors (arrivals) in accommodation establishments, year.',
        'nights': 'Overnight stays, year.', 'avg_nights': 'Nights per visitor.',
        'share_total_visitors_pct': 'Share of all visitors, % (annual totals).',
        'share_total_nights_pct': 'Share of all nights, % (annual totals).',
        'share_foreign_visitors_pct': 'Share of foreign visitors, % (annual totals; study countries only).',
        'share_foreign_nights_pct': 'Share of foreign nights, % (annual totals; study countries only).',
        'monthly_mean_share_total_visitors_pct': 'Plain mean of the 12 monthly shares of all visitors, %.',
        'monthly_mean_share_foreign_visitors_pct': 'Plain mean of the 12 monthly shares of foreign visitors, % '
                                                   '(study countries only).',
        'occupancy_contribution_pp': 'Nights / (available permanent bed places per day x days of the year) x 100: '
                                     'percentage points of the annual net bed-place occupancy rate; VISIT_TOTAL '
                                     'rebuilds the official rate.'}),
}


def write_meta(path, cube, frame, row, cols):
    info = META[cube]['info']
    assert set(frame.columns) == set(cols), (set(frame.columns) ^ set(cols))
    lines = [f'# {path.name} — {info["nameEn"]}', '',
             f'- **Source:** ŠÚ SR DATAcube `{cube}`, *{info["nameSk"].strip()}*',
             f'- **Last data change (cube):** {info["lastDataChange"]}',
             f'- **API call:** `{data_url(cube)}`',
             f'- **Raw response:** `{(API_DIR / f"{cube}_{YEAR}_{AREA}.csv").as_posix()}`',
             '- **Produced by:** notebooks/00_d1_slovakia_tourism_kosice.ipynb',
             f'- **Generated:** {dt.datetime.now().isoformat(timespec="seconds")}',
             f'- **One row is:** {row}', f'- **Rows:** {len(frame):,}', '',
             '| column | description |', '|---|---|']
    lines += [f'| `{c}` | {cols[c]} |' for c in frame.columns]
    Path(f'{path}.meta.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


for name, (cube, frame, row, cols) in OUTS.items():
    p = OUT_DIR / name
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, cube, frame, row, cols)
    print(f'[wrote] {p} ({len(frame)} rows) + .meta.md')
print(f'API calls made in this run: {n_fetched}')
