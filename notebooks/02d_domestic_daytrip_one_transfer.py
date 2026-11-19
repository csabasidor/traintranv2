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
# # 02d — Domestic same-day visits to Košice: direct trains or one-transfer journeys
#
# Can a resident of a Slovak municipality **go to Košice and come back the same day** by direct trains or one-transfer journeys? Reviewer 1: *"a
# destination cannot be considered accessible for a day visit merely because one feasible inbound itinerary exists"*
# (register PIP-16, VAL-3, CON-6). Reads 02a (`direct_legs.parquet`) and 02b (`one_transfer_itins.parquet`); code: `traintranv2/nb02_connections.py::daytrip_days`. These are
# **same-day visits**, not tourism trips (a tourist stays at least one night).
#
# **Rule** (config, unchanged from the legacy run): on a given date a station (or LAU) counts if
# * an **inbound** option arrives in Košice **by {max_arrival}**,
# * an **outbound** option leaves Košice **at or after {min_departure}** and at least **{dwell} min** after that arrival,
# * and is **back by {max_return}**,
# * both running **on that date** (run-date bitmasks; service-day clock without wrap, so a 25:10 return is after 23:59).
#
# Options are direct trains (02a) **or one-transfer journeys** (02b), in any combination: out with a transfer and back direct counts. The increment over 02c is what the transfer adds.
# A **LAU** counts on a date if the visit is possible from **any of its stations** (out from one, back to another of
# the same LAU allowed). Inbound and outbound come from the timetable separately (never mirrored).
#
# | § | step | output (`output/kosice/domestic/`) |
# |---|---|---|
# | 1 | options | — |
# | 2 | day-trip days per station and per LAU | `daytrip_one_transfer_station.csv`, `daytrip_one_transfer_lau.csv` |
# | 3 | coverage with denominators; NUTS3 × DEGURBA | `daytrip_one_transfer_coverage.csv` |
# | 4 | dwell sensitivity (VAL-3) | `daytrip_one_transfer_sensitivity.csv` |
# | 5 | against the legacy run and 02c | — |

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

KIND = 'one_transfer'
cfg = default_config()
FEED = cfg.domestic_feed
OUT = os.path.join(cfg.out_dir, 'domestic')
tags = pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str)
L = C.lau_with_city_units(load_lau_subset(cfg), cfg)          # Košice / Bratislava districts -> one unit each
tags = C.tags_with_city_units(tags, cfg, L)
hub_lau = C.hub_city_laus(cfg)                                 # the whole city of Košice
snap = pd.read_csv(os.path.join(cfg.out_dir, 'station_rail_snap.csv'), dtype={'station_key': str})
geo = tags.set_index('station_key')
days = C.window_days(cfg, FEED)
N = len(days)
WIN = {'window_start': str(days[0]), 'window_end': str(days[-1]), 'window_days': N}
pop = L.set_index('GISCO_ID')['POP_2025']
print(f'rule: arrive by {cfg.daytrip_max_arrival}, dwell >= {cfg.daytrip_min_dwell_min} min, depart >= {cfg.daytrip_min_departure}, '
      f'back by {cfg.daytrip_max_return}; dwell sensitivity {cfg.daytrip_dwell_sensitivity}')

# %% [markdown]
# ## 1. Options

# %%
legs = pd.read_parquet(os.path.join(OUT, 'direct_legs.parquet'))
opts = legs.rename(columns={'dep_s': 'start_s', 'arr_s': 'end_s'})[['direction', 'station_key', 'start_s', 'end_s', 'mask']].assign(kind='direct')
if KIND == 'one_transfer':
    it = pd.read_parquet(os.path.join(OUT, 'one_transfer_itins.parquet'))
    opts = pd.concat([opts, it[['direction', 'station_key', 'start_s', 'end_s', 'mask']].assign(kind='one_transfer')], ignore_index=True)
opts['nuts_rg_01_country_id'] = opts['station_key'].map(geo['nuts_rg_01_country_id'])
opts['lau_gisco_id'] = opts['station_key'].map(geo['lau_gisco_id'])
opts = opts[(opts['nuts_rg_01_country_id'] == 'SK') & ~opts['lau_gisco_id'].isin(hub_lau)]
inb, outb = opts[opts.direction == 'inbound'], opts[opts.direction == 'outbound']
print(opts.groupby(['direction', 'kind']).agg(options=('mask', 'size'), stations=('station_key', 'nunique')))

