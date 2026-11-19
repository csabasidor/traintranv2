"""
Notebook 05 -- the market-potential index and the purchasing-power profile (claude_code_prompts_market_potential.md,
P3-P6; register CON-1, CON-5, T25, VAL-2, VAL-7, VAL-8).

* ``contour``     -- primary form, no free parameter: Σ M over LAUs with journey time <= τ, a curve over τ.
* ``exponential`` -- Σ M · 2^(−t/h) over a half-life grid h (the grid is the sensitivity analysis, never an interval):
                     effective population, its ratio to Σ M (what the geography costs), and its share of the national
                     rail market.
* ``degurba_corners`` -- the bounded secondary sensitivity: city / town / rural propensity ratios, corners only.
* ``pps_profile`` -- purchasing power as a **characteristic** of the catchment, never a weight: catchment and rail market
                     by national PPS quartile, and the population-weighted mean PPS of the catchment against the country.
                     No function here multiplies a mass level by PPS (test-guarded).

The index is a joint supply-and-demand quantity: a municipality with no feasible itinerary contributes zero.
"""

import numpy as np

TAUS = (60, 90, 120, 180, 240, 300, 360)
HALF_LIVES = (60, 90, 120, 180, 240)
MASSES = ("M1", "M2", "M3")


def _groups(m):
    """(country, service level) groups plus 'all' service levels per country."""
    for (c, s), g in m.groupby(["country", "service_level"]):
        yield c, s, g
    for c, g in m.groupby("country"):
        yield c, "direct_or_onehop", g


def contour(m, taus=TAUS):
    """Cumulative opportunities: per country x service level x mass level x τ (with nominal bounds for M2 / M3)."""
    import pandas as pd
    rows = []
    for c, s, g in _groups(m):
        for mass in MASSES:
            tot = g[mass].sum(min_count=1)
            for tau in list(taus) + [np.inf]:
                x = g[g["journey_time_min"] <= tau]
                r = {"country": c, "service_level": s, "mass": mass, "tau_min": tau if np.isfinite(tau) else None,
                     "value": x[mass].sum(min_count=1), "total": tot, "n_lau": int(x[mass].notna().sum())}
                if mass != "M1":
                    r["low"], r["high"] = x[f"{mass}_low"].sum(min_count=1), x[f"{mass}_high"].sum(min_count=1)
                rows.append(r)
    out = pd.DataFrame(rows)
    out["share_of_catchment"] = out["value"] / out["total"]
    return out


def exponential(m, national_m2: dict, half_lives=HALF_LIVES):
    """Σ M · 2^(−t/h): effective population (population-equivalents at zero journey time), geography ratio and share
    of the national rail market (national_m2: country -> M2 of the whole country)."""
    import pandas as pd
    rows = []
    for c, s, g in _groups(m):
        for mass in MASSES:
            tot = g[mass].sum(min_count=1)
            for h in half_lives:
                w = np.power(2.0, -g["journey_time_min"].to_numpy() / h)
                v = np.nansum(g[mass].to_numpy() * w) if g[mass].notna().any() else np.nan
                r = {"country": c, "service_level": s, "mass": mass, "half_life_min": h, "effective_population": v,
                     "catchment": tot, "geography_ratio": v / tot if tot else np.nan,
                     "share_national_rail_market": v / national_m2[c] if mass != "M1" and national_m2.get(c) else np.nan}
                if mass != "M1":
                    r["low"] = np.nansum(g[f"{mass}_low"].to_numpy() * w)
                    r["high"] = np.nansum(g[f"{mass}_high"].to_numpy() * w)
                rows.append(r)
    return pd.DataFrame(rows)


def degurba_corners(m, L, ratios=((1.0, 1.0, 1.0), (1.2, 1.0, 0.8), (0.8, 1.0, 1.2)), mass="M2"):
    """M under city / town / rural propensity ratios, corners only (the ratios are stated).

    The FL551 rate is a national average, so the ratios are normalised over the **whole country's** 15+ population
    mix: the national rail market is unchanged, and a catchment more urban than its country gains under a
    city-high corner and loses under a rural-high one.
    """
    import pandas as pd
    a = L.assign(p15=L["POP_15_64_2025"].fillna(0) + L["POP_65PLUS_2025"].fillna(0))
    rows = []
    for rc, rt, rr in ratios:
        fmap = {1: rc, 2: rt, 3: rr}
        for c, g in m.groupby("country"):
            nat = a[a["CNTR_CODE"].eq(c)]
            norm = np.nansum(nat["p15"] * nat["DGURBA"].map(fmap)) / nat["p15"].sum() if nat["p15"].sum() else np.nan
            fg = g["dgurba"].map(fmap).astype(float)
            rows.append({"country": c, "ratio_city": rc, "ratio_town": rt, "ratio_rural": rr, "mass": mass,
                         "value": np.nansum(g[mass] * fg / norm) if norm else np.nan, "base": g[mass].sum(min_count=1)})
    return pd.DataFrame(rows)


