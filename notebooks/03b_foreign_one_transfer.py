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
# # 03b — Connections between Košice and places abroad with one transfer
#
# Journeys between the Košice hub and stations in Czechia, Hungary, Austria, Poland and Ukraine with **exactly one
# change of trains**, both directions. Code: `traintranv2/nb03_foreign.py` on the engine of 02b
# (`traintranv2/nb02_connections.py`).
#
# | § | step | output (`output/kosice/foreign/`) |
# |---|---|---|
# | 1 | rules and runs | — |
# | 2 | itineraries per country run; feeds, duplicates and transfers onto the same train | `one_transfer_itins.parquet`, `feed_quality.csv`, `cross_feed_duplicates.csv` |
# | 3 | per station and per LAU, four counts (R1) and gateway dependence | `one_transfer_station.csv`, `one_transfer_lau.csv` |
# | 4 | coverage: direct / newly reached / either, with denominators | `one_transfer_coverage.csv` |
# | 5 | gateways: volume and exclusive catchment | `one_transfer_hubs.csv` |
# | 6 | transfer waits and connections across midnight | — |
# | 7 | sensitivity: transfer window, transfers between two stations of one city | `one_transfer_sensitivity.csv` |
# | 8 | against the legacy run | — |
#
# **Rules** (Reviewer 1, register CON-10, PIP-4 to PIP-10, PIP-15, PIP-17, STA-2, VAL-2):
# * **The first leg is a ZSR train** between Košice and a transfer station T (in Slovakia or abroad). **The second
#   leg** runs between T and a station of the destination country, on **ZSR_SK or the country's own feed(s)**: the
#   Czech, Hungarian, Austrian, Polish (PKP Intercity + all other carriers) or Ukrainian timetable.
# * **One run per destination country** on the window its feeds share with ZSR (table in 03a): CZ 364, HU 301, AT 276,
#   UA 364 days; **PL 32 days** (5 June – 6 July 2026, both Polish feeds), plus **PL_IC alone on 101 days** as a
#   sensitivity run (`PL:PL_IC`). Per-day figures divide by the run's own window.
# * **A transfer** is at one station group (01b `station_group_id`): two feeds' records of one station are one place, so
#   a change from a ZSR train to a Czech-feed train at Bohumín needs no extra matching. Wait between
#   `min_connect_min` (10) and `max_connect_min` (90) minutes. No walk between two stations (PIP-17, measured in §7).
# * **A train in two feeds counts once** (PIP-8): ZSR's copy of a Czech, Hungarian or Austrian train (same stations,
#   departure and arrival within 2 minutes, a common date) is dropped and the national feed's leg kept, with the run
#   dates of both.
# * **No transfer onto the same train**: a "change" to the other feed's copy of the train one is on is dropped.
# * **Trains published in pieces are joined**: BAHN_AT cuts its trains at region and border points (RJX Wien –
#   Bratislava-Petržalka, then Petržalka – Bratislava hl.st.); pieces with one train number that meet at a station are
#   one trip (`nb02_connections.join_train_pieces`), as legs joined by stay-seated transfers are (Polish feeds).
# * **Across midnight** (PIP-6): a second train leaving after midnight on the next date connects to a first train
#   arriving late on date d (`next_day`); no modulo-24 h wrap.
# * Dated pairing, every destination kept, `has_direct`, the four counts and gateway dependence as in 02b.
# * A station's LAU abroad comes from the national feed (03a).

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
direct = pd.read_parquet(os.path.join(OUT, 'direct_legs.parquet'))     # 03a

# %% [markdown]
# ## 1. Rules of this run

# %%
print(f'transfer window : {cfg.min_connect_min} .. {cfg.max_connect_min} min   (sensitivity grid: {cfg.sensitivity_grid})')
print(f'pairing rule    : {cfg.transfer_pairing};  city-transfer sensitivity: any two stations of one LAU, >= 45 min')
display(pd.DataFrame([{'run': r['run'], 'feeds': ' + '.join([cfg.domestic_feed] + r['feeds']), **F.run_window(r),
                       'headline': r['headline']} for r in runs]))

# %% [markdown]
# ## 2. Itineraries per country run
#
# `feed_quality` (REP-4): first and second legs, ZSR copies of national trains removed, "transfers" onto the same train
# removed, itineraries, those across midnight, transfer stations, and itineraries by the feed of the train abroad.

