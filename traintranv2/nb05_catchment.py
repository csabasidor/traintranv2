"""
Notebook 05 -- the municipal catchment table and the three mass levels (claude_code_prompts_market_potential.md,
P1-P2; register CON-1, VAL-7, VAL-8, REP-9, STA-6).

* ``catchment``   -- one row per LAU (city units for Košice / Bratislava) reachable from Košice **inbound** on the
                     headline runs: service level (direct / onehop, exclusive), mean journey time of that level, rail
                     and route km, trips per day, population by age band (15+ is the only base used downstream), and
                     regional purchasing power with the NUTS level and year it was measured at.
* ``mass_levels`` -- M1 population catchment (15+); M2 rail-travelling population (age-banded FL551 rates; a flat-
                     rate version beside it); M3 connecting-adjusted (M2 on direct rows, M2 * (T2 | T1) on one-hop
                     rows). The conversion applies only beyond ``floor_km`` rail distance (FL551 Q1_1 describes
                     journeys of 50 km and more): inside it, M1 only, unconverted. Ukraine is not in FL551: M1 only.

FL551 is a **non-probability quota** survey: every interval derived from it is nominal, and its rate is an **upper
bound** on the rail-market share (prompt file, standing constraints 1-2).
"""

import numpy as np

SAMPLING = "non-probability quota"
INTERVAL = "nominal"


def pps_table(cfg, year: int = 2023):
    """NUTS3 purchasing power per inhabitant (PPS, EU27_2020 = 100 basis as published by Eurostat nama_10r_3gdp) for
    the five EU countries, one common year (2023: the latest year Austria and Poland publish at NUTS3)."""
    import json
    import os
    import pandas as pd
    p = os.path.join(cfg.nuts_dir, "NUTS_RG_01M_2024_4326_LEVL_3.geojson")
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    rows = [f["properties"] for f in d["features"]]
    t = pd.DataFrame(rows)[["NUTS_ID", "CNTR_CODE", "NUTS_NAME", f"PPS_EU27_2020_HAB_{year}"]]
    t = t.rename(columns={"NUTS_ID": "nuts3_id", "CNTR_CODE": "country", "NUTS_NAME": "nuts3_name",
                          f"PPS_EU27_2020_HAB_{year}": "pps_value"})
    t["pps_level"], t["pps_year"] = "NUTS3", year
    return t


def catchment(cfg, lau, L):
    """One row per reachable LAU (inbound, headline runs). ``lau``: explore/lau_table.csv; ``L``: the LAU layer with
    city units (nb02_connections.lau_with_city_units)."""
    import pandas as pd

    x = lau[(lau["direction"] == "inbound") & lau["headline"].astype(str).eq("True")].copy()
    x["level"] = np.where(x["network"].str.endswith("_direct"), "direct", "onehop")
    # exclusive service level: any direct service makes the LAU direct; its figures are then the direct ones
    x = x.sort_values("level").drop_duplicates("lau_gisco_id", keep="first")
    a = L.set_index("GISCO_ID")
    cat = pd.DataFrame({
        "lau_code": x["lau_gisco_id"].to_numpy(), "lau_name": x["lau_name"].to_numpy(),
        "country": x["country"].to_numpy(), "nuts2_id": x["nuts2_id"].to_numpy(), "nuts3_id": x["nuts3_id"].to_numpy(),
        "dgurba": x["degurba"].to_numpy(), "service_level": x["level"].to_numpy(), "network": x["network"].to_numpy(),
        "run": x["run"].to_numpy(), "journey_time_min": x["time_mean_min"].to_numpy(),
        "rail_km": x["rail_km_mean"].to_numpy(), "route_km": x["route_km_mean"].to_numpy(),
        "trips_per_day": x["f_per_day"].to_numpy()})
    for col, src in (("pop_0_14", "POP_0_14_2025"), ("pop_15_64", "POP_15_64_2025"), ("pop_65plus", "POP_65PLUS_2025"),
                     ("pop_total", "POP_2025")):
        cat[col] = cat["lau_code"].map(a[src]).to_numpy()
    ua = cat["country"].eq("UA")
    cat.loc[ua, "pop_total"] = cat.loc[ua, "lau_code"].map(a["POP_2024"]).to_numpy()     # UA: 2024 total, no bands
    cat["pop_15_plus"] = cat["pop_15_64"] + cat["pop_65plus"]
    pps = pps_table(cfg).set_index("nuts3_id")
    cat["pps_value"] = cat["nuts3_id"].map(pps["pps_value"])
    cat["pps_level"] = np.where(ua, "UA_no_PPS", "NUTS3")
    cat["pps_year"] = np.where(ua, np.nan, pps["pps_year"].iloc[0])
    cat.loc[ua, "pps_value"] = np.nan
    return cat.reset_index(drop=True)


