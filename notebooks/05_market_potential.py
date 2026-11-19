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
# # 05 — Population catchment, rail market and market potential; purchasing power as a catchment characteristic
#
# The demand-side quantities of the revision (`claude_code_prompts_market_potential.md`, P1–P7; register CON-1,
# CON-5, T25, T33, VAL-2, VAL-7, VAL-8, REP-9, STA-6), on the frozen 02 / 03 / 04 outputs. Code:
# `traintranv2/nb05_catchment.py`, `nb05_market_potential.py`.
#
# | § | step | output (`output/kosice/explore/`) |
# |---|---|---|
# | 1 | the municipal catchment table (inbound, headline runs), with its reconciliation | `catchment.csv` |
# | 2 | three mass levels M1 / M2 / M3; the Slovak cascade and the four-country headline | `catchment.csv`, `cascade.csv` |
# | 3 | market potential: contour (primary) and exponential by half-life | `market_potential_contour.csv`, `market_potential_exp.csv` |
# | 4 | uncertainty: nominal rate intervals; the DEGURBA corners | `degurba_corners.csv` |
# | 5 | purchasing power as a characteristic of the catchment | `pps_profile.csv`, `pps_bands.csv` |
# | 5b | car ownership, likewise (CON-11) | `car_profile.csv` |
# | 6 | the value index: data check (not built) | — |
# | 7 | the coverage-curve figure | `figures/coverage_curve_by_country.png` |
#
# **Standing constraints.**
# 1. FL551 is a **non-probability quota** survey: every interval derived from it is **nominal**. FL499 (probability)
#    is not used here.
# 2. The FL551 rate is an **upper bound** on the rail-market share. A cross-instrument test against FL499 `dx1` shows
#    the quota panel reporting fewer non-travellers than a probability sample in all five countries. Every
#    FL551-derived figure carries `rate_is_upper_bound = True`.
# 3. **Poland** is measured on 32 early-summer days (both Polish feeds, 03b); its figures are labelled so.
#
# **Units.** One row per municipality (LAU). The city of Košice (22 *mestské časti*) is the destination and appears
# nowhere; Bratislava's 17 districts are one unit. Population: end-2025, **aged 15+** (both surveys sample 15+); the
# 0–14 band is carried only to report the share left out. Ukraine has 2024 totals without age bands and is not in
# FL551: M1 is its total, reported separately; no rail-market figure.

# %%
import os, sys

# Run from the project root so every relative path resolves the same from notebooks/ or the root.
_here = os.path.abspath('')
if os.path.basename(_here) == 'notebooks':
    os.chdir(os.path.dirname(_here))
sys.path.insert(0, os.getcwd())
print('Working directory:', os.getcwd())

# %%
import datetime as dt
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import traintranv2  # noqa: F401  (PROJ data fix)
from traintranv2.config import default_config
from traintranv2 import nb02_connections as C
from traintranv2 import nb05_catchment as K
from traintranv2 import nb05_market_potential as MP
from traintranv2.nb01a_feeds import write_meta
from traintranv2.nb01b_stations import load_lau_subset

cfg = default_config()
OUT = os.path.join(cfg.out_dir, 'explore')
FIG = os.path.join(OUT, 'figures')
os.makedirs(FIG, exist_ok=True)
L = C.lau_with_city_units(load_lau_subset(cfg), cfg)
lau = pd.read_csv(os.path.join(OUT, 'lau_table.csv'), dtype={'lau_gisco_id': str})
rates = K.load_rates('data/eb')
META = {'source': 'Flash Eurobarometer 551 (GESIS ZA8901 v1.0.0, doi:10.4232/1.14506); traintranv2 02-04 outputs',
        'sampling': K.SAMPLING, 'interval_type': K.INTERVAL, 'rate_is_upper_bound': True,
        'generated_at': dt.datetime.now().isoformat(timespec='seconds')}
display(rates.round(3))

# %% [markdown]
# ## 1. The catchment table (P1)
#
# One row per LAU reachable **inbound** on the headline runs. `service_level` is exclusive: a municipality with any
# direct train is `direct` and never counted in the one-hop layer. Its journey time, distances and frequency are those
# of that level. Purchasing power: NUTS3 PPS per inhabitant (Eurostat `nama_10r_3gdp`) for all five EU countries,
# one common year (2023, the latest Austria and Poland publish at NUTS3); `pps_level` and `pps_year` per row; Ukraine
# `UA_no_PPS`.

