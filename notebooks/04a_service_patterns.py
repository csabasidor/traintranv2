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
# # 04a — Service patterns of the four networks
#
# The first explore notebook (Part B). It builds **one analysis table** for the four networks — domestic and
# foreign, each direct and with one transfer — from the 02 / 03 outputs alone, and then asks **when** the journeys
# run. Code: `traintranv2/nb04_frame.py`, `nb04_patterns.py`, `nb04_distance.py` (route km).
#
# | § | step | output (`output/kosice/explore/`) |
# |---|---|---|
# | 1 | journeys and the LAU table of the four networks (with route km) | `journeys.parquet`, `lau_table.csv` |
# | 2 | weekday / weekend / month / season patterns per LAU, pattern classes | `service_patterns.csv` |
# | 3 | inbound against outbound | `direction_asymmetry.csv` |
# | 4 | services by type, seasonal-only journeys | `route_types.csv` |
# | 5 | distinct journeys recounted per NUTS3 / NUTS2 / country | `hierarchy.csv` |
# | 6 | coverage at 1, 2 and 5 journeys per day | `coverage_curve.csv` |
#
# **Register items:** REP-8 (calendar treatment: weekdays, weekends, seasons, every exception via the run-date
# masks), CF-20 (no empty weekday pattern), CON-6 (both directions, and how they differ), PIP-9 (services
# included, by type), PIP-10 (distinct journeys, recounted at every level, never summed), CON-8 (coverage at
# measurable thresholds instead of "thin" or "ballpark").
#
# **Units.** A journey is a direct trip, or a first + second train pair (02b / 03b). A journey calling at several
# stations of one LAU is one journey for the LAU. Per-day figures divide by the **run's own window** (domestic
# 364 days; CZ 364, HU 301, AT 276, PL 32 + PL:PL_IC 101, UA 364). Domestic: Slovak LAUs except Košice's own;
# foreign: the LAUs of the destination country.

# %%
import os, sys

# Run from the project root so every relative path resolves the same from notebooks/ or the root.
_here = os.path.abspath('')
if os.path.basename(_here) == 'notebooks':
    os.chdir(os.path.dirname(_here))
sys.path.insert(0, os.getcwd())
print('Working directory:', os.getcwd())

# %%
import time
import numpy as np
import pandas as pd
import traintranv2  # noqa: F401  (PROJ data fix)
from traintranv2.config import default_config
from traintranv2 import nb02_connections as C
from traintranv2 import nb03_foreign as F
from traintranv2 import nb04_frame as FR
from traintranv2 import nb04_patterns as P
from traintranv2.nb01a_feeds import write_meta
from traintranv2.nb01b_stations import load_lau_subset

cfg = default_config()
OUT = os.path.join(cfg.out_dir, 'explore')
os.makedirs(OUT, exist_ok=True)
tags = pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str)
L = C.lau_with_city_units(load_lau_subset(cfg), cfg)          # Košice / Bratislava districts -> one unit each
tags = C.tags_with_city_units(tags, cfg, L)
hub_lau = C.hub_city_laus(cfg)                                 # the whole city of Košice
snap = pd.read_csv(os.path.join(cfg.out_dir, 'station_rail_snap.csv'), dtype={'station_key': str})
runs = F.country_runs(cfg)
days_by_run = {'SK': C.window_days(cfg, cfg.domestic_feed), **{r['run']: r['days'] for r in runs}}
HEADLINE = ['SK'] + [r['run'] for r in runs if r['headline']]

# %% [markdown]
# ## 1. Journeys and the LAU table
#
# Route km (the track distance along the stations the train calls at, both trains on one transfer) is computed once
# from the 01c graph and cached (`route_km_*.parquet`); the first run takes about four minutes.

# %%
t0 = time.time()
j = FR.journeys(cfg, tags, snap)
attrs = FR.lau_attributes(cfg, tags, L)
lau = FR.lau_table(j, attrs)
print(f'{len(j):,} journey x LAU rows, {len(lau):,} LAU rows  [{time.time() - t0:.0f}s]')
display(lau[lau.headline].groupby(['network', 'direction']).agg(laus=('lau_gisco_id', 'size'), population=('population', 'sum'),
                                                               journeys_per_day=('f_per_day', 'sum')).round(1))
