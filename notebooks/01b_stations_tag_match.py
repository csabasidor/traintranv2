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
# # 01b — Stations of all six feeds: tagging, foreign matching, cross-feed identity
#
# Second step of the split pipeline (**01a → 01b → 02 / 03**). Reads only what `01a_feeds_download`
# wrote (feeds, `windows.json`, `feed_roles.csv`). Code: `traintranv2/nb01b_stations.py`.
#
# **Domestic feed: ZSR_SK** (from `feed_roles.csv`); foreign: DRAHY_CZ, MAV_HU, BAHN_AT, PL_IC, PL_REG,
# UKRZ_UA. Every feed's stations get **the same treatment**:
#
# | § | step | writes (`output/kosice/` unless noted) |
# |---|---|---|
# | 1 | polygon check of every stop of every feed | `feed_stop_tags.parquet` |
# | 2 | manual LAU corrections, keyed on (feed_key, stop_id) | `data/manual/lau_manual_matches_v2.csv` |
# | 3 | **station catalog per feed**: platforms → their GTFS **parent** station; stops without a parent → same name within 2 km | — |
# | 4 | tagging: polygon → name check (SK only; **CZ, HU, PL, AT and UA: polygon only**) → manual → UA fallback; **review list of every unresolved in-scope station** | `station_tags_review.csv` |
# | 5 | foreign matching of the domestic stations in CZ/HU/AT/PL/UA (name or UIC code **and** same LAU **and** ≤ 0.5 km → auto; else review, with the feed's stations nearby as position candidates) | `station_feed_matches.csv`, `station_feed_review.csv` |
# | 6 | **cross-feed identity**: one `station_group_id` per physical station (UIC code / place + name / accepted match / reviewed pair); close pairs with different names → review | `station_tags.csv`, `station_group_links.csv`, `station_group_review.csv` |
# | 7 | data dictionaries | `*.meta.md` |
#
# **Why parents:** trips (`stop_times.txt`) reference only the **child** stops, the platforms; a parent
# (location_type 1) is the station as a whole and never appears in a trip. So a station = a parent with
# its platforms; entrances, tunnels and parkings (location_type 2/3) are dropped. HU, UA and the SK feed
# have no parents, so their stops are merged by name (same `norm_name` within 2 km), the domestic run's
# rule. Scope: only stations inside CZ, SK, AT, HU, PL, UA are tagged; GeoJSON inputs only.

# %%
import os, sys

# Run from the project root so every relative path ('data/...', 'traintranv2/...') resolves the
# same whether the notebook is launched from notebooks/ or from the root.
_here = os.path.abspath('')
if os.path.basename(_here) == 'notebooks':
    os.chdir(os.path.dirname(_here))
sys.path.insert(0, os.getcwd())
print('Working directory:', os.getcwd())

# %%
import json
from pathlib import Path

import pandas as pd

import traintranv2  # noqa: F401  (fixes PROJ on import)
from traintranv2.config import default_config
from traintranv2.nb01a_feeds import haversine_km, norm_name, read_table
from traintranv2.nb01a_feeds import feed_zip_path
from traintranv2.nb01a_feeds import write_meta

cfg = default_config()
cfg.city_slug = 'kosice'
OUT = Path(cfg.out_dir)
for f in ('windows.json', 'feed_roles.csv'):
    if not (OUT / f).exists():
        raise FileNotFoundError(f'{OUT / f} missing -- run 01a_feeds_download.ipynb first')
roles = pd.read_csv(OUT / 'feed_roles.csv', encoding='utf-8-sig')
DOMESTIC = roles.loc[roles.role == 'domestic', 'feed_key'].item()
assert DOMESTIC == cfg.domestic_feed
FEEDS = roles['feed_key'].tolist()
print(f'DOMESTIC FEED : {DOMESTIC}')
print(f'FOREIGN FEEDS : {[k for k in FEEDS if k != DOMESTIC]}')
print(f'matching      : name (or UIC code) + same LAU + <= {cfg.match_auto_max_km} km (fuzzy >= {cfg.fuzzy_threshold}); '
      f'position candidates within {cfg.match_candidate_km} km for review')

# %% [markdown]
# ## 1. Polygon check of every stop
#
# Each stop of each feed located in the LAU subset (point in polygon, no name check yet). Stops outside the
# six countries are counted under `outside` and otherwise ignored.

# %%
from traintranv2.nb01b_stations import tag_feed_stops

