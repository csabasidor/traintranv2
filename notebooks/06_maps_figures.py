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
# # 06 — Maps and figures
#
# The manuscript's figures, from the frozen 01–05 outputs (register PRE-4, PRE-5, PRE-6). Reviewer 2: a key map of the
# regional context, a conceptual diagram of the research process, high-resolution maps with captions a reader can use
# without the text. Reviewer 1: readable at page size; consistent classifications, scales, symbols and country labels.
# Code: `traintranv2/nb06_figures.py` — one style for every figure, shared class breaks, 300 dpi PNG and PDF, and a
# caption written beside each figure (`figures/captions.md`).
#
# | figure | content |
# |---|---|
# | F1 | key map: the six countries, the rail network (01c), Košice, the main transfer stations |
# | F2 | conceptual diagram of the pipeline |
# | F3 | journeys per day to Košice, per LAU: direct; one transfer |
# | F4 | same-day visits to Košice: share of days |
# | F5 | rail-travelling population (M2) per LAU |
# | F6 | journey time, efficiency, frequency and the transfer penalty (A4 grid) |
# | F7 | catchment within a journey time, by origin country (written by 05) |

# %%
import os, sys

# Run from the project root so every relative path resolves the same from notebooks/ or the root.
_here = os.path.abspath('')
if os.path.basename(_here) == 'notebooks':
    os.chdir(os.path.dirname(_here))
sys.path.insert(0, os.getcwd())
print('Working directory:', os.getcwd())

# %%
import numpy as np
import pandas as pd
import geopandas as gpd
import traintranv2  # noqa: F401  (PROJ data fix)
from traintranv2.config import default_config
from traintranv2 import nb02_connections as C
from traintranv2 import nb06_figures as FG
from traintranv2.nb01b_stations import load_lau_subset, load_nuts_level
from traintranv2.nb01c_rail_network import RailGraph

plt = FG.setup()
from matplotlib.collections import LineCollection  # noqa: E402

cfg = default_config()
OUT = os.path.join(cfg.out_dir, 'explore')
FIG = os.path.join(OUT, 'figures')
cap = FG.Captions(FIG)
L = C.lau_with_city_units(load_lau_subset(cfg), cfg).to_crs(FG.METRIC_CRS)
countries = load_nuts_level(cfg, 0, countries=FG.COUNTRY_ORDER).set_geometry('geom').to_crs(FG.METRIC_CRS)
tags = C.tags_with_city_units(pd.read_csv(os.path.join(cfg.out_dir, 'station_tags.csv'), dtype=str), cfg, L)
lau = pd.read_csv(os.path.join(OUT, 'lau_table.csv'), dtype={'lau_gisco_id': str})
lau = lau[lau.headline.astype(str).eq('True') & (lau.direction == 'inbound')]
cat = pd.read_csv(os.path.join(OUT, 'catchment.csv'), dtype={'lau_code': str})
pos = gpd.GeoDataFrame(tags[['station_key', 'stop_name']],
                       geometry=gpd.points_from_xy(tags.stop_lon.astype(float), tags.stop_lat.astype(float)),
                       crs='EPSG:4326').to_crs(FG.METRIC_CRS).set_index('station_key')
HUB = pos.loc[cfg.hub_station_keys[0]].geometry
H = cfg.hub_label                                               # the destination's name in titles / captions
OTHER = next(u for u in cfg.city_units if u != cfg.hub_city)    # the other city counted as one unit
reach = L[L.GISCO_ID.isin(set(cat.lau_code))]
x0, y0, x1, y1 = reach.total_bounds
EXT = (x0 - 60_000, x1 + 60_000, y0 - 60_000, y1 + 60_000)
print(f'{len(reach)} reached LAUs; map extent {[round(v / 1000) for v in EXT]} km (EPSG:3035)')


def base(ax):
    countries.plot(ax=ax, color='white', edgecolor='#7f7f7f', linewidth=0.6)
    ax.set_xlim(EXT[0], EXT[1])
    ax.set_ylim(EXT[2], EXT[3])
    for _, r in countries.iterrows():
        p = r.geom.representative_point()
        if EXT[0] < p.x < EXT[1] and EXT[2] < p.y < EXT[3]:
            ax.text(p.x, p.y, r.cntr_code, fontsize=9, color='#7f7f7f', ha='center', weight='bold')
    ax.plot(HUB.x, HUB.y, marker='*', color='black', markersize=10, zorder=5)
    ax.text(HUB.x + 15_000, HUB.y + 15_000, H, fontsize=8, weight='bold', zorder=5)
    ax.set_axis_off()


# %% [markdown]
# ## F1. Key map

# %%
g = RailGraph.load(os.path.join(cfg.out_dir, 'rail_graph.npz'))
track = np.asarray(g.kind) == 'track'
seg = np.stack([g.node_xy[g.u[track]], g.node_xy[g.v[track]]], axis=1)
inside = ((seg[:, :, 0] > EXT[0]) & (seg[:, :, 0] < EXT[1]) & (seg[:, :, 1] > EXT[2]) & (seg[:, :, 1] < EXT[3])).any(axis=1)
hubs = pd.concat([pd.read_csv(os.path.join(cfg.out_dir, 'domestic', 'one_transfer_hubs.csv')).assign(scope='domestic'),
                  pd.read_csv(os.path.join(cfg.out_dir, 'foreign', 'one_transfer_hubs.csv')).assign(scope='foreign')])