assert (lau['mean_days_per_journey'] <= lau['window_days']).all(), 'R / |I| > W: a journey counted twice'
# Route km is missing only where the train's track leaves the six-country network (01c clip): trains on to Germany /
# Switzerland (stations outside_network) and lines through German territory (e.g. Děčín - Šluknov via Sebnitz).
# Košice: none. Those journeys keep their time and frequency; distance-based measures leave them out.
na = j['route_km'].isna()
if na.any():
    print(f'route km missing for {int(na.sum()):,} of {len(j):,} journey x LAU rows (track outside the study network):')
    display(j[na].groupby(['network', 'run']).size().rename('rows').to_frame())
assert na.mean() < 0.001, f'route km missing for {na.mean():.2%} of rows'
print('R / |I| <= W holds for every LAU; route km present for every journey')

# %% [markdown]
# ## 2. Weekday, weekend, month and season
#
# Journeys per day in each slice = run days in the slice / days of the slice in the window. Pattern classes:
# **every_day** (all seven weekdays served at least once), **weekday_only**, **weekend_only**, **partial**. Every LAU
# with a journey gets a pattern (the legacy run left 517 of 559 Czech one-hop LAUs with an empty weekday pattern,
# CF-20).

# %%
pat = P.lau_patterns(j, days_by_run)
assert pat['pattern'].notna().all() and (pat['all'] > 0).all(), 'a LAU without a pattern'
cls = pat[pat.run.isin(HEADLINE)].groupby(['network', 'direction', 'pattern']).size().unstack(fill_value=0)
display(cls)
x = pat[pat.run.isin(HEADLINE) & (pat.direction == 'inbound')]
print('weekend against weekday service, inbound (median over LAUs of weekend / weekday journeys per day):')
display(x.assign(ratio=x['weekend'] / x['weekday'].replace(0, np.nan)).groupby(['network', 'run'])['ratio'].median().round(2).unstack())
print('journeys per day by season, inbound, summed over LAUs (domestic and the full-year runs):')
display(x[x.run.isin(['SK', 'CZ', 'UA'])].groupby(['network', 'run'])[['DJF', 'MAM', 'JJA', 'SON']].sum().round(1))

# %% [markdown]
# ## 3. Inbound against outbound
#
# Both directions are computed from the timetable, never mirrored (CON-6). Per LAU: journeys per day and median
# journey time each way, and the differences.

# %%
w = lau.pivot_table(index=['network', 'run', 'lau_gisco_id'], columns='direction',
                    values=['f_per_day', 'time_median_min'], aggfunc='first')
w.columns = [f'{a}_{b}' for a, b in w.columns]
asym = w.reset_index().rename(columns={'f_per_day_inbound': 'f_inbound', 'f_per_day_outbound': 'f_outbound',
                                       'time_median_min_inbound': 'time_inbound', 'time_median_min_outbound': 'time_outbound'})
asym['f_diff'] = asym['f_inbound'] - asym['f_outbound']
asym['time_diff'] = asym['time_inbound'] - asym['time_outbound']
asym['population'] = asym['lau_gisco_id'].map(attrs.set_index('lau_gisco_id')['population'])
asym = asym[['network', 'run', 'lau_gisco_id', 'f_inbound', 'f_outbound', 'time_inbound', 'time_outbound', 'f_diff',
             'time_diff', 'population']]
h = asym[asym.run.isin(HEADLINE)]
summ = h.groupby('network').agg(laus=('lau_gisco_id', 'size'),
                                one_way_only=('f_diff', lambda s: int(s.isna().sum())),
                                f_diff_median=('f_diff', 'median'),
                                f_diff_abs_p90=('f_diff', lambda s: s.abs().quantile(0.9)),
                                time_diff_median=('time_diff', 'median'),
                                time_diff_abs_p90=('time_diff', lambda s: s.abs().quantile(0.9)))
display(summ.round(2))
print('largest asymmetries in journeys per day (headline runs):')
display(h.reindex(h['f_diff'].abs().sort_values(ascending=False).index).head(10)
        .assign(name=lambda d: d['lau_gisco_id'].map(attrs.set_index('lau_gisco_id')['lau_name'])))

# %% [markdown]
# ## 4. Services by type, and seasonal-only journeys
#
# Every rail trip running in the window is included (bus routes and excluded agencies are left out in 01b / 02).
# GTFS `route_type`: 100 long distance, 102 / 103 express / interregional, 105 sleeper, 106 regional, 2 rail (feeds
# with basic types). A journey is **seasonal-only** if all its run days fall in one season; this is judged only for
# runs whose window spans all four seasons (empty for PL, 32 and 101 summer days). Reservation-only or
# restricted services are not identifiable in these feeds; they are included like any other trip (PIP-9).