# %%
itins, dups, quality, TT = [], [], [], {}
for r in runs:
    tt = F.load_run_timetables(cfg, r, tags)
    TT[r['run']] = tt
    it, dup, stats = F.run_one_transfer(cfg, r, tt, tags, hubs)
    W = F.run_window(r)
    dl = direct[direct.run == r['run']]
    has = {d: set(dl.loc[dl.direction == d, 'station_key']) for d in ('inbound', 'outbound')}
    it['has_direct'] = [k in has[d] for k, d in zip(it['station_key'], it['direction'])]
    itins.append(it.assign(**W))
    dups.append(dup.assign(country=r['country'], **W))
    for d in ('inbound', 'outbound'):
        x = it[it.direction == d]
        abroad = x['leg2_feed'] if d == 'outbound' else x['leg1_feed']      # the train on the foreign side
        quality.append({'country': r['country'], 'run': r['run'], 'direction': d, **stats[d],
                        'same_train_dropped': stats['same_train_dropped'], 'itineraries': len(x),
                        'itineraries_next_day': int(x['next_day'].sum()), 'transfer_stations': x['T_key'].nunique(),
                        'second_leg_feeds': '; '.join(f'{f}: {n}' for f, n in abroad.value_counts().items()), **W})
itins = pd.concat(itins, ignore_index=True)
dups = pd.concat(dups, ignore_index=True)
quality = pd.DataFrame(quality)
display(quality.drop(columns=['window_start', 'window_end']))
gname = tags.drop_duplicates('station_group_id').set_index('station_group_id')['stop_name']
print('trains present in two feeds (copies dropped), by feed pair and the busiest station pairs:')
display(dups.groupby(['run', 'drop_feed', 'keep_feed']).size().rename('legs dropped').to_frame())
display(dups.assign(pair=dups['from_group'].map(gname) + ' -> ' + dups['to_group'].map(gname))
        .groupby(['run', 'pair']).size().sort_values(ascending=False).head(10).rename('legs').to_frame())

# %% [markdown]
# ## 3. Per station and per LAU
#
# Four counts per unit (R1): distinct **journeys**, the distinct **first** and **second trains** behind them, and the
# journeys **sharing a train** with another journey to the same unit. Gateway dependence (PIP-15): the main transfer
# station's share of the LAU's journeys per day, and the fewest stations carrying 90 %.

# %%
station, lau, per_hub = [], [], []
for r in runs:
    N, W = len(r['days']), F.run_window(r)
    dl = direct[direct.run == r['run']]
    for d in ('inbound', 'outbound'):
        x = itins[(itins.run == r['run']) & (itins.direction == d)]
        if x.empty:
            continue
        s = C.summarise_one_transfer(x, 'station_key', N).assign(direction=d, country=r['country'], run=r['run'], **W)
        s['has_direct'] = s['station_key'].isin(set(dl.loc[dl.direction == d, 'station_key']))
        station.append(s)
        l = C.summarise_one_transfer(x, 'lau_gisco_id', N).assign(direction=d, country=r['country'], run=r['run'], **W)
        l['has_direct'] = l['lau_gisco_id'].isin(set(dl.loc[dl.direction == d, 'lau_gisco_id']))
        ph, hs = C.hub_dependence(x, 'lau_gisco_id', N, share=0.9)
        l = l.merge(hs[['lau_gisco_id', 'main_hub', 'main_hub_share', 'hubs_for_share']], on='lau_gisco_id', how='left')
        lau.append(l.rename(columns={'hubs_for_share': 'hubs_for_90'}))
        per_hub.append(ph.assign(direction=d, country=r['country'], run=r['run'], **W))
station = pd.concat(station, ignore_index=True)
station['lau_gisco_id'] = station['station_key'].map(lau_of)
station = (station.join(geo['stop_name'], on='station_key').join(lau_geo, on='lau_gisco_id')
           .join(snap.set_index('station_key')['rail_km'], on='station_key'))
station = station[['country', 'run', 'station_key', 'stop_name', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba',
                   'direction', 'n_journeys', 'journeys_per_day', 'service_days', 'service_share', 'min_time_min',
                   'median_time_min', 'n_first_legs', 'n_second_legs', 'n_shared_leg', 'n_hubs', 'median_wait_min',
                   'has_direct', 'rail_km', 'window_start', 'window_end', 'window_days']]
lau = pd.concat(lau, ignore_index=True).join(lau_geo, on='lau_gisco_id')
lau['population'] = lau['lau_gisco_id'].map(pop)
lau['pop_year'] = lau['lau_gisco_id'].map(pop_year)
lau = lau[['country', 'run', 'lau_gisco_id', 'lau_name_national', 'nuts3_id', 'degurba', 'population', 'pop_year',
           'direction', 'n_journeys', 'journeys_per_day', 'service_days', 'service_share', 'min_time_min', 'median_time_min',
           'n_first_legs', 'n_second_legs', 'n_shared_leg', 'n_hubs', 'median_wait_min', 'has_direct', 'main_hub',
           'main_hub_share', 'hubs_for_90', 'window_start', 'window_end', 'window_days']]