top = (hubs[hubs.direction == 'inbound'].groupby('T_key')['journeys_per_day'].sum().sort_values(ascending=False).head(10))
fig, ax = plt.subplots(figsize=(FG.A4_WIDTH_IN, 5.2))
base(ax)
ax.add_collection(LineCollection(seg[inside], colors='#555555', linewidths=0.25, zorder=2))
names, placed = [], [(HUB.x, HUB.y)]
for n, k in enumerate([k for k in top.index if k in pos.index], start=1):
    p = pos.loc[k].geometry
    x, y = p.x, p.y
    step = 0
    while any(np.hypot(x - a, y - b) < 18000 for a, b in placed):       # nudge off a neighbour or the star
        step += 1
        x, y = p.x + 22000 * step, p.y - 22000 * step
    if step:
        ax.plot([p.x, x], [p.y, y], color='#c0392b', lw=0.5, zorder=3)
    placed.append((x, y))
    ax.plot(x, y, 'o', color='#c0392b', markersize=7, zorder=4, markeredgecolor='white', markeredgewidth=0.5)
    ax.text(x, y, str(n), fontsize=5, color='white', ha='center', va='center', weight='bold', zorder=5)
    names.append(f'{n}  {pos.loc[k].stop_name}  ({top[k]:.0f} / day)')
ax.text(0.01, 0.99, 'Busiest transfer stations\n(one-transfer journeys per day)\n' + '\n'.join(names), transform=ax.transAxes,
        fontsize=6.5, va='top', ha='left', color='#c0392b', linespacing=1.4)
FG.scale_bar(ax, 100)
ax.set_title(f'Study area: the rail network of the six countries, {H}, and the ten busiest transfer stations')
FG.save(fig, FIG, 'F1_key_map', cap,
        'Key map. Rail network (OpenStreetMap, railway = rail / narrow gauge, cleaned and joined across borders, '
        f'notebook 01c) within the area reached from {H} (star). Red dots: the ten transfer stations carrying the '
        f'most one-transfer journeys per day to {H} (domestic and foreign, inbound). Country codes: SK Slovakia, CZ '
        'Czechia, HU Hungary, AT Austria, PL Poland, UA Ukraine. Projection ETRS89-LAEA (EPSG:3035).')
plt.close(fig)

# %% [markdown]
# ## Study-area map with a Europe locator
#
# The six countries in full, ETRS89-LAEA (EPSG:3035). Ukraine is cut at 28° E, as on the earlier version of this
# map. The layers:
#
# * neighbouring countries in grey;
# * a pale NUTS3 purchasing-power fill (PPS per inhabitant, 2023, five quantile classes of the 150
#   NUTS3 regions, unweighted; Ukraine has no PPS);
# * NUTS3 and country boundaries;
# * the rail graph of notebook 01c (the network every distance is measured on);
# * country codes and city labels.
#
# The city labels are the Slovak cities (DEGURBA 1), the EU cities above 150,000 residents (de-cluttered: a smaller
# city within 35 km of a labelled one is left out) and four Ukrainian cities on the network.
#
# A 2° graticule is drawn, labelled along the bottom and left edges. The north arrow and the scale bar sit on the
# left. The locator (top right) shows Europe at NUTS0, with the six
# countries darker and the main map's frame in red.

# %%
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
from shapely.geometry import box as _sbox  # noqa: E402
from traintranv2.nb05_catchment import pps_table  # noqa: E402

STUDY = FG.COUNTRY_ORDER                                        # SK CZ HU AT PL UA
eu0 = gpd.read_file(os.path.join(os.path.dirname(cfg.nuts_dir), 'NUTS_RG_01M_2024_4326_LEVL_0.geojson')).to_crs(FG.METRIC_CRS)
n3 = load_nuts_level(cfg, 3, countries=[c for c in STUDY if c != 'UA']).set_geometry('geom').to_crs(FG.METRIC_CRS)
ua2 = load_nuts_level(cfg, 2, countries=['UA']).set_geometry('geom').to_crs(FG.METRIC_CRS)
_pps = pps_table(cfg)
n3 = n3.merge(_pps[['nuts3_id', 'pps_value']], left_on='nuts_id', right_on='nuts3_id', how='left')

# frame: the five EU countries' bounds, the east edge at 28 deg E (the longitude, in EPSG:3035, at 49 deg N)
_x0, _y0, _x1, _y1 = countries[countries.cntr_code != 'UA'].total_bounds
_east = gpd.GeoSeries(gpd.points_from_xy([28.0], [49.0]), crs=4326).to_crs(FG.METRIC_CRS).x.iloc[0]
_pad = 40_000
SA = (_x0 - _pad, max(_x1, _east) + _pad, _y0 - _pad, _y1 + _pad)

# PPS classes: quintiles of the NUTS3 values (regions, not people)
_q = np.quantile(n3['pps_value'].dropna(), [0, 0.2, 0.4, 0.6, 0.8, 1.0])
_q[0], _q[-1] = _q[0] - 1, _q[-1] + 1
# a pale single-hue ramp, so the fill stays background to the network and never reads as "other countries" grey
from matplotlib.colors import ListedColormap  # noqa: E402
PPS_CMAP_SA = ListedColormap(plt.get_cmap('OrRd')(np.linspace(0.06, 0.55, 5)))
_norm = BoundaryNorm(_q, ncolors=5)
PPS_ALPHA = 1.0
# label nudges (metres, from the default +9 km / +7 km offset) where two labels collide
LABEL_NUDGE = {'Toruń': (0, -26_000, 'left'), 'Nitra': (0, -7_000, 'left'),
               'Uzhhorod': (2_000, -52_000, 'left'), 'Banská Bystrica': (0, -26_000, 'left'),
               'Bydgoszcz': (-18_000, 0, 'right')}