# %%
cat = K.catchment(cfg, lau, L)
rec = K.check_catchment(cat)
cov_d = pd.read_csv(os.path.join(cfg.out_dir, 'domestic', 'one_transfer_coverage.csv'))
cov_f = pd.read_csv(os.path.join(cfg.out_dir, 'foreign', 'one_transfer_coverage.csv'))
ref = pd.concat([cov_d.assign(country='SK'), cov_f[cov_f.run.isin(['CZ', 'HU', 'AT', 'PL', 'UA'])]], ignore_index=True)
ref = ref[(ref.direction == 'inbound') & (ref.group == 'direct_or_one_transfer')][['country', 'n_lau', 'population']]
chk = rec.groupby('country').agg(n_lau=('n_lau', 'sum'), pop_total=('pop_total', 'sum')).join(ref.set_index('country'), rsuffix='_0203')
print('reconciliation: the catchment table against the 02 / 03 coverage (direct or one transfer, inbound):')
display(chk)
assert (chk['n_lau'] == chk['n_lau_0203']).all(), 'catchment LAUs differ from 02 / 03 coverage'
display(rec)
print(f"0-14 left out of every rate base: {cat['pop_0_14'].sum():,.0f} "
      f"({cat['pop_0_14'].sum() / cat['pop_total'].sum():.1%} of the catchment's population, UA excluded)")

# %% [markdown]
# ## 2. Mass levels (P2)
#
# * **M1** population catchment = population 15+.
# * **M2** rail-travelling population = pop 15–64 · r(15–64) + pop 65+ · r(65+), the age-banded FL551 rates; the
#   flat-rate version (r national) beside it.
# * **M3** connecting-adjusted = M2 on direct rows, M2 · (T2 | T1) on one-hop rows. A traveller reaching Košice
#   directly never connects, so the behavioural discount applies to the one-hop layer only; Poland and Austria have
#   no direct train, so their whole catchment takes it.
#
# The conversion applies only **beyond 50 km rail distance**: FL551 Q1_1 describes journeys of 50 km and more, so it
# says nothing about the immediate hinterland (Prešov is 34 km away). The inner ring is reported at M1, unconverted,
# and is excluded from every converted total.

# %%
m = K.mass_levels(cat, rates)
K.check_mass_levels(m)
ring = m[m.in_inner_ring]
print(f'inner ring (< 50 km): {len(ring)} LAUs, {ring.M1.sum():,.0f} people aged 15+ (M1 only, unconverted)')
tot = m[~m.in_inner_ring].groupby(['country', 'service_level'])[['M1', 'M2', 'M2_flat', 'M3']].sum(min_count=1)
tot['M2_flat_vs_banded'] = (tot['M2_flat'] / tot['M2'] - 1).round(4)
display(tot.round(0))

# Slovak cascade, beside the legacy figures (register CON-1)
sk_all = L[(L.CNTR_CODE == 'SK') & ~L.GISCO_ID.isin(C.hub_city_laus(cfg))]
dtrip = pd.read_csv(os.path.join(cfg.out_dir, 'domestic', 'daytrip_one_transfer_lau.csv'), dtype={'lau_gisco_id': str})
same_day = set(dtrip['lau_gisco_id'])
msk = m[m.country == 'SK']
conv_sd = msk[msk.lau_code.isin(same_day)]
LEG = cfg.legacy_dir is not None          # legacy figures exist for Košice only
lg = lambda v: v if LEG else np.nan
cascade = pd.DataFrame([
    {'step': f'resident population (all Slovak LAUs except {cfg.hub_label})', 'base': 'total', 'new': sk_all.POP_2025.sum(), 'legacy': lg(5_195_773)},
    {'step': 'with a rail connection (direct or one transfer)', 'base': 'total', 'new': msk.pop_total.sum(), 'legacy': lg(2_920_024)},
    {'step': 'able to make a same-day return', 'base': 'total', 'new': msk[msk.lau_code.isin(same_day)].pop_total.sum(), 'legacy': lg(1_683_430)},
    {'step': 'rail travellers among them (M2, beyond 50 km)', 'base': '15+', 'new': conv_sd.M2.sum(), 'legacy': lg(846_494)},
    {'step': 'rail travellers among them, flat rate (legacy definition: total population x r_national)', 'base': 'total',
     'new': (msk[msk.lau_code.isin(same_day)].pop_total * rates.loc['SK', 'r_national']).sum(), 'legacy': lg(846_494)},
])
cascade['new_share_of_residents'] = cascade['new'] / cascade.loc[0, 'new']
cascade['legacy_share'] = cascade['legacy'] / cascade.loc[0, 'legacy']
display(cascade.round(3))
four = m[(m.country.isin(['CZ', 'HU', 'PL', 'AT'])) & (m.service_level == 'onehop')]
print(f"four-country one-transfer catchment (CZ, HU, PL, AT; no direct train): total population {four.pop_total.sum():,.0f}, "
      f"15+ {four.M1.sum():,.0f} -> rail market M2 {four.M2.sum():,.0f}"
      + ("  (legacy: 11.25 M -> 5.89 M, total population x flat rate)" if LEG else ""))
