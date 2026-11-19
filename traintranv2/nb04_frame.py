"""
Notebooks 04a-07 -- one analysis table for the four networks, built only from the 02 / 03 outputs.

Networks: domestic (Slovak LAUs, 02a / 02b) and foreign (CZ, HU, AT, PL, UA LAUs, 03a / 03b), each **direct** and
**one-transfer**. Two layers:

* ``journeys``  -- one row per distinct journey and LAU (a direct trip, or a first + second train pair) and
                   direction: journey time, run dates, route / rail / geo km, wait. A journey calling at several
                   stations of one LAU is one row for the LAU (the shortest ride kept, as 02 / 03 count it).
* ``lau_table`` -- per LAU x direction x network x run: the metric-spec aggregates (§1-4) -- n journeys, run days,
                   f = run days / window days, mean / median journey time, mean route / rail / geo km -- with
                   population (15+ too), DEGURBA, NUTS2 / NUTS3, country, has_direct.

Route km (``nb04_distance``) is computed once and cached in output/kosice/explore/route_km_*.parquet.
"""

import os

import numpy as np

from .config import RunConfig

NETWORKS = ["domestic_direct", "domestic_one_transfer", "foreign_direct", "foreign_one_transfer"]


def _out(cfg: RunConfig) -> str:
    p = os.path.join(cfg.out_dir, "explore")
    os.makedirs(p, exist_ok=True)
    return p


def _route_cache(cfg: RunConfig, tags, snap, refresh: bool = False):
    """route_km for the 02 / 03 direct legs and itineraries, aligned to the files' row order (cached)."""
    import pandas as pd
    from . import nb02_connections as C, nb03_foreign as F, nb04_distance as D
    from .nb01c_rail_network import RailGraph

    o, O = _out(cfg), cfg.out_dir
    paths = {k: os.path.join(o, f"route_km_{k}.parquet") for k in ("dom_legs", "dom_itins", "for_legs", "for_itins")}
    src = {"dom_legs": f"{O}/domestic/direct_legs.parquet", "dom_itins": f"{O}/domestic/one_transfer_itins.parquet",
           "for_legs": f"{O}/foreign/direct_legs.parquet", "for_itins": f"{O}/foreign/one_transfer_itins.parquet"}
    fresh = all(os.path.exists(p) and os.path.getmtime(p) >= os.path.getmtime(src[k]) for k, p in paths.items())
    if fresh and not refresh:
        return {k: pd.read_parquet(p)["route_km"].to_numpy() for k, p in paths.items()}

    g = RailGraph.load(os.path.join(O, "rail_graph.npz"))
    adj, nodes = g.csr(), D.station_nodes(snap, tags)
    hubs = C.hub_groups(cfg, tags)
    group_of = dict(zip(tags["station_key"], tags["station_group_id"]))
    cache, res = {}, {}

    def used(pairs):
        u = {}
        for df, fc, tc in pairs:
            for f, t in zip(df[fc], df[tc]):
                u.setdefault(f, set()).add(t)
        return u

    dl, di = pd.read_parquet(src["dom_legs"]), pd.read_parquet(src["dom_itins"])
    u = used([(dl, "feed_key", "trip_id"), (di, "leg1_feed", "leg1_trip"), (di, "leg2_feed", "leg2_trip")])
    cum = D._cum_for(cfg, [(cfg.domestic_feed, C.window_days(cfg, cfg.domestic_feed))], tags, adj, nodes, u, cache)
    res["dom_legs"] = D.route_km_direct(dl, cum, hubs, group_of)
    k1, k2 = D.route_km_itins(di, cum, hubs, group_of)
    res["dom_itins"] = k1 + k2

    fl, fi = pd.read_parquet(src["for_legs"]), pd.read_parquet(src["for_itins"])
    rl, ri = np.full(len(fl), np.nan), np.full(len(fi), np.nan)
    for r in F.country_runs(cfg):
        ml, mi = (fl["run"] == r["run"]).to_numpy(), (fi["run"] == r["run"]).to_numpy()
        a, b = fl[ml], fi[mi]
        u = used([(a, "feed_key", "trip_id"), (b, "leg1_feed", "leg1_trip"), (b, "leg2_feed", "leg2_trip")])
        cum = D._cum_for(cfg, [(f, r["days"]) for f in [cfg.domestic_feed] + r["feeds"]], tags, adj, nodes, u, cache)
        if cum is None:
            continue
        if len(a):
            rl[ml] = D.route_km_direct(a, cum, hubs, group_of)
        if len(b):
            k1, k2 = D.route_km_itins(b, cum, hubs, group_of)
            ri[mi] = k1 + k2
    res["for_legs"], res["for_itins"] = rl, ri
    for k, p in paths.items():
        pd.DataFrame({"route_km": res[k]}).to_parquet(p, index=False)
    return res