# city labels
_lau_pt = L[L.CNTR_CODE != 'UA'].copy()
_lau_pt['pt'] = _lau_pt.geometry.representative_point()
_dg = pd.to_numeric(_lau_pt['DGURBA'], errors='coerce')
_cand = pd.concat([_lau_pt[(_lau_pt.CNTR_CODE == 'SK') & (_dg == 1)],
                   _lau_pt[(_lau_pt.CNTR_CODE != 'SK') & (_lau_pt.POP_2025 >= 150_000)]]) \
    .drop_duplicates('GISCO_ID').sort_values('POP_2025', ascending=False)
_cities = []
for r in _cand.itertuples():
    if r.LAU_NAME_LATIN == H or r.CNTR_CODE == 'SK' or \
            all(np.hypot(r.pt.x - c[1], r.pt.y - c[2]) > 35_000 for c in _cities):
        _cities.append((r.LAU_NAME_LATIN, r.pt.x, r.pt.y, r.CNTR_CODE, r.POP_2025))
_ua_caps = gpd.read_file('data/ukraine/admin_boundaries/ukr_admincapitals.shp').to_crs(FG.METRIC_CRS)
for nm in ('Lviv', 'Uzhhorod', 'Mukachevo', 'Ivano-Frankivsk'):
    hit = _ua_caps[_ua_caps['name'] == nm]
    if len(hit):
        _cities.append((nm, hit.geometry.iloc[0].x, hit.geometry.iloc[0].y, 'UA', np.nan))
    else:
        print('  no Ukrainian admin centre named', nm)
CAPITALS = {'Wien', 'Warszawa', 'Budapest', 'Praha', 'Bratislava'}
print(f'{len(_cities)} city labels:', ', '.join(c[0] for c in _cities))

fig, ax = plt.subplots(figsize=(FG.A4_WIDTH_IN, FG.A4_WIDTH_IN * (SA[3] - SA[2]) / (SA[1] - SA[0])))
# white background: NUTS0 has no Belarus, Moldova or Russia, and a sea colour would draw them as water
eu0[~eu0.CNTR_CODE.isin(STUDY)].plot(ax=ax, color='#e4e4e4', edgecolor='#a6a6a6', linewidth=0.4, zorder=0)
n3.plot(ax=ax, color='white', linewidth=0, zorder=0.5)
n3[n3.pps_value.notna()].plot(ax=ax, column='pps_value', cmap=PPS_CMAP_SA, norm=_norm, alpha=PPS_ALPHA,
                              linewidth=0, zorder=1)
ua2.plot(ax=ax, color='#f7f7f7', linewidth=0, zorder=0.5)
n3.boundary.plot(ax=ax, color='#8c8c8c', linewidth=0.25, linestyle=(0, (3, 2)), zorder=2)
ua2.boundary.plot(ax=ax, color='#8c8c8c', linewidth=0.25, linestyle=(0, (3, 2)), zorder=2)
_in = ((seg[:, :, 0] > SA[0]) & (seg[:, :, 0] < SA[1]) & (seg[:, :, 1] > SA[2]) & (seg[:, :, 1] < SA[3])).any(axis=1)
ax.add_collection(LineCollection(seg[_in], colors='#3c3c3c', linewidths=0.22, zorder=3))
countries.boundary.plot(ax=ax, color='black', linewidth=0.9, zorder=4)
ax.set_xlim(SA[0], SA[1]); ax.set_ylim(SA[2], SA[3]); ax.set_aspect('equal')
_halo = [pe.withStroke(linewidth=2, foreground='white')]
_frame = _sbox(SA[0], SA[2], SA[1], SA[3])
for r in countries.itertuples():
    p = r.geom.intersection(_frame).representative_point()
    ax.text(p.x, p.y, r.cntr_code, fontsize=11, weight='bold', color='#4d4d4d', ha='center', va='center',
            zorder=6, path_effects=_halo)
for nm, x, y, cc, popv in _cities:
    if nm == H:
        continue
    big = nm in CAPITALS
    ax.plot(x, y, 's' if big else 'o', color='black', markersize=3 if big else 1.8, zorder=6)
    dx, dy, ha = LABEL_NUDGE.get(nm, (0, 0, 'left'))
    ax.text(x + (9_000 if ha == 'left' else -9_000) + dx, y + 7_000 + dy, nm, fontsize=7 if big else 5.5,
            weight='bold' if big else 'normal', ha=ha, zorder=6, path_effects=_halo)
ax.plot(HUB.x, HUB.y, marker='*', color='#c0392b', markersize=13, markeredgecolor='black', markeredgewidth=0.5, zorder=7)
ax.text(HUB.x + 18_000, HUB.y + 14_000, H, fontsize=10, weight='bold', zorder=7, path_effects=_halo)