per_hub = pd.concat(per_hub, ignore_index=True)
print('largest LAUs reached with one transfer, inbound, per headline run:')
for r in runs:
    if r['headline']:
        x = lau[(lau.run == r['run']) & (lau.direction == 'inbound')].sort_values('population', ascending=False).head(5)
        display(x[['run', 'lau_name_national', 'population', 'journeys_per_day', 'median_time_min', 'median_wait_min',
                   'has_direct', 'main_hub', 'main_hub_share', 'hubs_for_90']])

# %% [markdown]
# ## 4. Coverage, with its denominators
#
# Per country: **all** LAUs, LAUs **with a station** of the run's feeds, **direct**, **one transfer**, **newly reached**
# (one transfer, no direct train), **direct or one transfer**.

# %%
rows = []
for r in runs:
    c = r['country']
    allc = set(L.loc[L['CNTR_CODE'] == c, 'GISCO_ID'])
    feeds = [cfg.domestic_feed] + r['feeds']
    ws = {lau_of[k] for k in tags.loc[tags.feed_key.isin(feeds) & (tags.nuts_rg_01_country_id == c), 'station_key']}
    for d in ('inbound', 'outbound'):
        dl = set(direct.loc[(direct.run == r['run']) & (direct.direction == d), 'lau_gisco_id'])
        ol = set(lau.loc[(lau.run == r['run']) & (lau.direction == d), 'lau_gisco_id'])
        for g, ids in [('all_lau', allc), ('with_station', ws), ('direct', dl), ('one_transfer', ol),
                       ('newly_reached', ol - dl), ('direct_or_one_transfer', ol | dl)]:
            ids = ids & allc
            rows.append({'country': c, 'run': r['run'], 'direction': d, 'group': g, 'n_lau': len(ids),
                         'population': pop.reindex(list(ids)).sum(), **F.run_window(r)})
cov = pd.DataFrame(rows)
base = cov[cov.group == 'all_lau'].set_index(['run', 'direction'])
k = list(zip(cov['run'], cov['direction']))
cov['share_lau'] = (cov['n_lau'] / base['n_lau'].reindex(k).to_numpy()).round(4)
cov['share_population'] = (cov['population'] / base['population'].reindex(k).to_numpy()).round(5)
cov = cov[['country', 'run', 'direction', 'group', 'n_lau', 'population', 'share_lau', 'share_population',
           'window_start', 'window_end', 'window_days']]
display(cov[cov.direction == 'inbound'].pivot_table(index='run', columns='group', values='n_lau', aggfunc='sum'))
display(cov[cov.direction == 'inbound'].pivot_table(index='run', columns='group', values='population', aggfunc='sum')
        .map(lambda v: f'{v:,.0f}'))

# %% [markdown]
# ## 5. Gateways
#
# Per transfer station: journeys per day through it, LAUs reached, and the LAUs **without a direct train for which it is
# the only transfer station** — the catchment that depends on it alone (PIP-15).

# %%
hubs_tab = []
for r in runs:
    for d in ('inbound', 'outbound'):
        nd = set(lau.loc[(lau.run == r['run']) & (lau.direction == d) & ~lau.has_direct, 'lau_gisco_id'])
        ph = per_hub[(per_hub.run == r['run']) & (per_hub.direction == d)]
        if ph.empty:
            continue
        n_h = ph.groupby('lau_gisco_id')['T'].nunique()
        only = ph[ph['lau_gisco_id'].map(n_h).eq(1) & ph['lau_gisco_id'].isin(nd)]
        t = ph.groupby('T_key').agg(journeys_per_day=('journeys_per_day', 'sum'), n_lau=('lau_gisco_id', 'nunique'))
        t['n_lau_only_hub'] = only.groupby('T_key')['lau_gisco_id'].nunique()
        t['pop_only_hub'] = only.assign(p=only['lau_gisco_id'].map(pop)).groupby('T_key')['p'].sum()
        hubs_tab.append(t.fillna({'n_lau_only_hub': 0, 'pop_only_hub': 0}).reset_index()
                        .assign(direction=d, country=r['country'], run=r['run'], **F.run_window(r)))