feed_stops = tag_feed_stops(cfg, keys=FEEDS)
feed_stops.to_parquet(OUT / 'feed_stop_tags.parquet', index=False)
country = feed_stops['CNTR_CODE'].where(feed_stops['in_scope'], 'outside')
country = country.where(feed_stops['stop_lat'].notna(), 'no coordinates')
print(f'{len(feed_stops):,} stops in {feed_stops.feed_key.nunique()} feeds -> {OUT / "feed_stop_tags.parquet"}\n')
display(pd.crosstab(feed_stops['feed_key'], country, margins=True))

# %% [markdown]
# ## 2. Manual LAU corrections
#
# `lau_manual_matches_v2.csv` is keyed on **(feed_key, stop_id)**. It was converted once from the legacy
# `lau_manual_matches.csv` (keyed on the old run's `S000nn` ids and DEGURBA-2021 LAU ids): `S000nn` →
# the ZSR_SK stop_id through the legacy catalog (same name, ≤ 100 m `ok`, ≤ 1 km `ok_near`, else
# `unmatched`); DE / CH → `dropped_out_of_scope`; old UA ids → `ua_review`. Only `ok` / `ok_near` rows
# are applied. Rows without `feed_key` are domestic (ZSR_SK). Reviewed corrections for any feed are
# added with their `feed_key`.

# %%
REBUILD_MANUAL_V2 = False
V1 = Path('data/manual/lau_manual_matches.csv')
V2 = Path(cfg.lau_manual_matches_file)
if V2.exists() and not REBUILD_MANUAL_V2:
    print('[exists]', V2)
else:
    from traintranv2.nb01b_stations import load_lau_subset
    old = pd.read_csv(V1, dtype=str, encoding='utf-8-sig')
    legacy_cat = pd.read_csv('output/ke/station_catalog.csv', dtype=str, encoding='utf-8-sig')[['station_id', 'name', 'lat', 'lon']]
    sk = pd.DataFrame(list(read_table(feed_zip_path(cfg, DOMESTIC), 'stops.txt')))
    sk['n'] = sk['stop_name'].map(norm_name)
    gisco = set(load_lau_subset(cfg)['GISCO_ID'])
    rows = []
    for _, r in old.merge(legacy_cat, on='station_id', how='left').iterrows():
        same = sk[sk['n'] == norm_name(r['name'])]
        stop_id, d, key = '', None, 'unmatched'
        if len(same):
            dist = [haversine_km((float(r['lat']), float(r['lon'])), (float(a), float(b))) for a, b in zip(same.stop_lat, same.stop_lon)]
            k = min(range(len(dist)), key=dist.__getitem__)
            stop_id, d = same.iloc[k]['stop_id'], dist[k]
            key = 'ok' if d <= 0.1 else ('ok_near' if d <= 1.0 else 'unmatched_far')
        g = r['dgurba_gisco_id']   # legacy catalog column
        if not key.startswith('unmatched') and g not in gisco:
            key = 'dropped_out_of_scope' if g[:2] in ('DE', 'CH') else ('ua_review' if g.startswith('UA') else 'gisco_not_in_subset')
        rows.append({'feed_key': DOMESTIC, 'stop_id': stop_id, 'stop_name': r['name'], 'gisco_id': g, 'note': r['note'],
                     'conversion': key, 'legacy_station_id': r['station_id'], 'match_distance_km': None if d is None else round(d, 3)})
    pd.DataFrame(rows).to_csv(V2, index=False, encoding='utf-8')
    print('[wrote]', V2)
v2 = pd.read_csv(V2, dtype=str, encoding='utf-8-sig')
if 'feed_key' not in v2.columns:                       # files from before the multi-feed catalog
    v2.insert(0, 'feed_key', DOMESTIC)
    v2.to_csv(V2, index=False, encoding='utf-8')
    print('[updated]', V2, '-- feed_key column added (all existing rows are', DOMESTIC + ')')
display(pd.crosstab(v2['feed_key'], v2['conversion']))