def graticule(ax, ext, step=2, lons=(0, 40), lats=(40, 60)):
    """Lat/lon lines projected into EPSG:3035 (curved there), labelled where they cross the bottom (meridians) and
    the left edge (parallels) of the frame, as ticks of the axes."""
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, FG.METRIC_CRS, always_xy=True)
    xt, xl, yt, yl = [], [], [], []
    for lon in range(lons[0], lons[1] + 1, step):
        la = np.linspace(lats[0] - 5, lats[1] + 5, 400)
        x, y = tr.transform(np.full_like(la, lon), la)
        ax.plot(x, y, color='#7f7f7f', lw=0.35, ls=':', zorder=2.5)
        if y.min() < ext[2] < y.max():
            xb = np.interp(ext[2], y, x)
            if ext[0] < xb < ext[1]:
                xt.append(xb); xl.append(f'{lon}°E')
    for lat in range(lats[0], lats[1] + 1, step):
        lo = np.linspace(lons[0] - 10, lons[1] + 10, 400)
        x, y = tr.transform(lo, np.full_like(lo, lat))
        ax.plot(x, y, color='#7f7f7f', lw=0.35, ls=':', zorder=2.5)
        if x.min() < ext[0] < x.max():
            yb = np.interp(ext[0], x, y)
            if ext[2] < yb < ext[3]:
                yt.append(yb); yl.append(f'{lat}°N')
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_xticks(xt, xl); ax.set_yticks(yt, yl)
    ax.tick_params(labelsize=6, length=2, width=0.5, colors='#4d4d4d')


graticule(ax, SA)
for s in ax.spines.values():
    s.set_visible(True); s.set_linewidth(0.6)

# north arrow (left, top) and scale bar (left, bottom)
ax.annotate('', xy=(0.035, 0.955), xytext=(0.035, 0.885), xycoords='axes fraction',
            arrowprops=dict(facecolor='black', edgecolor='black', width=2, headwidth=7, headlength=6), zorder=9)
ax.text(0.035, 0.962, 'N', transform=ax.transAxes, ha='center', va='bottom', fontsize=8, weight='bold', zorder=9)
FG.scale_bar(ax, 200, loc=(0.03, 0.04))

# locator: Europe at NUTS0, the study countries darker, the main frame in red
loc = ax.inset_axes([0.735, 0.64, 0.26, 0.35])
LOC = (2_500_000, 6_900_000, 1_350_000, 5_450_000)
_eu = eu0.clip(_sbox(LOC[0], LOC[2], LOC[1], LOC[3]))
loc.set_facecolor('white')
_eu[~_eu.CNTR_CODE.isin(STUDY)].plot(ax=loc, color='#dedede', edgecolor='#9a9a9a', linewidth=0.2)
_eu[_eu.CNTR_CODE.isin(STUDY)].plot(ax=loc, color='#6f6f6f', edgecolor='white', linewidth=0.2)
loc.add_patch(Rectangle((SA[0], SA[2]), SA[1] - SA[0], SA[3] - SA[2], fill=False, edgecolor='#c0392b', lw=1.0))
loc.set_xlim(LOC[0], LOC[1]); loc.set_ylim(LOC[2], LOC[3]); loc.set_aspect('equal')
loc.set_xticks([]); loc.set_yticks([])
for s in loc.spines.values():
    s.set_linewidth(0.6)
loc.set_zorder(10)

# legend (bottom right): PPS classes, no-PPS, boundaries, rail, Kosice
_mid = (_q[:-1] + _q[1:]) / 2
_lbl = [f'{_q[0] + 1:,.0f}–{_q[1]:,.0f}'] + [f'{a:,.0f}–{b:,.0f}' for a, b in zip(_q[1:-2], _q[2:-1])] + \
       [f'{_q[-2]:,.0f}–{_q[-1] - 1:,.0f}']
hs = [Patch(facecolor=PPS_CMAP_SA(_norm(m)), alpha=PPS_ALPHA, edgecolor='#bdbdbd', lw=0.3, label=l)
      for m, l in zip(_mid, _lbl)]
hs += [Patch(facecolor='#f7f7f7', edgecolor='#bdbdbd', lw=0.4, label='UA: no PPS'),
       Patch(facecolor='#e4e4e4', edgecolor='none', label='other countries'),
       Line2D([], [], color='#3c3c3c', lw=0.8, label='rail network (01c)'),
       Line2D([], [], color='black', lw=1.2, label='country boundary'),
       Line2D([], [], color='#8c8c8c', lw=0.6, ls=(0, (3, 2)), label='NUTS3 / oblast boundary'),
       Line2D([], [], marker='*', color='w', markerfacecolor='#c0392b', markeredgecolor='black', markersize=10,
              label=H)]
ax.legend(handles=hs, loc='lower right', fontsize=6, title='PPS per inhabitant, NUTS3 (2023)', title_fontsize=6.5,
          framealpha=0.92, edgecolor='none', borderpad=0.6).set_zorder(11)
fig.tight_layout()
FG.save(fig, FIG, 'study_area_map', cap,
        f'Study area. The six countries whose rail services to {H} are analysed (SK Slovakia, CZ Czechia, HU Hungary, '
        'AT Austria, PL Poland, UA Ukraine, shown to 28° E), with the rail network the distances are measured on '
        '(OpenStreetMap, railway = rail / narrow gauge, cleaned and joined across borders, notebook 01c). Fill: '
        'purchasing power per inhabitant by NUTS3 region, 2023 (Eurostat nama_10r_3gdp), in five quantile classes of '
        'the regions; Ukraine has no PPS figure and its oblasts are left blank. Labels: Slovak cities and the larger '
        'cities of the neighbouring countries. Inset: location in Europe (NUTS0, GISCO 2024); the red frame is the '
        'main map. Projection ETRS89-LAEA (EPSG:3035); graticule every 2°.')
