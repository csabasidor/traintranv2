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
# # 02b — Domestic connections to and from Košice with one transfer
#
# Second analysis piece: journeys between the Košice hub and every Slovak station with **exactly one change of
# trains**, both directions, on the domestic feed (`ZSR_SK`) and its window. Builds on 02a (same timetable, hub
# and counting). Code: `traintranv2/nb02_connections.py`.
#
# | § | step | output (`output/kosice/domestic/`) |
# |---|---|---|
# | 1 | rules: transfer window, run dates, pairing | — |
# | 2 | itineraries, inbound and outbound, **for every destination** | `one_transfer_itins.parquet` |
# | 3 | per station and per LAU, four counts (R1) and hub dependence | `one_transfer_station.csv`, `one_transfer_lau.csv` |
# | 4 | coverage: direct / newly reached / either, with denominators | `one_transfer_coverage.csv` |
# | 5 | transfer hubs: volume and exclusive catchment | `one_transfer_hubs.csv` |
# | 6 | pairing rule and legacy run compared | — |
# | 7 | transfer-window sensitivity | `one_transfer_sensitivity.csv` |
#
# **Rules** (Reviewer 1, register PIP-4 to PIP-10, PIP-15, PIP-17, VAL-2, STA-6):
# * **A transfer** is a change between two trains at **one station** (one `station_group_id`): no walk between
#   separate stations (PIP-17, a stated limitation).
# * **Transfer window**: wait ≥ `min_connect_min` (10) and ≤ `max_connect_min` (90). The feed has no `transfers.txt`,
#   so no station-specific minimum applies (PIP-7, CF-25).
# * **Run dates**: a journey runs on the dates **both** trains run (bitmask AND of `calendar` + `calendar_dates`); times
#   are service-day seconds **without wrap at 24:00** (PIP-4).
# * **Across midnight** (PIP-6): a second train leaving just after midnight on the **next** service date connects
#   to a first train arriving late on date d. It is paired as a copy dated d with its times + 24 h (`next_day =
#   True`), so the journey stays on the first train's clock. A 00:20 train running on date d itself is never
#   paired with a 23:50 arrival on d (the legacy modulo-24 h error).
# * **Same train**: staying on board through a long stop is not a transfer; a pair of one trip with itself is
#   dropped.
# * **Pairing** (`cfg.transfer_pairing = "dated"`): on every date, each first train takes the **earliest** connection
#   running that date; if a later first train reaches the same connection on that date, only the later one counts
#   (the earlier one leaves earlier and arrives at the same time). This avoids combinatorial double counting (PIP-10)
#   and, unlike the legacy rule, does not lose a connection because the first candidate runs on other days (§6).
# * **Every destination** gets its one-transfer journeys, also those with a direct train (`has_direct`); "newly
#   reached" (no direct train) is a filter, so both views and all denominators are reported (STA-6).
# * **Counting** (§3): distinct complete journeys, plus the distinct first and second trains behind them and the
#   journeys sharing a train (R1's distinction between departures, journeys and alternatives on one train).

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
from traintranv2.nb01a_feeds import write_meta
from traintranv2.nb01b_stations import load_lau_subset

cfg = default_config()
FEED = cfg.domestic_feed
OUT = os.path.join(cfg.out_dir, 'domestic')
os.makedirs(OUT, exist_ok=True)
tags = pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str)
L = C.lau_with_city_units(load_lau_subset(cfg), cfg)          # Košice / Bratislava districts -> one unit each
tags = C.tags_with_city_units(tags, cfg, L)
hub_lau = C.hub_city_laus(cfg)                                 # the whole city of Košice
snap = pd.read_csv(os.path.join(cfg.out_dir, 'station_rail_snap.csv'), dtype={'station_key': str})
days = C.window_days(cfg, FEED)
N = len(days)
WIN = {'window_start': str(days[0]), 'window_end': str(days[-1]), 'window_days': N}
st, trips = C.load_timetable(cfg, FEED, tags, days)
hubs = C.hub_groups(cfg, tags)
geo = tags.set_index('station_key')
pop = L.set_index('GISCO_ID')['POP_2025']
print(f'{FEED}: {days[0]} .. {days[-1]} ({N} days); {len(trips):,} trips')

# %% [markdown]
# ## 1. Rules of this run

# %%
print(f'transfer window : {cfg.min_connect_min} .. {cfg.max_connect_min} min   (sensitivity grid: {cfg.sensitivity_grid})')
print(f'pairing rule    : {cfg.transfer_pairing}')
print(f'hub             : {sorted(cfg.hub_station_keys)} and their station groups')

# %% [markdown]
# ## 2. Itineraries, inbound and outbound