def pps_profile(m, L, pps):
    """PPS as a catchment characteristic, per country x service level (Ukraine never pooled; no PPS multiplication).

    Bands: the national quartiles of NUTS3 PPS, population-weighted over all the country's LAUs.
    """
    import pandas as pd
    a = L[["GISCO_ID", "CNTR_CODE", "NUTS3_ID", "POP_2025"]].rename(
        columns={"GISCO_ID": "lau_code", "CNTR_CODE": "country", "NUTS3_ID": "nuts3_id", "POP_2025": "pop"})
    a = a.merge(pps[["nuts3_id", "pps_value"]], on="nuts3_id", how="left")
    rows, bands = [], []
    for c, g in a[a["pps_value"].notna()].groupby("country"):
        o = g.sort_values("pps_value")
        cum = o["pop"].cumsum() / o["pop"].sum()
        cuts = [o.loc[cum >= q, "pps_value"].iloc[0] for q in (0.25, 0.5, 0.75)]
        nat = np.average(g["pps_value"], weights=g["pop"])
        mc = m[m["country"].eq(c)].copy()
        mc["pps_band"] = pd.cut(mc["pps_value"], [-np.inf] + cuts + [np.inf], labels=["Q1", "Q2", "Q3", "Q4"])
        for s in ("direct", "onehop", "direct_or_onehop"):
            x = mc if s == "direct_or_onehop" else mc[mc["service_level"].eq(s)]
            if x.empty:
                continue
            w = x["pop_15_plus"].fillna(0)
            rows.append({"country": c, "service_level": s, "pps_level": "NUTS3", "n_lau": len(x),
                         "pps_catchment_popweighted": np.average(x["pps_value"], weights=w) if w.sum() else np.nan,
                         "pps_country_popweighted": nat,
                         "catchment_vs_country": (np.average(x["pps_value"], weights=w) / nat) if w.sum() else np.nan})
            for b, gb in x.groupby("pps_band", observed=False):
                bands.append({"country": c, "service_level": s, "pps_level": "NUTS3", "pps_band": str(b),
                              "M1": gb["M1"].sum(min_count=1), "M2": gb["M2"].sum(min_count=1),
                              "M3": gb["M3"].sum(min_count=1), "n_lau": len(gb)})
    return pd.DataFrame(rows), pd.DataFrame(bands)


def car_profile(m, L, cars, year: int = 2023):
    """Car ownership as a catchment characteristic (CON-11), never a weight: passenger cars per 1,000 inhabitants
    (Eurostat tran_r_vehst, NUTS2), population-weighted over the catchment against the whole country, per service
    level. Ukraine has no figure and is not pooled."""
    import pandas as pd
    c = cars[cars["year"] == year].set_index("nuts2_id")["cars_per_1000"]
    a = L[["CNTR_CODE", "NUTS2_ID", "POP_2025"]].assign(v=lambda d: d["NUTS2_ID"].map(c)).dropna(subset=["v"])
    rows = []
    for ctry, g in a.groupby("CNTR_CODE"):
        nat = np.average(g["v"], weights=g["POP_2025"])
        mc = m[m["country"].eq(ctry)].assign(v=lambda d: d["nuts2_id"].map(c))
        for s in ("direct", "onehop", "direct_or_onehop"):
            x = mc if s == "direct_or_onehop" else mc[mc["service_level"].eq(s)]
            w = x["pop_15_plus"].fillna(0)
            if x.empty or not w.sum():
                continue
            v = np.average(x["v"], weights=w)
            rows.append({"country": ctry, "service_level": s, "level": "NUTS2", "year": year, "n_lau": len(x),
                         "cars_per_1000_catchment": v, "cars_per_1000_country": nat, "catchment_vs_country": v / nat})
    return pd.DataFrame(rows)