plt.close(fig)

# %% [markdown]
# ## F2. Conceptual diagram

# %%
steps = [('Open GTFS feeds', '7 feeds, 6 countries\nwindows from actual service\n(01a)'),
         ('Stations', 'catalog per feed, LAU tags,\ncross-feed station groups\n(01b)'),
         ('Rail network', 'OSM track graph,\nshortest-path and route km\n(01c, 04b)'),
         ('Timetable engine', 'dated run masks, no 24 h wrap,\none transfer, dedup across feeds\n(02, 03)'),
         ('Four networks', 'domestic / foreign ×\ndirect / one transfer\n(02a–03d)'),
         ('Catchment', 'LAU population 15+, DEGURBA,\nsame-day visits, service patterns\n(02c/d, 04a)'),
         ('Rail market', 'FL551 rates, mass levels M1–M3,\nmarket potential, PPS profile\n(05)')]
n = len(steps)
fig, ax = plt.subplots(figsize=(FG.A4_WIDTH_IN * 0.75, 0.62 * n))
ax.set_xlim(0, 10)
ax.set_ylim(0, n)
ax.set_axis_off()
for i, (h, t) in enumerate(steps):
    y = n - 1 - i
    ax.add_patch(plt.Rectangle((0.1, y + 0.12), 9.8, 0.76, facecolor='#eaf2f8', edgecolor='#1b6ca8', lw=0.8))
    ax.text(0.35, y + 0.5, h, ha='left', va='center', fontsize=8, weight='bold')
    ax.text(3.6, y + 0.5, t.replace('\n', ' ').replace('  ', ' '), ha='left', va='center', fontsize=7, wrap=True)
    if i < n - 1:
        ax.annotate('', xy=(1.5, y - 0.12), xytext=(1.5, y + 0.12), arrowprops=dict(arrowstyle='-|>', lw=0.8))
FG.save(fig, FIG, 'F2_pipeline', cap,
        'The research process. From independently published national GTFS feeds to station identity across feeds, the '
        'rail network, the timetable engine, the four networks (domestic / foreign, direct / one transfer), the '
        'population catchment and the rail market. Notebook numbers in brackets; every step is reproducible from the '
        'archived feeds and the code release.')
plt.close(fig)

# %% [markdown]
# ## F3. Journeys per day to Košice

# %%
geo = L.set_index('GISCO_ID')
c3 = cat.assign(geometry=cat.lau_code.map(geo.geometry))
c3 = gpd.GeoDataFrame(c3.dropna(subset=['geometry']), geometry='geometry', crs=FG.METRIC_CRS)
fig, axes = plt.subplots(1, 2, figsize=(FG.A4_WIDTH_IN, 3.6))
for ax, lvl, ttl in zip(axes, ['direct', 'onehop'], ['(a) direct train', '(b) one transfer (no direct train)']):
    base(ax)
    h = FG.choropleth(ax, c3[c3.service_level == lvl], 'trips_per_day', FG.BREAKS['journeys_per_day'], ttl, legend=False)
FG.scale_bar(axes[0], 100)
fig.legend(handles=h, title='journeys per day', loc='lower center', ncol=len(h), frameon=False, bbox_to_anchor=(0.5, -0.02))
fig.subplots_adjust(bottom=0.12)
FG.save(fig, FIG, 'F3_journeys_per_day', cap,
        f'Journeys per day to {H}, per municipality (LAU), inbound. (a) Municipalities with a direct train; (b) '
        'municipalities reached only with one change of trains (10–90 min). A journey is a distinct train (a) or a '
        'distinct pair of trains (b), counted once per municipality however many of its stations it serves, averaged '
        'over the run window (Slovakia, Czechia, Ukraine 364 days; Hungary 301; Austria 276; Poland 32 summer days). '
        f'Same classes in both panels. {OTHER} is one unit; the city of {H} is the destination.')
plt.close(fig)

# %% [markdown]
# ## F4. Same-day visits

# %%
dt_d = pd.read_csv(os.path.join(cfg.out_dir, 'domestic', 'daytrip_one_transfer_lau.csv'), dtype={'lau_gisco_id': str})
dt_f = pd.read_csv(os.path.join(cfg.out_dir, 'foreign', 'daytrip_one_transfer_lau.csv'), dtype={'lau_gisco_id': str})
dt_f = dt_f[dt_f.run.isin(['CZ', 'HU', 'AT', 'PL', 'UA'])]
d4 = pd.concat([dt_d[['lau_gisco_id', 'daytrip_share']], dt_f[['lau_gisco_id', 'daytrip_share']]], ignore_index=True)
d4 = gpd.GeoDataFrame(d4.assign(geometry=d4.lau_gisco_id.map(geo.geometry)).dropna(subset=['geometry']),
                      geometry='geometry', crs=FG.METRIC_CRS)
fig, ax = plt.subplots(figsize=(FG.A4_WIDTH_IN, 4.6))
base(ax)
FG.choropleth(ax, c3, 'trips_per_day', [0, np.inf], '', cmap='Greys', legend=False)       # served, as background
FG.choropleth(ax, d4, 'daytrip_share', FG.BREAKS['share'],
              f'Same-day visit to {H}: share of days possible (direct or one transfer)', legend_title='share of days')