# %% [markdown]
# ## 3. Station catalog of every feed
#
# Per feed: boarding stops (location_type empty / 0) → stations. A platform belongs to its GTFS **parent**
# station (`parent`); a stop without a parent joins an earlier same-name stop within 2 km (`name_2km`) or
# stands alone (`single`). `station_key = <feed>:<parent or first stop_id>` is stable. `uic_code` is the
# 7-digit UIC station code where the feed carries it (ZSR_SK and UKRZ_UA stop_ids; DRAHY_CZ 54 + its
# national number). For the domestic feed the catalog must equal the domestic run's stations exactly.
#
# **Excluded before grouping** (`cfg.excluded_agencies`, `cfg.drop_bus_only_stops`): stops served only by an
# excluded agency — MÁV agency 1743, the **Budapest Children's Railway** (Gyermekvasút, a heritage line with no
# link to the network) — and stops whose every trip is a **bus** (route_type 3 / 700–799): Postbus stops in
# the AT feed, rail-replacement stops (NAD, ZKA), and stations whose whole service in the window is a
# replacement bus. A stop also served by any train stays. ZSR_SK and UKRZ_UA lose no station.
#
# **How bus-only stops are identified** (`nb01b_stations.excluded_stop_ids`), from each feed's own timetable —
# no names or positions are used:
#
# 1. **Bus routes**: `routes.txt` rows whose GTFS `route_type` is **3** (basic bus) or **700–799** (extended
#    bus types; 714 = rail-replacement bus).
# 2. **Bus trips**: every trip of such a route (`trips.txt`).
# 3. **Stop usage**: the whole `stop_times.txt` is read; for each `stop_id` it is recorded whether bus trips,
#    train trips, or both call there.
# 4. **Rule**: a stop is dropped only if **every** trip calling there is a bus. One train trip anywhere in the
#    feed keeps it.
#
# How the feeds code their buses:
#
# | feed | bus route_type | what they are |
# |---|---|---|
# | MAV_HU | 3 (2,542 routes) | MÁV bus routes (G40, G70, S30 …) |
# | BAHN_AT | 3 (237 routes) | Postbus / regional buses |
# | DRAHY_CZ | 714 (3,848 routes) | rail-replacement buses, "… (NAD)" |
# | PL_REG | 3 (49 routes) | replacement buses, "ZKA …" (PL_IC: 2 PKP Intercity bus routes) |
# | ZSR_SK, UKRZ_UA | — | rail route types only (100–106) |
#
# **Children no train uses are not members.** Some feeds hang every stop of a transport hub under the rail
# station's parent: BAHN_AT puts the bus bays, tram and U-Bahn stops there ("Bus an", "86A", "10A", "Tram",
# "U6", "Vorplatz" under Wien Meidling / Stadlau / Gersthof …; 774 such stops), and the Polish feeds keep
# an unused stop record next to the platforms. **A parent's child that no kept trip calls at is left out**;
# the parent still gives the station's name and point. A station with no used stop at all keeps its stops
# (`in_trips = False`). No name rule is used: a used platform named differently from its station (BAHN_AT
# "Graz Hbf" under "Graz Hauptbahnhof", 55 cases) stays. ZSR_SK, MÁV, UZ and the CZ feed lose nothing (their
# route types are rail only, or every child is used).
#
# Replacement buses usually have their **own stop_id under the same parent station**, so dropping them removes
# the bus stand, not the station (CZ: 2,113 stops dropped, 18 stations). A **whole station disappears only when
# no train calls there at all in the feed's window**: the line is bus-replaced for the whole year (CZ
# Opava–Hlučín, PL ZKA lines, MÁV's suspended lines) or it is a pure bus stop (AT Postbus).
# *Limitation:* the rule looks at the whole window — a station with trains for part of the year and buses for
# the rest is kept.

# %%
from traintranv2.nb01b_stations import build_station_catalog, excluded_stop_ids, trip_stop_ids
from traintranv2.nb01a_feeds import load_calendars, load_network, stations_frame

catalogs, summary = [], []
for k in FEEDS:
    c = build_station_catalog(cfg, k)
    catalogs.append(c)
    summary.append({'feed_key': k, 'stops': c.attrs['n_stops'], 'boarding_stops': c.attrs['n_boarding'],
                    'stops_used_by_trips': c.attrs['n_used'], 'stations': len(c),
                    **c['dedup_method'].value_counts().reindex(['parent', 'name_2km', 'single'], fill_value=0).to_dict(),
                    'unused_children_left_out': c.attrs['n_unused_children'],
                    'stations_in_trips': int(c['in_trips'].sum()), 'with_uic_code': int((c['uic_code'] != '').sum())})
catalog = pd.concat(catalogs, ignore_index=True)
display(pd.DataFrame(summary).set_index('feed_key'))