# %%
direct = {d: C.direct_legs(st, trips, hubs, d, FEED) for d in ('inbound', 'outbound')}


def build(rule=cfg.transfer_pairing, mn=cfg.min_connect_min, mx=cfg.max_connect_min):
    """One-transfer itineraries in both directions, every destination."""
    out = []
    T_out = set(direct['outbound']['group'])
    second = C.attach_trips(C.od_pairs(st, from_groups=T_out, not_to_groups=hubs), trips, FEED)
    out.append(C.one_transfer(direct['outbound'], second, 'outbound', mn, mx, N, rule=rule))
    T_in = set(direct['inbound']['group'])
    first = C.attach_trips(C.od_pairs(st, to_groups=T_in), trips, FEED)
    first = first[~first['from_group'].isin(hubs)]
    out.append(C.one_transfer(first, direct['inbound'], 'inbound', mn, mx, N, rule=rule))
    it = pd.concat(out, ignore_index=True)
    it = it[~it['group'].isin(hubs)]
    has = {d: set(direct[d]['station_key']) for d in direct}
    it['has_direct'] = [k in has[d] for k, d in zip(it['station_key'], it['direction'])]
    it['nuts_rg_01_country_id'] = it['station_key'].map(geo['nuts_rg_01_country_id'])
    it['lau_gisco_id'] = it['station_key'].map(geo['lau_gisco_id'])
    return it


itins = build()
dom = itins[(itins['nuts_rg_01_country_id'] == 'SK') & ~itins['lau_gisco_id'].isin(hub_lau)].copy()
print(f'{len(itins):,} itineraries (all countries); Slovak stations: {len(dom):,}')
print(f"of them across midnight (next_day, PIP-6): {int(dom['next_day'].sum()):,} itineraries, "
      f"{dom.loc[dom.next_day, 'station_key'].nunique()} stations, "
      f"{dom.loc[dom.next_day & ~dom.has_direct, 'station_key'].nunique()} of them without a direct train")
print(dom.groupby(['direction', 'has_direct']).agg(itineraries=('leg1_trip', 'size'), stations=('station_key', 'nunique')))

# %% [markdown]
# ## 3. Per station and per LAU
#
# Four counts per unit (R1): distinct **journeys**, the distinct **first** and **second trains** behind them, and the
# journeys **sharing a train** with another journey to the same unit. Hub dependence is frequency-weighted
# (PIP-15): the main transfer station's share of the LAU's journeys per day, and the fewest stations carrying 90 %.

# %%
station, lau, per_hub = [], [], []
for d in ('inbound', 'outbound'):
    x = dom[dom.direction == d]
    s = C.summarise_one_transfer(x, 'station_key', N).assign(direction=d)
    s['has_direct'] = s['station_key'].isin(set(direct[d]['station_key']))
    station.append(s)
    l = C.summarise_one_transfer(x, 'lau_gisco_id', N).assign(direction=d)
    dlau = set(direct[d]['station_key'].map(geo['lau_gisco_id']))
    l['has_direct'] = l['lau_gisco_id'].isin(dlau)
    ph, hs = C.hub_dependence(x, 'lau_gisco_id', N, share=0.9)
    l = l.merge(hs[['lau_gisco_id', 'main_hub', 'main_hub_share', 'hubs_for_share']], on='lau_gisco_id', how='left')
    lau.append(l.rename(columns={'hubs_for_share': 'hubs_for_90'}))
    per_hub.append(ph.assign(direction=d))