FG.scale_bar(ax, 100)
FG.save(fig, FIG, 'F4_same_day', cap,
        f'Same-day visits to {H}. Share of the window\'s days on which a resident can arrive in {H} by 11:00, stay '
        'at least six hours, leave at 17:00 or later and be home by 23:59, by direct trains or with one transfer each '
        'way. Grey: municipalities with a connection but no same-day visit on any day.')
plt.close(fig)

# %% [markdown]
# ## F5. Rail-travelling population

# %%
fig, ax = plt.subplots(figsize=(FG.A4_WIDTH_IN, 4.6))
base(ax)
FG.choropleth(ax, c3, 'M2', FG.BREAKS['rail_market'], 'Rail-travelling population aged 15+ (M2) per municipality',
              legend_title='people')
FG.scale_bar(ax, 100)
FG.save(fig, FIG, 'F5_rail_market', cap,
        f'Rail-travelling population per municipality reached from {H} (M2): residents aged 15+ times the national '
        'share who travel 50 km or more for leisure and used a train for it (Flash Eurobarometer 551; age-banded; a '
        'nominal, upper-bound estimate from a non-probability sample). Municipalities under 50 km of rail distance are '
        'not converted (grey outline only); Ukraine is not in the survey.')
plt.close(fig)

# %% [markdown]
# ## F6. Journey time, efficiency, frequency and the transfer penalty

# %%
coef = pd.read_csv(os.path.join(OUT, 'models_coef.csv'))
eff = pd.read_csv(os.path.join(OUT, 'efficiency_lau.csv'))
fig, axes = plt.subplots(2, 2, figsize=(FG.A4_WIDTH_IN, 6.2))
a, b, c, d = axes.ravel()
for net, col in FG.NETWORK_COLORS.items():
    x = lau[lau.network == net]
    a.scatter(x.route_km_mean, x.time_mean_min, s=4, color=col, alpha=0.5, label=net.replace('_', ' '))
    k = coef[(coef.network == net) & (coef.family == 'decay') & (coef['sample'] == 'all') & (coef.distance == 'route')].set_index('term')
    if len(k):
        xs = np.linspace(0, x.route_km_mean.max(), 50)
        a.plot(xs, k.loc['Intercept', 'coef'] + k.loc['route_km_mean', 'coef'] * xs, color=col, lw=1)
    e = eff[eff.network == net]
    b.scatter(e.route_km_mean, e.e_route, s=4, color=col, alpha=0.5)
    c.scatter(np.log(x.rail_km_mean), np.log(x.f_per_day), s=4, color=col, alpha=0.5)
a.set_xlabel('route km'); a.set_ylabel('mean journey time, min'); a.set_title('(a) journey time against route distance')
a.legend(frameon=False, markerscale=3)
b.set_xlabel('route km'); b.set_ylabel('min per km'); b.set_ylim(0, 4); b.set_title('(b) journey efficiency')
c.set_xlabel('log shortest-path km'); c.set_ylabel('log journeys per day'); c.set_title('(c) frequency against distance')
pen = coef[(coef.family == 'transfer') & (((coef.term == 'transfer') & (coef['sample'] == 'pooled')) |
                                          ((coef.term == 'Intercept') & (coef['sample'] == 'matched')))]
pen = pen.assign(lbl=pen.network + ' ' + pen['sample'] + '\n' + pen.distance + ' km')
d.barh(pen.lbl, pen.coef, xerr=[pen.coef - pen.ci_low, pen.ci_high - pen.coef], color='#7fb3d5', ecolor='black', capsize=2)
d.set_xlabel('minutes added by one transfer (95 % CI)'); d.set_title('(d) transfer penalty, net of distance')
d.tick_params(axis='y', labelsize=6)
fig.tight_layout()
FG.save(fig, FIG, 'F6_time_efficiency_frequency', cap,
        'Journey time, efficiency and frequency per municipality, inbound, the four networks. (a) Mean journey time '
        'against mean route distance (the track along the stations the trains call at), with the least-squares lines '
        'of notebook 04c. (b) Minutes per route kilometre. (c) Journeys per day against shortest-path distance, logs. '
        '(d) The time a transfer adds at equal distance: the transfer term of a pooled model of direct and '
        'one-transfer municipalities, and the intercept of a matched comparison of municipalities with both; bars are '
        '95 % intervals with heteroskedasticity-robust errors.')
plt.close(fig)

# %% [markdown]
# ## Supplementary grids: journey time, efficiency and frequency against route distance
#
# One A4 2×2 grid per network (inbound, headline runs), the same encoding in all four:
#
# * **colour**: NUTS3 purchasing power per inhabitant (PPS, 2023, `pps_table`, the year notebook 05 uses). Each Slovak
#   kraj gets its own colour (domestic networks). The foreign regions use a continuous scale. Ukraine has no PPS (grey);
# * **shape**: DEGURBA (city, town / suburb, rural);
# * **area**: the FL551-adjusted rail market **M2** of notebook 05 (residents 15+ × the age-band rail rates). Below
#   the 50 km floor, and in Ukraine (outside the survey), M2 is not defined. Those municipalities are drawn hollow
#   and sized by M1 (residents 15+). Ukraine has no age split, so it is sized by all residents.
#
# The panels:
#
# * (a) mean journey time against mean route distance;
# * (b) minutes per route km (`e_route`), with the f-weighted network mean ē of 04b (cut-off 5 km);
# * (c) journeys per day.
#
# The dashed lines in (a) and (c) are descriptive least-squares fits on logs, not the 04c models.

