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
# # 03d — Same-day visits to Košice from abroad, direct or with one transfer
#
# As 03c, but each way may also be a **one-transfer** journey from 03b (`foreign/one_transfer_itins.parquet`): a ZSR
# train to / from Košice plus a ZSR or national train abroad. The LAUs **added** beyond 03c are what a transfer brings.
#
# | § | step | output (`output/kosice/foreign/`) |
# |---|---|---|
# | 1 | options: inbound (home → Košice) and outbound (Košice → home), per country run | — |
# | 2 | day-trip days per station and per LAU | `daytrip_one_transfer_station.csv`, `daytrip_one_transfer_lau.csv` |
# | 3 | coverage per country with its denominators | `daytrip_one_transfer_coverage.csv` |
# | 4 | dwell sensitivity (VAL-3) | `daytrip_one_transfer_sensitivity.csv` |
# | 5 | against the legacy run | — |
#
# **Rule** (register PIP-16): on one date, an inbound option **arriving by** `daytrip_max_arrival`, at least
# `daytrip_min_dwell_min` in Košice, and an outbound option **leaving at or after** `daytrip_min_departure` and **back
# by** `daytrip_max_return`. Service-day clock, no wrap: an overnight arrival (after 24:00) or a return after 23:59 is
# not a same-day visit. Each country run on its own window (03a); `daytrip_share` = days / window days.

# %%
import os, sys

# Run from the project root so every relative path resolves the same from notebooks/ or the root.
_here = os.path.abspath('')
if os.path.basename(_here) == 'notebooks':
    os.chdir(os.path.dirname(_here))
sys.path.insert(0, os.getcwd())
print('Working directory:', os.getcwd())

# %%
import pandas as pd
import traintranv2  # noqa: F401  (PROJ data fix)
from traintranv2.config import default_config
from traintranv2 import nb02_connections as C
from traintranv2 import nb03_foreign as F
from traintranv2.nb01a_feeds import write_meta
from traintranv2.nb01b_stations import load_lau_subset

KIND = 'one_transfer'
cfg = default_config()
OUT = os.path.join(cfg.out_dir, 'foreign')
tags = pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str)
L = C.lau_with_city_units(load_lau_subset(cfg), cfg)          # Košice / Bratislava districts -> one unit each
tags = C.tags_with_city_units(tags, cfg, L)
hub_lau = C.hub_city_laus(cfg)                                 # the whole city of Košice
snap = pd.read_csv(os.path.join(cfg.out_dir, 'station_rail_snap.csv'), dtype={'station_key': str})
geo = tags.set_index('station_key')
lau_of = F.station_lau(tags, cfg)
pop, pop_year = F.lau_population(L)
lau_geo = tags.drop_duplicates('lau_gisco_id').set_index('lau_gisco_id')[['lau_name_national', 'nuts3_id', 'degurba']]
runs = F.country_runs(cfg)
print(f'rule: arrive by {cfg.daytrip_max_arrival}, dwell >= {cfg.daytrip_min_dwell_min} min, depart >= {cfg.daytrip_min_departure}, '
      f'back by {cfg.daytrip_max_return}; dwell sensitivity {cfg.daytrip_dwell_sensitivity}')

# %% [markdown]
# ## 1. Options

# %%
legs = pd.read_parquet(os.path.join(OUT, 'direct_legs.parquet'))
opts = legs.rename(columns={'dep_s': 'start_s', 'arr_s': 'end_s'})[['run', 'direction', 'station_key', 'lau_gisco_id', 'start_s', 'end_s', 'mask']].assign(kind='direct')
if KIND == 'one_transfer':
    it = pd.read_parquet(os.path.join(OUT, 'one_transfer_itins.parquet'))
    opts = pd.concat([opts, it[['run', 'direction', 'station_key', 'lau_gisco_id', 'start_s', 'end_s', 'mask']].assign(kind='one_transfer')],
                     ignore_index=True)
print(opts.groupby(['run', 'direction', 'kind']).agg(options=('mask', 'size'), stations=('station_key', 'nunique')).unstack('direction'))

# %% [markdown]
# ## 2. Day-trip days per station and per LAU

# %%
station, lau = [], []
for r in runs:
    N, W = len(r['days']), F.run_window(r)
    o = opts[opts.run == r['run']]
    inb, outb = o[o.direction == 'inbound'], o[o.direction == 'outbound']
    if inb.empty or outb.empty:
        continue
    station.append(C.daytrip_days(inb, outb, cfg, N, by='station_key').assign(country=r['country'], run=r['run'], **W))
    lau.append(C.daytrip_days(inb, outb, cfg, N, by='lau_gisco_id').assign(country=r['country'], run=r['run'], **W))
station = pd.concat(station, ignore_index=True)
station['lau_gisco_id'] = station['station_key'].map(lau_of)
station = (station.join(geo['stop_name'], on='station_key').join(lau_geo, on='lau_gisco_id')
           .join(snap.set_index('station_key')['rail_km'], on='station_key'))
station = station[['country', 'run', 'station_key', 'stop_name', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba',
                   'n_daytrip_days', 'daytrip_share', 'rail_km', 'window_start', 'window_end', 'window_days']]
lau = pd.concat(lau, ignore_index=True).join(lau_geo, on='lau_gisco_id')
lau['population'] = lau['lau_gisco_id'].map(pop)
lau['pop_year'] = lau['lau_gisco_id'].map(pop_year)
lau = lau[['country', 'run', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba', 'population', 'pop_year',
           'n_daytrip_days', 'daytrip_share', 'window_start', 'window_end', 'window_days']]
print(f"LAUs with >= 1 day-trip day: {lau.groupby('run').size().to_dict()}")
display(lau.sort_values('population', ascending=False).head(15))

