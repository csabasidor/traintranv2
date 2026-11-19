"""
Notebooks 03a-03d -- connections between the Košice hub and places abroad (CZ, HU, AT, PL, UA).

Builds on the shared engine ``nb02_connections``. Decisions (revision register CON-10, CF-23, PIP-6/8/15/17):

* **First legs from ZSR_SK only.** Every itinerary leaves or reaches Košice on a train of the domestic feed. The
  second leg (the one away from Košice) comes from ZSR_SK or from the destination country's own feed(s).
* **One run per destination country**, on the window shared by ZSR_SK and that country's feeds (``windows.json``):
  CZ 364 days, HU 301, AT 276, UA 364, PL 32 (PL_IC + PL_REG). A country with several feeds also gets a run per
  feed whose own window is longer (PL_IC alone, 101 days) as a sensitivity.
* **Transfers between feeds** happen at a shared ``station_group_id`` (01b); no extra matching.
* **A train in two feeds counts once** (``dedupe_cross_feed``): the same from / to station groups, departure and
  arrival within ``tol_s``, and a common run date. The foreign feed's row is kept.
* **No transfer onto the same train** (``drop_same_train``): a second leg that is the first train itself (same trip,
  or the other feed's copy of it) is not a transfer.
"""

import datetime as dt
import json
import os
from typing import Dict, List, Optional

import numpy as np

from .config import RunConfig
from . import nb02_connections as C


# ==========================================================================
# Runs: destination country -> feeds and window
# ==========================================================================

def _window(cfg: RunConfig, feed: str):
    with open(os.path.join(cfg.out_dir, "windows.json"), encoding="utf-8") as fh:
        w = json.load(fh)[feed]
    return dt.date.fromisoformat(w["start"]), dt.date.fromisoformat(w["end"])


def _days(d0, d1) -> List[dt.date]:
    return [d0 + dt.timedelta(days=k) for k in range((d1 - d0).days + 1)]


def country_runs(cfg: RunConfig, countries: Optional[List[str]] = None) -> List[dict]:
    """One headline run per destination country + one sensitivity run per feed with a longer window.

    Each run: run (id), country, feeds (the country's feeds; ZSR_SK is always added as cfg.domestic_feed),
    days (list of dates), headline (bool).
    """
    countries = countries or [c for c in cfg.search_countries if c != "SK"]
    home = cfg.domestic_feed
    h0, h1 = _window(cfg, home)
    runs = []
    for c in countries:
        feeds = [f for f in cfg.country_feeds.get(c, []) if f in cfg.feeds]
        if not feeds:
            continue
        ws = [(h0, h1)] + [_window(cfg, f) for f in feeds]
        d0, d1 = max(w[0] for w in ws), min(w[1] for w in ws)
        if d1 < d0:
            raise ValueError(f"{c}: the windows of {[home] + feeds} do not overlap")
        runs.append({"run": c, "country": c, "feeds": feeds, "days": _days(d0, d1), "headline": True})
        if len(feeds) > 1:
            for f in feeds:
                f0, f1 = _window(cfg, f)
                e0, e1 = max(h0, f0), min(h1, f1)
                if (e1 - e0) > (d1 - d0):
                    runs.append({"run": f"{c}:{f}", "country": c, "feeds": [f], "days": _days(e0, e1),
                                 "headline": False})
    return runs


def run_window(run: dict) -> dict:
    return {"window_start": str(run["days"][0]), "window_end": str(run["days"][-1]), "window_days": len(run["days"])}


def load_run_timetables(cfg: RunConfig, run: dict, tags) -> Dict[str, tuple]:
    """{feed: (stop_times, trips)} for ZSR_SK and the run's feeds, all on the run's window."""
    out = {}
    for f in [cfg.domestic_feed] + list(run["feeds"]):
        out[f] = C.load_timetable(cfg, f, tags, run["days"])
    return out


# ==========================================================================
# Destinations, populations
# ==========================================================================

def station_country(tags) -> dict:
    return dict(zip(tags["station_key"], tags["nuts_rg_01_country_id"]))