# The domestic catalog must be the domestic run's stations (same member stop_ids).
cfg.enabled = [DOMESTIC]
_fc, _fi = load_calendars(cfg)
_net = load_network(cfg, _fc, _fi)
_a = sorted(sorted(x.split(';')) for x in catalog.loc[catalog.feed_key == DOMESTIC, 'stop_ids'])
_b = sorted(sorted(x.split(';')) for x in stations_frame(_net)['stop_ids'])
assert _a == _b, 'domestic catalog differs from the domestic run'
# Every stop used by a trip belongs to exactly one station of its feed.
for k in FEEDS:
    members = catalog.loc[catalog.feed_key == k, 'stop_ids'].str.split(';').explode()
    assert members.is_unique, f'{k}: a stop sits in two stations'
    _ex = excluded_stop_ids(cfg, k)
    _dropped = _ex['agency'] | _ex['bus_only']
    missing = trip_stop_ids(cfg, k) - set(members) - _dropped
    assert not missing, f'{k}: {len(missing)} trip stops in no station, e.g. {sorted(missing)[:3]}'
    if _dropped:
        print(f'  {k}: {len(_ex["agency"])} stops of excluded agencies, {len(_ex["bus_only"])} bus-only stops left out on purpose')
print(f'catalog: {len(catalog):,} stations; domestic = the domestic run ({len(_b)}); '
      f'every trip stop not excluded on purpose is in exactly one station')

# %% [markdown]
# ## 4. Tagging all stations, and the review list
#
# Each station gets exactly one LAU (and through it NUTS 2 / 3, DEGURBA and population). The steps, in order:
#
# 1. **Polygon.** The LAU whose polygon contains the station point (§1). A station outside every polygon of
#    the six countries is `in_scope = False` and is not reviewed.
# 2. **Name check: depends on the country of that polygon.**
#    * **CZ, HU, PL, AT and UA: polygon only** (`cfg.lau_polygon_only_countries`). Stations in these
#      countries are mostly named after a village, locality or part of a municipality (*část obce*,
#      *településrész*, *wieś*, *Ortschaft* / *Katastralgemeinde*, *село*) inside a larger **obec** /
#      **település** / **gmina** / **Gemeinde** / **hromada**: Vrbka lies in Budyně nad Ohří, Hetényegyháza
#      in Kecskemét, Radostowice in gmina Suszec, Schauboden in Purgstall an der Erlauf. UA hromada names are moreover adjectival forms
#      ("Мукачівська" for the Mukachevo hromada), so they rarely match a station name even for the town itself.
#      The station name rarely contains the LAU name, so a name check says nothing about whether the
#      LAU is right. The polygon LAU is taken as it is: `lau_match_method = polygon_accepted`. There is
#      no fuzzy matching and no move to a neighbour. `lau_name_score` is still filled in, for information only.
#    * **SK (the domestic feed's own country): the polygon LAU is checked against the station name**, using the LAU's national
#      **and** Latin name, whichever fits better. "Fits" means one name contains the other, or the LAU
#      name is the leading word(s) of the station name ("Łódź Fabryczna", "Wien Hbf"), or the fuzzy
#      score is at least `cfg.lau_fuzzy_threshold` (0.6). The method is one of:
#      * `contains_primary` / `fuzzy_primary`: the polygon LAU fits, so it is kept;
#      * `contains_neighbor` / `fuzzy_neighbor`: the polygon LAU does not fit, but a LAU within
#        `cfg.lau_neighbor_radius_km` (2 km, measured in metres in EPSG:5514) does. The station moves to that LAU;
#      * `unresolved`: nothing fits. The polygon LAU is kept, and the station goes to the review list.
# 3. **Manual corrections** (`data/manual/lau_manual_matches_v2.csv`, keyed on `feed_key` + one member
#    `stop_id`, rows with `conversion = ok` / `ok_near`) override steps 1–2: `lau_match_method = manual`.
#    They apply in every country, PL and AT included.
# 4. **UA fallback**: only for a UA station outside every hromada polygon (hard-coded Chop / Mukachevo /
#    Uzhhorod values).
#
# **Review list** (`station_tags_review.csv`): every in-scope station still `unresolved` after step 3, with
# up to three LAU candidates within 2 km and their name scores. Decisions go into
# `lau_manual_matches_v2.csv` (`feed_key`, one member `stop_id`, `gisco_id`, `conversion = ok`, a note).

