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
# # 02a — Domestic direct connections to and from Košice
#
# The first of the eight analysis pieces (02a–02d domestic, 03a–03d foreign): **direct trains between the
# Košice hub and every Slovak station**, in both directions, on the domestic feed (`ZSR_SK`) and its full
# window. Reads 01a (`windows.json`), 01b (`station_tags.csv`) and 01c (`station_rail_snap.csv`). Code:
# `traintranv2/nb02_connections.py`. The legacy `ksc_analysis.ipynb` and `output/ke/` are untouched.
#
# | § | step | output (`output/kosice/domestic/`) |
# |---|---|---|
# | 1 | feed, window, hub, what services are included | `../timetable/ZSR_SK_*.parquet` (cache) |
# | 2 | direct trips, inbound and outbound, computed separately | `direct_legs.parquet` |
# | 3 | per station and per LAU (distinct trips) | `direct_station.csv`, `direct_lau.csv` |
# | 4 | coverage with its denominators | `direct_coverage.csv` |
# | 5 | against the legacy run | — |
#
# **Rules** (Reviewer 1, register CON-6, PIP-4, PIP-9, PIP-10, STA-6):
# * **Run dates**: every trip carries the exact set of window days it runs on, from `calendar.txt` **and**
#   `calendar_dates.txt` (added and removed dates) — no weekday-pattern approximation.
# * **Times** are seconds of the GTFS service day, **not wrapped at 24:00** (a 25:10 arrival stays 25:10).
# * **Directions** are computed separately from the timetable, never mirrored: inbound = trips calling at a
#   station and *later* at the hub; outbound = at the hub and later at the station.
# * **The hub** is the **Košice main station** and every station grouped with it in another feed (01b
#   `station_group_id`). All 101 trains calling at Košice predmestie also call at the main station, so none is lost;
#   journeys are measured to / from the main station.
# * **Cities split into district LAUs are one unit** (`cfg.city_units`): the 22 *mestské časti* of Košice are the hub
#   city, left out of every origin set and denominator (its other stations — predmestie, Ťahanovce, Barca, Krásna —
#   are not origins); the 17 of Bratislava are one origin unit, as Budapest, Wien or Praha are one LAU (register T8 /
#   CF-16). Stations stay separate for transfers.
# * **Counting**: a station's figure is its distinct trips; a LAU's is the distinct trips over all its stations
#   — a train stopping at three stations of one LAU is one train for that LAU, not three.
# * **Services included**: every rail trip of the feed running in the window; bus routes are excluded (01b).
#   The service types are listed in §1.

# %%
import os, sys

# Run from the project root so every relative path resolves the same from notebooks/ or the root.
_here = os.path.abspath('')
if os.path.basename(_here) == 'notebooks':
    os.chdir(os.path.dirname(_here))
sys.path.insert(0, os.getcwd())
print('Working directory:', os.getcwd())

# %%
import zipfile
import pandas as pd
import traintranv2  # noqa: F401  (PROJ data fix)
from traintranv2.config import default_config
from traintranv2 import nb02_connections as C
from traintranv2.nb01b_stations import load_lau_subset
from traintranv2.nb01a_feeds import feed_zip_path, write_meta

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
print(f'feed {FEED}: window {days[0]} .. {days[-1]} ({N} days)')

# %% [markdown]
# ## 1. Feed, hub and the services included

# %%
st, trips = C.load_timetable(cfg, FEED, tags, days)
hubs = C.hub_groups(cfg, tags)
hub_st = tags[tags['station_group_id'].isin(hubs)][['feed_key', 'station_key', 'stop_name', 'station_group_id']]
print(f'{len(trips):,} trips run in the window, {len(st):,} station calls')
print('hub = these stations (all feeds):'); display(hub_st)
with zipfile.ZipFile(feed_zip_path(cfg, FEED)) as z:
    has_transfers = any(n.lower().endswith('transfers.txt') for n in z.namelist())
print(f'transfers.txt in the feed: {has_transfers}  (none: every transfer uses the config minimum, 02b)')
RT = {'100': 'long distance', '101': 'high speed', '102': 'long distance (express)', '103': 'interregional',
      '105': 'sleeper', '106': 'regional', '2': 'rail'}
svc = trips.assign(service=trips['route_type'].map(RT).fillna(trips['route_type']))
print('services included, by GTFS route_type (trips in the window):')
display(svc.groupby(['route_type', 'service']).agg(trips=('trip_id', 'size'), run_days=('n_days', 'sum')).reset_index())

# %% [markdown]
# ## 2. Direct trips, inbound and outbound

# %%
legs = pd.concat([C.direct_legs(st, trips, hubs, d, FEED) for d in ('inbound', 'outbound')], ignore_index=True)
legs = legs.join(tags.set_index('station_key')[['stop_name', 'nuts_rg_01_country_id', 'lau_gisco_id']], on='station_key')
print(legs.groupby(['direction', 'nuts_rg_01_country_id']).agg(trips=('trip_id', 'nunique'), stations=('station_key', 'nunique'))
      .unstack('direction'))
dom = legs[(legs['nuts_rg_01_country_id'] == 'SK') & ~legs['lau_gisco_id'].isin(hub_lau)].copy()
print(f'domestic (SK stations): {dom.station_key.nunique()} stations; the foreign stations go to 03a')

# %% [markdown]
# ## 3. Per station and per LAU