if LEG:
    print('why the figures differ: corrected hub (Košice station), Košice as one city, Bratislava one unit, LAU 2024 and 2025 '
          'population, midnight / dedup / same-train fixes, both Polish feeds (CF-23), 15+ base, the 50 km floor')

# %% [markdown]
# ## 3. Market potential (P3)
#
# **Contour (primary; no free parameter):** Σ M over the LAUs with mean journey time ≤ τ, a curve over τ ∈ {60 … 360}
# minutes, per country × service level × mass level. **Exponential:** Σ M · 2^(−t/h), with the half-life h ∈ {60 …
# 240} minutes as the parameter — a half-life is explicable, a bare decay coefficient is not; the grid over h is the
# sensitivity analysis. Reported as **effective population** (population-equivalents at zero journey time), its ratio
# to Σ M (what the geography costs), and its share of the national rail market (M2 of the whole country). Cost =
# journey time only: a frequency or transfer term would add parameters not calibratable here.

# %%
nat = {}
A = L.set_index('GISCO_ID')
for c in rates.index:
    x = A[A.CNTR_CODE == c]
    nat[c] = float((x.POP_15_64_2025 * rates.loc[c, 'r_15_64'] + x.POP_65PLUS_2025 * rates.loc[c, 'r_65plus']).sum())
conv = m      # inner-ring rows carry no M2 / M3, so every converted total leaves them out; M1 keeps them
cont = MP.contour(m)
expo = MP.exponential(m, nat)
pts = cont[(cont.country == 'SK') & (cont.service_level == 'direct') & (cont.mass == 'M1') & cont.tau_min.isin([60, 90])]
print('domestic direct, share of the catchment (15+) within 60 / 90 minutes:',
      dict(zip(pts.tau_min, pts.share_of_catchment.round(3))), '(manuscript: 14.5 % / 30 % of the total population)')
display(cont[(cont.mass == 'M1') & cont.tau_min.notna()].pivot_table(index=['country', 'service_level'], columns='tau_min',
                                                                       values='share_of_catchment').round(3))
display(expo[(expo.mass == 'M2') & (expo.service_level == 'direct_or_onehop')]
        .pivot_table(index='country', columns='half_life_min', values=['effective_population', 'share_national_rail_market']).round(3))

# %% [markdown]
# ## 4. Uncertainty (P4)
#
# * **The propensity rates are uncertain** (nominal ±3.1 to ±3.3 pp at country level). One rate applies to every
#   municipality of a country, so the errors are perfectly correlated: Var(Σ Nᵢ p̂) = (Σ Nᵢ)² Var(p̂), and the
#   relative interval of any total equals that of the rate. Age-banding moves the point estimate, not the width. The
#   `low` / `high` columns of the M2 / M3 outputs carry these nominal bounds.
# * **The half-life is not uncertain, it is unknown:** a grid, never an interval, and never combined with the rate
#   interval into one error bar.
# * **DEGURBA composition** (bounded secondary sensitivity): applying a country rate uniformly assumes the same
#   propensity in cities, towns and rural areas. Corners only: city / town / rural ratios 1.2 / 1 / 0.8 and
#   0.8 / 1 / 1.2, against the uniform 1 / 1 / 1. The FL551 rate is a national average, so the ratios are normalised
#   over each country's whole 15+ population mix: the national rail market stays the same, and a catchment more urban
#   than its country gains under the city-high corner.

# %%
x = conv.groupby('country')[['M2', 'M2_low', 'M2_high']].sum(min_count=1)
x['rel_halfwidth'] = ((x['M2_high'] - x['M2_low']) / 2 / x['M2']).round(4)
x['rate_rel_halfwidth'] = ((rates['ci_high'] - rates['ci_low']) / 2 / rates['r_national']).reindex(x.index).round(4)
display(x)
corners = MP.degurba_corners(conv, L)
display(corners.round({'value': 0, 'base': 0}))