# %%
from traintranv2.nb01b_stations import tag_stops, unresolved_review

tags = tag_stops(catalog.assign(stop_id=catalog['station_key']), cfg).drop(columns='stop_id')
display(pd.crosstab(tags['feed_key'], tags['lau_match_method'], margins=True))
display(pd.crosstab(tags['feed_key'], tags['nuts_rg_01_country_id']))

review_lau = unresolved_review(tags, cfg)
review_lau.to_csv(OUT / 'station_tags_review.csv', index=False, encoding='utf-8-sig')
print(f'[wrote] {OUT / "station_tags_review.csv"}: {len(review_lau)} unresolved in-scope stations')
display(review_lau.groupby('feed_key').size().rename('to review').to_frame().T)

# %%
# Domestic stations against the legacy run (output/ke/station_catalog.csv), by name.
legacy = (pd.read_csv('output/ke/station_catalog.csv', dtype=str, encoding='utf-8-sig')[['name', 'dgurba_gisco_id']]
          .rename(columns={'dgurba_gisco_id': 'lau_gisco_id'}))   # legacy column name
dom_tags = tags[tags.feed_key == DOMESTIC]
cmp = dom_tags[['stop_name', 'lau_gisco_id', 'lau_match_method', 'in_scope']].merge(
    legacy.drop_duplicates('name'), left_on='stop_name', right_on='name', how='left', suffixes=('', '_legacy'))
both = cmp[cmp['lau_gisco_id_legacy'].notna()]
diff = both[both['lau_gisco_id'] != both['lau_gisco_id_legacy']]
print(f'domestic: {len(both)} stations also in the legacy catalog; same LAU {len(both) - len(diff)}, different {len(diff)} '
      f'({int((~diff.in_scope.astype(bool)).sum())} of them now out of scope)')
display(diff[['stop_name', 'lau_gisco_id_legacy', 'lau_gisco_id', 'lau_match_method']])

# %% [markdown]
# ## 5. Foreign matching of the domestic stations
#
# Domestic stations tagged in **CZ, HU, AT, PL or UA** are matched to their country's feed(s) — Poland to
# both PL_IC (PKP Intercity) and PL_REG (the other carriers). Only the feed's **catalog stations** (§3) are
# searched: entrances, dropped bus stops and unused children cannot be hit.
#
# **1. Name.** A hit is the same **UIC code** or a **name** match, tried over the name and its rewrites:
#
# | tier / rule | example (SK feed → foreign feed) |
# |---|---|
# | exact (`norm_name`: lower case, no diacritics) | Zwardon → Zwardoń |
# | country tag in brackets dropped (every country) | Zwardon(PL), Rybnik(PL) → Zwardoń, Rybnik |
# | PL abbreviations: Sl. Śląski, Gl. Główny, Pd. Południe, Pn. Północ | Wodzislaw Sl. → Wodzisław Śląski |
# | SK abbreviations: p. pod, n. nad, N. Nová, zast. zastávka | Lúky p.Makytou → Lúky pod Makytou |
# | CZ abbreviations, brackets | Brno hl.n. → Brno hlavní nádraží |
# | AT Hbf → Hauptbahnhof, `… Bahnhof`, qualifiers (b.Wien, am …, /…) dropped | Baden b.Wien → Baden Bahnhof |
# | HU ` pu`; UA Cyrillic name map | Budapest-Keleti pu → Budapest-Keleti |
# | **core**: generic station words at the end dropped on both sides (Bahnhof, Bhf., pályaudvar, stacja kolejowa, železniční stanice, stanica, CZ request flag "z") | Sopron → Sopron pályaudvar |
# | fuzzy (SequenceMatcher ≥ 0.90) | Miskolc Tiszai pu → Miskolc-Tiszai |
#
# "zastávka" is not a generic word: Skalité zast. and Skalité are different stops about 1 km apart.
#
# **2. Position and LAU.** A name hit is **auto** only if its station lies in the **same LAU** as the domestic
# one (the foreign *station's* LAU from §4) **and** within **0.5 km** (`cfg.match_auto_max_km`; 99 % of the
# accepted pairs are within 0.44 km). An exact name across a LAU border is **not** enough: the two feeds'
# points of one station can lie either side of a municipal border (Hidasnémeti, Ropice zastávka, Bruck/Leitha
# …), but so can two different places. Such pairs are decided once, by hand.
#
# **3. No automatic hit → position candidates.** The feed's stations within 1 km (`cfg.match_candidate_km`),
# **same LAU first**, then by distance, are listed in `alternatives`; the first is in `suggested_feed_stop_id`
# (`reason = position_candidate`, or `no_name_match` if nothing is near). Review rows are not used until decided in
# `data/manual/station_feed_manual.csv` (`accept` / `reject`, `feed_stop_id` = the suggested or another stop).
#
# An accepted match expands to the foreign **catalog station**: its GTFS parent plus the member stops trains use
# (`feed_station_name` carries the station's name).