def station_lau(tags, cfg: RunConfig) -> dict:
    """station_key -> LAU. Abroad, the national feed decides: a station of another feed takes the LAU of its
    group's station in the feed of the country it lies in (ZSR_SK's point of Hidasnémeti lies in
    Tornyosnémeti, MÁV's own in Hidasnémeti; likewise Neudorf b.Parndorf, Bruck/Leitha, Petrov u Strážnice)."""
    feed_country = {f: c for c, fs in cfg.country_feeds.items() for f in fs}
    feed_country[cfg.domestic_feed] = "SK"
    own = tags[tags["feed_key"].map(feed_country) == tags["nuts_rg_01_country_id"]]
    grp = own.groupby("station_group_id")["lau_gisco_id"].first()
    out = {}
    for k, g, f, c, l in zip(tags["station_key"], tags["station_group_id"], tags["feed_key"],
                             tags["nuts_rg_01_country_id"], tags["lau_gisco_id"]):
        out[k] = grp[g] if feed_country.get(f) != c and g in grp.index else l
    return out


def lau_population(L):
    """Per LAU: population (2025 where available, else 2024 -- UA has 2024 only) and its year."""
    import pandas as pd
    p25, p24 = L.set_index("GISCO_ID")["POP_2025"], L.set_index("GISCO_ID")["POP_2024"]
    pop = p25.where(p25.notna() & (p25 > 0), p24)
    year = pd.Series(np.where(p25.notna() & (p25 > 0), 2025, 2024), index=p25.index)
    return pop, year


# ==========================================================================
# Legs
# ==========================================================================

def first_legs(tt, hubs: set, direction: str, cfg: RunConfig):
    """Direct ZSR_SK legs between the hub and every station (the first leg of every itinerary)."""
    st, trips = tt[cfg.domestic_feed]
    return C.direct_legs(st, trips, hubs, direction, cfg.domestic_feed)


def second_legs(tt, transfer_groups: set, hubs: set, direction: str, dest_keys: set):
    """Legs between a transfer station group and a destination station, from every feed of the run.

    outbound: T -> X (from_group in transfer_groups, to_key in dest_keys);
    inbound:  X -> T (to_group in transfer_groups, from_key in dest_keys).
    """
    import pandas as pd
    parts = []
    for f, (st, trips) in tt.items():
        if direction == "outbound":
            p = C.od_pairs(st, from_groups=transfer_groups, not_to_groups=hubs)
            p = p[p["to_key"].isin(dest_keys)]
        else:
            p = C.od_pairs(st, to_groups=transfer_groups)
            p = p[p["from_key"].isin(dest_keys) & ~p["from_group"].isin(hubs)]
        if len(p):
            parts.append(C.attach_trips(p, trips, f))
    if not parts:
        return pd.DataFrame(columns=["feed_key", "trip_id", "from_key", "from_group", "dep_s", "to_key", "to_group",
                                     "arr_s", "ride_s", "route_type", "n_days", "mask"])
    return pd.concat(parts, ignore_index=True)