# %%
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm, Normalize  # noqa: E402
from matplotlib.cm import ScalarMappable  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from traintranv2.nb05_catchment import pps_table  # noqa: E402

_PPS_COLORS = ['#596e64', '#839e85', '#bbcfa2', '#ffffc0', '#efc466', '#e8801e', '#de0205']
PPS_CMAP = LinearSegmentedColormap.from_list('pps_scale', _PPS_COLORS, N=256)
DEGURBA_MARKER = {1: 'o', 2: 's', 3: '^'}
DEGURBA_LABELS = {1: 'City', 2: 'Town/Suburb', 3: 'Rural'}
SIZE_DIVISOR, SIZE_CAP = 500, 300          # the old chart's scale: area = M2 / 500, floored at 100, capped at 300
SIZE_REFS = [5_000, 25_000, 75_000]
NO_PPS = '#9a9a9a'

pps = pps_table(cfg)
pps_val = pps.set_index('nuts3_id')['pps_value']
pps_name = pps.set_index('nuts3_id')['nuts3_name']
mass = cat[['lau_code', 'M1', 'M2']].rename(columns={'lau_code': 'lau_gisco_id'})
eff_lau = pd.read_csv(os.path.join(OUT, 'efficiency_lau.csv'), dtype={'lau_gisco_id': str})
eff_lau = eff_lau[eff_lau.direction == 'inbound']
eff_sum = pd.read_csv(os.path.join(OUT, 'efficiency_summary.csv'))
e_bar = eff_sum[(eff_sum.direction == 'inbound') & (eff_sum.distance == 'route') & (eff_sum.cutoff_km == 5)] \
    .set_index('network')['e_weighted']


def _size(v):
    return (pd.Series(v, dtype=float).clip(lower=100) / SIZE_DIVISOR).clip(upper=SIZE_CAP).to_numpy()


def _prep(df):
    d = df.merge(mass, on='lau_gisco_id', how='left')
    d['pps'] = d['nuts3_id'].map(pps_val)
    d['hollow'] = d['M2'].isna()
    # no M2: residents 15+ (M1); Ukraine publishes no age split, so its total residents
    d['_size'] = _size(d['M2'].fillna(d['M1']).fillna(d['pop_15plus']).fillna(d['population']))
    return d