def journeys(cfg: RunConfig, tags, snap, refresh_route: bool = False):
    """One row per distinct journey x LAU x direction x network x run (see module docstring)."""
    import pandas as pd
    from . import nb03_foreign as F

    O = cfg.out_dir
    rk = _route_cache(cfg, tags, snap, refresh_route)
    lau_of = F.station_lau(tags, cfg)
    country = dict(zip(tags["station_key"], tags["nuts_rg_01_country_id"]))
    sn = snap.set_index("station_key")
    from . import nb02_connections as C0
    hub_lau = C0.hub_city_laus(cfg)          # the whole city of Košice (tags must carry the city units)
    n_dom = None
    parts = []

    # domestic: the ZSR window; Slovak LAUs except the city of Košice
    from . import nb02_connections as C
    n_dom = len(C.window_days(cfg, cfg.domestic_feed))
    dl = pd.read_parquet(f"{O}/domestic/direct_legs.parquet").assign(route_km=rk["dom_legs"])
    dl = dl.assign(journey=dl["feed_key"] + "|" + dl["trip_id"], time_s=dl["ride_s"], wait_s=np.nan,
                   network="domestic_direct", run="SK", headline=True, window_days=n_dom, has_direct=True)
    di = pd.read_parquet(f"{O}/domestic/one_transfer_itins.parquet").assign(route_km=rk["dom_itins"])
    di = di.assign(journey=di["leg1_feed"] + "|" + di["leg1_trip"] + ">" + di["leg2_feed"] + "|" + di["leg2_trip"],
                   time_s=di["total_s"], network="domestic_one_transfer", run="SK", headline=True, window_days=n_dom)
    for x in (dl, di):
        x["lau_gisco_id"] = x["station_key"].map(lau_of)
        x["country"] = x["station_key"].map(country)
        parts.append(x[x["country"].eq("SK") & ~x["lau_gisco_id"].isin(hub_lau)])

    # foreign: per country run, its own window
    runs = {r["run"]: r for r in F.country_runs(cfg)}
    fl = pd.read_parquet(f"{O}/foreign/direct_legs.parquet").assign(route_km=rk["for_legs"])
    fl = fl.assign(journey=fl["feed_key"] + "|" + fl["trip_id"], time_s=fl["ride_s"], wait_s=np.nan,
                   network="foreign_direct", has_direct=True)
    fi = pd.read_parquet(f"{O}/foreign/one_transfer_itins.parquet").assign(route_km=rk["for_itins"])
    fi = fi.assign(journey=fi["leg1_feed"] + "|" + fi["leg1_trip"] + ">" + fi["leg2_feed"] + "|" + fi["leg2_trip"],
                   time_s=fi["total_s"], network="foreign_one_transfer")
    for x in (fl, fi):
        x["headline"] = x["run"].map(lambda r: runs[r]["headline"])
        parts.append(x)

    cols = ["network", "run", "headline", "country", "window_days", "direction", "lau_gisco_id", "station_key",
            "journey", "time_s", "wait_s", "n_days", "mask", "route_km", "has_direct"]
    j = pd.concat([p[cols] for p in parts], ignore_index=True)
    j["rail_km"] = j["station_key"].map(sn["rail_km"])
    j["geo_km"] = j["station_key"].map(sn["geo_km"])
    # one row per journey and LAU: the shortest ride (as 02 / 03 summarise)
    j = j.sort_values("time_s").drop_duplicates(["network", "run", "direction", "lau_gisco_id", "journey"])
    j["time_min"] = j["time_s"] / 60
    j["wait_min"] = j["wait_s"] / 60
    return j.drop(columns=["time_s", "wait_s"]).reset_index(drop=True)