st_cols = ['stop_name', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba']
station = (pd.concat(station, ignore_index=True).join(geo[st_cols], on='station_key')
           .join(snap.set_index('station_key')['rail_km'], on='station_key'))
station = station[['station_key'] + st_cols + ['direction', 'n_journeys', 'journeys_per_day', 'service_days', 'service_share',
                   'min_time_min', 'median_time_min', 'n_first_legs', 'n_second_legs', 'n_shared_leg', 'n_hubs',
                   'median_wait_min', 'has_direct', 'rail_km']].assign(**WIN)
lau_geo = tags.drop_duplicates('lau_gisco_id').set_index('lau_gisco_id')[['lau_name_national', 'nuts3_id', 'degurba']]
lau = pd.concat(lau, ignore_index=True).join(lau_geo, on='lau_gisco_id')
lau['lau_pop_2025'] = lau['lau_gisco_id'].map(pop)
lau = lau[['lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba', 'lau_pop_2025', 'direction', 'n_journeys',
           'journeys_per_day', 'service_days', 'service_share', 'min_time_min', 'median_time_min', 'n_first_legs',
           'n_second_legs', 'n_shared_leg', 'n_hubs', 'median_wait_min', 'has_direct', 'main_hub', 'main_hub_share',
           'hubs_for_90']].assign(**WIN)
per_hub = pd.concat(per_hub, ignore_index=True)
print(f"stations: {station.groupby(['direction', 'has_direct']).size().to_dict()}")
print(f"LAUs    : {lau.groupby(['direction', 'has_direct']).size().to_dict()}")
print('the four counts, inbound, LAUs newly reached (sums):')
display(lau[(lau.direction == 'inbound') & ~lau.has_direct][['n_journeys', 'n_first_legs', 'n_second_legs', 'n_shared_leg']].sum().to_frame().T)
print('largest newly reached LAUs (inbound):')
display(lau[(lau.direction == 'inbound') & ~lau.has_direct].sort_values('lau_pop_2025', ascending=False).head(10)
        [['lau_name_national', 'lau_pop_2025', 'journeys_per_day', 'median_time_min', 'median_wait_min', 'main_hub', 'main_hub_share', 'hubs_for_90']])

# %% [markdown]
# ## 4. Coverage, with its denominators
#
# Groups of Slovak LAUs (the city of Košice left out of every group; Bratislava one unit): **all**, **with a station**, **direct**, **one
# transfer** (any journey with one change), **newly reached** (one transfer and no direct train), **direct or one
# transfer**. Population end-2025.

# %%
sk = L[(L['CNTR_CODE'] == 'SK') & ~L['GISCO_ID'].isin(hub_lau)].set_index('GISCO_ID')['POP_2025']
with_station = set(tags.loc[(tags.feed_key == FEED) & (tags.nuts_rg_01_country_id == 'SK'), 'lau_gisco_id']) - hub_lau
rows = []
for d in ('inbound', 'outbound'):
    dl = set(direct[d]['station_key'].map(geo['lau_gisco_id'])) & set(sk.index)
    ol = set(lau.loc[lau.direction == d, 'lau_gisco_id']) & set(sk.index)
    for g, ids in [('all_lau', set(sk.index)), ('with_station', with_station & set(sk.index)), ('direct', dl),
                   ('one_transfer', ol), ('newly_reached', ol - dl), ('direct_or_one_transfer', ol | dl)]:
        rows.append({'direction': d, 'group': g, 'n_lau': len(ids), 'population': sk.reindex(list(ids)).sum()})
cov = pd.DataFrame(rows)
base = cov[cov.group == 'all_lau'].set_index('direction')
cov['share_lau'] = (cov['n_lau'] / cov['direction'].map(base['n_lau'])).round(4)
cov['share_population'] = (cov['population'] / cov['direction'].map(base['population'])).round(4)
cov = cov.assign(**WIN)
display(cov)

# %% [markdown]
# ## 5. Transfer hubs
#
# Per transfer station: journeys per day through it (Slovak LAUs), LAUs reached, and the LAUs **without a direct
# train for which it is the only transfer station** — the catchment that depends on it alone (PIP-15).

# %%
nd = {d: set(lau.loc[(lau.direction == d) & ~lau.has_direct, 'lau_gisco_id']) for d in ('inbound', 'outbound')}
hubs_tab = []
for d in ('inbound', 'outbound'):
    ph = per_hub[per_hub.direction == d]
    n_h = ph.groupby('lau_gisco_id')['T'].nunique()
    only = ph[ph['lau_gisco_id'].map(n_h).eq(1) & ph['lau_gisco_id'].isin(nd[d])]
    t = ph.groupby('T_key').agg(journeys_per_day=('journeys_per_day', 'sum'), n_lau=('lau_gisco_id', 'nunique'))
    t['n_lau_only_hub'] = only.groupby('T_key')['lau_gisco_id'].nunique()
    t['pop_only_hub'] = only.assign(p=only['lau_gisco_id'].map(pop)).groupby('T_key')['p'].sum()
    hubs_tab.append(t.fillna({'n_lau_only_hub': 0, 'pop_only_hub': 0}).reset_index().assign(direction=d))
hubs_tab = pd.concat(hubs_tab, ignore_index=True)
hubs_tab['stop_name'] = hubs_tab['T_key'].map(geo['stop_name'])
hubs_tab['journeys_per_day'] = hubs_tab['journeys_per_day'].round(2)
hubs_tab = hubs_tab[['direction', 'T_key', 'stop_name', 'journeys_per_day', 'n_lau', 'n_lau_only_hub', 'pop_only_hub']] \
    .sort_values(['direction', 'pop_only_hub'], ascending=[True, False]).assign(**WIN)
display(hubs_tab[hubs_tab.direction == 'inbound'].head(12))

# %% [markdown]
# ## 6. Pairing rule and the legacy run
#
# The same itineraries with the legacy pairing rule (`traintran.analysis.feasible_itineraries`: each first train tries
# only one connection), and the stations the legacy run (`output/ke`) reached with one transfer — it computed them
# only for stations **without** a direct train.

# %%
leg_rule = build(rule='legacy')
leg_rule = leg_rule[(leg_rule['nuts_rg_01_country_id'] == 'SK') & ~leg_rule['lau_gisco_id'].isin(hub_lau)]
cmp = pd.DataFrame({r: {'itineraries': len(x[x.direction == 'inbound']),
                        'stations': x.loc[x.direction == 'inbound', 'station_key'].nunique(),
                        'stations_without_direct': x.loc[(x.direction == 'inbound') & ~x.has_direct, 'station_key'].nunique(),
                        'journeys_per_day_total': x[x.direction == 'inbound'].drop_duplicates(['station_key', 'leg1_trip', 'leg2_trip'])['n_days'].sum() / N}
                    for r, x in [('dated', dom), ('legacy rule', leg_rule)]})
display(cmp.round(1))
old = pd.read_csv('output/ke/ke_inbound_onehop_stats.csv')
old = set(old.loc[old['country'] == 'SK', 'name'])
new = set(station.loc[(station.direction == 'inbound') & ~station.has_direct, 'stop_name'])
print(f'stations without direct reached inbound: new {len(new)}, legacy {len(old)}, both {len(new & old)}')
print('only new   :', sorted(new - old)[:20])
print('only legacy:', sorted(old - new)[:20])

# %% [markdown]
# ## 7. Transfer-window sensitivity (VAL-2)
#
# The configured grid against the base window: LAUs and population newly reached, journeys per day, journey time and
# the share of single-hub LAUs, per direction.

# %%
grid = sorted(set(cfg.sensitivity_grid) | {(cfg.min_connect_min, cfg.max_connect_min)})
sens = []
for mn, mx in grid:
    it = build(mn=mn, mx=mx)
    it = it[(it['nuts_rg_01_country_id'] == 'SK') & ~it['lau_gisco_id'].isin(hub_lau)]
    for d in ('inbound', 'outbound'):
        x = it[(it.direction == d) & ~it.has_direct]
        dl = set(direct[d]['station_key'].map(geo['lau_gisco_id']))
        x = x[~x['lau_gisco_id'].isin(dl)]
        s = C.summarise_one_transfer(x, 'lau_gisco_id', N)
        _, hs = C.hub_dependence(x, 'lau_gisco_id', N) if len(x) else (None, pd.DataFrame(columns=['hubs_for_share']))
        sens.append({'direction': d, 'min_connect_min': mn, 'max_connect_min': mx,
                     'is_base': (mn, mx) == (cfg.min_connect_min, cfg.max_connect_min),
                     'n_lau_newly_reached': len(s), 'pop_newly_reached': s['lau_gisco_id'].map(pop).sum(),
                     'journeys_per_day_median': round(s['journeys_per_day'].median(), 2),
                     'median_time_min': round(s['median_time_min'].median(), 1),
                     'single_hub_share': round((hs['hubs_for_share'] == 1).mean(), 3) if len(hs) else None})
sens = pd.DataFrame(sens).assign(**WIN)
display(sens[sens.direction == 'inbound'])

# %% [markdown]
# ## 8. Outputs

# %%
p = os.path.join(OUT, 'one_transfer_itins.parquet')
itins.to_parquet(p, index=False)
write_meta(p, 'domestic_one_transfer_itins', itins, {**{k: str(v) for k, v in WIN.items()}, 'Feed': FEED,
           'Transfer window': f'{cfg.min_connect_min}-{cfg.max_connect_min} min', 'Pairing': cfg.transfer_pairing})
print(f'[wrote] {p} ({len(itins):,} rows; all countries, the foreign stations are used by 03)')
for name, key, frame in [('one_transfer_station.csv', 'domestic_one_transfer_station', station),
                         ('one_transfer_lau.csv', 'domestic_one_transfer_lau', lau),
                         ('one_transfer_hubs.csv', 'domestic_one_transfer_hubs', hubs_tab),
                         ('one_transfer_coverage.csv', 'domestic_one_transfer_coverage', cov),
                         ('one_transfer_sensitivity.csv', 'domestic_one_transfer_sensitivity', sens)]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Feed': FEED, 'Transfer window': f'{cfg.min_connect_min}-{cfg.max_connect_min} min',
                               'Pairing': cfg.transfer_pairing})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')