# %% [markdown]
# ## 5. Purchasing power: a characteristic of the catchment, not a weight (P5; CON-5, T25)
#
# **The index is not multiplied by PPS**, for two reasons:
# 1. **It would double-count income.** The FL551 rate is *observed* behaviour, not income-standardised: part of the gap
#    between Czechia's 59.4 % and Hungary's 44.7 % is an income difference between those populations. Multiplying by
#    PPS on top counts income twice. FL551 carries no income variable (occupation `d5a` is the nearest), so the rate
#    cannot be decomposed to remove it.
# 2. **PPS is regional, not municipal.** One NUTS3 value applies to every municipality of the region, so as a weight it
#    adds no variation within a region, and spreading it over municipalities does not reduce its error (VAL-8, point 4).
#    Ukraine has no PPS at all.
#
# **Aim 3 is narrowed accordingly:** the catchment is weighted by population and degree of urbanisation; regional
# purchasing power is reported as a characteristic of the catchment. Below: catchment and rail market by national PPS
# quartile (population-weighted over each country's LAUs), the population-weighted mean PPS of the catchment against
# the country, direct against one-hop (does a transfer reach different economic territory?). Ukraine is never pooled.

# %%
pps = K.pps_table(cfg)
prof, bands = MP.pps_profile(conv, L, pps)
display(prof.round(3))
display(bands.pivot_table(index=['country', 'service_level'], columns='pps_band', values='M1', aggfunc='sum').round(0))
# Bratislava and the Košice region (legacy: 479,389 inhabitants, a third of the directly connected population;
# Košice region 5th nationally, 44th among the sampled EU regions)
# the other city unit in the catchment (Bratislava when the hub is Košice, and the reverse)
from traintranv2.config import DESTINATIONS
other = next(u for u in cfg.city_units if u != cfg.hub_city)
other_nuts3 = next(d['hub_nuts3'] for d in DESTINATIONS.values() if d['hub_city'] == other)
_raw = load_lau_subset(cfg)
n_districts = int(((_raw.CNTR_CODE == 'SK') & _raw.LAU_NAME_NATIONAL.astype(str).str.startswith(cfg.city_units[other])).sum())
ba = m[m.lau_code == f'SK_CITY_{other}']
d_sk = m[(m.country == 'SK') & (m.service_level == 'direct')]
print(f"{other} ({n_districts} districts, one unit): {ba.pop_total.sum():,.0f} inhabitants, {ba.service_level.iloc[0] if len(ba) else '-'}; "
      f"{ba.pop_total.sum() / d_sk.pop_total.sum():.1%} of the directly connected population; "
      f"PPS {pps.set_index('nuts3_id').loc[other_nuts3, 'pps_value']:.0f}; "
      f"journey {(ba.journey_time_min.iloc[0] if len(ba) else float('nan')):.0f} min"
      + (" (legacy 479,389, about a third)" if LEG else ""))
p = pps.dropna(subset=['pps_value']).sort_values('pps_value', ascending=False).reset_index(drop=True)
rk_n = p[p.country == 'SK'].reset_index(drop=True)
H3 = cfg.hub_nuts3
print(f"{cfg.hub_label} region {H3}: PPS {pps.set_index('nuts3_id').loc[H3, 'pps_value']:.0f}; "
      f"rank {rk_n.index[rk_n.nuts3_id == H3][0] + 1} of {len(rk_n)} in Slovakia, "
      f"{p.index[p.nuts3_id == H3][0] + 1} of {len(p)} NUTS3 regions of the five EU countries "
      + (f"(legacy: 5th nationally, 44th; year {int(pps.pps_year.iloc[0])})" if LEG else f"(year {int(pps.pps_year.iloc[0])})"))

# %% [markdown]
# ## 5b. Car ownership: also a characteristic (CON-11)
#
# Among the demand determinants Reviewer 1 lists, car ownership is the one with harmonised regional data: passenger
# cars per 1,000 inhabitants, Eurostat `tran_r_vehst`, NUTS2, 2023 (fetched once into `data/eu/eurostat/` with a
# manifest of URL, retrieval time and SHA-256). Like PPS it describes the catchment and is not a weight: it is
# regional, and its effect on rail use is what FL551's observed rate already contains. Ukraine has no figure.