def dedupe_cross_feed(legs, prefer: List[str], tol_s: int = 120):
    """A train present in two feeds counts once (Reviewer 1, PIP-8).

    Two legs of different feeds are the same train if they have the same from_group and to_group, departure and
    arrival each within ``tol_s``, and at least one common run date. The leg of the feed listed first in ``prefer``
    is kept; the dropped leg's run dates are added to it (mask OR). Each dropped leg goes to its closest match.

    Returns (kept legs, duplicates table: dropped feed / trip, kept feed / trip, groups, time differences).
    """
    import pandas as pd

    legs = legs.reset_index(drop=True)
    if legs.empty or legs["feed_key"].nunique() < 2:
        return legs.assign(also_in=""), pd.DataFrame(columns=["drop_feed", "drop_trip", "keep_feed", "keep_trip",
                                                              "from_group", "to_group", "d_dep_s", "d_arr_s"])
    rank = {f: k for k, f in enumerate(prefer)}
    x = legs.assign(_i=legs.index, _r=legs["feed_key"].map(rank).fillna(len(prefer)),
                    _m=legs["mask"].map(C.str_to_mask), _b=legs["dep_s"].astype("int64") // max(tol_s, 1))
    cols = ["_i", "_r", "feed_key", "trip_id", "from_group", "to_group", "dep_s", "arr_s", "_m", "_b"]
    # Candidates only within the departure tolerance: the dropped side is offered in its own time bucket and the
    # two neighbours, so every pair with |dep difference| <= tol_s meets (the exact test follows). One feed pair at
    # a time keeps the join small at large hubs; the result is the same as a full join on (from_group, to_group).
    parts = []
    feeds = list(x["feed_key"].unique())
    for fk in feeds:
        k = x.loc[x["feed_key"] == fk, cols]
        for fd in feeds:
            if fd == fk:
                continue
            d = x.loc[x["feed_key"] == fd, cols]
            if k["_r"].iloc[0] >= d["_r"].iloc[0]:
                continue
            d3 = pd.concat([d.assign(_b=d["_b"] + o) for o in (-1, 0, 1)], ignore_index=True)
            mm = k.merge(d3, on=["from_group", "to_group", "_b"], suffixes=("_k", "_d"))
            mm = mm[((mm["dep_s_k"] - mm["dep_s_d"]).abs() <= tol_s) & ((mm["arr_s_k"] - mm["arr_s_d"]).abs() <= tol_s)]
            if len(mm):
                parts.append(mm)
    m = (pd.concat(parts, ignore_index=True) if parts else
         pd.DataFrame(columns=[c + s for c in cols if c not in ("from_group", "to_group", "_b") for s in ("_k", "_d")]
                      + ["from_group", "to_group", "_b"]))
    if len(m):
        m = m[[bool(a & b) for a, b in zip(m["_m_k"], m["_m_d"])]]
    if m.empty:
        return legs.assign(also_in=""), pd.DataFrame(columns=["drop_feed", "drop_trip", "keep_feed", "keep_trip",
                                                              "from_group", "to_group", "d_dep_s", "d_arr_s"])
    m = m.assign(_cost=(m["dep_s_k"] - m["dep_s_d"]).abs() + (m["arr_s_k"] - m["arr_s_d"]).abs())
    m = m.sort_values(["_cost", "_r_k"]).drop_duplicates("_i_d")
    masks = x.set_index("_i")["_m"].to_dict()
    also = {}
    for k, d in zip(m["_i_k"], m["_i_d"]):
        masks[k] |= masks[d]
        also.setdefault(k, set()).add(legs.at[d, "feed_key"])
    n = len(next(iter(legs["mask"])))
    out = legs.drop(index=list(m["_i_d"])).copy()
    out["mask"] = [C.mask_to_str(masks[i], n) for i in out.index]
    out["n_days"] = [C.popcount(masks[i]) for i in out.index]
    out["also_in"] = [";".join(sorted(also.get(i, ()))) for i in out.index]
    dup = pd.DataFrame({"drop_feed": m["feed_key_d"].to_numpy(), "drop_trip": m["trip_id_d"].to_numpy(),
                        "keep_feed": m["feed_key_k"].to_numpy(), "keep_trip": m["trip_id_k"].to_numpy(),
                        "from_group": m["from_group"].to_numpy(), "to_group": m["to_group"].to_numpy(),
                        "d_dep_s": (m["dep_s_k"] - m["dep_s_d"]).to_numpy(), "d_arr_s": (m["arr_s_k"] - m["arr_s_d"]).to_numpy()})
    return out.reset_index(drop=True), dup


def drop_same_train(it, tt, tol_s: int = 120):
    """Remove 'transfers' onto the train one is already on.

    Same trip in both legs, or the second leg is another feed's copy of the first train: outbound, the first
    train itself leaves T within ``tol_s`` of the second leg; inbound, the second train itself arrives at T within
    ``tol_s`` of the first leg. Returns (kept, number dropped).
    """
    if it.empty:
        return it, 0
    calls = {}
    for f, (st, _) in tt.items():
        s = st[["trip_id", "group", "arr_s", "dep_s"]]
        calls[f] = s.drop_duplicates(["trip_id", "group"]).set_index(["trip_id", "group"])
    same = (it["leg1_feed"] == it["leg2_feed"]) & (it["leg1_trip"] == it["leg2_trip"])
    out = it["direction"].eq("outbound")
    # outbound: does the first train itself depart from T at the second leg's time?
    dep1 = np.full(len(it), np.nan)
    arr2 = np.full(len(it), np.nan)
    for f, c in calls.items():
        k1 = it["leg1_feed"].eq(f) & out
        if k1.any():
            idx = list(zip(it.loc[k1, "leg1_trip"], it.loc[k1, "T"]))
            dep1[k1.to_numpy()] = c["dep_s"].reindex(idx).to_numpy()
        k2 = it["leg2_feed"].eq(f) & ~out
        if k2.any():
            idx = list(zip(it.loc[k2, "leg2_trip"], it.loc[k2, "T"]))
            arr2[k2.to_numpy()] = c["arr_s"].reindex(idx).to_numpy()
    cont_out = out.to_numpy() & (np.abs(dep1 - it["t_dep_s"].to_numpy()) <= tol_s)
    cont_in = (~out).to_numpy() & (np.abs(arr2 - it["t_arr_s"].to_numpy()) <= tol_s)
    drop = same.to_numpy() | cont_out | cont_in
    return it[~drop].reset_index(drop=True), int(drop.sum())


# ==========================================================================
# One country run
# ==========================================================================

def run_one_transfer(cfg: RunConfig, run: dict, tt, tags, hubs: set, mn: Optional[int] = None,
                     mx: Optional[int] = None, transfer_unit: str = "group", rule: Optional[str] = None):
    """One-transfer itineraries between the hub and the run's country, both directions.

    transfer_unit "group": a transfer is at one station group (headline);
                  "lau":   any two stations of one LAU (PIP-17 sensitivity; T becomes the LAU).
    Returns (itineraries, duplicates table, stats dict).
    """
    import pandas as pd

    mn = cfg.min_connect_min if mn is None else mn
    mx = cfg.max_connect_min if mx is None else mx
    rule = rule or cfg.transfer_pairing
    n = len(run["days"])
    ctry = station_country(tags)
    lau_of = station_lau(tags, cfg)
    dest = {k for k, c in ctry.items() if c == run["country"] and k.split(":", 1)[0] in tt}
    prefer = list(run["feeds"]) + [cfg.domestic_feed]
    out, dups, stats = [], [], {}
    for d in ("outbound", "inbound"):
        f1 = first_legs(tt, hubs, d, cfg)
        T = set(f1["group"])
        if transfer_unit == "lau":
            f1 = f1.assign(group=f1["station_key"].map(lau_of))
            group_lau = dict(zip(tags["station_group_id"], tags["lau_gisco_id"]))
            T_lau = set(f1["group"])
            T = {g for g, l in group_lau.items() if l in T_lau}
        s2 = second_legs(tt, T, hubs, d, dest)
        s2, dup = dedupe_cross_feed(s2, prefer)
        dups.append(dup.assign(direction=d))
        stats[d] = {"first_legs": len(f1), "second_legs": len(s2), "duplicates_dropped": len(dup)}
        if transfer_unit == "lau":
            if d == "outbound":
                s2 = s2.assign(from_group=s2["from_key"].map(lau_of))
            else:
                s2 = s2.assign(to_group=s2["to_key"].map(lau_of))
        if d == "outbound":
            it = C.one_transfer(f1, s2, "outbound", mn, mx, n, rule=rule)
        else:
            it = C.one_transfer(s2, f1, "inbound", mn, mx, n, rule=rule)
        out.append(it)
    it = pd.concat(out, ignore_index=True)
    if transfer_unit == "group":
        it, n_same = drop_same_train(it, tt)
    else:
        n_same = 0
    stats["same_train_dropped"] = n_same
    it = it[it["station_key"].map(ctry).eq(run["country"])].copy()
    it["lau_gisco_id"] = it["station_key"].map(lau_of)
    it["country"] = run["country"]
    it["run"] = run["run"]
    return it.reset_index(drop=True), pd.concat(dups, ignore_index=True).assign(run=run["run"]), stats


def run_direct(cfg: RunConfig, run: dict, tt, tags, hubs: set):
    """Direct ZSR_SK trips between the hub and the run's country, both directions."""
    import pandas as pd
    ctry = station_country(tags)
    lau_of = station_lau(tags, cfg)
    legs = pd.concat([first_legs(tt, hubs, d, cfg) for d in ("inbound", "outbound")], ignore_index=True)
    legs = legs[legs["station_key"].map(ctry).eq(run["country"])].copy()
    legs["lau_gisco_id"] = legs["station_key"].map(lau_of)
    legs["country"] = run["country"]
    legs["run"] = run["run"]
    return legs.reset_index(drop=True)


# ==========================================================================
# Data dictionaries of the 03 outputs (registered with nb01a_feeds.write_meta)
# ==========================================================================

from .nb01a_feeds import SCHEMAS as _SCHEMAS                                        # noqa: E402
from .nb02_connections import _COUNTS, _STATION, _TRANSFER, _WINDOW, _DAYTRIP        # noqa: E402

_RUN = {
    "country": ("str", "Destination country (CZ, HU, AT, PL, UA)."),
    "run": ("str", "Run id: the country (headline), or country:feed for a single-feed sensitivity run (PL:PL_IC)."),
}
_POP = {
    "population": ("float", "LAU population: end-2025 where available, else 2024 (UA)."),
    "pop_year": ("int", "Year of that population figure."),
}
_LAU = {"lau_gisco_id": _STATION["lau_gisco_id"], "lau_name_national": _STATION["lau_name_national"],
        "nuts3_id": ("str", "NUTS3 region (empty for UA)."), "degurba": _STATION["degurba"]}
_COV_GROUPS = ("all_lau (every LAU of the country), with_station (LAUs with a station of the run's feeds), direct (a "
               "direct ZSR train), one_transfer (a journey with one change), newly_reached (one transfer and no direct "
               "train), direct_or_one_transfer.")
_SHARES = {"n_lau": ("int", "LAUs in the group."), "population": _POP["population"],
           "share_lau": ("float", "n_lau / n_lau of all_lau."),
           "share_population": ("float", "population / population of all_lau.")}
_SCHEMAS.update({
    "foreign_direct_legs": {
        "title": "Direct ZSR_SK trains between the Košice hub and stations abroad, per destination-country window",
        "produced_by": "notebooks/03a_foreign_direct.ipynb",
        "row": "one trip between the hub and one foreign station, in one direction, in one country run",
        "columns": {**{k: v for k, v in _SCHEMAS["domestic_direct_legs"]["columns"].items()
                       if k not in ("stop_name", "nuts_rg_01_country_id")}, **_RUN, **_WINDOW},
    },
    "foreign_direct_station": {
        "title": "Direct connections to / from Košice per foreign station",
        "produced_by": "notebooks/03a_foreign_direct.ipynb",
        "row": "one foreign station in one direction with at least one direct ZSR trip, in one country run",
        "columns": {**_RUN, **_STATION, **_COUNTS,
                    "rail_km": ("float", "Shortest track distance from the Košice station (01c)."),
                    "geo_km": ("float", "Geodesic distance from the Košice station (01c)."), **_WINDOW},
    },
    "foreign_direct_lau": {
        "title": "Direct connections to / from Košice per foreign LAU",
        "produced_by": "notebooks/03a_foreign_direct.ipynb",
        "row": "one foreign LAU in one direction with at least one direct ZSR trip, in one country run",
        "columns": {**_RUN, **_LAU, **_POP,
                    "n_stations": ("int", "Stations of the LAU with a direct trip in this direction."), **_COUNTS,
                    "journeys_per_day_364": ("float", "The same on ZSR_SK's full window (364 days), for reference."),
                    **_WINDOW},
    },
    "foreign_direct_coverage": {
        "title": "Foreign LAUs and population reached by a direct ZSR train to / from Košice, with denominators",
        "produced_by": "notebooks/03a_foreign_direct.ipynb",
        "row": "one group of LAUs of one country in one direction",
        "columns": {**_RUN, "direction": _COUNTS["direction"],
                    "group": ("str", "all_lau (every LAU of the country), with_station (LAUs with a station of the run's feeds), direct."),
                    **_SHARES, **_WINDOW},
    },
    "foreign_one_transfer_itins": {
        "title": "One-transfer itineraries between the Košice hub and stations abroad (ZSR first leg)",
        "produced_by": "notebooks/03b_foreign_one_transfer.ipynb",
        "row": "one itinerary (ZSR train + ZSR or national train, paired at one transfer station) with the dates both run",
        "columns": {**{k: v for k, v in _SCHEMAS["domestic_one_transfer_itins"]["columns"].items()
                       if k != "nuts_rg_01_country_id"},
                    "lau_gisco_id": ("str", "LAU of the station abroad (from the national feed's station of its group, 03a)."),
                    "has_direct": ("bool", "The station also has a direct ZSR train in this direction."),
                    **_RUN, **_WINDOW},
    },
    "foreign_one_transfer_station": {
        "title": "One-transfer connections to / from Košice per foreign station",
        "produced_by": "notebooks/03b_foreign_one_transfer.ipynb",
        "row": "one foreign station in one direction with at least one one-transfer journey",
        "columns": {**_RUN, **_STATION, "direction": _COUNTS["direction"], **_TRANSFER,
                    "has_direct": ("bool", "The station also has a direct ZSR train in this direction."),
                    "rail_km": ("float", "Shortest track distance from the Košice station (01c)."), **_WINDOW},
    },
    "foreign_one_transfer_lau": {
        "title": "One-transfer connections to / from Košice per foreign LAU, with gateway dependence",
        "produced_by": "notebooks/03b_foreign_one_transfer.ipynb",
        "row": "one foreign LAU in one direction with at least one one-transfer journey",
        "columns": {**_RUN, **_LAU, **_POP, "direction": _COUNTS["direction"], **_TRANSFER,
                    "has_direct": ("bool", "The LAU also has a direct ZSR train in this direction."),
                    "main_hub": ("str", "Transfer station carrying the largest share of the LAU's journeys per day."),
                    "main_hub_share": ("float", "That share."),
                    "hubs_for_90": ("int", "Fewest transfer stations carrying 90 % of the LAU's journeys per day (1 = depends on one gateway)."),
                    **_WINDOW},
    },
    "foreign_one_transfer_hubs": {
        "title": "Transfer stations (gateways) of the foreign one-transfer journeys",
        "produced_by": "notebooks/03b_foreign_one_transfer.ipynb",
        "row": "one transfer station in one direction in one country run",
        "columns": {**_RUN, "direction": _COUNTS["direction"], "T_key": ("str", "Transfer station."),
                    "stop_name": _STATION["stop_name"],
                    "journeys_per_day": ("float", "Journeys per day through it (to / from LAUs of the country)."),
                    "n_lau": ("int", "LAUs reached through it."),
                    "n_lau_only_hub": ("int", "LAUs without a direct train for which it is the only transfer station."),
                    "pop_only_hub": ("float", "Their population."), **_WINDOW},
    },
    "foreign_one_transfer_coverage": {
        "title": "Foreign LAUs and population reached with one transfer, with denominators",
        "produced_by": "notebooks/03b_foreign_one_transfer.ipynb",
        "row": "one group of LAUs of one country in one direction",
        "columns": {**_RUN, "direction": _COUNTS["direction"], "group": ("str", _COV_GROUPS), **_SHARES, **_WINDOW},
    },
    "foreign_one_transfer_sensitivity": {
        "title": "Sensitivity of the foreign one-transfer results: transfer window and city transfers",
        "produced_by": "notebooks/03b_foreign_one_transfer.ipynb",
        "row": "one variant x country run x direction",
        "columns": {**_RUN, "direction": _COUNTS["direction"],
                    "variant": ("str", "window (transfer-window grid, VAL-2) or city_transfer (any two stations of one LAU, PIP-17)."),
                    "min_connect_min": ("int", "Minimum transfer, minutes."),
                    "max_connect_min": ("int", "Maximum transfer, minutes."),
                    "is_base": ("bool", "The headline settings."),
                    "n_lau_one_transfer": ("int", "LAUs with a one-transfer journey."),
                    "n_lau_newly_reached": ("int", "LAUs with a one-transfer journey and no direct train."),
                    "pop_newly_reached": ("float", "Their population."),
                    "journeys_per_day": ("float", "Journeys per day over all LAUs of the country (distinct per LAU, summed)."),
                    "single_hub_share": ("float", "Share of newly reached LAUs depending on one transfer station (hubs_for_90 = 1)."),
                    **_WINDOW},
    },
    "foreign_cross_feed_duplicates": {
        "title": "Trains present in two feeds: the copy dropped and the leg kept (PIP-8)",
        "produced_by": "notebooks/03b_foreign_one_transfer.ipynb",
        "row": "one dropped second leg (station-group pair of one trip) and the leg it duplicates",
        "columns": {**_RUN, "direction": _COUNTS["direction"],
                    "drop_feed": ("str", "Feed of the dropped copy (usually ZSR_SK)."), "drop_trip": ("str", "Its trip_id."),
                    "keep_feed": ("str", "Feed of the kept leg (the destination country's feed)."),
                    "keep_trip": ("str", "Its trip_id."),
                    "from_group": ("str", "Departure station group."), "to_group": ("str", "Arrival station group."),
                    "d_dep_s": ("int", "Departure difference kept - dropped, seconds (|.| <= 120)."),
                    "d_arr_s": ("int", "Arrival difference kept - dropped, seconds (|.| <= 120)."), **_WINDOW},
    },
    "foreign_feed_quality": {
        "title": "Per country run and direction: legs, duplicates and itineraries behind the foreign results (REP-4)",
        "produced_by": "notebooks/03b_foreign_one_transfer.ipynb",
        "row": "one country run x direction",
        "columns": {**_RUN, "direction": _COUNTS["direction"],
                    "first_legs": ("int", "ZSR legs between the hub and a station (first legs)."),
                    "second_legs": ("int", "Second legs (all feeds of the run) after removing cross-feed copies."),
                    "duplicates_dropped": ("int", "Second legs dropped as another feed's copy of the same train."),
                    "same_train_dropped": ("int", "Itineraries dropped as a transfer onto the same train (both directions of the run)."),
                    "itineraries": ("int", "One-transfer itineraries to / from stations of the country."),
                    "itineraries_next_day": ("int", "Of them, connections across midnight (PIP-6)."),
                    "transfer_stations": ("int", "Transfer stations used."),
                    "second_leg_feeds": ("str", "Itineraries by the second train's feed, 'feed: n' joined by '; '."),
                    **_WINDOW},
    },
})


def _foreign_daytrip_schemas(kind: str, nb: str, what: str):
    return {
        f"foreign_daytrip_{kind}_station": {
            "title": f"Same-day visits to Košice from foreign stations ({what})",
            "produced_by": f"notebooks/{nb}",
            "row": "one foreign station with at least one day-trip day, in one country run",
            "columns": {**_RUN, **_STATION, **_DAYTRIP,
                        "rail_km": ("float", "Shortest track distance from Košice (01c)."), **_WINDOW},
        },
        f"foreign_daytrip_{kind}_lau": {
            "title": f"Same-day visits to Košice per foreign LAU ({what})",
            "produced_by": f"notebooks/{nb}",
            "row": "one foreign LAU with at least one day-trip day, in one country run",
            "columns": {**_RUN, **_LAU, **_POP, **_DAYTRIP, **_WINDOW},
        },
        f"foreign_daytrip_{kind}_coverage": {
            "title": f"Foreign LAUs and population with same-day visits to Košice ({what}), with denominators",
            "produced_by": f"notebooks/{nb}",
            "row": "one group of LAUs of one country",
            "columns": {**_RUN,
                        "group": ("str", "all_lau, served (an option in both directions), daytrip_any (>= 1 day), daytrip_50 / daytrip_90 (on >= 50 % / 90 % of the window's days)."),
                        **_SHARES, **_WINDOW},
        },
        f"foreign_daytrip_{kind}_sensitivity": {
            "title": f"Dwell-time sensitivity of foreign same-day visits ({what})",
            "produced_by": f"notebooks/{nb}",
            "row": "one minimum dwell x country run",
            "columns": {**_RUN, "dwell_min": ("int", "Minimum time in Košice, minutes."),
                        "is_base": ("bool", "The configured dwell."),
                        "n_lau_any": ("int", "LAUs with >= 1 day-trip day."), "pop_any": ("float", "Their population."),
                        "n_lau_50": ("int", "LAUs with day trips on >= 50 % of days."), "pop_50": ("float", "Their population."),
                        **_WINDOW},
        },
    }


_SCHEMAS.update(_foreign_daytrip_schemas("direct", "03c_foreign_daytrip_direct.ipynb", "direct"))
_SCHEMAS.update(_foreign_daytrip_schemas("one_transfer", "03d_foreign_daytrip_one_transfer.ipynb", "direct or one-transfer"))
