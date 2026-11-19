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
# # 04b — Distance, journey time and journey efficiency
#
# Metric definitions §1–4 on the analysis table of 04a (`explore/journeys.parquet`, `lau_table.csv`): journey time,
# three distances, detour factors, journey efficiency, and the checks Reviewer 1 asks for. Code:
# `traintranv2/nb04_distance.py`.
#
# | § | step | output (`output/kosice/explore/`) |
# |---|---|---|
# | 1 | three distances per journey and LAU: route, shortest path, straight line; detour factors | `detour_summary.csv` |
# | 2 | route km against the distances the feeds publish (UZ, ÖBB, ČD) | `route_validation.csv` |
# | 3 | network length: track-km and line-km (01c) | — |
# | 4 | journey efficiency e = τ̄ / r̄, network means, Δ and Δ̂; the cut-off | `efficiency_lau.csv`, `efficiency_summary.csv` |
# | 5 | ratio of means against mean of ratios (PIP-14) | — |
# | 6 | which distance: route, shortest path or straight line | — |
# | 7 | against the legacy run | — |
#
# **Distances** (Reviewer 1: "the geometrically shortest path may not represent the line actually used by a train";
# register PIP-11, PIP-12, PIP-14):
# * **route km** — the track distance along the stations the train calls at, summed over both trains on one transfer
#   (`nb04_distance`): the distance the passenger travels. **Used for efficiency.**
# * **rail km** — 01c's shortest track path from the Košice station to the station: a lower bound.
# * **geo km** — the straight line (geodesic).
#
# The same distance is used for every network (the legacy foreign charts divided by the straight line, the domestic
# ones by rail km).

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
from traintranv2 import nb04_distance as D
from traintranv2.nb01b_stations import load_lau_subset
from traintranv2 import nb04_frame as FR  # noqa: F401  (registers the 04 schemas)
from traintranv2.nb01a_feeds import write_meta
from traintranv2.nb01c_rail_network import RailGraph

cfg = default_config()
OUT = os.path.join(cfg.out_dir, 'explore')
tags = pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str)
tags = C.tags_with_city_units(tags, cfg, C.lau_with_city_units(load_lau_subset(cfg), cfg))
snap = pd.read_csv(os.path.join(cfg.out_dir, 'station_rail_snap.csv'), dtype={'station_key': str})
j = pd.read_parquet(os.path.join(OUT, 'journeys.parquet'))
lau = pd.read_csv(os.path.join(OUT, 'lau_table.csv'), dtype={'lau_gisco_id': str})
HEAD = lau['headline'].astype(str).eq('True')
lau = lau[HEAD].copy()
j = j[j['headline']].copy()
NETS = ['domestic_direct', 'domestic_one_transfer', 'foreign_direct', 'foreign_one_transfer']
print(f'{len(j):,} journeys, {len(lau):,} LAU rows (headline runs)')

# %% [markdown]
# ## 1. Three distances and the detour factors
#
# Per journey: route km against the straight line (how far the train travels for the distance covered), shortest
# path against the straight line (the network's own detour, spec §2 δ), and route against shortest path (how much the
# shortest path understates the trip). A route below the shortest path is impossible except for trains leaving from
# Košice predmestie, 1.6 km nearer some lines than the Košice station that rail km starts from.

# %%
x = j.assign(route_geo=j.route_km / j.geo_km, rail_geo=j.rail_km / j.geo_km, route_rail=j.route_km / j.rail_km)
q = [0.05, 0.25, 0.5, 0.75, 0.95]
rows = []
for net, g in x.groupby('network'):
    for col in ('route_geo', 'rail_geo', 'route_rail'):
        s = g[col].replace([np.inf, -np.inf], np.nan).dropna()
        rows.append({'network': net, 'ratio': col, 'n': len(s), **{f'p{int(v * 100)}': round(s.quantile(v), 3) for v in q}})
detour = pd.DataFrame(rows)
display(detour.pivot(index='network', columns='ratio', values='p50'))
below = x[(x.route_km < x.rail_km - 2)]
print(f'journeys with route km more than 2 km below rail km: {len(below)} of {len(x):,}')
far = x[x.route_rail > 3].groupby('network').size()
print('journeys with route km > 3 x rail km (out-and-back via a distant transfer station):', far.to_dict())

# %% [markdown]
# ## 2. Route km against the distances the feeds publish
#
# Three feeds publish their own distance along the stops (`shape_dist_traveled`, metres): UKRZ_UA, BAHN_AT, DRAHY_CZ.
# For consecutive station pairs of a sample of their trips, route km between the pair (the OSM track graph) is set
# against the published distance. This validates the distance method on operator data (Reviewer 1: "validation
# against actual scheduled route distances"). ZSR_SK and MÁV publish no distances.