# %%
from traintranv2.nb01b_stations import _load_stops_from_zip, _match_station, match_foreign_stations, match_summary

MANUAL_FEED = Path(cfg.station_feed_manual_file)
if not MANUAL_FEED.exists():
    bts = tags[(tags.feed_key == DOMESTIC) & (tags['stop_name'].map(norm_name) == norm_name('Bratislava hl.st.'))]
    assert len(bts) == 1, bts
    _at = _load_stops_from_zip(feed_zip_path(cfg, 'BAHN_AT'))
    at_hit = next((h for q in ('Bratislava hl.st.', 'Bratislava hlavná stanica')
                   for h in [_match_station(q, _at, cfg.fuzzy_threshold)] if h), None)
    assert at_hit, 'Bratislava hl.st. not found in BAHN_AT'
    pd.DataFrame([{'station_name': bts.iloc[0]['stop_name'], 'station_stop_id': bts.iloc[0]['stop_ids'].split(';')[0],
                   'feed_key': 'BAHN_AT', 'feed_stop_id': at_hit[0]['feed_stop_id'],
                   'feed_stop_name': at_hit[0]['feed_stop_name'], 'decision': 'accept',
                   'note': 'legacy manual override (ksc_analysis cfg.manual_station_matches)'}]
                 ).to_csv(MANUAL_FEED, index=False, encoding='utf-8')
    print('[seeded]', MANUAL_FEED)

matches = match_foreign_stations(cfg, tags, feed_stops)
matches.to_csv(OUT / 'station_feed_matches.csv', index=False, encoding='utf-8-sig')
summary_m = match_summary(matches)
review = summary_m[summary_m['status'] == 'review'].assign(decision='', note='')
review[['station_name', 'station_stop_ids', 'country', 'feed_key', 'reason', 'match_type', 'score',
        'feed_stop_id', 'feed_stop_name', 'feed_station_name', 'match_distance_km', 'same_lau', 'alternatives',
        'suggested_feed_stop_id', 'decision', 'note']
       ].to_csv(OUT / 'station_feed_review.csv', index=False, encoding='utf-8-sig')
print(f'[wrote] {OUT / "station_feed_matches.csv"} ({len(matches)} rows), {OUT / "station_feed_review.csv"} ({len(review)} to review)\n')
display(pd.crosstab(summary_m['country'], summary_m['status'], margins=True))
display(pd.crosstab(summary_m['status'], summary_m['match_type']))
display(review[['station_name', 'country', 'feed_key', 'reason', 'match_type', 'feed_stop_name', 'match_distance_km', 'alternatives']])
print('previous run (exact name across a LAU border auto, 1 km limit): 173 auto / 1 manual / 13 review')

# %% [markdown]
# ## 6. Cross-feed identity: `station_group_id`
#
# The same physical station in several feeds (Bohumín is in the SK, CZ, PL and AT feeds) gets one
# `station_group_id`. Links between stations of **different** feeds:
#
# 1. **code**: the same UIC code (SK ↔ CZ, SK ↔ UA); a code pair more than 5 km apart is a **conflict**
#    and is not linked;
# 2. **place**: the same LAU, within **0.5 km**, and the names match (the §5 name rules on both names:
#    equal, equal core name, or fuzzy ≥ 0.90). "Skalité p.Poľanou" = PL_REG "Skalité pod Poľanou",
#    "Sopron" = BAHN_AT "Sopron pályaudvar";
# 3. **match**: an accepted foreign match from §5;
# 4. **manual**: a pair accepted in `data/manual/station_group_manual.csv` (a `reject` there removes any
#    direct link between the two stations).
#
# **Review** (`station_group_review.csv`): stations of different feeds in the same LAU within 0.5 km whose
# names do not match and that stay in different groups. Position alone is not enough — Bratislava predm. and
# Bratislava-Vinohrady lie 0.17 km apart, Wien Hbf and Wien Quartier Belvedere 0.32 km — so these are decided
# by hand (`a`, `b`, `decision` accept / reject, `note`).
#
# Groups are connected components; the id is `G:` + the smallest `station_key` of the group.