# %%
rt = {}
for run, days in days_by_run.items():
    feeds = [cfg.domestic_feed] + ([] if run == 'SK' else next(r['feeds'] for r in runs if r['run'] == run))
    for f in feeds:
        _, trips = C.load_timetable(cfg, f, tags, days)
        rt.update({(run, f + '|' + t): str(v) for t, v in zip(trips['trip_id'], trips['route_type'])})


def route_types(row):
    legs = row['journey'].split('>')
    return ' > '.join(rt.get((row['run'], leg), '?') for leg in legs)


u = j.drop_duplicates(['network', 'run', 'journey']).copy()
u['route_types'] = u.apply(route_types, axis=1)
seas = {}
for run, g in u.groupby('run'):
    sl = P.slices(days_by_run[run])
    c, _ = P.day_counts(g['mask'].tolist(), days_by_run[run])
    if not all(s in c for s in ('DJF', 'MAM', 'JJA', 'SON')):
        seas.update({i: np.nan for i in g.index})        # the window does not span the year
        continue
    one = np.zeros(len(g), bool)
    for s in ('DJF', 'MAM', 'JJA', 'SON'):
        one |= (c[s].to_numpy() == g['n_days'].to_numpy()) & (g['n_days'].to_numpy() > 0)
    seas.update(dict(zip(g.index, one.astype(float))))
u['seasonal_only'] = u.index.map(seas)
types = (u.groupby(['network', 'run', 'route_types'])
         .agg(journeys=('journey', 'size'), run_days=('n_days', 'sum'),
              seasonal_only=('seasonal_only', lambda s: s.sum(min_count=1)))
         .reset_index().sort_values(['network', 'run', 'run_days'], ascending=[True, True, False]))
display(types[types.run.isin(HEADLINE)].groupby(['network', 'run']).head(4))
print('sleeper (105) journeys:', int(types.loc[types.route_types.str.contains('105'), 'journeys'].sum()),
      '| seasonal-only journeys (full-year runs):', int(types['seasonal_only'].sum()))

# %% [markdown]
# ## 5. Distinct journeys per region
#
# A train serving five LAUs of one region is **one** journey for the region (PIP-10): regions are recounted from the
# journeys, never summed from LAU counts.

# %%
jj = j.merge(attrs[['lau_gisco_id', 'nuts2_id', 'nuts3_id']], on='lau_gisco_id', how='left')
hier = []
for level, col in [('nuts3', 'nuts3_id'), ('nuts2', 'nuts2_id'), ('country', 'country')]:
    r = P.recount(jj[jj[col].notna()], col).rename(columns={col: 'region'})
    hier.append(r.assign(level=level))
hier = pd.concat(hier, ignore_index=True)[['network', 'run', 'direction', 'level', 'region', 'n_journeys', 'run_days',
                                           'window_days', 'n_lau', 'f_per_day']]
ctry = hier[(hier.level == 'country') & hier.run.isin(HEADLINE) & (hier.direction == 'inbound')]
summed = lau[lau.run.isin(HEADLINE) & (lau.direction == 'inbound')].groupby(['network', 'run'])['f_per_day'].sum()
display(ctry.set_index(['network', 'run'])[['region', 'n_journeys', 'n_lau', 'f_per_day']]
        .assign(sum_of_lau_f=summed).round(1))
print('sum_of_lau_f is what summing LAU figures would give: the double counting the recount avoids')

# %% [markdown]
# ## 6. Coverage at 1, 2 and 5 journeys per day (CON-8)
#
# LAUs and population with at least k journeys per day, by network, country and direction — measurable thresholds
# in place of "thin" or "ballpark".

# %%
curve = P.coverage_curve(lau[lau.run.isin(HEADLINE)])
display(curve[curve.direction == 'inbound'].pivot_table(index=['network', 'country'], columns='min_per_day',
                                                         values='population', aggfunc='sum').map(lambda v: f'{v:,.0f}'))

# %% [markdown]
# ## 7. Outputs

# %%
p = os.path.join(OUT, 'journeys.parquet')
j.to_parquet(p, index=False)
write_meta(p, 'explore_journeys', j, {'Built from': '02a, 02b, 03a, 03b outputs'})
print(f'[wrote] {p} ({len(j):,} rows)')
for name, key, frame in [('lau_table.csv', 'explore_lau_table', lau),
                         ('service_patterns.csv', 'explore_service_patterns', pat),
                         ('direction_asymmetry.csv', 'explore_direction_asymmetry', asym),
                         ('route_types.csv', 'explore_route_types', types),
                         ('hierarchy.csv', 'explore_hierarchy', hier),
                         ('coverage_curve.csv', 'explore_coverage_curve', curve)]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Built from': '02a, 02b, 03a, 03b outputs'})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')
