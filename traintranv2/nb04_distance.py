"""
Notebook 04b -- route distance: the track distance along the stations a train actually calls at.

Reviewer 1 (register PIP-11, PIP-12, PIP-14): "the geometrically shortest path may not represent the line actually
used by a train". 01c's ``rail_km`` is the shortest path on the track graph from Košice to a station, a lower bound.
Here the distance follows the train:

* ``pair_km``: the shortest track distance between two **consecutive** calls of a trip. Between adjacent stops the
  shortest path is the line the train runs on, so summing them follows the train. Each search is capped at
  ``3 x geodesic + 20 km`` (consecutive stops are close; a cap keeps one search local on a graph of millions of
  nodes). A pair is undefined (NaN) if either station has no usable node (01c ``snap_too_far`` / outside) or the
  two lie in different graph components.
* ``trip_cum_km``: per trip, the cumulative route distance at every call (and the count of undefined pairs so far).
* ``leg_route_km``: a leg's route distance = cumulative distance at its arrival call minus at its departure call;
  NaN if any pair in between is undefined.
"""

from typing import Dict, Tuple

import numpy as np

R_EARTH_KM = 6371.0088


def _geo_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dlmb = p2 - p1, np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R_EARTH_KM * np.arcsin(np.sqrt(a))


def station_nodes(snap, tags) -> Dict[str, Tuple[int, float, float]]:
    """station_key -> (graph node, lat, lon) for stations snapped onto the graph (01c status 'ok' or
    'other_component'; a pair across components is caught by the search itself)."""
    s = snap[snap["status"].isin(["ok", "other_component"]) & snap["node"].notna()]
    pos = tags.set_index("station_key")[["stop_lat", "stop_lon"]].astype(float)
    out = {}
    for k, n in zip(s["station_key"], s["node"].astype(np.int64)):
        if k in pos.index:
            out[k] = (int(n), float(pos.at[k, "stop_lat"]), float(pos.at[k, "stop_lon"]))
    return out


def pair_km(adj, nodes: dict, pairs, cap_factor: float = 3.0, cap_add_km: float = 20.0, cache: dict = None):
    """Shortest track distance (km) for each (station_a, station_b) in ``pairs``; NaN where undefined.

    ``adj``: 01c ``RailGraph.csr()`` (metres). ``cache``: dict reused across calls {(a, b): km}.
    """
    from scipy.sparse.csgraph import dijkstra

    cache = {} if cache is None else cache
    todo = {}
    for a, b in pairs:
        if (a, b) in cache or (b, a) in cache:
            continue
        if a not in nodes or b not in nodes:
            cache[(a, b)] = np.nan
            continue
        todo.setdefault(a, set()).add(b)
    for a, targets in todo.items():
        na, la, oa = nodes[a]
        tg = sorted(targets)
        geo = np.array([_geo_km(la, oa, nodes[b][1], nodes[b][2]) for b in tg])
        limit_m = float((cap_factor * geo.max() + cap_add_km) * 1000)
        d = dijkstra(adj, directed=False, indices=na, limit=limit_m)
        for b in tg:
            v = d[nodes[b][0]]
            cache[(a, b)] = float(v) / 1000 if np.isfinite(v) else np.nan
    return [cache.get((a, b), cache.get((b, a), np.nan)) for a, b in pairs]


def trip_cum_km(st, adj, nodes: dict, cache: dict = None):
    """Per call of every trip: cumulative route km from the trip's first call and the number of undefined pairs
    so far. ``st``: stop_times of 02/03 (trip_id, seq, station_key). Returns st with cum_km, cum_undef."""
    s = st.sort_values(["trip_id", "seq"]).reset_index(drop=True)
    prev = s["station_key"].shift()
    same = s["trip_id"].eq(s["trip_id"].shift())
    pairs = list(zip(prev[same], s.loc[same, "station_key"]))
    km = np.zeros(len(s))
    km[same.to_numpy()] = pair_km(adj, nodes, pairs, cache=cache)
    undef = np.isnan(km)
    km = np.where(undef, 0.0, km)
    s["cum_km"] = km
    s["cum_undef"] = undef.astype(int)
    g = s.groupby("trip_id", sort=False)
    s["cum_km"] = g["cum_km"].cumsum()
    s["cum_undef"] = g["cum_undef"].cumsum()
    return s


def leg_route_km(legs, cum, from_col: str, to_col: str, key: str = "station_key"):
    """Route km of each leg: trip_id + departure (``from_col``) + arrival (``to_col``), matched on the ``key``
    column of ``cum`` -- ``station_key``, or ``group`` (station_group_id) when the leg names the station of
    another feed (a second train at the transfer station).

    The departure call is the trip's call at the from station that comes before the arrival call; with several
    candidates, the pair giving the shortest positive distance (as od_pairs keeps the shortest ride).
    Returns an array aligned with ``legs`` (NaN where a pair in between is undefined or a call is missing).
    """
    import pandas as pd

    c = cum[["trip_id", "seq", key, "cum_km", "cum_undef"]]
    x = legs[["trip_id", from_col, to_col]].reset_index(drop=True)
    x["_i"] = np.arange(len(x))
    a = x.merge(c.rename(columns={key: "_kf"}), left_on=["trip_id", from_col], right_on=["trip_id", "_kf"])
    b = a.merge(c.rename(columns={key: "_kt"}), left_on=["trip_id", to_col], right_on=["trip_id", "_kt"],
                suffixes=("_f", "_t"))
    b = b[b["seq_t"] > b["seq_f"]]
    b = b.assign(km=b["cum_km_t"] - b["cum_km_f"], undef=b["cum_undef_t"] - b["cum_undef_f"])
    b = b.sort_values("km").drop_duplicates("_i")
    km = pd.Series(np.where(b["undef"] > 0, np.nan, b["km"]), index=b["_i"].to_numpy())
    return km.reindex(range(len(legs))).to_numpy()