# ==========================================================================
# Data dictionaries of the 05 outputs (registered with nb01a_feeds.write_meta)
# ==========================================================================

from .nb01a_feeds import SCHEMAS as _SCHEMAS   # noqa: E402

_META = {
    "source": ("str", "Flash Eurobarometer 551 (GESIS ZA8901 v1.0.0) and the traintranv2 02-04 outputs."),
    "sampling": ("str", "non-probability quota (FL551)."),
    "interval_type": ("str", "nominal: an FL551 interval is a design-effect-adjusted binomial half-width, not a margin of error."),
    "rate_is_upper_bound": ("bool", "True: the FL551 rate overstates the rail-market share (fewer non-travellers than a probability sample, FL499 dx1)."),
    "generated_at": ("str", "When the file was written."),
}
_MASS = {"mass": ("str", "M1 population catchment (15+), M2 rail-travelling population, M3 connecting-adjusted.")}
_SL = {"country": ("str", "Origin country."),
       "service_level": ("str", "direct, onehop (no direct train) or direct_or_onehop.")}
_SCHEMAS.update({
    "mp_catchment": {
        "title": "Municipal catchment of Košice (inbound) with its three mass levels",
        "produced_by": "notebooks/05_market_potential.ipynb (nb05_catchment)",
        "row": "one LAU (Bratislava one unit; the city of Košice excluded) reachable inbound on the headline runs",
        "columns": {"lau_code": ("str", "LAU (or city unit) id."), "lau_name": ("str", "Name."), **{"country": _SL["country"]},
                    "nuts2_id": ("str", "NUTS2."), "nuts3_id": ("str", "NUTS3."), "dgurba": ("float", "Degree of urbanisation."),
                    "service_level": ("str", "direct (any direct train) or onehop; exclusive."),
                    "network": ("str", "The 04 network the figures come from."), "run": ("str", "Country run (03)."),
                    "journey_time_min": ("float", "Mean journey time of the service level, minutes."),
                    "rail_km": ("float", "Mean shortest-path km."), "route_km": ("float", "Mean route km."),
                    "trips_per_day": ("float", "Journeys per day."),
                    "pop_0_14": ("float", "Population 0-14 (outside both surveys; reported only)."),
                    "pop_15_64": ("float", "Population 15-64."), "pop_65plus": ("float", "Population 65+."),
                    "pop_total": ("float", "Total population (UA: 2024)."), "pop_15_plus": ("float", "15-64 + 65+: the only base for rates."),
                    "pps_value": ("float", "NUTS3 PPS per inhabitant (2023)."),
                    "pps_level": ("str", "NUTS3, or UA_no_PPS."), "pps_year": ("float", "Year of the PPS value."),
                    "in_inner_ring": ("bool", "Rail distance < 50 km: below FL551's distance floor, not converted."),
                    "in_survey": ("bool", "The country is in FL551 (not UA)."),
                    "M1": ("float", "Population catchment: pop_15_plus."),
                    "M2": ("float", "Rail-travelling population: age-banded FL551 rates (beyond 50 km)."),
                    "M2_low": ("float", "M2 at the rates' nominal lower bounds."), "M2_high": ("float", "M2 at the upper bounds."),
                    "M2_flat": ("float", "M2 with the flat national rate (for comparison)."),
                    "M3": ("float", "Connecting-adjusted: M2 (direct) or M2 x (T2|T1) (onehop)."),
                    "M3_low": ("float", "M3 at the nominal lower bounds."), "M3_high": ("float", "M3 at the upper bounds."), **_META},
    },
    "mp_cascade": {
        "title": "The Slovak cascade: residents -> with a connection -> same-day return -> rail travellers, against the legacy figures",
        "produced_by": "notebooks/05_market_potential.ipynb",
        "row": "one step",
        "columns": {"step": ("str", "Step."), "base": ("str", "Population base (total or 15+)."),
                    "new": ("float", "This run."), "legacy": ("float", "The register's legacy figure."),
                    "new_share_of_residents": ("float", "new / residents."), "legacy_share": ("float", "legacy / legacy residents."),
                    **_META},
    },
    "mp_contour": {
        "title": "Market potential, contour form: catchment within a journey time τ",
        "produced_by": "notebooks/05_market_potential.ipynb (nb05_market_potential.contour)",
        "row": "one country x service level x mass level x τ (empty τ = the whole catchment)",
        "columns": {**_SL, **_MASS, "tau_min": ("float", "Journey-time limit, minutes."),
                    "value": ("float", "Σ M over LAUs with mean journey time <= τ."), "total": ("float", "Σ M of the whole catchment."),
                    "n_lau": ("int", "LAUs counted."), "low": ("float", "At the rates' nominal lower bounds (M2 / M3)."),
                    "high": ("float", "At the upper bounds."), "share_of_catchment": ("float", "value / total."), **_META},
    },
    "mp_exp": {
        "title": "Market potential, exponential form by half-life: effective population",
        "produced_by": "notebooks/05_market_potential.ipynb (nb05_market_potential.exponential)",
        "row": "one country x service level x mass level x half-life",
        "columns": {**_SL, **_MASS, "half_life_min": ("int", "Half-life h, minutes (the grid is the sensitivity analysis)."),
                    "effective_population": ("float", "Σ M · 2^(-t/h): population-equivalents at zero journey time."),
                    "catchment": ("float", "Σ M."), "geography_ratio": ("float", "effective_population / catchment."),
                    "share_national_rail_market": ("float", "effective_population / M2 of the whole country (M2, M3)."),
                    "low": ("float", "At the rates' nominal lower bounds."), "high": ("float", "At the upper bounds."), **_META},
    },
    "mp_degurba_corners": {
        "title": "DEGURBA sensitivity: rail market under city / town / rural propensity ratios (corners)",
        "produced_by": "notebooks/05_market_potential.ipynb (nb05_market_potential.degurba_corners)",
        "row": "one country x corner",
        "columns": {"country": _SL["country"], "ratio_city": ("float", "Propensity ratio for cities (DEGURBA 1)."),
                    "ratio_town": ("float", "For towns and suburbs (2)."), "ratio_rural": ("float", "For rural areas (3)."),
                    **_MASS, "value": ("float", "The mass under the ratios (renormalised to the catchment mix)."),
                    "base": ("float", "Uniform-rate value."), **_META},
    },
    "mp_pps_profile": {
        "title": "Purchasing power of the catchment against its country (a characteristic, not a weight)",
        "produced_by": "notebooks/05_market_potential.ipynb (nb05_market_potential.pps_profile)",
        "row": "one country x service level (UA not included: no PPS)",
        "columns": {**_SL, "pps_level": ("str", "NUTS3."), "n_lau": ("int", "LAUs."),
                    "pps_catchment_popweighted": ("float", "Population(15+)-weighted mean PPS of the catchment."),
                    "pps_country_popweighted": ("float", "Population-weighted mean PPS of the whole country."),
                    "catchment_vs_country": ("float", "Ratio of the two (> 1: the reachable population is in richer regions)."), **_META},
    },
    "mp_car_profile": {
        "title": "Car ownership of the catchment against its country (a characteristic, not a weight; CON-11)",
        "produced_by": "notebooks/05_market_potential.ipynb (nb05_market_potential.car_profile)",
        "row": "one country x service level (UA not included: no figure)",
        "columns": {**_SL, "level": ("str", "NUTS2."), "year": ("int", "Reference year (2023, as PPS)."),
                    "n_lau": ("int", "LAUs."),
                    "cars_per_1000_catchment": ("float", "Population(15+)-weighted passenger cars per 1,000 inhabitants of the catchment (Eurostat tran_r_vehst)."),
                    "cars_per_1000_country": ("float", "Population-weighted value of the whole country."),
                    "catchment_vs_country": ("float", "Ratio of the two (< 1: the reachable population owns fewer cars)."), **_META},
    },
    "mp_pps_bands": {
        "title": "Catchment and rail market by national PPS quartile",
        "produced_by": "notebooks/05_market_potential.ipynb (nb05_market_potential.pps_profile)",
        "row": "one country x service level x PPS quartile",
        "columns": {**_SL, "pps_level": ("str", "NUTS3."),
                    "pps_band": ("str", "Q1 (poorest) .. Q4: national quartiles of NUTS3 PPS, population-weighted over the LAUs."),
                    "M1": ("float", "Population catchment (15+)."), "M2": ("float", "Rail-travelling population."),
                    "M3": ("float", "Connecting-adjusted."), "n_lau": ("int", "LAUs."), **_META},
    },
})
