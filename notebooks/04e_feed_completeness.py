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
# # 04e — Feed completeness: what the data can and cannot show
#
# Reviewer 1: "the differences observed between countries may partly reflect data availability and feed
# harmonisation rather than actual railway connectivity. Although this issue is acknowledged briefly, its effect is
# not quantified." This notebook quantifies it (register REP-4, CON-10, VAL-4). Code: `traintranv2/nb04_feeds.py`.
#
# | § | step | output (`output/kosice/explore/`) |
# |---|---|---|
# | 1 | the feeds: size, time coverage, exceptions, known omissions | `feed_table.csv` |
# | 2 | what each national feed adds over the Slovak feed alone | `feed_effect.csv` |
# | 3 | the station-merge radius (VAL-4) | `dedup_radius.csv`, `dedup_changes.csv` |
#
# **How the effect is measured.** For each destination country, the one-transfer analysis of 03b is run twice on the
# same window: with the Slovak feed alone (every train from ZSR_SK), and with ZSR_SK plus the country's own feed (the
# headline). The difference — LAUs and people reached only because the national feed exists — is the part of a
# country's figure that depends on data availability. A country whose national feed is incomplete (Ukraine) shows
# what is missing as a small difference that cannot be told apart from an absence of service: the result is
# **observed connectivity within the available feeds** (CON-10).

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
from traintranv2 import nb04_feeds as FD
from traintranv2.nb01a_feeds import write_meta
from traintranv2.nb01b_stations import load_lau_subset

cfg = default_config()
OUT = os.path.join(cfg.out_dir, 'explore')
tags = pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str)
L = C.lau_with_city_units(load_lau_subset(cfg), cfg)
tags = C.tags_with_city_units(tags, cfg, L)
hubs = C.hub_groups(cfg, tags)
pop, _ = F.lau_population(L)

# %% [markdown]
# ## 1. The feeds
#
# Size, the calendar each feed declares and the analysis window used (01a), and its exceptions (`calendar_dates`
# rows adding or removing service days: holidays, engineering works, seasonal days). Known omissions, from the
# feeds' documentation and the earlier notebooks:
#
# | feed | known limitation |
# |---|---|
# | ZSR_SK | complete for ŽSR / ZSSK services, incl. international trains on Slovak track; the reference feed |
# | DRAHY_CZ | whole year; carries the Czech-operated trains abroad too |
# | MAV_HU | older snapshot (Jan–Nov 2026, 301 days) |
# | BAHN_AT | trains published in pieces at region and border points (joined in 02, `join_train_pieces`); window Mar–Dec 2026 |
# | PL_IC | PKP Intercity only, 101 days (May–Aug 2026) |
# | PL_REG | all other Polish carriers; a rolling feed of 32 days (June–July 2026) |
# | UKRZ_UA | a subset of Ukrzaliznytsia's services (international and western Ukraine) |

# %%
ft = FD.feed_table(cfg, tags)
display(ft)

# %% [markdown]
# ## 2. What each national feed adds
#
# Per country, inbound and outbound: LAUs and population reached directly or with one transfer, with ZSR_SK alone and
# with the national feed added. Same window, same rules (03b).

# %%
fe = FD.feed_effect(cfg, tags, hubs, pop)
assert (fe['added_lau'] >= 0).all(), 'adding a feed cannot lose a LAU'
show = fe[fe.direction == 'inbound'].pivot_table(index='country', columns='variant', values=['n_lau', 'population'])
show[('share of population from the national feed', '')] = (
    1 - show[('population', 'ZSR_SK alone')] / show[('population', 'ZSR_SK + national feed')]).round(3)
display(show)

# %% [markdown]
# ## 3. The station-merge radius (VAL-4)
#
# For the feeds without GTFS parent stations (ZSR_SK, MÁV, UZ), stops of the same name are one station if they lie
# within 2 km (01b, the domestic run's rule). The same at 0.5, 1 and 5 km: how many stations, and which merges change.
# (Feeds with parent stations — CZ, AT, PL — group platforms by the parent and are not affected.)

# %%
dr, dc = FD.dedup_radius(cfg)
display(dr.pivot_table(index='feed_key', columns='radius_km', values='stations'))
print(f'stations that a radius other than 2 km would form differently: {len(dc)}')
if len(dc):
    display(dc.groupby(['feed_key', 'radius_km']).size().rename('changed').to_frame().T)
    display(dc.head(15))

# %% [markdown]
# ## 4. Outputs

# %%
for name, key, frame in [('feed_table.csv', 'explore_feed_table', ft), ('feed_effect.csv', 'explore_feed_effect', fe),
                         ('dedup_radius.csv', 'explore_dedup_radius', dr), ('dedup_changes.csv', 'explore_dedup_changes', dc)]:
    p = os.path.join(OUT, name)
    frame.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, key, frame, {'Runs': 'headline country runs (03)'})
    print(f'[wrote] {p} ({len(frame):,} rows) + .meta.md')