# %%
g = RailGraph.load(os.path.join(cfg.out_dir, 'rail_graph.npz'))
adj, nodes = g.csr(), D.station_nodes(snap, tags)
val = []
for feed in ['UKRZ_UA', 'BAHN_AT', 'DRAHY_CZ']:
    t0 = time.time()
    p = D.published_pairs(cfg, feed, tags, max_trips=400)
    p['route_km'] = D.pair_km(adj, nodes, list(zip(p['a'], p['b'])))
    p['published_km'] = p['published'] / 1000
    val.append(p.dropna(subset=['route_km']).assign(feed=feed))
    print(f'{feed}: {len(p):,} station pairs [{time.time() - t0:.0f}s]')
val = pd.concat(val, ignore_index=True)
val['ratio'] = val['route_km'] / val['published_km']
vs = val.groupby('feed').agg(pairs=('ratio', 'size'), median=('ratio', 'median'),
                             p05=('ratio', lambda s: s.quantile(0.05)), p95=('ratio', lambda s: s.quantile(0.95)),
                             within_5pct=('ratio', lambda s: ((s - 1).abs() <= 0.05).mean()),
                             within_10pct=('ratio', lambda s: ((s - 1).abs() <= 0.10).mean())).round(3)
display(vs)
nm = tags.set_index('station_key')['stop_name']
print('largest relative differences:')
display(val.reindex((val['ratio'] - 1).abs().sort_values(ascending=False).index).head(10)
        .assign(a=lambda d: d['a'].map(nm), b=lambda d: d['b'].map(nm))[['feed', 'a', 'b', 'route_km', 'published_km', 'ratio']])

# %% [markdown]
# ## 3. Network length: track-km and line-km
#
# From 01c §3b. Track-km is the summed length of the OSM ways (each mapped track counts); line-km counts parallel
# tracks of one line once. Distances above are shortest paths and are not affected by parallel tracks.

# %%
display(pd.read_csv(os.path.join(cfg.out_dir, 'rail_network_length.csv')))

# %% [markdown]
# ## 4. Journey efficiency
#
# Spec §3, on route km: **e_ℓ = τ̄_ℓ / r̄_ℓ** (minutes per km; v = 60 / e km/h), defined for r̄ above a cut-off. Per
# network: the **trip-weighted mean** ē (weights f_ℓ, journeys per day) and the **median**, Δ_ℓ = e_ℓ − ē (a signed
# difference) and Δ̂_ℓ = e_ℓ / ē (a ratio). The cut-off excludes LAUs next to the hub, where the denominator is near
# zero; its effect is shown at 0, 3, 5 and 10 km (PIP-13), around the corrected hub (the Košice station, CF-13).

# %%
lau['e_route'] = lau['time_mean_min'] / lau['route_km_mean']
lau['e_rail'] = lau['time_mean_min'] / lau['rail_km_mean']
lau['e_geo'] = lau['time_mean_min'] / lau['geo_km_mean']


def net_summary(df, col, cut):
    out = []
    for (net, d), g in df[df['route_km_mean'] > cut].groupby(['network', 'direction']):
        g = g[np.isfinite(g[col])]
        w = np.average(g[col], weights=g['f_per_day']) if len(g) else np.nan
        out.append({'network': net, 'direction': d, 'cutoff_km': cut, 'distance': col.split('_')[1], 'n_lau': len(g),
                    'e_weighted': round(w, 3), 'e_median': round(g[col].median(), 3),
                    'speed_weighted_kmh': round(60 / w, 1) if w else np.nan})
    return out


summ = pd.DataFrame([r for cut in (0, 3, 5, 10) for r in net_summary(lau, 'e_route', cut)])
display(summ[summ.direction == 'inbound'].pivot(index='network', columns='cutoff_km', values=['n_lau', 'e_weighted', 'e_median']))
CUT = 5
eff = lau[lau['route_km_mean'] > CUT].copy()
base = {(r.network, r.direction): r.e_weighted for r in summ[summ.cutoff_km == CUT].itertuples()}
eff['e_network'] = [base[(n, d)] for n, d in zip(eff['network'], eff['direction'])]
eff['delta'] = eff['e_route'] - eff['e_network']
eff['delta_hat'] = eff['e_route'] / eff['e_network']
print(f'cut-off {CUT} km: LAUs left out (route km <= {CUT}):',
      lau[lau.route_km_mean <= CUT].groupby('network').size().to_dict())

# %% [markdown]
# ## 5. Ratio of means against mean of ratios (PIP-14)
#
# e_ℓ divides the mean journey time by the mean distance. The alternative, the mean of the journeys' own ratios
# τ_i / r_i, can differ when a LAU is served by journeys of very different length (several stations, or direct and
# roundabout itineraries). Both per LAU, and their difference.

# %%
jj = j[j['route_km'] > 0].assign(e_i=lambda d: d['time_min'] / d['route_km'])
mor = jj.groupby(['network', 'run', 'direction', 'lau_gisco_id'])['e_i'].mean().rename('e_mean_of_ratios')
eff = eff.join(mor, on=['network', 'run', 'direction', 'lau_gisco_id'])
eff['rom_mor'] = eff['e_route'] / eff['e_mean_of_ratios']
cmp = eff.groupby('network').agg(n=('rom_mor', 'size'), median_ratio=('rom_mor', 'median'),
                                 within_5pct=('rom_mor', lambda s: ((s - 1).abs() <= 0.05).mean()),
                                 spearman=('e_route', lambda s: s.rank().corr(eff.loc[s.index, 'e_mean_of_ratios'].rank())))