# ==========================================================================
# Route km for the 02 / 03 outputs
# ==========================================================================

def _cum_for(cfg, feeds_days, tags, adj, nodes, trips_by_feed, cache):
    """Cumulative route km for the used trips of each (feed, window); trip ids prefixed 'feed|'."""
    import pandas as pd
    from . import nb02_connections as C
    parts = []
    for feed, days in feeds_days:
        used = trips_by_feed.get(feed, set())
        if not used:
            continue
        st, _ = C.load_timetable(cfg, feed, tags, days)
        st = st[st["trip_id"].isin(used)]
        c = trip_cum_km(st, adj, nodes, cache=cache)
        c["trip_id"] = feed + "|" + c["trip_id"]
        parts.append(c)
    return pd.concat(parts, ignore_index=True) if parts else None


def _hub_min(frame, cum, hubs, start_col, end_col, which):
    """Route km of legs with one end at the hub: the hub station group giving the shortest positive route
    (a train calling at both hub stations is measured from / to the nearer one, as 02a counts it)."""
    res = []
    for h in sorted(hubs):
        f = frame.assign(_hub=h)
        res.append(leg_route_km(f, cum, "_hub", end_col, key="group") if which == "from_hub"
                   else leg_route_km(f, cum, start_col, "_hub", key="group"))
    out = res[0]
    for r in res[1:]:
        out = np.fmin(out, r)
    return out


def route_km_direct(legs, cum, hubs, group_of: dict):
    """route_km of direct legs (columns feed_key, trip_id, direction, station_key).

    ``group_of``: station_key -> station_group_id from the current station_tags. Stored ``group`` labels are not
    used: a later 01b run can rename a group (its id is the smallest member key), which would break the lookup."""
    f = legs.assign(trip_id=legs["feed_key"] + "|" + legs["trip_id"], group=legs["station_key"].map(group_of))
    out = _hub_min(f, cum, hubs, "group", "group", "from_hub")
    inn = _hub_min(f, cum, hubs, "group", "group", "to_hub")
    return np.where(f["direction"].eq("outbound"), out, inn)


def route_km_itins(it, cum, hubs, group_of: dict):
    """(leg1 km, leg2 km) of one-transfer itineraries (02b / 03b columns); groups from ``group_of`` (see
    route_km_direct)."""
    it = it.assign(group=it["station_key"].map(group_of), T=it["T_key"].map(group_of))
    o = it["direction"].eq("outbound").to_numpy()
    l1 = it.assign(trip_id=it["leg1_feed"] + "|" + it["leg1_trip"])
    l2 = it.assign(trip_id=it["leg2_feed"] + "|" + it["leg2_trip"])
    k1 = np.where(o, _hub_min(l1, cum, hubs, "T", "T", "from_hub"), leg_route_km(l1, cum, "group", "T", key="group"))
    k2 = np.where(o, leg_route_km(l2, cum, "T", "group", key="group"), _hub_min(l2, cum, hubs, "T", "T", "to_hub"))
    return k1, k2


# ==========================================================================
# Validation against the distances the feeds publish (Reviewer 1: "validation against actual scheduled route
# distances")
# ==========================================================================

def published_pairs(cfg, feed: str, tags, max_trips: int = 3000, seed: int = 0):
    """Consecutive station pairs of a sample of trips with the feed's own distance between them.

    Uses stop_times.shape_dist_traveled (UKRZ_UA, BAHN_AT, DRAHY_CZ publish it). Stops are mapped to the 01b
    stations; consecutive calls at one station are merged. Units are not fixed by GTFS: returned raw, the caller
    scales them (metres in these feeds). Returns a frame: a, b (station keys), published.
    """
    import zipfile
    import pandas as pd
    from .nb01a_feeds import feed_zip_path
    from .nb02_connections import station_lookup

    zp = feed_zip_path(cfg, feed)
    with zipfile.ZipFile(zp) as z:
        name = next(n for n in z.namelist() if n.lower().endswith("stop_times.txt"))
        st = pd.read_csv(z.open(name), dtype={"trip_id": str, "stop_id": str},
                         usecols=["trip_id", "stop_id", "stop_sequence", "shape_dist_traveled"])
    trips = st["trip_id"].drop_duplicates().sample(n=min(max_trips, st["trip_id"].nunique()), random_state=seed)
    st = st[st["trip_id"].isin(set(trips)) & st["shape_dist_traveled"].notna()]
    st = st.join(station_lookup(tags, feed), on="stop_id", how="inner").sort_values(["trip_id", "stop_sequence"])
    st = st.drop_duplicates(["trip_id", "station_key"], keep="first")
    st["a"] = st.groupby("trip_id")["station_key"].shift()
    st["d"] = st.groupby("trip_id")["shape_dist_traveled"].diff()
    p = st.dropna(subset=["a", "d"])
    p = p[p["d"] > 0].rename(columns={"station_key": "b", "d": "published"})[["a", "b", "published"]]
    return p.groupby(["a", "b"], as_index=False)["published"].median()