# %%
from traintranv2.nb01b_stations import link_station_groups

MANUAL_GROUP = Path(cfg.station_group_manual_file)
if not MANUAL_GROUP.exists():
    pd.DataFrame(columns=['a', 'a_name', 'b', 'b_name', 'decision', 'note']).to_csv(MANUAL_GROUP, index=False, encoding='utf-8')
    print('[created, empty]', MANUAL_GROUP)
tags, links, conflicts, group_review = link_station_groups(tags, cfg, matches)
tags.to_csv(OUT / 'station_tags.csv', index=False, encoding='utf-8-sig')
links.to_csv(OUT / 'station_group_links.csv', index=False, encoding='utf-8-sig')
conflicts.to_csv(OUT / 'station_group_conflicts.csv', index=False, encoding='utf-8-sig')
group_review.to_csv(OUT / 'station_group_review.csv', index=False, encoding='utf-8-sig')
print(f'[wrote] {OUT / "station_tags.csv"} ({len(tags):,} stations), station_group_links.csv ({len(links)}), '
      f'station_group_conflicts.csv ({len(conflicts)}), station_group_review.csv ({len(group_review)} to review)\n')
display(group_review.drop(columns=['decision', 'note']))
display(links['tier'].value_counts().rename('links').to_frame().T)
g = tags.drop_duplicates('station_group_id')
display(g['group_n_feeds'].value_counts().sort_index().rename('groups').to_frame().T)
multi = tags[tags.group_n_feeds > 1]
print(f'{multi.station_group_id.nunique()} stations appear in more than one feed')
for name in ['Bohumín', 'Bratislava hl.st.', 'Wien Hbf', 'Chop', 'Košice', 'Budapest-Keleti']:
    gid = tags.loc[tags.stop_name.str.startswith(name) & (tags.feed_key == DOMESTIC), 'station_group_id']
    if len(gid):
        print(f'\n{name}:')
        display(tags[tags.station_group_id == gid.iloc[0]][['feed_key', 'station_key', 'stop_name', 'uic_code', 'lau_gisco_id', 'link_tiers']])
if len(conflicts):
    print('code conflicts (same UIC code, > 5 km apart, not linked):')
    display(conflicts)

# %% [markdown]
# ## 7. Data dictionaries
#
# Every tabular output gets a `<file>.meta.md` (`traintranv2/nb01a_feeds.py`, `SCHEMAS`); writing fails if a column is
# undocumented.

# %%
_r = lambda p: pd.read_csv(p, dtype=str, encoding='utf-8-sig')
for path, key, read in [
    (OUT / 'station_tags.csv', 'station_tags', _r),
    (OUT / 'station_tags_review.csv', 'station_tags_review', _r),
    (OUT / 'feed_stop_tags.parquet', 'feed_stop_tags', pd.read_parquet),
    (OUT / 'station_feed_matches.csv', 'station_feed_matches', _r),
    (OUT / 'station_feed_review.csv', 'station_feed_review', _r),
    (OUT / 'station_group_links.csv', 'station_group_links', _r),
    (OUT / 'station_group_conflicts.csv', 'station_group_links', _r),
    (OUT / 'station_group_review.csv', 'station_group_review', _r),
    (Path(cfg.station_group_manual_file), 'station_group_manual', _r),
    (Path(cfg.station_feed_manual_file), 'station_feed_manual', _r),
    (Path(cfg.lau_manual_matches_file), 'lau_manual_matches_v2', _r),
]:
    print('[meta]', write_meta(str(path), key, read(path), extra={'Domestic feed': DOMESTIC}))

# %% [markdown]
# ## Next
#
# 1. Review `station_tags_review.csv` (LAU), `station_feed_review.csv` (foreign matches) and
#    `station_group_review.csv` (cross-feed pairs); record the decisions in `data/manual/` and re-run.
# 2. `02_analysis_domestic` reads `station_tags.csv` (domestic rows) and `windows.json`;
#    `03_analysis_foreign` reads `station_feed_matches.csv` (`best_match = 1`), `station_tags.csv` (all
#    feeds) and `windows.json`. Connection counting follows the trip-based rule in
#    `plan_part_a_tagging_refactor.md` §5, using `station_group_id` across feeds.
