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
# # 01a — Feeds: download, roles and analysis windows
#
# | role | feed | country | file | analysed on |
# |---|---|---|---|---|
# | **domestic** | **ZSR_SK** — Železnice Slovenskej republiky (ŽSR), via Transitious (**snapshot of 2026-05-13**, the legacy run's file) | **SK** | `sk_zsr.gtfs.zip` | its **service span** |
# | foreign | DRAHY_CZ — CZPTT / JrUtil, via Transitious (**snapshot of 2026-11-03**, whole year kept) | CZ | `cz_CZPTT_new.gtfs.zip` | its service overlap with ZSR_SK |
# | foreign | MAV_HU — MÁV, via Transitious (**snapshot of 2026-05-19**) | HU | `hu_mav.gtfs.zip` | its service overlap with ZSR_SK |
# | foreign | BAHN_AT — Mobilitätsverbünde Österreich, via Transitious (**snapshot of 2026-05-19**) | AT | `BAHN_AT.zip` | its service overlap with ZSR_SK |
# | foreign | PL_IC — **PKP Intercity** (gtfs.kasznia.net, snapshot of 2026-05-18) | PL | `PL_kasznia.zip` | its service overlap with ZSR_SK |
# | foreign | PL_REG — **all other Polish carriers** (PolishTrainsGTFS, snapshot of 2026-06-06; PKP Intercity left out) | PL | `polish-trains.zip` | its service overlap with ZSR_SK |
# | foreign | UKRZ_UA — Ukrzaliznytsya (OSM), via Transitious (**snapshot of 2026-07-09**) | UA | `ua-ukrzaliznytsya.gtfs.zip` | its service overlap with ZSR_SK |
#
# **The domestic feed is ZSR_SK** (`cfg.domestic_feed`). Košice is reached through it; the five foreign
# feeds are each analysed **separately** on their own overlap with it. The table is regenerated below
# from the config and written to `output/kosice/feed_roles.csv`.
#
# First step of the split pipeline (`plan_part_a_tagging_refactor.md`): **01a feeds → 01b stations →
# 02 domestic / 03 foreign**. Code: `traintranv2/nb01a_feeds.py`. Legacy `ksc_analysis.ipynb` and
# `output/ke/` are untouched.
#
# | writes | content |
# |---|---|
# | `data/feeds/feeds.manifest.json` | file, size, sha256 and calendar span of every feed (REP-2) |
# | `output/kosice/feed_roles.csv` (+ `.meta.md`) | role, file, provider, window of every feed |
# | `output/kosice/windows.json` | analysis window per feed (read by 01b, 02, 03) |

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
from traintranv2.nb01a_feeds import download_feeds, feed_manifest, feed_roles, pair_windows

cfg = default_config()
cfg.city_slug = 'kosice'                       # outputs -> output/kosice/ (legacy run: output/ke/)
OUT = Path(cfg.out_dir)
OUT.mkdir(parents=True, exist_ok=True)
FEEDS = list(cfg.feeds)
dom = cfg.feeds[cfg.domestic_feed]
print(f'DOMESTIC FEED : {cfg.domestic_feed} ({dom["country"]}, {dom["data_origin"]}, {dom["filename"]})')
print(f'FOREIGN FEEDS : {[k for k in FEEDS if k != cfg.domestic_feed]}')
print(f'output dir    : {OUT}')

# %% [markdown]
# ## 1. Download and manifest
#
# Only missing files are downloaded (`[skip]` otherwise). **Every feed is an older snapshot** taken near the
# start of the timetable year (SK, HU, AT in May 2026, UA in July) — except CZ, whose November file keeps the whole year, has 7–9 % more trains and carries UIC codes and parent stations: a snapshot published late in the year
# keeps its calendar but drops the services already run (the current SK file of 2026-10-27 has ~3.7 instead of
# ~40 trains a day on the Košice – Žilina line before September; the current AT file none before September).
# The current files are kept as `*_new` / under their Transitious names and not used. **Poland comes from two feeds**, because no full-year all-carrier Polish GTFS exists:
# **PL_IC** = the PKP Intercity feed `PL_kasznia.zip` (2026-05-18 .. 08-26, 101 days), and **PL_REG** = the all-carrier
# PolishTrainsGTFS `polish-trains.zip`, a rolling one-month feed (2026-06-06 .. 07-06), **with PKP Intercity left out**
# (`excluded_agencies`, agency `IC`). So no train is in both feeds: the de-duplication is that agency filter. PL_REG
# carries the regional lines toward the Slovak border (Muszyna – Plaveč, Zwardoń – Skalité, the seasonal Kraków –
# Poprad trains). Each feed keeps its own window; how the two are combined is decided in notebooks 03.
# Both Polish files split some through trains into legs joined by stay-seated transfers; notebooks 02 / 03 rebuild them
# as one train (`nb02_connections.merge_stay_seated`). The domestic file is checked
# by sha256: it must be the legacy run's (`9dc3c38b05fb…`).