hubs_tab = pd.concat(hubs_tab, ignore_index=True)
hubs_tab['stop_name'] = hubs_tab['T_key'].map(geo['stop_name'])
hubs_tab['journeys_per_day'] = hubs_tab['journeys_per_day'].round(2)
hubs_tab = hubs_tab[['country', 'run', 'direction', 'T_key', 'stop_name', 'journeys_per_day', 'n_lau', 'n_lau_only_hub',
                     'pop_only_hub', 'window_start', 'window_end', 'window_days']] \
    .sort_values(['run', 'direction', 'pop_only_hub'], ascending=[True, True, False])
for r in runs:
    if r['headline']:
        display(hubs_tab[(hubs_tab.run == r['run']) & (hubs_tab.direction == 'inbound')].head(6)
                [['run', 'stop_name', 'journeys_per_day', 'n_lau', 'n_lau_only_hub', 'pop_only_hub']])
x = lau[lau.run.isin([r['run'] for r in runs if r['headline']]) & ~lau.has_direct]
print('newly reached LAUs depending on one gateway (hubs_for_90 = 1), share by run and direction:')
display(x.groupby(['run', 'direction'])['hubs_for_90'].apply(lambda s: round((s == 1).mean(), 3)).unstack())

# %% [markdown]
# ## 6. Transfer waits and connections across midnight
#
# The observed wait at the transfer station (STA-2), per run and direction, over the distinct journeys; and the
# journeys whose second train leaves after midnight on the next date (PIP-6), with the LAUs reached **only** that way.

# %%
u = itins.drop_duplicates(['run', 'direction', 'lau_gisco_id', 'leg1_trip', 'leg2_trip'])
w = u.groupby(['run', 'direction'])['wait_s'].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])
display((w.drop(columns='count') / 60).round(1).assign(journeys=w['count'].astype(int)))
nd_only = []
for (rid, d), g in u.groupby(['run', 'direction']):
    any_l = set(g['lau_gisco_id'])
    same = set(g.loc[~g['next_day'], 'lau_gisco_id'])
    dl = set(direct.loc[(direct.run == rid) & (direct.direction == d), 'lau_gisco_id'])
    only = any_l - same - dl
    nd_only.append({'run': rid, 'direction': d, 'journeys_next_day': int(g['next_day'].sum()),
                    'lau_only_next_day': len(only), 'pop_only_next_day': pop.reindex(list(only)).sum()})
display(pd.DataFrame(nd_only))

# %% [markdown]
# ## 7. Sensitivity
#
# * **Transfer window** (VAL-2): the configured grid against the base window, per headline run.
# * **City transfers** (PIP-17): a transfer may join **any two stations of one LAU** (Budapest-Keleti → Nyugati, Praha
#   hl.n. → Masarykovo, Wien Meidling → Hbf) with a minimum of **45 min** for crossing the city. The headline keeps
#   same-station transfers; the extra LAUs and population this reaches measure what that rule leaves out.

# %%
def sens_row(r, it, d, variant, mn, mx):
    N = len(r['days'])
    dl = set(direct.loc[(direct.run == r['run']) & (direct.direction == d), 'lau_gisco_id'])
    x = it[it.direction == d]
    s = C.summarise_one_transfer(x, 'lau_gisco_id', N) if len(x) else pd.DataFrame(columns=['lau_gisco_id', 'journeys_per_day'])
    new = x[~x['lau_gisco_id'].isin(dl)]
    _, hs = C.hub_dependence(new, 'lau_gisco_id', N) if len(new) else (None, pd.DataFrame(columns=['hubs_for_share']))
    nl = set(new['lau_gisco_id'])
    return {'country': r['country'], 'run': r['run'], 'direction': d, 'variant': variant, 'min_connect_min': mn,
            'max_connect_min': mx, 'is_base': variant == 'window' and (mn, mx) == (cfg.min_connect_min, cfg.max_connect_min),
            'n_lau_one_transfer': len(s), 'n_lau_newly_reached': len(nl), 'pop_newly_reached': pop.reindex(list(nl)).sum(),
            'journeys_per_day': round(s['journeys_per_day'].sum(), 2),
            'single_hub_share': round((hs['hubs_for_share'] == 1).mean(), 3) if len(hs) else None, **F.run_window(r)}


grid = sorted(set(cfg.sensitivity_grid) | {(cfg.min_connect_min, cfg.max_connect_min)})
sens = []
for r in runs:
    if not r['headline']:
        continue
    for mn, mx in grid:
        it = itins[itins.run == r['run']] if (mn, mx) == (cfg.min_connect_min, cfg.max_connect_min) else \
            F.run_one_transfer(cfg, r, TT[r['run']], tags, hubs, mn=mn, mx=mx)[0]
        for d in ('inbound', 'outbound'):
            sens.append(sens_row(r, it, d, 'window', mn, mx))
    city = F.run_one_transfer(cfg, r, TT[r['run']], tags, hubs, mn=45, transfer_unit='lau')[0]
    for d in ('inbound', 'outbound'):
        sens.append(sens_row(r, city, d, 'city_transfer', 45, cfg.max_connect_min))