# %% [markdown]
# ## 2. Day-trip days per station and per LAU

# %%
ds = C.daytrip_days(inb, outb, cfg, N, by='station_key')
station = ds.join(geo[['stop_name', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba']], on='station_key') \
    .join(snap.set_index('station_key')['rail_km'], on='station_key')
station = station[['station_key', 'stop_name', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba',
                   'n_daytrip_days', 'daytrip_share', 'rail_km']].assign(**WIN)
dl = C.daytrip_days(inb, outb, cfg, N, by='lau_gisco_id')
lau_geo = tags.drop_duplicates('lau_gisco_id').set_index('lau_gisco_id')[['lau_name_national', 'nuts3_id', 'degurba']]
lau = dl.join(lau_geo, on='lau_gisco_id')
lau['lau_pop_2025'] = lau['lau_gisco_id'].map(pop)
lau = lau[['lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba', 'lau_pop_2025', 'n_daytrip_days', 'daytrip_share']].assign(**WIN)
print(f'stations with >= 1 day-trip day: {len(station)}; LAUs: {len(lau)}')
print('largest LAUs with a same-day visit:')
display(lau.sort_values('lau_pop_2025', ascending=False).head(10))

# %% [markdown]
# ## 3. Coverage, with its denominators
#
# **all**: every Slovak LAU except the hub's; **served**: an option both ways (some day); **daytrip_any**: a
# same-day visit on at least one day; **daytrip_50** / **daytrip_90**: on at least half / 90 % of the window's days.

# %%
sk = L[(L['CNTR_CODE'] == 'SK') & ~L['GISCO_ID'].isin(hub_lau)].set_index('GISCO_ID')['POP_2025']
served = set(inb['lau_gisco_id']) & set(outb['lau_gisco_id'])
share = lau.set_index('lau_gisco_id')['daytrip_share']
groups = [('all_lau', set(sk.index)), ('served', served), ('daytrip_any', set(share.index)),
          ('daytrip_50', set(share[share >= 0.5].index)), ('daytrip_90', set(share[share >= 0.9].index))]
cov = pd.DataFrame([{'group': g, 'n_lau': len(ids & set(sk.index)), 'population': sk.reindex(list(ids & set(sk.index))).sum()}
                    for g, ids in groups])
cov['share_lau'] = (cov['n_lau'] / cov.loc[0, 'n_lau']).round(4)
cov['share_population'] = (cov['population'] / cov.loc[0, 'population']).round(4)
cov = cov.assign(**WIN)
display(cov)
x = lau[lau.daytrip_share >= 0.5]
ct = pd.crosstab(x['nuts3_id'], x['degurba'], values=x['lau_pop_2025'], aggfunc='sum').fillna(0)
tot = pd.crosstab(L.loc[L.CNTR_CODE == 'SK', 'NUTS3_ID'], L.loc[L.CNTR_CODE == 'SK', 'DGURBA'],
                  values=L.loc[L.CNTR_CODE == 'SK', 'POP_2025'], aggfunc='sum').fillna(0)
tot.columns = tot.columns.astype(str)
print('share of each kraj x DEGURBA population with same-day visits on >= 50 % of days:')
display((ct.reindex(index=tot.index, columns=tot.columns).fillna(0) / tot).round(3))

# %% [markdown]
# ## 4. Dwell sensitivity (VAL-3)

# %%
sens = []
for dwell in sorted(cfg.daytrip_dwell_sensitivity):
    d = C.daytrip_days(inb, outb, cfg, N, by='lau_gisco_id', dwell_min=dwell)
    d = d[d.lau_gisco_id.isin(sk.index)]
    h = d[d.daytrip_share >= 0.5]
    sens.append({'dwell_min': dwell, 'is_base': dwell == cfg.daytrip_min_dwell_min,
                 'n_lau_any': len(d), 'pop_any': d['lau_gisco_id'].map(pop).sum(),
                 'n_lau_50': len(h), 'pop_50': h['lau_gisco_id'].map(pop).sum()})
sens = pd.DataFrame(sens).assign(**WIN)
display(sens)

# %% [markdown]
# ## 5. What the transfer adds (against 02c)

# %%
d02c = pd.read_csv(os.path.join(OUT, 'daytrip_direct_lau.csv'))
c02c = pd.read_csv(os.path.join(OUT, 'daytrip_direct_coverage.csv')).set_index('group')
add = cov.set_index('group')[['n_lau', 'population']].join(c02c[['n_lau', 'population']], rsuffix='_direct_only')
add['added_lau'] = add['n_lau'] - add['n_lau_direct_only']
add['added_population'] = add['population'] - add['population_direct_only']
display(add)
new = lau[~lau.lau_gisco_id.isin(d02c.lau_gisco_id)].sort_values('lau_pop_2025', ascending=False)
print(f'LAUs with a same-day visit only thanks to a transfer: {len(new)}')
display(new.head(10))

# %% [markdown]
# ## 5b. Why the same-day share changed with the city units
#
# Making Košice one hub station and one city and Bratislava one unit raised the share of the Slovak population with a
# same-day visit (33.4 % before; the legacy run had 32.4 %). Decomposed in three steps on this run's station results
# (a station with at least one day-trip day serves its LAU), each step changing one definition:
# 1. **old units** — districts separate, only the two hub stations' districts left out of the base;
# 2. **Košice one city** — all 22 districts out of the base and of the served;
# 3. **Bratislava one unit** — its 17 districts one LAU: the whole city counts as served once any of its stations is.

# %%
# legacy-only: decomposes the change of units made for Košice; skipped by run_destination.py for other destinations
L_raw = load_lau_subset(cfg)
pop_raw = L_raw.set_index('GISCO_ID')['POP_2025']
tags_raw = pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str).set_index('station_key')
raw_lau = station['station_key'].map(tags_raw['lau_gisco_id'])
umap = C.city_unit_map(cfg, L_raw)
ke = {g for g, u in umap.items() if u.endswith('Košice')}
old_hub = {'SK_598186', 'SK_599824'}                    # the districts of the two former hub stations
sk_raw = L_raw[L_raw.CNTR_CODE == 'SK']
served_raw = set(raw_lau[station['n_daytrip_days'] > 0])
steps = []
for name, base_ids, served in [
        ('1 old units', set(sk_raw.GISCO_ID) - old_hub, served_raw - old_hub),
        ('2 Košice one city', set(sk_raw.GISCO_ID) - ke, served_raw - ke),
        ('3 + Bratislava one unit', set(sk_raw.GISCO_ID) - ke,
         (served_raw - ke) | ({g for g, u in umap.items() if u.endswith('Bratislava')} if any(umap.get(g, '').endswith('Bratislava') for g in served_raw) else set()))]:
    b, sv = pop_raw.reindex(list(base_ids)).sum(), pop_raw.reindex(list(served & base_ids)).sum()
    steps.append({'step': name, 'base_population': b, 'served_population': sv, 'share': sv / b})
steps = pd.DataFrame(steps)
steps['change_pp'] = (100 * steps['share'].diff()).round(2)
display(steps.round(4))
print(f"reported now: {cov.loc[cov.group == 'daytrip_any', 'share_population'].iloc[0]:.4f} (LAU-level, the table above)")
print('the three Košice stations inside the city (Ťahanovce, Barca, Krásna) were origins under the old units; they are no '
      'longer in this run, so step 1 slightly understates the old share (their districts hold about 12,000 people).')

# %% [markdown]
# ## 6. Outputs

# %%
for name, key, frame in [(f'daytrip_{KIND}_station.csv', f'domestic_daytrip_{KIND}_station', station),
                         (f'daytrip_{KIND}_lau.csv', f'domestic_daytrip_{KIND}_lau', lau),
                         (f'daytrip_{KIND}_coverage.csv', f'domestic_daytrip_{KIND}_coverage', cov),
                         (f'daytrip_{KIND}_sensitivity.csv', f'domestic_daytrip_{KIND}_sensitivity', sens)]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Feed': FEED, 'Rule': f'arrive <= {cfg.daytrip_max_arrival}, dwell >= {cfg.daytrip_min_dwell_min} min, '
                                                     f'depart >= {cfg.daytrip_min_departure}, back <= {cfg.daytrip_max_return}'})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')