# %% [markdown]
# ## 3. Coverage, with its denominators
#
# Per country: **all** LAUs; **served** (an option in both directions); a same-day visit on **at least one** day,
# on **≥ 50 %** and on **≥ 90 %** of the run's days.

# %%
rows = []
for r in runs:
    c = r['country']
    allc = set(L.loc[L['CNTR_CODE'] == c, 'GISCO_ID'])
    o = opts[opts.run == r['run']]
    served = set(o.loc[o.direction == 'inbound', 'lau_gisco_id']) & set(o.loc[o.direction == 'outbound', 'lau_gisco_id'])
    sh = lau[lau.run == r['run']].set_index('lau_gisco_id')['daytrip_share']
    for g, ids in [('all_lau', allc), ('served', served), ('daytrip_any', set(sh.index)),
                   ('daytrip_50', set(sh[sh >= 0.5].index)), ('daytrip_90', set(sh[sh >= 0.9].index))]:
        ids = ids & allc
        rows.append({'country': c, 'run': r['run'], 'group': g, 'n_lau': len(ids), 'population': pop.reindex(list(ids)).sum(),
                     **F.run_window(r)})
cov = pd.DataFrame(rows)
base = cov[cov.group == 'all_lau'].set_index('run')
cov['share_lau'] = (cov['n_lau'] / cov['run'].map(base['n_lau'])).round(4)
cov['share_population'] = (cov['population'] / cov['run'].map(base['population'])).round(5)
cov = cov[['country', 'run', 'group', 'n_lau', 'population', 'share_lau', 'share_population', 'window_start', 'window_end', 'window_days']]
display(cov.pivot_table(index='run', columns='group', values='n_lau', aggfunc='sum'))
display(cov.pivot_table(index='run', columns='group', values='population', aggfunc='sum').map(lambda v: f'{v:,.0f}'))

# %%
# LAUs added by a transfer: same-day visit possible here, not with direct trains only (03c)
d03c = pd.read_csv(os.path.join(OUT, 'daytrip_direct_lau.csv'), dtype={'lau_gisco_id': str})
added = []
for r in runs:
    a = set(lau.loc[lau.run == r['run'], 'lau_gisco_id']) - set(d03c.loc[d03c.run == r['run'], 'lau_gisco_id'])
    added.append({'run': r['run'], 'lau_added_by_transfer': len(a), 'pop_added_by_transfer': pop.reindex(list(a)).sum()})
display(pd.DataFrame(added))

# %% [markdown]
# ## 4. Dwell sensitivity (VAL-3)

# %%
sens = []
for r in runs:
    N = len(r['days'])
    o = opts[opts.run == r['run']]
    inb, outb = o[o.direction == 'inbound'], o[o.direction == 'outbound']
    for dwell in sorted(cfg.daytrip_dwell_sensitivity):
        d = C.daytrip_days(inb, outb, cfg, N, by='lau_gisco_id', dwell_min=dwell) if len(inb) and len(outb) else \
            pd.DataFrame(columns=['lau_gisco_id', 'daytrip_share'])
        h = d[d.daytrip_share >= 0.5]
        sens.append({'country': r['country'], 'run': r['run'], 'dwell_min': dwell, 'is_base': dwell == cfg.daytrip_min_dwell_min,
                     'n_lau_any': len(d), 'pop_any': pop.reindex(list(d['lau_gisco_id'])).sum(),
                     'n_lau_50': len(h), 'pop_50': pop.reindex(list(h['lau_gisco_id'])).sum(), **F.run_window(r)})
sens = pd.DataFrame(sens)
display(sens.drop(columns=['window_start', 'window_end']))

# %% [markdown]
# ## 5. Against the legacy run
#
# The legacy run wrote `ke_daytrip_onehop_station.csv` (its own station ids); matched by station name for the stations abroad.

# %%
old = pd.read_csv('output/ke/ke_daytrip_onehop_station.csv', encoding='utf-8-sig').merge(
    pd.read_csv('output/ke/station_catalog.csv', encoding='utf-8-sig', dtype=str)[['station_id', 'name', 'country']], on='station_id')
old = old[(old['country'] != 'SK') & (old['n_daytrip_days'] > 0)][['name', 'country', 'n_daytrip_days']].rename(columns={'name': 'stop_name', 'n_daytrip_days': 'legacy_days'})
new = station[station.run.isin([r['run'] for r in runs if r['headline']])][['stop_name', 'country', 'n_daytrip_days', 'window_days']]
cmpd = new.merge(old, on='stop_name', how='outer', indicator=True)
print(cmpd['_merge'].value_counts().to_dict())
both = cmpd[cmpd._merge == 'both']
print(f"matched {len(both)} stations; the legacy run used the 364-day window for every country")
display(both.head(20))
display(cmpd[cmpd._merge != 'both'].head(20))

# %% [markdown]
# ## 6. Outputs

# %%
for name, key, frame in [(f'daytrip_{KIND}_station.csv', f'foreign_daytrip_{KIND}_station', station),
                         (f'daytrip_{KIND}_lau.csv', f'foreign_daytrip_{KIND}_lau', lau),
                         (f'daytrip_{KIND}_coverage.csv', f'foreign_daytrip_{KIND}_coverage', cov),
                         (f'daytrip_{KIND}_sensitivity.csv', f'foreign_daytrip_{KIND}_sensitivity', sens)]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Rule': f'arrive <= {cfg.daytrip_max_arrival}, dwell >= {cfg.daytrip_min_dwell_min} min, '
                                       f'depart >= {cfg.daytrip_min_departure}, back <= {cfg.daytrip_max_return}'})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')