sens = pd.DataFrame(sens)
display(sens[sens.direction == 'inbound'][['run', 'variant', 'min_connect_min', 'max_connect_min', 'is_base', 'n_lau_one_transfer',
                                            'n_lau_newly_reached', 'pop_newly_reached', 'journeys_per_day', 'single_hub_share']])
base_l = {(x.run, x.direction): set(lau.loc[(lau.run == x.run) & (lau.direction == x.direction), 'lau_gisco_id']) for x in sens.itertuples()}
print('city transfers (PIP-17): LAUs reached only with a transfer between two stations of one city, inbound:')
for r in runs:
    if r['headline']:
        city = F.run_one_transfer(cfg, r, TT[r['run']], tags, hubs, mn=45, transfer_unit='lau')[0]
        c_in = set(city.loc[city.direction == 'inbound', 'lau_gisco_id'])
        extra = c_in - base_l[(r['run'], 'inbound')] - set(direct.loc[(direct.run == r['run']) & (direct.direction == 'inbound'), 'lau_gisco_id'])
        via = city[(city.direction == 'inbound') & city['lau_gisco_id'].isin(extra)]['T'].value_counts().head(3)
        print(f"  {r['run']}: {len(extra)} LAUs, {pop.reindex(list(extra)).sum():,.0f} people; transfer cities: "
              + ', '.join(f"{lau_geo['lau_name_national'].get(t, t)} ({n})" for t, n in via.items()))

# %% [markdown]
# ## 8. Against the legacy run (`output/ke`)
#
# The legacy run (`journey_efficiency_foreign_onehop.csv`) paired a ZSSK leg with the national feed at **matched
# gateway stations only**, on the domestic window, with the wrong Polish feed (CF-23: PKP Intercity under the name of
# PolishTrainsGTFS) and a modulo-24 h wait (PIP-6); its LAU codes are DEGURBA-2021. Compared per country: LAUs reached
# (inbound, one transfer), and journeys per day for LAUs in both.

# %%
old = pd.read_csv('output/ke/journey_efficiency_foreign_onehop.csv', encoding='utf-8-sig')[['euc_lau_code', 'euc_lau_national', 'country', 'avg_per_day']]
new = lau[(lau.direction == 'inbound') & lau.run.isin([r['run'] for r in runs if r['headline']])]
print('LAUs per country, new (inbound, one transfer) vs legacy:')
display(pd.DataFrame({'new': new.groupby('country').size(), 'legacy': old.groupby('country').size()}).fillna(0).astype(int))
m = new.merge(old, left_on='lau_gisco_id', right_on='euc_lau_code', how='inner')
m['ratio'] = (m['journeys_per_day'] / m['avg_per_day']).round(2)
print(f'{len(m)} LAUs in both; median ratio new / legacy journeys per day by country:')
display(m.groupby('country_x')['ratio'].describe()[['count', '25%', '50%', '75%']])
print('legacy LAUs not reached now (first 15):')
display(old[~old['euc_lau_code'].isin(new['lau_gisco_id'])].head(15))

# %% [markdown]
# ## 9. Outputs

# %%
p = os.path.join(OUT, 'one_transfer_itins.parquet')
itins.to_parquet(p, index=False)
write_meta(p, 'foreign_one_transfer_itins', itins, {'Transfer window': f'{cfg.min_connect_min}-{cfg.max_connect_min} min',
                                                     'Pairing': cfg.transfer_pairing})
print(f'[wrote] {p} ({len(itins):,} rows)')
for name, key, frame in [('one_transfer_station.csv', 'foreign_one_transfer_station', station),
                         ('one_transfer_lau.csv', 'foreign_one_transfer_lau', lau),
                         ('one_transfer_hubs.csv', 'foreign_one_transfer_hubs', hubs_tab),
                         ('one_transfer_coverage.csv', 'foreign_one_transfer_coverage', cov),
                         ('one_transfer_sensitivity.csv', 'foreign_one_transfer_sensitivity', sens),
                         ('cross_feed_duplicates.csv', 'foreign_cross_feed_duplicates', dups),
                         ('feed_quality.csv', 'foreign_feed_quality', quality)]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Transfer window': f'{cfg.min_connect_min}-{cfg.max_connect_min} min',
                               'Pairing': cfg.transfer_pairing})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')