def distance_grid(net):
    domestic = net.startswith('domestic')
    a_df = _prep(lau[lau.network == net])
    b_df = _prep(eff_lau[eff_lau.network == net].merge(lau[lau.network == net][['lau_gisco_id', 'nuts3_id', 'pop_15plus']],
                                                       on='lau_gisco_id', how='left'))
    assert a_df['_size'].notna().all() and b_df['_size'].notna().all()

    # colour: one band per kraj (domestic) or a continuous ramp over the plotted NUTS3 values (foreign)
    vals = a_df['pps'].dropna()
    if domestic:
        sv = np.array(sorted(set(vals)))
        mids = (sv[:-1] + sv[1:]) / 2
        norm = BoundaryNorm(np.concatenate([[sv[0] - 1], mids, [sv[-1] + 1]]), ncolors=256)
    else:
        norm = Normalize(vals.min(), vals.max())

    def colours(d):
        return [PPS_CMAP(norm(v)) if pd.notna(v) else NO_PPS for v in d['pps']]

    fig, axes = plt.subplots(2, 2, figsize=(FG.A4_WIDTH_IN, FG.A4_WIDTH_IN))
    panels = [('(a)', axes[0][0], a_df, 'time_mean_min', f'Mean journey time to {H} (min)', 'loglog'),
              ('(b)', axes[0][1], b_df, 'e_route', 'Journey efficiency (min per route km)', 'ebar'),
              ('(c)', axes[1][0], a_df, 'f_per_day', 'Journeys per day', 'loglog')]
    for letter, ax, d, ycol, ylabel, trend in panels:
        col = np.array(colours(d), dtype=object)
        for dg, mk in DEGURBA_MARKER.items():
            for hollow in (False, True):
                m = (d['degurba'] == dg).to_numpy() & (d['hollow'] == hollow).to_numpy()
                if not m.any():
                    continue
                c = list(col[m])
                kw = dict(facecolors='none', edgecolors=c, linewidths=0.8) if hollow else \
                    dict(c=c, edgecolors='none')
                ax.scatter(d['route_km_mean'][m], d[ycol][m], marker=mk, s=d['_size'][m], alpha=0.7, **kw)
        if trend == 'loglog':
            x, y = d['route_km_mean'].to_numpy(float), d[ycol].to_numpy(float)
            ok = (x > 0) & (y > 0)
            if ok.sum() > 2:
                k = np.polyfit(np.log(x[ok]), np.log(y[ok]), 1)
                xs = np.linspace(x[ok].min(), x[ok].max(), 200)
                ax.plot(xs, np.exp(k[1]) * xs ** k[0], 'k--', lw=1.2)
        else:
            ax.axhline(e_bar[net], color='k', lw=0.8, ls='--')
        ax.set_xlabel(f'Route distance from {H} (km)', fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.set_box_aspect(1)
        ax.text(0.5, 0.98, letter, transform=ax.transAxes, ha='center', va='top', fontsize=10, fontweight='bold')

    # --- fourth cell: the shared legend ------------------------------------------------------------------------
    lg = axes[1][1]
    lg.axis('off')
    lg.set_box_aspect(1)
    blank = [Line2D([], [], lw=0, label='')]
    if domestic:
        present = a_df.dropna(subset=['pps']).drop_duplicates('nuts3_id').sort_values('pps', ascending=False)
        region = [Line2D([0], [0], marker='o', color='w', markerfacecolor=PPS_CMAP(norm(r.pps)), markersize=7,
                         label=f'{pps_name[r.nuts3_id]} ({r.pps:,.0f} PPS)') for r in present.itertuples()]
        title = 'Colour: PPS per inhabitant by kraj (NUTS3, 2023), richest to poorest\n'
    else:
        from matplotlib.ticker import MaxNLocator, FuncFormatter
        cax = lg.inset_axes([0.12, 0.95, 0.76, 0.035])
        cb = fig.colorbar(ScalarMappable(norm=norm, cmap=PPS_CMAP), cax=cax, orientation='horizontal')
        cb.locator = MaxNLocator(5)
        cb.formatter = FuncFormatter(lambda v, _: f'{v / 1000:.0f}k')
        cb.update_ticks()
        cax.tick_params(labelsize=6)
        cax.set_title('Colour: PPS per inhabitant, NUTS3 (2023)', fontsize=7)
        region = [Line2D([0], [0], marker='o', color='w', markerfacecolor=NO_PPS, markersize=7,
                         label='Ukraine (no PPS)')] if a_df['pps'].isna().any() else []
        title = ''
    dg = [Line2D([0], [0], marker=m, color='gray', markersize=7, lw=0, label=f'DEGURBA {d} – {DEGURBA_LABELS[d]}')
          for d, m in DEGURBA_MARKER.items()]
    # scatter's `s` is an area in points^2, Line2D's markersize a diameter -> sqrt
    sz = [Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                 markersize=np.sqrt(min(p / SIZE_DIVISOR, SIZE_CAP)), label=f'{p:,} rail travellers (M2)')
          for p in SIZE_REFS]
    if a_df['hollow'].any():
        sz.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='none', markeredgecolor='gray',
                         markersize=np.sqrt(10_000 / SIZE_DIVISOR),
                         label='no M2 (< 50 km or Ukraine): sized by residents 15+'
                               + ('\n(Ukraine: all residents)' if (a_df['country'] == 'UA').any() else '')))
    tr = [Line2D([0], [0], color='k', ls='--', lw=1.2, label='log-log fit (a, c)'),
          Line2D([0], [0], color='k', ls='--', lw=0.8, label='f-weighted mean min/km, ē (b)')]
    hs = (region + blank if region else []) + dg + blank + sz + blank + tr
    lg.legend(handles=hs, loc='center' if domestic else 'upper center', bbox_to_anchor=None if domestic else (0.5, 0.86),
              frameon=False, fontsize=7, labelspacing=0.8,
              title=title + 'Shape: urban degree   ·   Size: rail market M2 (FL551)', title_fontsize=7)
    fig.tight_layout()

    n, n_h = len(a_df), int(a_df['hollow'].sum())
    label = net.replace('_', ' ')
    countries_ = ', '.join(c for c in FG.COUNTRY_ORDER if c in set(a_df['country']))
    FG.save(fig, FIG, f'grid_{net}', cap,
            f'Journey time, efficiency and frequency against route distance, {label}, inbound to {H} '
            f'({n} municipalities; {countries_}). (a) Mean journey time; (b) minutes per route kilometre, the dashed '
            f'line the frequency-weighted network mean ē = {e_bar[net]:.2f} min/km (notebook 04b, municipalities '
            'beyond 5 km); (c) journeys per day. Route distance is the track along the stations the trains call at. '
            'Dashed lines in (a) and (c) are descriptive least-squares fits on logarithms, not the models of '
            'notebook 04c. Colour: NUTS3 purchasing power per inhabitant (PPS, 2023)'
            + ('' if domestic else '; grey: Ukraine, no PPS') + '. Shape: degree of urbanisation. Marker area: the '
            'rail market M2 (residents aged 15+ times the Flash Eurobarometer 551 age-band shares of rail use; '
            'nominal, non-probability quota sample)'
            + (f'; hollow markers ({n_h}) have no M2 (under the 50 km floor or outside the survey) and are sized by '
               'residents aged 15+' + (' (Ukraine, without an age split: all residents)'
                                       if (a_df['country'] == 'UA').any() else '') if n_h else '') + '.')
    plt.close(fig)
    return n, n_h, int(len(b_df))


for net in FG.NETWORK_COLORS:
    print(net, 'LAUs (a,c) / hollow / LAUs (b):', distance_grid(net), '| e_bar =', e_bar[net])

# %% [markdown]
# ## F7 and the captions

# %%
cap.add('F7_coverage_curve_by_country',
        f'Share of each origin country\'s catchment (population aged 15+) within a mean journey time of {H}, direct '
        'and direct or one transfer (notebook 05). Poland is observed on 32 summer days.')
print('[wrote]', cap.write())
for f in sorted(os.listdir(FIG)):
    print(' ', f)
