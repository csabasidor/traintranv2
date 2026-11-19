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
# # 03a — Direct trains between Košice and places abroad
#
# The first foreign piece (03a–03d): **direct trains between the Košice hub and stations in Czechia, Hungary,
# Austria, Poland and Ukraine**, both directions. Same engine and counting as 02a
# (`traintranv2/nb02_connections.py`); the foreign runs are in `traintranv2/nb03_foreign.py`.
#
# | § | step | output (`output/kosice/foreign/`) |
# |---|---|---|
# | 1 | one run per destination country: feeds and window | — |
# | 2 | direct ZSR trips to / from stations of the country | `direct_legs.parquet` |
# | 3 | per station and per LAU (distinct trips), with the full-year figure | `direct_station.csv`, `direct_lau.csv` |
# | 4 | coverage per country with its denominators | `direct_coverage.csv` |
# | 5 | against the legacy run | — |
#
# **Rules** (Reviewer 1, register CON-6, CON-10, PIP-4, PIP-10, STA-6):
# * **Only the domestic feed (ZSR_SK) reaches Košice** in this analysis: a direct train is a ZSR trip calling at the
#   hub and at a station abroad. (The Ukrainian feed also contains Košice; its own trains are not used — every
#   itinerary leaves or reaches Košice on a ZSR train.)
# * **One run per destination country, on the window its feeds share with ZSR_SK** (01a `windows.json`). 03b combines
#   ZSR with the country's own feed(s); 03a uses the same window so that direct and one-transfer figures for a
#   country are comparable. The ZSR figure on its full 364 days is given beside it (`journeys_per_day_364`).
#
#   | country | feeds | window |
#   |---|---|---|
#   | CZ | ZSR_SK + DRAHY_CZ | 364 days |
#   | HU | ZSR_SK + MAV_HU | 301 days (Jan–Nov 2026) |
#   | AT | ZSR_SK + BAHN_AT | 276 days (Mar–Dec 2026) |
#   | PL | ZSR_SK + PL_IC + PL_REG | **32 days (5 June – 6 July 2026)**, early summer: seasonal trains included |
#   | PL:PL_IC (sensitivity) | ZSR_SK + PL_IC | 101 days (May–Aug 2026) |
#   | UA | ZSR_SK + UKRZ_UA | 364 days |
#
# * **Observed within the available feeds** (CON-10): a place without a direct train here has none in these feeds on
#   these windows.
# * Run dates, times without wrap at 24:00, the hub group and distinct-trip counting are those of 02a.
# * **A station's LAU abroad comes from the national feed** (`nb03_foreign.station_lau`): a ZSR station takes the LAU
#   of its group's station in the country's own feed. ZSR's point of Hidasnémeti lies in the neighbouring
#   Tornyosnémeti; MÁV's in Hidasnémeti (likewise Neudorf b.Parndorf, Bruck/Leitha, Petrov u Strážnice).
# * **Population**: end-2025 where available; Ukraine has 2024 only (`pop_year`).

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

cfg = default_config()
OUT = os.path.join(cfg.out_dir, 'foreign')
os.makedirs(OUT, exist_ok=True)
tags = pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str)
L = C.lau_with_city_units(load_lau_subset(cfg), cfg)          # Košice / Bratislava districts -> one unit each
tags = C.tags_with_city_units(tags, cfg, L)
hub_lau = C.hub_city_laus(cfg)                                 # the whole city of Košice
snap = pd.read_csv(os.path.join(cfg.out_dir, 'station_rail_snap.csv'), dtype={'station_key': str})
geo = tags.set_index('station_key')
lau_of = F.station_lau(tags, cfg)
hubs = C.hub_groups(cfg, tags)
pop, pop_year = F.lau_population(L)
lau_geo = tags.drop_duplicates('lau_gisco_id').set_index('lau_gisco_id')[['lau_name_national', 'nuts3_id', 'degurba']]
runs = F.country_runs(cfg)

# %% [markdown]
# ## 1. Runs: destination country, feeds, window

# %%
display(pd.DataFrame([{'run': r['run'], 'country': r['country'], 'feeds': ' + '.join([cfg.domestic_feed] + r['feeds']),
                       **F.run_window(r), 'headline': r['headline']} for r in runs]))