# %%
geo = tags.set_index('station_key')[['stop_name', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba', 'lau_pop_2025']]
station = (pd.concat([C.summarise(dom[dom.direction == d], 'station_key', ['trip_id'], N).assign(direction=d)
                      for d in ('inbound', 'outbound')], ignore_index=True)
           .join(geo, on='station_key')
           .join(snap.set_index('station_key')[['rail_km', 'geo_km']], on='station_key'))
station = station[['station_key', 'stop_name', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba', 'direction',
                   'n_journeys', 'journeys_per_day', 'service_days', 'service_share', 'min_time_min', 'median_time_min',
                   'rail_km', 'geo_km']].assign(**WIN)
lau_cols = ['lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba', 'lau_pop_2025']
lau = []
for d in ('inbound', 'outbound'):
    x = dom[dom.direction == d]
    s = C.summarise(x, 'lau_gisco_id', ['trip_id'], N)
    s['n_stations'] = s['lau_gisco_id'].map(x.groupby('lau_gisco_id')['station_key'].nunique())
    lau.append(s.assign(direction=d))
lau = pd.concat(lau, ignore_index=True).join(tags.drop_duplicates('lau_gisco_id').set_index('lau_gisco_id')[lau_cols[1:]], on='lau_gisco_id')
lau = lau[lau_cols + ['n_stations', 'direction', 'n_journeys', 'journeys_per_day', 'service_days', 'service_share',
                      'min_time_min', 'median_time_min']].assign(**WIN)
print(f"stations: {station.groupby('direction').size().to_dict()}   LAUs: {lau.groupby('direction').size().to_dict()}")
print('busiest inbound LAUs:')
display(lau[lau.direction == 'inbound'].sort_values('journeys_per_day', ascending=False).head(10))

# %% [markdown]
# ## 4. Coverage, with its denominators
#
# Every share is given with its base (Reviewer 1, STA-6): **all Slovak LAUs** except the city of Košice, the LAUs
# **with a station** of the domestic catalog, and those **served directly**. Population is end-2025 (00_b5).

# %%
sk = L[L['CNTR_CODE'] == 'SK'][['GISCO_ID', 'POP_2025']].rename(columns={'GISCO_ID': 'lau_gisco_id', 'POP_2025': 'pop'})
sk = sk[~sk['lau_gisco_id'].isin(hub_lau)]
with_station = set(tags.loc[(tags.feed_key == FEED) & (tags.nuts_rg_01_country_id == 'SK'), 'lau_gisco_id']) - hub_lau
rows = []
for d in ('inbound', 'outbound'):
    served = set(lau.loc[lau.direction == d, 'lau_gisco_id']) - hub_lau
    for g, ids in [('all_lau', set(sk.lau_gisco_id)), ('with_station', with_station), ('direct', served)]:
        part = sk[sk.lau_gisco_id.isin(ids)]
        rows.append({'direction': d, 'group': g, 'n_lau': len(part), 'population': part['pop'].sum()})
cov = pd.DataFrame(rows)
base = cov[cov.group == 'all_lau'].set_index('direction')
cov['share_lau'] = (cov['n_lau'] / cov['direction'].map(base['n_lau'])).round(4)
cov['share_population'] = (cov['population'] / cov['direction'].map(base['population'])).round(4)
cov = cov.assign(**WIN)
print(f'left out of the base: the city of {cfg.hub_label} {sorted(hub_lau)} (all its districts); '
      f'{next(u for u in cfg.city_units if u != cfg.hub_city)} = one unit')
display(cov)

# %% [markdown]
# ## 5. Against the legacy run (`output/ke`)
#
# Same feed; the legacy run used a 400-day cap, its own station catalog (887 stations deduplicated by name) and
# the per-station hub. Matched by station name; inbound trains per day.

# %%
leg = pd.read_csv('output/ke/ke_inbound_direct_stats.csv')
leg = leg[leg['country'] == 'SK'][['name', 'avg_trips_per_day']].rename(columns={'name': 'stop_name', 'avg_trips_per_day': 'legacy_per_day'})
new = station[station.direction == 'inbound'][['stop_name', 'journeys_per_day']]
cmpd = new.merge(leg, on='stop_name', how='outer', indicator=True)
print(cmpd['_merge'].value_counts().to_dict())
both = cmpd[cmpd._merge == 'both'].copy()
both['diff'] = (both['journeys_per_day'] - both['legacy_per_day']).round(2)
print(f"matched {len(both)} stations: |diff| < 0.05 for {(both['diff'].abs() < 0.05).sum()}")
display(both.reindex(both['diff'].abs().sort_values(ascending=False).index).head(12))
display(cmpd[cmpd._merge != 'both'])

# %% [markdown]
# ## 6. Outputs

# %%
legs_out = legs[['feed_key', 'trip_id', 'direction', 'station_key', 'group', 'hub_key', 'dep_s', 'arr_s', 'ride_s',
                 'route_type', 'n_days', 'mask', 'stop_name', 'nuts_rg_01_country_id', 'lau_gisco_id']]
p = os.path.join(OUT, 'direct_legs.parquet')
legs_out.to_parquet(p, index=False)
write_meta(p, 'domestic_direct_legs', legs_out, {**{k: str(v) for k, v in WIN.items()}, 'Feed': FEED})
print(f'[wrote] {p} ({len(legs_out):,} rows; all countries, the foreign stations are used by 03a)')
for name, key, frame in [('direct_station.csv', 'domestic_direct_station', station),
                         ('direct_lau.csv', 'domestic_direct_lau', lau),
                         ('direct_coverage.csv', 'domestic_direct_coverage', cov)]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Feed': FEED})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')