def lau_attributes(cfg: RunConfig, tags, L):
    """Per LAU: name, country, NUTS2 / NUTS3, DEGURBA, population (2025, else 2024), 15+ population."""
    import pandas as pd
    from . import nb03_foreign as F

    pop, year = F.lau_population(L)
    a = L.set_index("GISCO_ID")
    p15 = a["POP_15_64_2025"].fillna(0) + a["POP_65PLUS_2025"].fillna(0)
    p15 = p15.where(p15 > 0)
    out = pd.DataFrame({"lau_name": tags.drop_duplicates("lau_gisco_id").set_index("lau_gisco_id")["lau_name_national"]
                        .reindex(a.index), "country": a["CNTR_CODE"], "nuts2_id": a["NUTS2_ID"],
                        "nuts3_id": a["NUTS3_ID"], "degurba": a["DGURBA"], "population": pop, "pop_year": year,
                        "pop_15plus": p15})
    out.index.name = "lau_gisco_id"
    return out.reset_index()


def lau_table(j, attrs):
    """The metric-spec aggregates per LAU x direction x network x run (§1-4 of the metric definitions)."""
    import pandas as pd
    from . import nb02_connections as C

    g = j.groupby(["network", "run", "headline", "direction", "lau_gisco_id"], sort=False)
    out = g.agg(window_days=("window_days", "first"), n_journeys=("journey", "size"), run_days=("n_days", "sum"),
                time_mean_min=("time_min", "mean"), time_median_min=("time_min", "median"),
                time_min_min=("time_min", "min"), wait_median_min=("wait_min", "median"),
                route_km_mean=("route_km", "mean"), rail_km_mean=("rail_km", "mean"), geo_km_mean=("geo_km", "mean"),
                n_stations=("station_key", "nunique"), has_direct=("has_direct", "max")).reset_index()
    sd = g["mask"].agg(lambda s: C.popcount(np.bitwise_or.reduce([C.str_to_mask(m) for m in s], dtype=object)))
    out["service_days"] = sd.to_numpy()
    out["f_per_day"] = out["run_days"] / out["window_days"]
    out["mean_days_per_journey"] = out["run_days"] / out["n_journeys"]       # R / |I| <= W (spec §4)
    out = out.merge(attrs, on="lau_gisco_id", how="left")
    return out


# ==========================================================================
# Data dictionaries of the 04 outputs (registered with nb01a_feeds.write_meta)
# ==========================================================================

from .nb01a_feeds import SCHEMAS as _SCHEMAS   # noqa: E402

_KEY = {
    "network": ("str", "domestic_direct, domestic_one_transfer, foreign_direct or foreign_one_transfer."),
    "run": ("str", "SK (domestic, ZSR_SK window) or the foreign country run (CZ, HU, AT, PL, UA; PL:PL_IC = sensitivity)."),
    "headline": ("bool", "False only for single-feed sensitivity runs (PL:PL_IC)."),
    "direction": ("str", "inbound (to Košice) or outbound (from Košice)."),
    "lau_gisco_id": ("str", "LAU (abroad: from the national feed's station, 03a)."),
}
_ATTR = {
    "lau_name": ("str", "LAU name (national)."), "country": ("str", "Country of the LAU."),
    "nuts2_id": ("str", "NUTS2 region (UA: oblast)."), "nuts3_id": ("str", "NUTS3 region (empty for UA)."),
    "degurba": ("float", "Degree of urbanisation (1 city, 2 town / suburb, 3 rural)."),
    "population": ("float", "Population: end-2025 where available, else 2024 (UA)."),
    "pop_year": ("int", "Year of that population figure."),
    "pop_15plus": ("float", "Population aged 15+ (15-64 + 65+, end-2025); empty where not available (UA)."),
}
_SLICES = {"all": "every day", "weekday": "Mon-Fri", "weekend": "Sat-Sun",
           **{w: w.capitalize() for w in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]},
           **{f"m{m:02d}": f"month {m}" for m in range(1, 13)},
           "DJF": "Dec-Feb", "MAM": "Mar-May", "JJA": "Jun-Aug", "SON": "Sep-Nov"}