def check_catchment(cat):
    """The P1 acceptance rules; returns the reconciliation table (printed by the notebook)."""
    import pandas as pd
    assert cat["lau_code"].is_unique, "one row per LAU"
    assert set(cat["service_level"]) <= {"direct", "onehop"}
    nonua = ~cat["country"].eq("UA")
    assert np.allclose(cat.loc[nonua, "pop_15_plus"], cat.loc[nonua, "pop_15_64"] + cat.loc[nonua, "pop_65plus"])
    assert cat["pps_level"].notna().all()
    return (cat.groupby(["country", "service_level"])
            .agg(n_lau=("lau_code", "size"), pop_total=("pop_total", "sum"), pop_15_plus=("pop_15_plus", "sum"),
                 pop_0_14=("pop_0_14", "sum")).reset_index())


def load_rates(eb_dir: str = "data/eb"):
    """FL551 country rates (percent -> share): r_15_64, r_65plus, r_national with nominal intervals, and T2 | T1."""
    import os
    import pandas as pd
    c = pd.read_csv(os.path.join(eb_dir, "fl551_conversion_national.csv"), encoding="utf-8-sig").set_index("isocntry")
    t = pd.read_csv(os.path.join(eb_dir, "fl551_connecting_national.csv"), encoding="utf-8-sig").set_index("isocntry")
    r = pd.DataFrame({k: c[k] / 100 for k in ("r_national", "r_15_64", "r_65plus", "ci_low", "ci_high",
                                              "ci_low_15_64", "ci_high_15_64", "ci_low_65plus", "ci_high_65plus")})
    r["t2_given_t1"] = t["T2_pct_of_T1"] / 100
    return r


def mass_levels(cat, rates, floor_km: float = 50.0):
    """M1 / M2 / M3 per LAU with nominal intervals (perfectly correlated within a country, VAL-8 point 4)."""
    m = cat.copy()
    m["in_inner_ring"] = m["rail_km"] < floor_km
    m["in_survey"] = m["country"].isin(rates.index)
    m["M1"] = m["pop_15_plus"]
    conv = ~m["in_inner_ring"] & m["in_survey"]
    rr = rates.reindex(m["country"])
    for suf, a, b in (("", "r_15_64", "r_65plus"), ("_low", "ci_low_15_64", "ci_low_65plus"),
                      ("_high", "ci_high_15_64", "ci_high_65plus")):
        v = m["pop_15_64"].to_numpy() * rr[a].to_numpy() + m["pop_65plus"].to_numpy() * rr[b].to_numpy()
        m[f"M2{suf}"] = np.where(conv, v, np.nan)
    m["M2_flat"] = np.where(conv, m["pop_15_plus"].to_numpy() * rr["r_national"].to_numpy(), np.nan)
    t = np.where(m["service_level"].eq("onehop"), rr["t2_given_t1"].to_numpy(), 1.0)
    for suf in ("", "_low", "_high"):
        m[f"M3{suf}"] = m[f"M2{suf}"] * t
    return m


def check_mass_levels(m):
    ok = m["M2"].notna()
    assert (m.loc[ok, "M3"] <= m.loc[ok, "M2"] + 1e-9).all() and (m.loc[ok, "M2"] <= m.loc[ok, "M1"] + 1e-9).all()
    d = ok & m["service_level"].eq("direct")
    assert np.allclose(m.loc[d, "M3"], m.loc[d, "M2"]), "M3 = M2 on direct rows"
    assert m.loc[m["in_inner_ring"], "M2"].isna().all(), "the inner ring stays unconverted"