# %% [markdown]
# ## 2. Direct trips, inbound and outbound

# %%
legs = []
for r in runs:
    tt = {cfg.domestic_feed: C.load_timetable(cfg, cfg.domestic_feed, tags, r['days'])}
    legs.append(F.run_direct(cfg, r, tt, tags, hubs).assign(**F.run_window(r)))
legs = pd.concat(legs, ignore_index=True)
print(legs.groupby(['run', 'direction']).agg(trips=('trip_id', 'nunique'), stations=('station_key', 'nunique'),
                                             laus=('lau_gisco_id', 'nunique')).unstack('direction'))

# %% [markdown]
# ## 3. Per station and per LAU
#
# Distinct trips per unit; a train calling at several stations of one LAU counts once for it. `journeys_per_day_364` is
# the same LAU on ZSR's full window (02a's legs), to show what the shorter country windows leave out.

# %%
full = pd.read_parquet(os.path.join(cfg.out_dir, 'domestic', 'direct_legs.parquet'))
full = full[full['nuts_rg_01_country_id'] != 'SK'].assign(lau_gisco_id=lambda d: d['station_key'].map(lau_of))
n_full = len(C.window_days(cfg, cfg.domestic_feed))
station, lau = [], []
for r in runs:
    N, W = len(r['days']), F.run_window(r)
    x = legs[legs.run == r['run']]
    for d in ('inbound', 'outbound'):
        xd = x[x.direction == d]
        if xd.empty:
            continue
        s = C.summarise(xd, 'station_key', ['trip_id'], N).assign(direction=d, country=r['country'], run=r['run'], **W)
        station.append(s)
        l = C.summarise(xd, 'lau_gisco_id', ['trip_id'], N).assign(direction=d, country=r['country'], run=r['run'], **W)
        l['n_stations'] = l['lau_gisco_id'].map(xd.groupby('lau_gisco_id')['station_key'].nunique())
        fd = full[full.direction == d]
        ref = C.summarise(fd, 'lau_gisco_id', ['trip_id'], n_full).set_index('lau_gisco_id')['journeys_per_day']
        l['journeys_per_day_364'] = l['lau_gisco_id'].map(ref).round(3)
        lau.append(l)