# %%
download_feeds(cfg, keys=FEEDS)
manifest = pd.DataFrame(feed_manifest(cfg, keys=FEEDS))
display(manifest[['key', 'country', 'file', 'bytes', 'sha256', 'span_start', 'span_end', 'span_days']]
        .assign(MB=lambda x: (x.bytes / 1e6).round(1), sha256=lambda x: x.sha256.str[:12]).drop(columns='bytes'))

EXPECTED_SPANS = {'MAV_HU': ('2026-01-19', '2026-11-15'), 'UKRZ_UA': ('2025-12-14', '2026-12-12'),
                  'ZSR_SK': ('2025-12-14', '2026-12-12'), 'BAHN_AT': ('2025-12-14', '2026-12-12'),
                  'DRAHY_CZ': ('2025-12-14', '2026-12-12'), 'PL_IC': ('2026-05-18', '2026-08-26'),
                  'PL_REG': ('2026-06-04', '2026-07-06')}
assert manifest.set_index('key').loc[cfg.domestic_feed, 'sha256'].startswith('9dc3c38b05fb'),     'the domestic file is not the legacy snapshot (feed_version 2026-05-13)'
spans = manifest.set_index('key')[['span_start', 'span_end']]
for k, (a, b) in EXPECTED_SPANS.items():
    assert tuple(spans.loc[k]) == (a, b), f'{k}: span {tuple(spans.loc[k])} -- not the expected snapshot'
print('feed snapshots as expected; manifest ->', Path(cfg.feeds_dir) / 'feeds.manifest.json')

# %% [markdown]
# ## 1b. Coverage check: trains per day by month
#
# Rail trains per day (bus routes and excluded agencies left out) from each feed's calendar, by month, over the
# domestic calendar span. A feed whose months drop well below its usual level does not cover them, whatever its
# calendar declares; the windows in §2 are cut to the days that carry service.

# %%
from traintranv2.nb01a_feeds import monthly_trains

coverage = monthly_trains(cfg, keys=FEEDS)
display(coverage)
coverage.to_csv(OUT / 'feed_monthly_trains.csv', encoding='utf-8')
print('[wrote]', OUT / 'feed_monthly_trains.csv')

# %% [markdown]
# ## 2. Roles and analysis windows
#
# Windows come from the **days the trains actually run**, not from the calendar's declared span (§1b): a feed's
# service span runs from the first to the last day with at least **50 %** of its median daily trains
# (`cfg.window_min_share`). The **domestic** feed is analysed on its service span; every **foreign** feed on the
# overlap of its service span with the domestic one, separately. `windows.json` keeps the declared calendar
# span beside it (`calendar_start` / `calendar_end`).

# %%
from traintranv2.nb01a_feeds import write_meta

roles = feed_roles(cfg, keys=FEEDS)
display(roles)
assert roles.loc[roles.role == 'domestic', 'feed_key'].tolist() == [cfg.domestic_feed] == ['ZSR_SK']

windows = pair_windows(cfg, keys=FEEDS)
EXPECTED_DAYS = {'ZSR_SK': 364, 'BAHN_AT': 276, 'DRAHY_CZ': 364, 'PL_IC': 101, 'PL_REG': 32, 'UKRZ_UA': 364, 'MAV_HU': 301}
assert {k: v['days'] for k, v in windows.items()} == EXPECTED_DAYS, {k: v['days'] for k, v in windows.items()}
for k, v in windows.items():
    v['role'] = 'domestic' if k == cfg.domestic_feed else 'foreign'

roles.to_csv(OUT / 'feed_roles.csv', index=False, encoding='utf-8-sig')
(OUT / 'windows.json').write_text(json.dumps(windows, indent=2), encoding='utf-8')
print('[wrote]', OUT / 'feed_roles.csv', '|', OUT / 'windows.json')
print('[meta] ', write_meta(str(OUT / 'feed_roles.csv'), 'feed_roles', roles,
                            extra={'Domestic feed': cfg.domestic_feed}))

# %% [markdown]
# ## Next
#
# `01b_stations_tag_match.ipynb` builds the station catalogs of all six feeds from these files.