# %%
import json
cars = pd.read_csv('data/eu/eurostat/tran_r_vehst_car_p_thab.csv')
man = json.load(open('data/eu/eurostat/tran_r_vehst_car_p_thab.manifest.json', encoding='utf-8'))
print(f"tran_r_vehst retrieved {man['retrieved_utc']}, sha256 {man['sha256_json'][:12]}, {man['regions_requested']} NUTS2 regions")
carp = MP.car_profile(conv, L, cars)
display(carp.round(3))

# %% [markdown]
# ## 6. The value index (P6): not built
#
# Before any PPS-based spending proxy, the data check: does a direct measure exist? **Yes.** ŠÚ SR (`cr3804mr`, notebook
# 00_d1) publishes Košice visitors **and nights by country of origin**, so the average length of stay by origin is
# measured directly. A direct measure beats a proxy; the value index is therefore not constructed.

# %%
if cfg.visitors_file and os.path.exists(cfg.visitors_file):
    v = pd.read_csv(cfg.visitors_file)
    v = v[v.period == 'YEAR'].pivot_table(index='origin_code', columns='indic_code', values='value')
    v = v.rename(columns={'U_CR_0005': 'visitors', 'U_CR_0008': 'nights', 'U_CR_0011': 'avg_nights'})
    display(v.loc[['VISIT_DOM', 'CZ', 'HU', 'PL', 'AT', 'UA', 'VISIT_FOR', 'VISIT_TOTAL']])
else:
    print(f'no visitors-by-origin file for {cfg.hub_label}: section not computed')

# %% [markdown]
# ## 7. The coverage-curve figure
#
# Share of each country's catchment (15+) within a mean journey time τ, one line per origin country; direct and direct
# or one-hop as separate series.

# %%
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
for k, s in enumerate(['direct', 'direct_or_onehop']):
    x = cont[(cont.mass == 'M1') & (cont.service_level == s) & cont.tau_min.notna()]
    for c, g in x.groupby('country'):
        g = g.sort_values('tau_min')
        if g['total'].iloc[0] and np.isfinite(g['total'].iloc[0]):
            ax[k].plot(g.tau_min, g.share_of_catchment, marker='o', label=c)
    ax[k].set_title('direct' if s == 'direct' else 'direct or one transfer')
    ax[k].set_xlabel(f'mean journey time to {cfg.hub_label}, minutes')
    ax[k].grid(alpha=0.3)
ax[0].set_ylabel('share of the catchment (15+)')
ax[1].legend(title='origin', frameon=False)
fig.suptitle(f'Catchment within a journey time of {cfg.hub_label}, by origin country (inbound; PL: 32 summer days)')
fig.tight_layout()
fig.savefig(os.path.join(FIG, 'coverage_curve_by_country.png'), dpi=300)
plt.close(fig)
print('[wrote]', os.path.join(FIG, 'coverage_curve_by_country.png'))

# %% [markdown]
# ## 8. Methods text and outputs
#
# **For the manuscript.** The market-potential index is a **joint supply-and-demand quantity**: municipalities with no
# feasible itinerary contribute zero, so it embeds the connectivity result and is not an independent measure of demand.
# The survey conversion applies beyond 50 km rail distance only; the inner ring is reported unconverted. The decay
# half-life is swept over a grid, not given an interval, because it is unknown rather than uncertain. Regional
# purchasing power characterises the catchment rather than weighting it, for the two reasons in §5. The FL551 rate is a
# nominal, non-probability estimate and an upper bound on the rail-market share. Poland is observed on 32 early-summer
# days.

# %%
for f, k, frame in [('catchment.csv', 'mp_catchment', m), ('cascade.csv', 'mp_cascade', cascade),
                    ('market_potential_contour.csv', 'mp_contour', cont), ('market_potential_exp.csv', 'mp_exp', expo),
                    ('degurba_corners.csv', 'mp_degurba_corners', corners), ('pps_profile.csv', 'mp_pps_profile', prof),
                    ('pps_bands.csv', 'mp_pps_bands', bands), ('car_profile.csv', 'mp_car_profile', carp)]:
    out = frame.assign(**META)
    p = os.path.join(OUT, f)
    out.to_csv(p, index=False, encoding='utf-8')
    write_meta(p, k, out, {'Inputs': 'explore/lau_table.csv, data/eb/fl551_*_national.csv, NUTS subset PPS 2023'})
    print(f'[wrote] {p} ({len(out):,} rows) + .meta.md')