_SCHEMAS.update({
    "explore_journeys": {
        "title": "Distinct journeys per LAU of the four networks (domestic / foreign x direct / one transfer)",
        "produced_by": "notebooks/04a_service_patterns.ipynb (nb04_frame.journeys)",
        "row": "one distinct journey (direct trip, or first + second train) x LAU x direction x run; the shortest ride if it calls at several stations of the LAU",
        "columns": {**{k: _KEY[k] for k in ("network", "run", "headline")},
                    "country": ("str", "Country of the station."),
                    "window_days": ("int", "Days in the run window."), "direction": _KEY["direction"],
                    "lau_gisco_id": _KEY["lau_gisco_id"], "station_key": ("str", "Station of the LAU the journey uses."),
                    "journey": ("str", "feed|trip (direct) or feed|leg1>feed|leg2 (one transfer)."),
                    "n_days": ("int", "Run days in the window (both legs, on one transfer)."),
                    "mask": ("str", "Run dates, '0'/'1' per window day."),
                    "route_km": ("float", "Track km along the stations the train(s) call at (nb04_distance)."),
                    "has_direct": ("bool", "The station / LAU also has a direct train in this direction."),
                    "rail_km": ("float", "Shortest track path Košice - station (01c)."),
                    "geo_km": ("float", "Geodesic Košice - station (01c)."),
                    "time_min": ("float", "Journey time: ride (direct) or first departure to final arrival incl. the wait, minutes."),
                    "wait_min": ("float", "Wait at the transfer station, minutes (empty for direct).")},
    },
    "explore_lau_table": {
        "title": "Per LAU: the metric-definition aggregates of the four networks",
        "produced_by": "notebooks/04a_service_patterns.ipynb (nb04_frame.lau_table)",
        "row": "one LAU x direction x network x run with at least one journey",
        "columns": {**_KEY, "window_days": ("int", "W: days in the window."),
                    "n_journeys": ("int", "|I|: distinct journeys."), "run_days": ("int", "R: their run days summed."),
                    "time_mean_min": ("float", "Mean journey time (spec §1)."),
                    "time_median_min": ("float", "Median journey time."), "time_min_min": ("float", "Shortest journey time."),
                    "wait_median_min": ("float", "Median transfer wait (one transfer)."),
                    "route_km_mean": ("float", "Mean route km over the journeys."),
                    "rail_km_mean": ("float", "Mean shortest-path km of the stations used (spec §2)."),
                    "geo_km_mean": ("float", "Mean geodesic km of the stations used."),
                    "n_stations": ("int", "Stations of the LAU used."),
                    "has_direct": ("bool", "A direct train exists in this direction."),
                    "service_days": ("int", "Days with at least one journey."),
                    "f_per_day": ("float", "f = R / W: journeys per day (spec §4)."),
                    "mean_days_per_journey": ("float", "R / |I|; must be <= W."), **_ATTR},
    },
    "explore_service_patterns": {
        "title": "Journeys per day by weekday, month and season, per LAU (REP-8, CF-20)",
        "produced_by": "notebooks/04a_service_patterns.ipynb (nb04_patterns.lau_patterns)",
        "row": "one LAU x direction x network x run",
        "columns": {**{k: _KEY[k] for k in ("network", "run", "direction", "lau_gisco_id")},
                    **{k: ("float", f"Journeys per day on {v} (run days in the slice / days of the slice in the window; empty if the window has none).")
                       for k, v in _SLICES.items()},
                    "pattern": ("str", "every_day (all seven weekdays served), weekday_only, weekend_only, partial.")},
    },
    "explore_direction_asymmetry": {
        "title": "Inbound against outbound per LAU",
        "produced_by": "notebooks/04a_service_patterns.ipynb",
        "row": "one LAU x network x run",
        "columns": {**{k: _KEY[k] for k in ("network", "run", "lau_gisco_id")},
                    "f_inbound": ("float", "Journeys per day to Košice."), "f_outbound": ("float", "Journeys per day from Košice."),
                    "time_inbound": ("float", "Median journey time inbound, minutes."),
                    "time_outbound": ("float", "Median journey time outbound, minutes."),
                    "f_diff": ("float", "f_inbound - f_outbound."), "time_diff": ("float", "time_inbound - time_outbound."),
                    "population": _ATTR["population"]},
    },
    "explore_route_types": {
        "title": "Services behind the journeys, by GTFS route_type (PIP-9)",
        "produced_by": "notebooks/04a_service_patterns.ipynb",
        "row": "one network x run x route_type (or route_type pair for one transfer)",
        "columns": {"network": _KEY["network"], "run": _KEY["run"],
                    "route_types": ("str", "route_type of the train (direct) or 'first > second' (one transfer); 100 long distance, 102/103 express / interregional, 105 sleeper, 106 regional, 2 rail."),
                    "journeys": ("int", "Distinct journeys (both directions)."), "run_days": ("int", "Their run days."),
                    "seasonal_only": ("float", "Of them, journeys running in one season only; empty where the window does not span all four seasons (PL).")},
    },
    "explore_hierarchy": {
        "title": "Distinct journeys recounted per NUTS3, NUTS2 and country (never summed from LAUs)",
        "produced_by": "notebooks/04a_service_patterns.ipynb (nb04_patterns.recount)",
        "row": "one region x level x direction x network x run",
        "columns": {**{k: _KEY[k] for k in ("network", "run", "direction")},
                    "level": ("str", "nuts3 / nuts2 / country."), "region": ("str", "Region id."),
                    "n_journeys": ("int", "Distinct journeys serving the region."), "run_days": ("int", "Their run days."),
                    "window_days": ("int", "Days in the window."), "n_lau": ("int", "LAUs of the region reached."),
                    "f_per_day": ("float", "Journeys per day for the region.")},
    },
    "explore_detour_summary": {
        "title": "Detour factors per network: route / straight line, shortest path / straight line, route / shortest path",
        "produced_by": "notebooks/04b_distance_time_efficiency.ipynb",
        "row": "one network x ratio",
        "columns": {"network": _KEY["network"],
                    "ratio": ("str", "route_geo, rail_geo (spec §2 delta) or route_rail."),
                    "n": ("int", "Journeys."), **{f"p{v}": ("float", f"{v}th percentile over the journeys.")
                                                   for v in (5, 25, 50, 75, 95)}},
    },
    "explore_route_validation": {
        "title": "Route km between consecutive stations against the distance the feed publishes",
        "produced_by": "notebooks/04b_distance_time_efficiency.ipynb",
        "row": "one consecutive station pair of the sampled trips of one feed",
        "columns": {"feed": ("str", "UKRZ_UA, BAHN_AT or DRAHY_CZ (feeds publishing shape_dist_traveled)."),
                    "a": ("str", "First station."), "b": ("str", "Next station."),
                    "route_km": ("float", "Shortest track distance on the OSM graph (nb04_distance.pair_km)."),
                    "published_km": ("float", "The feed's shape_dist_traveled difference, km (median over the sampled trips)."),
                    "ratio": ("float", "route_km / published_km.")},
    },
    "explore_efficiency_lau": {
        "title": "Journey efficiency per LAU (spec §3, route km), with the network mean and both aggregations",
        "produced_by": "notebooks/04b_distance_time_efficiency.ipynb",
        "row": "one LAU x direction x network x run with mean route km above the cut-off",
        "columns": {**{k: _KEY[k] for k in ("network", "run", "direction", "lau_gisco_id")},
                    "lau_name": _ATTR["lau_name"], "country": _ATTR["country"], "degurba": _ATTR["degurba"],
                    "population": _ATTR["population"], "f_per_day": ("float", "Journeys per day."),
                    "time_mean_min": ("float", "Mean journey time, minutes."),
                    "route_km_mean": ("float", "Mean route km."), "rail_km_mean": ("float", "Mean shortest-path km."),
                    "geo_km_mean": ("float", "Mean straight-line km."),
                    "e_route": ("float", "e = mean time / mean route km, min per km."),
                    "e_rail": ("float", "The same on shortest-path km."), "e_geo": ("float", "The same on straight-line km."),
                    "e_network": ("float", "Trip-weighted network mean of e_route (weights f_per_day)."),
                    "delta": ("float", "e_route - e_network (signed difference)."),
                    "delta_hat": ("float", "e_route / e_network (ratio)."),
                    "e_mean_of_ratios": ("float", "Mean over the journeys of time / route km."),
                    "rom_mor": ("float", "e_route / e_mean_of_ratios."),
                    "n_stations": ("int", "Stations of the LAU used."), "window_days": ("int", "Days in the window.")},
    },
    "explore_efficiency_summary": {
        "title": "Network efficiency: trip-weighted mean and median, by cut-off and by distance",
        "produced_by": "notebooks/04b_distance_time_efficiency.ipynb",
        "row": "one network x direction x cut-off x distance",
        "columns": {"network": _KEY["network"], "direction": _KEY["direction"],
                    "cutoff_km": ("int", "LAUs with mean route km above this are included."),
                    "distance": ("str", "route, rail or geo."), "n_lau": ("int", "LAUs included."),
                    "e_weighted": ("float", "Trip-weighted mean efficiency, min per km."),
                    "e_median": ("float", "Median over the LAUs."),
                    "speed_weighted_kmh": ("float", "60 / e_weighted.")},
    },
    "explore_models_coef": {
        "title": "Coefficients of the 04c models, with HC3 standard errors and 95 % intervals",
        "produced_by": "notebooks/04c_models.ipynb (nb04_models)",
        "row": "one term of one model",
        "columns": {"network": ("str", "Network (or domestic / foreign for the transfer models)."),
                    "family": ("str", "decay, transfer, power, joint or two_part."),
                    "distance": ("str", "route (route km) or rail (shortest-path km)."),
                    "sample": ("str", "Sample or variant: all, pop < 100k, excl. top-5 influential, pooled, matched, "
                                      "country effects (C(country) fixed effects), clustered (SEs clustered by country), "
                                      "spatial lag / spatial error (ML, check on the OLS fit) ..."),
                    "model": ("str", "Model label."), "term": ("str", "Model term (rho / lambda: the spatial parameter)."),
                    "coef": ("float", "Estimate."),
                    "se": ("float", "Standard error: HC3 (OLS), cluster-robust by country (sample 'clustered'), HC1 (logit), "
                                    "ML asymptotic (spatial lag / error)."),
                    "ci_low": ("float", "95 % interval, low."), "ci_high": ("float", "95 % interval, high."),
                    "p": ("float", "p-value.")},
    },
    "explore_models_summary": {
        "title": "Fit statistics and diagnostics of the 04c models",
        "produced_by": "notebooks/04c_models.ipynb (nb04_models)",
        "row": "one model",
        "columns": {"network": ("str", "Network."), "family": ("str", "Model family."), "distance": ("str", "route or rail."),
                    "sample": ("str", "Sample or variant."), "model": ("str", "Model label."), "n": ("int", "Observations (LAUs)."),
                    "r2": ("float", "R²; pseudo-R² (1 - deviance / null deviance) for the two-part logit, ML pseudo-R² for "
                                    "the spatial models. A two-part pseudo-R² near 0 (Košice foreign_one_transfer: 0.048) means "
                                    "that part explains almost nothing; it is never presented as if it did."),
                    "adj_r2": ("float", "Adjusted R² (OLS only)."), "bp_p": ("float", "Breusch-Pagan p (heteroskedasticity)."),
                    "reset_p": ("float", "Ramsey RESET p (nonlinearity); see specification_choice.csv for what follows."),
                    "resid_skew": ("float", "Skew of the residuals (HC3 intervals stay valid; no normal-theory interval is reported)."),
                    "n_influential": ("float", "LAUs with Cook's distance > 4/n (named in influential_observations.csv)."),
                    "max_cooks": ("float", "Largest Cook's distance (no interval exists for it)."),
                    "moran_i": ("float", "Moran's I of the residuals (5 nearest LAUs, row-standardised); the outcome's I and "
                                         "the k sweep are in spatial_diagnostics.csv."),
                    "moran_p": ("float", "Its pseudo p-value (999 permutations; 0.001 is the floor)."),
                    "n_served": ("float", "Served LAUs (two-part logit only; empty for every other family by design)."),
                    "mean_d_time": ("float", "Matched transfer model only (empty elsewhere by design): mean one-transfer "
                                             "minus direct time, minutes."),
                    "median_d_time": ("float", "Matched transfer model only: the median of that difference."),
                    "cov_type": ("str", "Standard errors: HC3, cluster by country (with the number of clusters), HC1 (logit), ML."),
                    "n_removed": ("float", "Observations removed against the full fit (pop < 100k, excl. top-5 influential); "
                                           "0 for full fits. The domestic pop < 100k refit removes one LAU and establishes nothing."),
                    "si_understated": ("object", "True where the residuals are spatially autocorrelated (Moran p < 0.05): "
                                                 "the intervals understate the uncertainty; empty where not tested.")},
    },
    "explore_correlations": {
        "title": "Correlations of log frequency with log distance and log population, with intervals",
        "produced_by": "notebooks/04c_models.ipynb",
        "row": "one network x variable x country (pooled, and within each country for the foreign networks)",
        "columns": {"network": ("str", "Network."), "with": ("str", "rail_km (shortest path) or population."),
                    "country": ("str", "pooled, or the country of a within-country correlation."),
                    "n": ("int", "LAUs."), "pearson_r": ("float", "Pearson r on logs."),
                    "pearson_low": ("float", "Fisher-z 95 % interval, low."), "pearson_high": ("float", "Fisher-z 95 % interval, high."),
                    "pearson_p": ("float", "p-value."), "spearman_rho": ("float", "Spearman rank correlation."),
                    "spearman_low": ("float", "Bootstrap 95 % interval, low."), "spearman_high": ("float", "Bootstrap 95 % interval, high."),
                    "sign_differs_from_pooled": ("object", "Country rows: the within-country Pearson r has the opposite sign "
                                                           "of the pooled one. Pooled rows: the pooled sign differs from the "
                                                           "majority of the within-country signs (Simpson's paradox check). "
                                                           "Empty for the single-country domestic networks.")},
    },
    "explore_country_residuals": {
        "title": "Mean residual of the joint frequency model per country (spec §7)",
        "produced_by": "notebooks/04c_models.ipynb",
        "row": "one network x country",
        "columns": {"network": ("str", "Network."), "country": ("str", "Country."), "n": ("int", "LAUs."),
                    "mean_resid": ("float", "Mean log-scale residual."),
                    "multiplier": ("float", "exp(mean residual): served this many times as often as size and distance predict.")},
    },
    "explore_claims_audit": {
        "title": "Every coefficient the submitted manuscript states, against the computed value (STA-5)",
        "produced_by": "notebooks/04c_models.ipynb",
        "row": "one stated quantity",
        "columns": {"network": ("str", "Network."), "quantity": ("str", "What the manuscript states."),
                    "stated": ("float", "The stated value."),
                    "computed": ("float", "Computed here with the manuscript's definition (shortest-path km, inbound, LAU)."),
                    "ci_low": ("float", "95 % interval, low (where defined)."), "ci_high": ("float", "95 % interval, high."),
                    "within_ci": ("object", "The stated value lies inside the computed interval (empty where no interval)."),
                    "where": ("str", "Section / figure of the submitted manuscript."),
                    "form_basis": ("str", "The specification behind the quantity (whose RESET decides form_rejected); empty "
                                          "for quantities that come from no model (trip-weighted efficiency)."),
                    "form_reset_p": ("float", "RESET p of that specification."),
                    "form_rejected": ("object", "True where that specification is rejected (RESET p < 0.01).")},
    },
    "explore_specification_choice": {
        "title": "Functional form per network and model: RESET of each form, the curvature probe, and the primary form",
        "produced_by": "notebooks/04c_models.ipynb (nb04_models.curvature / choose_form)",
        "row": "one network x family x distance",
        "columns": {"network": ("str", "Network (domestic / foreign for the transfer model)."),
                    "family": ("str", "decay (time ~ km), frequency (f ~ km), joint (f ~ km + population), transfer (pooled)."),
                    "distance": ("str", "route or rail."), "n": ("int", "LAUs."),
                    "reset_linear": ("float", "RESET p of the linear form."),
                    "reset_loglog": ("float", "RESET p of the log-log form (empty where none exists)."),
                    "r2_linear": ("float", "R² of the linear form."), "r2_loglog": ("float", "R² of the log-log form."),
                    "quad_coef": ("float", "Coefficient of km² added to the linear form: + the gradient steepens with "
                                           "distance, - it flattens (a shape probe, not a proposed model)."),
                    "quad_low": ("float", "Its 95 % interval, low (HC3)."), "quad_high": ("float", "Its 95 % interval, high."),
                    "quad_p": ("float", "Its p-value."),
                    "rule": ("str", "The rule that fired (RESET level 0.01)."),
                    "primary_form": ("str", "linear | log-log | linear, caveat (a descriptive average gradient, not a "
                                            "structural parameter).")},
    },
    "explore_influential_observations": {
        "title": "Influential LAUs by name: every LAU with Cook's distance > 4/n in a headline model",
        "produced_by": "notebooks/04c_models.ipynb (nb04_models.influence_table)",
        "row": "one LAU x model",
        "columns": {"network": ("str", "Network."), "family": ("str", "Model family."), "distance": ("str", "route or rail."),
                    "sample": ("str", "The headline sample of the model."), "n": ("int", "Observations of the model."),
                    "lau_gisco_id": ("str", "LAU."), "lau_name": ("str", "LAU name."), "country": ("str", "Country."),
                    "population": ("float", "Population."),
                    "cooks_d": ("float", "Cook's distance (no interval exists for it)."),
                    "fitted": ("float", "Fitted value of the outcome."), "actual": ("float", "Observed value."),
                    "d_intercept": ("float", "Leave-one-out change in the intercept (all LAUs minus without this one)."),
                    "d_slope": ("float", "Leave-one-out change in the distance coefficient."),
                    "above_1": ("bool", "Cook's D > 1: this LAU moves the fit on its own.")},
    },
    "explore_spatial_diagnostics": {
        "title": "Spatial autocorrelation of the outcome and of the residuals, per model, on the LAU KNN graph",
        "produced_by": "notebooks/04c_models.ipynb (nb04_models.moran_pair)",
        "row": "one model",
        "columns": {"network": ("str", "Network."), "family": ("str", "Model family."), "distance": ("str", "route or rail."),
                    "sample": ("str", "Sample or variant."), "n": ("int", "LAUs."),
                    "k": ("int", "Neighbours of the reported graph (5)."),
                    "moran_i_y": ("float", "Moran's I of the outcome."), "moran_p_y": ("float", "Its pseudo p (999 permutations; floor 0.001)."),
                    "moran_i_resid": ("float", "Moran's I of the residuals."), "moran_p_resid": ("float", "Its pseudo p."),
                    "absorbed": ("float", "moran_i_y - moran_i_resid: the spatial structure the covariates absorbed."),
                    "i_resid_min_k": ("float", "Smallest residual I over k = 3, 5, 8, 10."),
                    "i_resid_max_k": ("float", "Largest residual I over k = 3, 5, 8, 10."),
                    "p_resid_max_k": ("float", "Largest residual pseudo p over those k."),
                    "i_y_min_k": ("float", "Smallest outcome I over those k."), "i_y_max_k": ("float", "Largest outcome I over those k.")},
    },
    "explore_coverage_curve": {
        "title": "LAUs and population with at least k journeys per day (CON-8)",
        "produced_by": "notebooks/04a_service_patterns.ipynb (nb04_patterns.coverage_curve)",
        "row": "one threshold x country x direction x network x run",
        "columns": {**{k: _KEY[k] for k in ("network", "run", "direction")}, "country": _ATTR["country"],
                    "min_per_day": ("int", "Threshold k (0 = any journey)."), "n_lau": ("int", "LAUs with f >= k."),
                    "population": ("float", "Their population.")},
    },
})