display(cmp.round(3))
multi = eff[eff['n_stations'] > 1]
print(f"LAUs served at several stations: {len(multi)}; median ratio of means / mean of ratios {multi['rom_mor'].median():.3f}")

# %% [markdown]
# ## 6. Which distance: route, shortest path or straight line
#
# The same efficiency on the three distances. Rank agreement shows whether the choice changes which places look
# slow; the levels show how much the distance choice matters.
#
# **Both are reported, as two measures:**
# * **operating efficiency** `e_route` = τ̄ / route km — how fast the trains and the change of trains run along the
#   path actually taken (Reviewer 1: efficiency should follow the line used);
# * **access efficiency** `e_rail` = τ̄ / shortest-path km — how fast one effectively gets there; a roundabout
#   journey is penalised.
#
# They are linked exactly, `e_rail = e_route × (route km / rail km)`: the detour factor of §1. For direct trains
# the two nearly coincide (detour ≈ 1.00); for one-transfer journeys they differ by the detour, which is named
# rather than hidden.

# %%
three = pd.DataFrame([r for col in ('e_route', 'e_rail', 'e_geo') for r in net_summary(lau, col, CUT)])
display(three[three.direction == 'inbound'].pivot(index='network', columns='distance', values=['e_weighted', 'speed_weighted_kmh']))
sp = eff.groupby('network').apply(lambda g: pd.Series({
    'spearman_route_rail': g['e_route'].rank().corr(g['e_rail'].rank()),
    'spearman_route_geo': g['e_route'].rank().corr(g['e_geo'].rank())}), include_groups=False).round(3)
display(sp)

# %% [markdown]
# ## 7. Against the legacy run (`output/ke`)
#
# The legacy `journey_efficiency_*.csv` divided the mean journey time by rail km (domestic) or by the straight line
# (foreign, `dist_km_mean`), measured from a hub 5.8 km south of the station (CF-13). Compared per LAU, inbound: on
# the LAU code (foreign) or the Slovak LAU name (the domestic files carry names only).

# %%
legacy = []
for net, f in [('domestic_direct', 'journey_efficiency_domestic.csv'), ('domestic_one_transfer', 'journey_efficiency_onehop.csv'),
               ('foreign_direct', 'journey_efficiency_foreign_direct.csv'), ('foreign_one_transfer', 'journey_efficiency_foreign_onehop.csv')]:
    p = os.path.join('output', 'ke', f)
    if os.path.exists(p):
        o = pd.read_csv(p, encoding='utf-8-sig')
        if 'euc_lau_code' in o:
            o = o.rename(columns={'euc_lau_code': 'lau_gisco_id'})
        else:   # the domestic files name the LAU (lau_group); matched on the Slovak LAU names
            names = lau[lau.country == 'SK'].drop_duplicates('lau_gisco_id').set_index('lau_name')['lau_gisco_id']
            o['lau_gisco_id'] = o['lau_group'].map(names)
        legacy.append(o.assign(network=net)[['network', 'lau_gisco_id', 'min_per_km', 'duration_mean']].dropna(subset=['lau_gisco_id']))
legacy = pd.concat(legacy, ignore_index=True)
m = eff[eff.direction == 'inbound'].merge(legacy, on=['network', 'lau_gisco_id'], how='inner')
m['ratio_e'] = m['e_route'] / m['min_per_km']
m['ratio_time'] = m['time_mean_min'] / m['duration_mean']
display(m.groupby('network')[['ratio_e', 'ratio_time']].median().round(3).assign(n=m.groupby('network').size()))
print('ratio_time near 1: the journey times agree; ratio_e differs mainly through the distance (route km from the '
      'Košice station against the legacy rail km / straight line from the wrong hub point)')

# %% [markdown]
# ## 8. Outputs

# %%
eff_out = eff[['network', 'run', 'direction', 'lau_gisco_id', 'lau_name', 'country', 'degurba', 'population',
               'f_per_day', 'time_mean_min', 'route_km_mean', 'rail_km_mean', 'geo_km_mean', 'e_route', 'e_rail', 'e_geo',
               'e_network', 'delta', 'delta_hat', 'e_mean_of_ratios', 'rom_mor', 'n_stations', 'window_days']]
for name, key, frame in [('detour_summary.csv', 'explore_detour_summary', detour),
                         ('route_validation.csv', 'explore_route_validation', val[['feed', 'a', 'b', 'route_km', 'published_km', 'ratio']]),
                         ('efficiency_lau.csv', 'explore_efficiency_lau', eff_out),
                         ('efficiency_summary.csv', 'explore_efficiency_summary', pd.concat([summ, three], ignore_index=True)
                          .drop_duplicates())]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Built from': '04a journeys / lau_table', 'Efficiency cut-off': f'{CUT} km route'})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')