st_cols = ['stop_name', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba']
station = pd.concat(station, ignore_index=True)
station['lau_gisco_id'] = station['station_key'].map(lau_of)
station = (station.join(geo['stop_name'], on='station_key').join(lau_geo, on='lau_gisco_id')
           .join(snap.set_index('station_key')[['rail_km', 'geo_km']], on='station_key'))
station = station[['country', 'run', 'station_key'] + st_cols + ['direction', 'n_journeys', 'journeys_per_day', 'service_days',
                  'service_share', 'min_time_min', 'median_time_min', 'rail_km', 'geo_km', 'window_start', 'window_end', 'window_days']]
lau = pd.concat(lau, ignore_index=True).join(lau_geo, on='lau_gisco_id')
lau['population'] = lau['lau_gisco_id'].map(pop)
lau['pop_year'] = lau['lau_gisco_id'].map(pop_year)
lau = lau[['country', 'run', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba', 'population', 'pop_year', 'n_stations',
           'direction', 'n_journeys', 'journeys_per_day', 'service_days', 'service_share', 'min_time_min', 'median_time_min',
           'journeys_per_day_364', 'window_start', 'window_end', 'window_days']]
display(lau[(lau.direction == 'inbound')].sort_values(['run', 'journeys_per_day'], ascending=[True, False])
        [['run', 'lau_name_national', 'population', 'n_stations', 'journeys_per_day', 'journeys_per_day_364', 'service_share',
          'min_time_min']])

# %% [markdown]
# ## 4. Coverage, with its denominators
#
# Per country: **all** its LAUs, the LAUs **with a station** of the run's feeds (ZSR stations abroad included), and
# those **served directly**.

# %%
rows = []
for r in runs:
    c = r['country']
    allc = L.loc[L['CNTR_CODE'] == c, 'GISCO_ID']
    feeds = [cfg.domestic_feed] + r['feeds']
    with_station = set(tags.loc[tags.feed_key.isin(feeds) & (tags.nuts_rg_01_country_id == c), 'lau_gisco_id'])
    for d in ('inbound', 'outbound'):
        served = set(lau.loc[(lau.run == r['run']) & (lau.direction == d), 'lau_gisco_id'])
        for g, ids in [('all_lau', set(allc)), ('with_station', with_station), ('direct', served)]:
            ids = ids & set(allc)
            rows.append({'country': c, 'run': r['run'], 'direction': d, 'group': g, 'n_lau': len(ids),
                         'population': pop.reindex(list(ids)).sum(), **F.run_window(r)})
cov = pd.DataFrame(rows)
base = cov[cov.group == 'all_lau'].set_index(['run', 'direction'])
k = list(zip(cov['run'], cov['direction']))
cov['share_lau'] = (cov['n_lau'] / base['n_lau'].reindex(k).to_numpy()).round(4)
cov['share_population'] = (cov['population'] / base['population'].reindex(k).to_numpy()).round(5)
cov = cov[['country', 'run', 'direction', 'group', 'n_lau', 'population', 'share_lau', 'share_population',
           'window_start', 'window_end', 'window_days']]
display(cov[cov.direction == 'inbound'].pivot_table(index='run', columns='group', values=['n_lau', 'population'], aggfunc='sum'))

# %% [markdown]
# ## 5. Against the legacy run (`output/ke`)
#
# The legacy run (`journey_efficiency_foreign_direct.csv`) counted direct trains per LAU on the domestic 364-day
# window with DEGURBA-2021 LAU codes; it matched only CZ, HU and UA stations. Compared here with
# `journeys_per_day_364` (the same window), inbound.

# %%
old = pd.read_csv('output/ke/journey_efficiency_foreign_direct.csv', encoding='utf-8-sig')[['euc_lau_code', 'euc_lau_national', 'country', 'avg_per_day']]
new = lau[(lau.direction == 'inbound') & lau.run.isin([r['run'] for r in runs if r['headline']])][['lau_gisco_id', 'lau_name_national', 'country', 'journeys_per_day_364']]
cmpd = new.merge(old, left_on='lau_gisco_id', right_on='euc_lau_code', how='outer', indicator=True)
print(cmpd['_merge'].value_counts().to_dict())
print('LAUs per country, new vs legacy:', new.groupby('country').size().to_dict(), old.groupby('country').size().to_dict())
both = cmpd[cmpd._merge == 'both'].copy()
both['diff'] = (both['journeys_per_day_364'] - both['avg_per_day']).round(2)
print(f"matched {len(both)} LAUs: |diff| < 0.05 for {(both['diff'].abs() < 0.05).sum()}")
display(both.reindex(both['diff'].abs().sort_values(ascending=False).index)
        [['lau_name_national', 'country_x', 'journeys_per_day_364', 'avg_per_day', 'diff']].head(12))
display(cmpd[cmpd._merge != 'both'][['lau_gisco_id', 'lau_name_national', 'euc_lau_code', 'euc_lau_national', 'country_x', 'country_y', '_merge']])

# %% [markdown]
# ## 6. Outputs

# %%
legs_out = legs[['feed_key', 'trip_id', 'direction', 'station_key', 'group', 'hub_key', 'dep_s', 'arr_s', 'ride_s', 'route_type',
                 'n_days', 'mask', 'lau_gisco_id', 'country', 'run', 'window_start', 'window_end', 'window_days']]
p = os.path.join(OUT, 'direct_legs.parquet')
legs_out.to_parquet(p, index=False)
write_meta(p, 'foreign_direct_legs', legs_out, {'Runs': '; '.join(r['run'] for r in runs)})
print(f'[wrote] {p} ({len(legs_out):,} rows)')
for name, key, frame in [('direct_station.csv', 'foreign_direct_station', station),
                         ('direct_lau.csv', 'foreign_direct_lau', lau),
                         ('direct_coverage.csv', 'foreign_direct_coverage', cov)]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Runs': '; '.join(r['run'] for r in runs)})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')
