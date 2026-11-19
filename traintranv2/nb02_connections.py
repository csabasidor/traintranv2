"""
Notebooks 02 / 03 -- connections to and from the Košice hub: the shared engine.

Used by notebooks/02a-02d (domestic) and 03a-03d (foreign). Every function works on one tidy
timetable per feed, on that feed's analysis window (output/kosice/windows.json).

* ``load_timetable``   -- trips running in the window (bus routes and excluded agencies left out, as
                          the 01b catalog does) with a **run-date bitmask** built from calendar.txt and
                          calendar_dates.txt; stop_times mapped onto the 01b stations
                          (``station_key``, ``station_group_id``); times in seconds of the service day,
                          **not wrapped at 24:00**.
* ``od_pairs``         -- for every trip, the station pairs (i before j), restricted to given groups;
                          per trip and pair of groups only the shortest ride is kept.
* ``direct_legs``      -- trips between the hub and every other station, inbound or outbound.
* ``pair_legs`` / ``one_transfer`` -- first and second legs paired at a transfer station (one station
                          group), within [min, max] minutes, on the **dates both legs run** (bitmask AND).
* ``daytrip_days``     -- same-day visits: an inbound and an outbound option on the same date with the
                          dwell / time rules of the config.
* ``summarise``        -- per station / LAU: distinct trips or journeys, per day, service days.

Bitmasks are Python ints, bit k = day k of the window; files store them as '0'/'1' strings (day 0
first), the format of the legacy ``trip_rundates.csv``.
"""

import datetime as dt
import json
import os
import zipfile
from functools import reduce
from typing import Dict, Iterable, List, Optional

import numpy as np

from .config import RunConfig
from .nb01a_feeds import feed_zip_path, read_table, service_rundates_in_window

HUB = "hub"
# Bump when load_timetable's rules change, so cached timetables are rebuilt.
# 2: train pieces joined (join_train_pieces), masks kept as Python ints.
TIMETABLE_VERSION = 2


# ==========================================================================
# Bitmasks and windows
# ==========================================================================

def mask_to_str(m: int, n: int) -> str:
    """'0'/'1' string, day 0 first."""
    return format(m, f"0{n}b")[::-1] if n else ""


def str_to_mask(s: str) -> int:
    return int(s[::-1], 2) if s else 0


def popcount(m: int) -> int:
    return bin(m).count("1")


def window_days(cfg: RunConfig, feed: str) -> List[dt.date]:
    """The feed's analysis window from output/kosice/windows.json (written by 01a)."""
    with open(os.path.join(cfg.out_dir, "windows.json"), encoding="utf-8") as fh:
        w = json.load(fh)[feed]
    d0, d1 = dt.date.fromisoformat(w["start"]), dt.date.fromisoformat(w["end"])
    return [d0 + dt.timedelta(days=k) for k in range((d1 - d0).days + 1)]


# ==========================================================================
# Timetable
# ==========================================================================

def _hms_seconds(s):
    """Vectorised GTFS 'H:MM:SS' -> seconds (hours may exceed 24); NaN where empty."""
    import pandas as pd
    p = s.fillna("").str.strip().str.split(":", expand=True)
    if p.shape[1] < 3:
        p = p.reindex(columns=range(3))
    h, m, sec = (pd.to_numeric(p[k], errors="coerce") for k in range(3))
    return h * 3600 + m * 60 + sec.fillna(0)


def station_lookup(tags, feed: str):
    """{stop_id: (station_key, station_group_id)} for one feed from station_tags."""
    t = tags[tags["feed_key"] == feed][["station_key", "station_group_id", "stop_ids"]].copy()
    t["stop_id"] = t["stop_ids"].astype(str).str.split(";")
    t = t.explode("stop_id")
    return t.set_index("stop_id")[["station_key", "station_group_id"]]


def load_timetable(cfg: RunConfig, feed: str, tags, days: Optional[List[dt.date]] = None,
                   cache: bool = True):
    """(stop_times, trips) of one feed on its window; cached in output/kosice/timetable/.

    stop_times: trip_id, seq (0..), station_key, group, arr_s, dep_s -- consecutive stops of one
                station inside a trip are merged (first arrival, last departure);
    trips:      trip_id, route_id, route_type, agency_id, service_id, n_days, mask (str).
    """
    import pandas as pd
    from .nb01b_stations import _is_bus_route_type

    days = days or window_days(cfg, feed)
    n = len(days)
    tdir = os.path.join(cfg.out_dir, "timetable")
    # one cache per feed AND window: 03 loads ZSR_SK on each destination country's window
    p_st, p_tr = (os.path.join(tdir, f"{feed}_{days[0]}_{days[-1]}_{x}.parquet") for x in ("stop_times", "trips"))
    zp0 = feed_zip_path(cfg, feed)
    # the cache is valid for this window AND this feed file (a replaced snapshot must rebuild it)
    tag = (f"{days[0]}..{days[-1]}|{os.path.basename(zp0)}|{os.path.getsize(zp0)}|{int(os.path.getmtime(zp0))}"
           f"|{TIMETABLE_VERSION}")
    if cache and os.path.exists(p_st) and os.path.exists(p_tr):
        tr = pd.read_parquet(p_tr)
        if len(tr) and tr["window"].iloc[0] == tag:
            return pd.read_parquet(p_st), tr

    zp = feed_zip_path(cfg, feed)
    runs = service_rundates_in_window(list(read_table(zp, "calendar.txt")),
                                      list(read_table(zp, "calendar_dates.txt")), days)
    idx = {d: k for k, d in enumerate(days)}
    svc_mask = {sid: sum(1 << idx[d] for d in ds) for sid, ds in runs.items() if ds}

    routes = pd.DataFrame(list(read_table(zp, "routes.txt")))
    for c in ("agency_id", "route_type"):
        if c not in routes:
            routes[c] = ""
    trips = pd.DataFrame(list(read_table(zp, "trips.txt")))[["trip_id", "route_id", "service_id"]]
    trips = trips.merge(routes[["route_id", "route_type", "agency_id"]], on="route_id", how="left")
    # Python ints, never floats: for a window under 64 days the masks fit in int64, and a service with
    # no day in the window (NaN) would turn the whole column into float
    trips["m"] = pd.Series([svc_mask.get(x, 0) for x in trips["service_id"]], index=trips.index, dtype=object)
    excluded = set((getattr(cfg, "excluded_agencies", {}) or {}).get(feed, []))
    bus = trips["route_type"].map(_is_bus_route_type) if getattr(cfg, "drop_bus_only_stops", False) else False
    keep = (trips["m"] != 0) & ~trips["agency_id"].astype(str).isin(excluded) & ~bus
    trips = trips[keep].copy()
    keep_ids = set(trips["trip_id"])

    look = station_lookup(tags, feed)
    parts = []
    with zipfile.ZipFile(zp) as zf:
        name = next(x for x in zf.namelist() if x.lower().endswith("stop_times.txt"))
        with zf.open(name) as fh:
            for ch in pd.read_csv(fh, dtype=str, chunksize=1_000_000,
                                  usecols=["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"]):
                ch = ch[ch["trip_id"].isin(keep_ids)]
                parts.append(ch)
    st = pd.concat(parts, ignore_index=True)
    st["stop_id"] = st["stop_id"].str.strip()
    st = st.join(look, on="stop_id", how="inner").rename(columns={"station_group_id": "group"})
    st["seq_raw"] = pd.to_numeric(st["stop_sequence"], errors="coerce")
    arr, dep = _hms_seconds(st["arrival_time"]), _hms_seconds(st["departure_time"])
    st["arr_s"], st["dep_s"] = arr.fillna(dep), dep.fillna(arr)
    st = st.dropna(subset=["arr_s", "dep_s", "seq_raw"]).sort_values(["trip_id", "seq_raw"])
    # merge consecutive calls at one station (several stop_ids of one station in a row)
    new = (st["trip_id"] != st["trip_id"].shift()) | (st["station_key"] != st["station_key"].shift())
    st["blk"] = new.cumsum()
    st = (st.groupby("blk", sort=False)
          .agg(trip_id=("trip_id", "first"), station_key=("station_key", "first"), group=("group", "first"),
               arr_s=("arr_s", "first"), dep_s=("dep_s", "last"))
          .reset_index(drop=True))
    st["seq"] = st.groupby("trip_id").cumcount()
    st[["arr_s", "dep_s"]] = st[["arr_s", "dep_s"]].astype("int64")
    st = st[["trip_id", "seq", "station_key", "group", "arr_s", "dep_s"]]

    trips = trips[trips["trip_id"].isin(set(st["trip_id"]))].copy()
    st, trips, n_merged = merge_stay_seated(st, trips, zp)
    if n_merged:
        print(f"  [{feed}] {n_merged} through trains rebuilt from legs joined by stay-seated transfers")
    st, trips, n_joined = join_train_pieces(st, trips, zp)
    if n_joined:
        print(f"  [{feed}] {n_joined} through trains rebuilt from pieces of one train (block_id / train number)")
    trips["n_days"] = trips["m"].map(popcount).astype(int)
    trips["mask"] = trips["m"].map(lambda m: mask_to_str(int(m), n))
    trips["window"] = tag
    trips = trips[["trip_id", "route_id", "route_type", "agency_id", "service_id", "n_days", "mask", "window"]]
    if cache:
        os.makedirs(tdir, exist_ok=True)
        st.to_parquet(p_st, index=False)
        trips.to_parquet(p_tr, index=False)
    return st, trips


def join_train_pieces(st, trips, zip_path: str, max_gap_s: int = 1800, max_passes: int = 8):
    """Join the pieces of one train that a feed publishes as separate trips.

    BAHN_AT cuts every train at region and border points (RJX 167: Zürich -> Buchs, Buchs -> Kufstein,
    Kufstein -> Wien -> Bratislava-Petržalka, Petržalka -> Bratislava hl.st.), linked only by ``block_id``
    and the train number (``trip_short_name``), not by transfers.txt. Trip B continues trip A if
    * they carry the same non-empty train number (``trip_short_name``; ``block_id`` only for a feed without
      train numbers -- a block alone also links a vehicle's turnaround, which is another train),
    * B starts at the station group where A ends, 0 .. ``max_gap_s`` after A arrives there, and
    * they run on a common date.
    On those dates the pair becomes one trip ``A+B`` (the junction keeps A's arrival and B's departure);
    each piece keeps the dates it runs alone. Repeated until no piece continues (chains of several
    pieces). ``trips`` needs the int mask column ``m``. Returns (stop_times, trips, through trains built).
    """
    import pandas as pd

    raw = pd.DataFrame(list(read_table(zip_path, "trips.txt")))
    keys = [c for c in ("trip_short_name", "block_id") if c in raw.columns
            and raw[c].fillna("").astype(str).str.strip().ne("").any()][:1]
    if not keys or raw.empty:
        return st, trips, 0
    ident = raw.set_index("trip_id")[keys].fillna("").astype(str)
    st = st.sort_values(["trip_id", "seq"]).reset_index(drop=True)
    calls = {t: g for t, g in st.groupby("trip_id", sort=False)}
    m = dict(zip(trips["trip_id"], trips["m"]))
    info = {t: tuple(ident.loc[t]) if t in ident.index else ("",) * len(keys) for t in m}
    meta = trips.set_index("trip_id")
    n_built = 0
    for _ in range(max_passes):
        alive = [t for t in m if m[t] and t in calls]
        first = {t: (calls[t]["group"].iat[0], calls[t]["dep_s"].iat[0]) for t in alive}
        last = {t: (calls[t]["group"].iat[-1], calls[t]["arr_s"].iat[-1]) for t in alive}
        cand = []
        for k in range(len(keys)):
            by = {}
            for t in alive:
                v = info[t][k]
                if v:
                    by.setdefault(v, []).append(t)
            for ts in by.values():
                if len(ts) < 2:
                    continue
                for a in ts:
                    ga, ta = last[a]
                    for b in ts:
                        if a == b:
                            continue
                        gb, tb = first[b]
                        if gb == ga and 0 <= tb - ta <= max_gap_s and (m[a] & m[b]):
                            cand.append((tb - ta, a, b))
        if not cand:
            break
        made = False
        for _, a, b in sorted(set(cand)):
            common = m[a] & m[b]
            if not common:
                continue
            ga, gb = calls[a], calls[b].copy()
            gb.iloc[0, gb.columns.get_loc("arr_s")] = ga["arr_s"].iat[-1]
            tid = f"{a}+{b}"
            if tid in calls:
                m[tid] |= common
            else:
                g = pd.concat([ga.iloc[:-1], gb], ignore_index=True).assign(trip_id=tid)
                g["seq"] = range(len(g))
                calls[tid] = g
                m[tid] = common
                info[tid] = info[b]
                n_built += 1
            m[a] &= ~common
            m[b] &= ~common
            made = True
        if not made:
            break
    if not n_built:
        return st, trips, 0
    # rebuild: every trip (original or joined) with the days it still runs
    def _src(t):
        while t not in meta.index:
            t = t.split("+", 1)[0]
        return t
    keep = [t for t in m if m[t]]
    tr = pd.DataFrame([{**meta.loc[_src(t)].to_dict(), "trip_id": t, "m": m[t]} for t in keep])
    tr["m"] = tr["m"].astype(object)
    st = pd.concat([calls[t] for t in keep], ignore_index=True)
    st[["arr_s", "dep_s"]] = st[["arr_s", "dep_s"]].astype("int64")
    return st[["trip_id", "seq", "station_key", "group", "arr_s", "dep_s"]], tr[trips.columns], n_built


def merge_stay_seated(st, trips, zip_path: str):
    """Join the legs of one through train into one trip.

    Some feeds (PolishTrainsGTFS, PKP Intercity) split a train into legs (``…_LEG0``, ``…_LEG1``)
    linked in transfers.txt by a trip-to-trip transfer (``from_trip_id`` / ``to_trip_id``,
    transfer_type 1 or 4): the passenger stays on board. A link is used only if the first leg's last
    station is the second leg's first station. A chain of legs becomes one trip
    ``<leg0>+<leg1>+…`` running on the days all legs run (mask AND); the junction station keeps the
    arrival of the earlier leg and the departure of the later one. A leg keeps any days it runs
    without the others as its own trip. ``trips`` needs the int mask column ``m``.
    Returns (stop_times, trips, number of through trains built).
    """
    import pandas as pd

    links = pd.DataFrame(list(read_table(zip_path, "transfers.txt")))
    need = {"from_trip_id", "to_trip_id", "transfer_type"}
    if links.empty or not need <= set(links.columns):
        return st, trips, 0
    links = links[links["transfer_type"].astype(str).str.strip().isin(["1", "4"])
                  & links["from_trip_id"].fillna("").ne("") & links["to_trip_id"].fillna("").ne("")]
    have = set(trips["trip_id"])
    links = links[links["from_trip_id"].isin(have) & links["to_trip_id"].isin(have)]
    if links.empty:
        return st, trips, 0
    first = st.sort_values("seq").drop_duplicates("trip_id", keep="first").set_index("trip_id")["station_key"]
    last = st.sort_values("seq").drop_duplicates("trip_id", keep="last").set_index("trip_id")["station_key"]
    links = links[links["from_trip_id"].map(last) == links["to_trip_id"].map(first)]
    # unambiguous chains only (one successor, one predecessor)
    links = links.drop_duplicates(["from_trip_id", "to_trip_id"])
    links = links[~links["from_trip_id"].duplicated(keep=False) & ~links["to_trip_id"].duplicated(keep=False)]
    nxt = dict(zip(links["from_trip_id"], links["to_trip_id"]))
    heads = set(nxt) - set(nxt.values())
    if not heads:
        return st, trips, 0

    tm = dict(zip(trips["trip_id"], trips["m"]))
    by_trip = {t: g.sort_values("seq") for t, g in st[st["trip_id"].isin(set(nxt) | set(nxt.values()))].groupby("trip_id")}
    new_st, new_tr, drop = [], [], set()
    trips_ix = trips.set_index("trip_id")
    for h in sorted(heads):
        chain = [h]
        while chain[-1] in nxt and nxt[chain[-1]] not in chain:
            chain.append(nxt[chain[-1]])
        m = reduce(lambda a, b: a & b, (tm[t] for t in chain))
        if not m:
            continue
        tid = "+".join(chain)
        parts = []
        for k, t in enumerate(chain):
            g = by_trip[t].copy()
            if k > 0:                                     # junction: arrival from the earlier leg
                parts[-1] = parts[-1].iloc[:-1]
                g.iloc[0, g.columns.get_loc("arr_s")] = by_trip[chain[k - 1]]["arr_s"].iloc[-1]
            parts.append(g)
        g = pd.concat(parts, ignore_index=True).assign(trip_id=tid)
        g["seq"] = range(len(g))
        new_st.append(g)
        row = trips_ix.loc[h].copy()
        row["m"], row["service_id"] = m, "+".join(str(trips_ix.loc[t, "service_id"]) for t in chain)
        new_tr.append(row.rename(tid))
        for t in chain:                                   # days a leg runs without the others
            tm[t] = tm[t] & ~m
            if not tm[t]:
                drop.add(t)
    if not new_st:
        return st, trips, 0
    trips = trips.assign(m=trips["trip_id"].map(tm).astype(object))
    trips = pd.concat([trips[~trips["trip_id"].isin(drop)],
                       pd.DataFrame(new_tr).rename_axis("trip_id").reset_index()], ignore_index=True)
    st = pd.concat([st[~st["trip_id"].isin(drop)], *new_st], ignore_index=True)
    return st, trips, len(new_st)


# ==========================================================================
# Cities split into district LAUs: one unit each (Košice, Bratislava)
# ==========================================================================

def city_unit_id(name: str) -> str:
    return f"SK_CITY_{name}"


def city_unit_map(cfg: RunConfig, L) -> Dict[str, str]:
    """{district GISCO_ID: unit id} for cfg.city_units (SK LAUs whose national name starts with the prefix)."""
    out = {}
    sk = L[L["CNTR_CODE"].eq("SK")]
    for city, prefix in (getattr(cfg, "city_units", {}) or {}).items():
        ids = sk.loc[sk["LAU_NAME_NATIONAL"].astype(str).str.startswith(prefix), "GISCO_ID"]
        if ids.empty:
            raise ValueError(f"city unit {city}: no SK LAU starts with {prefix!r}")
        out.update({g: city_unit_id(city) for g in ids})
    return out


def lau_with_city_units(L, cfg: RunConfig):
    """The LAU layer with each city's districts merged into one row (populations summed, geometry dissolved;
    DEGURBA, NUTS2 / NUTS3 of the districts, which are uniform); other LAUs unchanged."""
    import geopandas as gpd
    import pandas as pd
    m = city_unit_map(cfg, L)
    d = L[L["GISCO_ID"].isin(m)].copy()
    d["GISCO_ID"] = d["GISCO_ID"].map(m)
    sums = [c for c in L.columns if c.startswith("POP_") and c[4:5].isdigit() or c in ("AREA_KM2",)]
    sums = [c for c in sums if pd.api.types.is_numeric_dtype(L[c])]
    rows = []
    for unit, g in d.groupby("GISCO_ID"):
        for c in ("CNTR_CODE", "DGURBA", "NUTS3_ID", "NUTS2_ID"):
            if g[c].nunique() > 1:
                raise ValueError(f"{unit}: districts differ in {c}")
        r = g.iloc[0].to_dict()
        r.update({c: g[c].sum(min_count=1) for c in sums})
        if "POP_DENS_2024" in r and r.get("AREA_KM2"):
            r["POP_DENS_2024"] = r["POP_2024"] / r["AREA_KM2"]
        name = unit.replace("SK_CITY_", "")
        r.update({"GISCO_ID": unit, "LAU_NAME": name, "LAU_NAME_NATIONAL": name, "LAU_NAME_LATIN": name,
                  "geometry": g.geometry.union_all(),
                  "TERRITORIAL_NOTE": f"city unit of {len(g)} districts (mestské časti)"})
        rows.append(r)
    units = gpd.GeoDataFrame(rows, geometry="geometry", crs=L.crs)
    return pd.concat([L[~L["GISCO_ID"].isin(m)], units], ignore_index=True)


def tags_with_city_units(tags, cfg: RunConfig, L):
    """station_tags with lau_gisco_id / lau_name_national of city districts replaced by the city unit.

    The districts are found from the tags themselves (SK LAU id + the district name), so ``L`` may be the raw LAU layer
    or the one already merged by ``lau_with_city_units`` (it supplies the unit's attributes)."""
    import pandas as pd
    t = tags.copy()
    sk = t["lau_gisco_id"].astype(str).str.startswith("SK_")
    m = {}
    for city, prefix in (getattr(cfg, "city_units", {}) or {}).items():
        sel = sk & t["lau_name_national"].astype(str).str.startswith(prefix)
        m.update({g: city_unit_id(city) for g in t.loc[sel, "lau_gisco_id"]})
    hit = t["lau_gisco_id"].isin(m)
    t.loc[hit, "lau_gisco_id"] = t.loc[hit, "lau_gisco_id"].map(m)
    # the unit's own attributes (population of the whole city, not of one district)
    merged = L["GISCO_ID"].astype(str).str.startswith("SK_CITY_").any()
    U = (L if merged else lau_with_city_units(L, cfg)).set_index("GISCO_ID")
    cols = {"lau_name_national": "LAU_NAME_NATIONAL", "lau_name_latin": "LAU_NAME_LATIN", "lau_pop_2025": "POP_2025",
            "lau_pop_2024": "POP_2024", "lau_pop_15_64_2025": "POP_15_64_2025", "lau_pop_65plus_2025": "POP_65PLUS_2025",
            "lau_area_km2": "AREA_KM2"}
    for tc, lc in cols.items():
        if tc in t.columns and lc in U.columns:
            v = t.loc[hit, "lau_gisco_id"].map(U[lc])
            if not pd.api.types.is_numeric_dtype(t[tc]):       # tags are read as text: keep them text
                v = v.map(lambda x: "" if pd.isna(x) else str(x))
            t.loc[hit, tc] = v.to_numpy()
    return t


def hub_city_laus(cfg: RunConfig) -> set:
    """The hub city's unit: left out of every catchment and denominator."""
    return {city_unit_id(cfg.hub_city)}


def hub_groups(cfg: RunConfig, tags) -> set:
    """station_group_ids of the hub stations (cfg.hub_station_keys)."""
    g = tags.loc[tags["station_key"].isin(cfg.hub_station_keys), "station_group_id"]
    missing = set(cfg.hub_station_keys) - set(tags["station_key"])
    if missing:
        raise ValueError(f"hub stations not in station_tags: {sorted(missing)}")
    return set(g)


# ==========================================================================
# Trips between stations
# ==========================================================================

def od_pairs(st, from_groups: Optional[Iterable] = None, to_groups: Optional[Iterable] = None,
             not_to_groups: Optional[Iterable] = None):
    """Station pairs served by one trip, ``from`` called before ``to``.

    Per trip and (from_group, to_group) only the shortest ride is kept (a trip calling twice at a
    group, or at two hub stations, gives one leg). Columns: trip_id, from_key, from_group, dep_s,
    to_key, to_group, arr_s, ride_s.
    """
    a = st if from_groups is None else st[st["group"].isin(set(from_groups))]
    b = st if to_groups is None else st[st["group"].isin(set(to_groups))]
    if not_to_groups is not None:
        b = b[~b["group"].isin(set(not_to_groups))]
    m = a[["trip_id", "seq", "station_key", "group", "dep_s"]].merge(
        b[["trip_id", "seq", "station_key", "group", "arr_s"]], on="trip_id", suffixes=("_f", "_t"))
    m = m[(m["seq_t"] > m["seq_f"]) & (m["group_f"] != m["group_t"])]
    m = m.rename(columns={"station_key_f": "from_key", "group_f": "from_group",
                          "station_key_t": "to_key", "group_t": "to_group"})
    m["ride_s"] = m["arr_s"] - m["dep_s"]
    m = m[m["ride_s"] >= 0].sort_values("ride_s")
    m = m.drop_duplicates(["trip_id", "from_group", "to_group"])
    return m[["trip_id", "from_key", "from_group", "dep_s", "to_key", "to_group", "arr_s", "ride_s"]].reset_index(drop=True)


def attach_trips(legs, trips, feed: str):
    """Add feed, route_type, n_days and mask (str) from the trips table."""
    t = trips.set_index("trip_id")[["route_type", "n_days", "mask"]]
    out = legs.join(t, on="trip_id")
    out.insert(0, "feed_key", feed)
    return out


def direct_legs(st, trips, hubs: set, direction: str, feed: str):
    """Trips between the hub and every other station: one row per (trip, station).

    outbound: from the hub (its last call before the station) to the station;
    inbound:  from the station to the hub (its first call after the station).
    Columns: feed_key, trip_id, direction, station_key, group, hub_key, dep_s, arr_s, ride_s,
    route_type, n_days, mask.
    """
    if direction == "outbound":
        p = od_pairs(st, from_groups=hubs, not_to_groups=hubs)
        p = p.rename(columns={"to_key": "station_key", "to_group": "group", "from_key": "hub_key"})
    elif direction == "inbound":
        p = od_pairs(st, to_groups=hubs)
        p = p[~p["from_group"].isin(hubs)]
        p = p.rename(columns={"from_key": "station_key", "from_group": "group", "to_key": "hub_key"})
    else:
        raise ValueError(direction)
    p = p.drop_duplicates(["trip_id", "group"])          # one row per trip and station group
    p["direction"] = direction
    p = attach_trips(p, trips, feed)
    return p[["feed_key", "trip_id", "direction", "station_key", "group", "hub_key", "dep_s", "arr_s",
              "ride_s", "route_type", "n_days", "mask"]].reset_index(drop=True)


# ==========================================================================
# One transfer
# ==========================================================================

def pair_legs(arr1, mask1, dep2, mask2, min_s: int, max_s: int, rule: str = "dated"):
    """Pair first legs (arrival at the transfer station) with second legs (departure from it).

    Returns a list of (i, j, dates_mask). Feasible: arr1[i] + min_s <= dep2[j] <= arr1[i] + max_s and
    a common run date. Times are seconds of the service day without wrap, so a connection over
    midnight is only feasible when both legs carry times on the same service-day clock.

    rule "dated": on every date, first leg i takes the earliest second leg j running that date;
                  if a later first leg takes the same (j, date), the earlier one is dropped for that
                  date (it departs earlier and arrives at the same time: dominated).
    rule "legacy": traintran.analysis.feasible_itineraries -- first legs in arrival order, each
                  tries only the first unclaimed second leg in the window; a claim needs a common
                  date, and the attempt ends there either way.
    """
    order2 = np.argsort(np.asarray(dep2), kind="stable")
    d2 = np.asarray(dep2)[order2]
    out = []
    if rule == "legacy":
        used = np.zeros(len(order2), bool)
        for i in np.argsort(np.asarray(arr1), kind="stable"):
            a = arr1[i]
            k = int(np.searchsorted(d2, a + min_s, side="left"))
            while k < len(order2) and d2[k] - a <= max_s:
                if not used[k]:
                    j = int(order2[k])
                    common = mask1[i] & mask2[j]
                    if common:
                        out.append((int(i), j, common))
                        used[k] = True
                    break
                k += 1
        return out
    if rule != "dated":
        raise ValueError(rule)
    claimed: Dict[int, int] = {}
    for i in np.argsort(-np.asarray(arr1), kind="stable"):          # latest first leg first
        a, rem = arr1[i], mask1[i]
        k = int(np.searchsorted(d2, a + min_s, side="left"))
        while rem and k < len(order2) and d2[k] - a <= max_s:
            j = int(order2[k])
            avail = rem & mask2[j]
            if avail:
                take = avail & ~claimed.get(j, 0)
                if take:
                    out.append((int(i), j, take))
                    claimed[j] = claimed.get(j, 0) | take
                rem &= ~avail
            k += 1
    return out


def one_transfer(first, second, direction: str, min_connect_min: int, max_connect_min: int,
                 n_days: int, rule: str = "dated", min_transfer_s: Optional[Dict[str, int]] = None,
                 cross_midnight: bool = True):
    """Itineraries with exactly one transfer, at one station group T.

    outbound: ``first`` = hub -> T legs (direct_legs outbound: group = T), ``second`` = T -> X legs
              (od_pairs + attach_trips: from_group = T);
    inbound:  ``first`` = X -> T legs (od_pairs + attach_trips: to_group = T), ``second`` = T -> hub
              legs (direct_legs inbound: group = T).
    Both frames need feed_key, trip_id, dep_s, arr_s and mask (str).
    Every destination X is kept (also X with a direct train); X is never the hub or T. A "transfer" onto the
    same trip (a train that stops long enough at T) is not one and is dropped.

    cross_midnight (Reviewer 1, PIP-6): a second leg that leaves just after midnight on the NEXT
    service date also connects to a first leg arriving late on date d. Such second legs are added as
    copies dated one day earlier (mask >> 1) with their times + 24 h, so the itinerary stays on the
    first leg's service-day clock (no wrap) and ``next_day`` = True. Only next-date departures pair;
    a 00:20 departure running on day d itself is not mistaken for one (the legacy modulo-24 h error).
    Returns one row per itinerary with dates_mask, n_days and the times of both legs.
    """
    import pandas as pd

    min_transfer_s = min_transfer_s or {}
    if direction == "outbound":
        f = first.rename(columns={"group": "T", "station_key": "T_key", "trip_id": "leg1_trip",
                                  "feed_key": "leg1_feed", "dep_s": "start_s", "arr_s": "t_arr_s"})
        s = second.rename(columns={"from_group": "T", "from_key": "T_key2", "trip_id": "leg2_trip",
                                   "feed_key": "leg2_feed", "dep_s": "t_dep_s", "arr_s": "end_s",
                                   "to_key": "station_key", "to_group": "group"})
        key = "group"
    elif direction == "inbound":
        f = first.rename(columns={"to_group": "T", "to_key": "T_key", "trip_id": "leg1_trip",
                                  "feed_key": "leg1_feed", "dep_s": "start_s", "arr_s": "t_arr_s",
                                  "from_key": "station_key", "from_group": "group"})
        s = second.rename(columns={"group": "T", "station_key": "T_key2", "trip_id": "leg2_trip",
                                   "feed_key": "leg2_feed", "dep_s": "t_dep_s", "arr_s": "end_s"})
        key = "group"
    else:
        raise ValueError(direction)
    f = f.assign(m1=f["mask"].map(str_to_mask))
    s = s.assign(m2=s["mask"].map(str_to_mask), next_day=False).reset_index(drop=True)
    if cross_midnight and len(f) and len(s):
        lim = f["t_arr_s"].max() + max_connect_min * 60
        nx = s[s["t_dep_s"] + 86400 <= lim].copy()
        if len(nx):
            nx[["t_dep_s", "end_s"]] = nx[["t_dep_s", "end_s"]] + 86400
            nx["m2"] = [m >> 1 for m in nx["m2"]]
            nx = nx[[m != 0 for m in nx["m2"]]].assign(next_day=True)
            s = pd.concat([s, nx], ignore_index=True)
    rows = []
    s_by_T = {t: g for t, g in s.groupby("T", sort=False)}
    for T, g1 in f.groupby("T", sort=False):
        g2 = s_by_T.get(T)
        if g2 is None or g1.empty:
            continue
        mn = max(min_connect_min * 60, min_transfer_s.get(T, 0))
        mx = max_connect_min * 60
        # pair per destination X (outbound: X on the second leg; inbound: X on the first leg)
        if direction == "outbound":
            for X, g2x in g2.groupby(key, sort=False):
                for i, j, m in pair_legs(g1["t_arr_s"].to_numpy(), g1["m1"].tolist(),
                                         g2x["t_dep_s"].to_numpy(), g2x["m2"].tolist(), mn, mx, rule):
                    rows.append((g1.index[i], g2x.index[j], m))
        else:
            for X, g1x in g1.groupby(key, sort=False):
                for i, j, m in pair_legs(g1x["t_arr_s"].to_numpy(), g1x["m1"].tolist(),
                                         g2["t_dep_s"].to_numpy(), g2["m2"].tolist(), mn, mx, rule):
                    rows.append((g1x.index[i], g2.index[j], m))
    cols = ["direction", "station_key", "group", "T", "T_key", "leg1_feed", "leg1_trip", "leg2_feed",
            "leg2_trip", "start_s", "t_arr_s", "t_dep_s", "end_s", "ride_s", "wait_s", "total_s",
            "next_day", "n_days", "mask"]
    if not rows:
        return pd.DataFrame(columns=cols)
    i1, i2, ms = zip(*rows)
    a = f.loc[list(i1)].reset_index(drop=True)
    b = s.loc[list(i2)].reset_index(drop=True)
    it = pd.DataFrame({
        "direction": direction,
        "station_key": (b["station_key"] if direction == "outbound" else a["station_key"]).to_numpy(),
        "group": (b["group"] if direction == "outbound" else a["group"]).to_numpy(),
        "T": a["T"].to_numpy(), "T_key": a["T_key"].to_numpy(),
        "leg1_feed": a["leg1_feed"].to_numpy(), "leg1_trip": a["leg1_trip"].to_numpy(),
        "leg2_feed": b["leg2_feed"].to_numpy(), "leg2_trip": b["leg2_trip"].to_numpy(),
        "start_s": a["start_s"].to_numpy(), "t_arr_s": a["t_arr_s"].to_numpy(),
        "t_dep_s": b["t_dep_s"].to_numpy(), "end_s": b["end_s"].to_numpy(),
        "next_day": b["next_day"].to_numpy(),
    })
    it["wait_s"] = it["t_dep_s"] - it["t_arr_s"]
    it["total_s"] = it["end_s"] - it["start_s"]
    it["ride_s"] = it["total_s"] - it["wait_s"]
    it["n_days"] = [popcount(m) for m in ms]
    it["mask"] = [mask_to_str(m, n_days) for m in ms]
    it = it[(it["station_key"] != it["T_key"])]
    # staying on the same train through a long stop is not a transfer
    it = it[~((it["leg1_feed"] == it["leg2_feed"]) & (it["leg1_trip"] == it["leg2_trip"]))]
    return it[cols].reset_index(drop=True)


# ==========================================================================
# Same-day visits
# ==========================================================================

def _hhmm(s: str) -> int:
    h, m = str(s).split(":")[:2]
    return (int(h) * 60 + int(m)) * 60


def daytrip_days(inbound, outbound, cfg: RunConfig, n_days: int, by: str = "station_key",
                 dwell_min: Optional[int] = None):
    """Days on which a same-day visit to the hub is possible, per ``by`` (station or LAU).

    inbound rows: start_s (leave home), end_s (arrive hub), mask;
    outbound rows: start_s (leave hub), end_s (back home), mask.
    A date counts if one inbound option arriving <= cfg.daytrip_max_arrival and one outbound option
    leaving >= cfg.daytrip_min_departure and >= arrival + dwell, back <= cfg.daytrip_max_return,
    both run on that date (service-day clock, no wrap: a 25:10 return is after 23:59).
    Returns by, n_daytrip_days, daytrip_share, mask.
    """
    import pandas as pd

    dwell = (dwell_min if dwell_min is not None else cfg.daytrip_min_dwell_min) * 60
    max_arr, min_dep, max_ret = (_hhmm(cfg.daytrip_max_arrival), _hhmm(cfg.daytrip_min_departure),
                                 _hhmm(cfg.daytrip_max_return))
    ib = inbound[inbound["end_s"] <= max_arr]
    ob = outbound[(outbound["start_s"] >= min_dep) & (outbound["end_s"] <= max_ret)]
    ob_by = {k: g.sort_values("start_s") for k, g in ob.groupby(by, sort=False)}
    rows = []
    for k, gi in ib.groupby(by, sort=False):
        go = ob_by.get(k)
        if go is None:
            continue
        dep = go["start_s"].to_numpy()
        om = [str_to_mask(x) for x in go["mask"]]
        suffix = [0] * (len(om) + 1)                    # OR of outbound masks from position p on
        for p in range(len(om) - 1, -1, -1):
            suffix[p] = suffix[p + 1] | om[p]
        days = 0
        for a, ms in zip(gi["end_s"].to_numpy(), gi["mask"]):
            p = int(np.searchsorted(dep, a + dwell, side="left"))
            days |= str_to_mask(ms) & suffix[p]
        if days:
            rows.append((k, popcount(days), mask_to_str(days, n_days)))
    out = pd.DataFrame(rows, columns=[by, "n_daytrip_days", "mask"])
    out["daytrip_share"] = out["n_daytrip_days"] / n_days
    return out[[by, "n_daytrip_days", "daytrip_share", "mask"]]


# ==========================================================================
# Counting
# ==========================================================================

def summarise(rows, by, journey_cols: List[str], n_days: int, time_cols=("ride_s",)):
    """Per ``by``: distinct journeys, journeys per day, service days, journey time.

    A journey is the distinct combination of ``journey_cols`` (a trip for direct, leg1 + leg2 trip
    for one transfer), so one train calling at several stations of one LAU counts once for the LAU.
    journeys_per_day = sum of the distinct journeys' run days / window days; service_days = days
    with at least one journey (OR of the masks).
    """
    import pandas as pd

    by = [by] if isinstance(by, str) else list(by)
    if rows.empty:
        return pd.DataFrame(columns=by + ["n_journeys", "journeys_per_day", "service_days", "service_share"])
    tcol = list(time_cols)[0]
    u = rows.sort_values(tcol).drop_duplicates(by + journey_cols)
    u = u.assign(_m=u["mask"].map(str_to_mask))
    g = u.groupby(by, sort=False)
    out = g.agg(n_journeys=("n_days", "size"), run_days=("n_days", "sum"),
                min_time_min=(tcol, "min"), median_time_min=(tcol, "median")).reset_index()
    sd = g["_m"].agg(lambda s: popcount(reduce(lambda a, b: a | b, s, 0))).rename("service_days").reset_index()
    out = out.merge(sd, on=by)
    out["journeys_per_day"] = out["run_days"] / n_days
    out["service_share"] = out["service_days"] / n_days
    out[["min_time_min", "median_time_min"]] = (out[["min_time_min", "median_time_min"]] / 60).round(1)
    return out[by + ["n_journeys", "journeys_per_day", "service_days", "service_share",
                     "min_time_min", "median_time_min"]]


def summarise_one_transfer(it, by, n_days: int):
    """Per ``by`` (station / LAU): one-transfer journeys counted four ways (Reviewer 1, PIP-10).

    * n_journeys / journeys_per_day / service_days: distinct complete journeys (leg1 trip + leg2 trip);
    * n_first_legs, n_second_legs: distinct first / second trains behind them (unique departures);
    * n_shared_leg: journeys sharing their first or second train with another journey to the same unit
      (transfer alternatives built on the same physical train);
    * n_hubs: transfer stations used; min / median journey and median wait in minutes.
    """
    import pandas as pd

    by = [by] if isinstance(by, str) else list(by)
    if it.empty:
        return pd.DataFrame(columns=by + ["n_journeys", "journeys_per_day", "service_days", "service_share",
                                          "min_time_min", "median_time_min", "n_first_legs", "n_second_legs",
                                          "n_shared_leg", "n_hubs", "median_wait_min"])
    base = summarise(it, by, ["leg1_trip", "leg2_trip"], n_days, time_cols=("total_s",))
    u = it.sort_values("total_s").drop_duplicates(by + ["leg1_trip", "leg2_trip"])
    c1 = u.groupby(by + ["leg1_trip"])["leg2_trip"].transform("size")
    c2 = u.groupby(by + ["leg2_trip"])["leg1_trip"].transform("size")
    u = u.assign(_shared=(c1 > 1) | (c2 > 1))
    g = u.groupby(by, sort=False)
    extra = g.agg(n_first_legs=("leg1_trip", "nunique"), n_second_legs=("leg2_trip", "nunique"),
                  n_shared_leg=("_shared", "sum"), n_hubs=("T", "nunique"),
                  median_wait_min=("wait_s", "median")).reset_index()
    extra["median_wait_min"] = (extra["median_wait_min"] / 60).round(1)
    return base.merge(extra, on=by)


def hub_dependence(it, unit: str, n_days: int, share: float = 0.9):
    """Frequency-weighted gateway dependence (Reviewer 1, PIP-15).

    Returns (per unit x hub: journeys_per_day, share; per unit: n_hubs, main_hub, main_hub_share,
    hubs_for_share = the fewest hubs carrying ``share`` of the unit's journeys per day).
    """
    import pandas as pd

    u = it.drop_duplicates([unit, "leg1_trip", "leg2_trip"])
    per = (u.groupby([unit, "T"]).agg(T_key=("T_key", "first"), run_days=("n_days", "sum")).reset_index())
    per["journeys_per_day"] = per["run_days"] / n_days
    per["share"] = per["journeys_per_day"] / per.groupby(unit)["journeys_per_day"].transform("sum")
    per = per.sort_values([unit, "share"], ascending=[True, False])
    per["cum"] = per.groupby(unit)["share"].cumsum()
    need = (per[per["cum"] - per["share"] < share - 1e-9].groupby(unit).size().rename("hubs_for_share"))
    top = per.drop_duplicates(unit).set_index(unit)
    summ = pd.DataFrame({"n_hubs": per.groupby(unit).size(), "main_hub": top["T_key"],
                         "main_hub_share": top["share"].round(3), "hubs_for_share": need,
                         "journeys_per_day": per.groupby(unit)["journeys_per_day"].sum()}).reset_index()
    per["share"] = per["share"].round(3)
    return per.drop(columns=["cum", "run_days"]), summ


def fmt_s(s) -> str:
    """Seconds of the service day -> 'HH:MM' (hours may exceed 24)."""
    s = int(s)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"


# ==========================================================================
# Data dictionaries of the 02 / 03 outputs (registered with nb01a_feeds.write_meta)
# ==========================================================================

from .nb01a_feeds import SCHEMAS as _SCHEMAS   # noqa: E402

_WINDOW = {
    "window_start": ("str", "First day of the analysis window (ISO date)."),
    "window_end": ("str", "Last day of the window."),
    "window_days": ("int", "Days in the window; per-day figures divide by this."),
}
_COUNTS = {
    "direction": ("str", "inbound (to the Košice hub) or outbound (from it); computed separately from the timetable, never mirrored."),
    "n_journeys": ("int", "Distinct trips (direct) serving the unit in this direction; a train calling at several stations of one LAU counts once for the LAU."),
    "journeys_per_day": ("float", "Sum of those trips' run days in the window / window_days: average trains per day."),
    "service_days": ("int", "Days of the window with at least one such trip."),
    "service_share": ("float", "service_days / window_days."),
    "min_time_min": ("float", "Shortest ride between the hub and the unit, minutes."),
    "median_time_min": ("float", "Median ride over the distinct trips, minutes."),
}
_STATION = {
    "station_key": ("str", "Station (01b catalog)."),
    "stop_name": ("str", "Station name."),
    "lau_gisco_id": ("str", "LAU of the station (01b)."),
    "lau_name_national": ("str", "LAU name."),
    "nuts3_id": ("str", "NUTS3 region."),
    "degurba": ("str", "Degree of urbanisation of the LAU (1 city, 2 town / suburb, 3 rural)."),
}
_SCHEMAS.update({
    "domestic_direct_legs": {
        "title": "Direct trains between the Košice hub and every station of the domestic feed (both directions)",
        "produced_by": "notebooks/02a_domestic_direct.ipynb",
        "row": "one trip between the hub and one station, in one direction (the trip's shortest hub - station ride)",
        "columns": {
            "feed_key": ("str", "Feed of the trip (ZSR_SK)."),
            "trip_id": ("str", "GTFS trip_id."),
            "direction": _COUNTS["direction"],
            "station_key": _STATION["station_key"],
            "group": ("str", "station_group_id of the station (01b)."),
            "hub_key": ("str", "Hub station of the trip: the last hub call before the station (outbound) or the first after it (inbound)."),
            "dep_s": ("int", "Departure, seconds of the service day (hub outbound, station inbound); not wrapped at 24:00."),
            "arr_s": ("int", "Arrival, seconds of the service day (station outbound, hub inbound)."),
            "ride_s": ("int", "arr_s - dep_s, seconds."),
            "route_type": ("str", "GTFS route_type of the trip (extended types: 100 long distance, 102 / 103 express / interregional, 105 sleeper, 106 regional)."),
            "n_days": ("int", "Days of the window the trip runs (calendar + calendar_dates)."),
            "mask": ("str", "Run dates as '0'/'1' per window day, day 0 first."),
            "stop_name": _STATION["stop_name"],
            "nuts_rg_01_country_id": ("str", "Country of the station's LAU (domestic analysis = SK; other countries are in 03a)."),
            "lau_gisco_id": _STATION["lau_gisco_id"],
        },
    },
    "domestic_direct_station": {
        "title": "Direct connections to / from Košice per Slovak station",
        "produced_by": "notebooks/02a_domestic_direct.ipynb",
        "row": "one Slovak station in one direction, with at least one direct trip",
        "columns": {**_STATION, **_COUNTS, "rail_km": ("float", "Shortest track distance from the Košice station (01c)."),
                    "geo_km": ("float", "Geodesic distance from the Košice station (01c)."), **_WINDOW},
    },
    "domestic_direct_lau": {
        "title": "Direct connections to / from Košice per Slovak LAU",
        "produced_by": "notebooks/02a_domestic_direct.ipynb",
        "row": "one Slovak LAU in one direction with at least one direct trip at any of its stations",
        "columns": {
            "lau_gisco_id": _STATION["lau_gisco_id"], "lau_name_national": _STATION["lau_name_national"],
            "nuts3_id": _STATION["nuts3_id"], "degurba": _STATION["degurba"],
            "lau_pop_2025": ("float", "LAU population end-2025 (00_b5)."),
            "n_stations": ("int", "Stations of the LAU with a direct trip in this direction."),
            **_COUNTS, **_WINDOW},
    },
    "domestic_direct_coverage": {
        "title": "Slovak LAUs and population reached by a direct train to / from Košice, with denominators",
        "produced_by": "notebooks/02a_domestic_direct.ipynb",
        "row": "one group of LAUs (all, with a station, served directly) in one direction",
        "columns": {
            "direction": _COUNTS["direction"],
            "group": ("str", "all_lau (every Slovak LAU except the hub's), with_station (LAUs with a station of the domestic catalog), direct (LAUs with a direct trip)."),
            "n_lau": ("int", "LAUs in the group."),
            "population": ("float", "Their population end-2025."),
            "share_lau": ("float", "n_lau / n_lau of all_lau."),
            "share_population": ("float", "population / population of all_lau."),
            **_WINDOW},
    },
})

_TRANSFER = {
    "n_journeys": ("int", "Distinct one-transfer journeys (first train + second train) serving the unit in this direction; a pair calling at several stations of one LAU counts once for the LAU."),
    "journeys_per_day": ("float", "Sum of those journeys' run days / window_days."),
    "service_days": ("int", "Days with at least one such journey."),
    "service_share": ("float", "service_days / window_days."),
    "min_time_min": ("float", "Shortest door-to-door time (first departure to final arrival, incl. the wait), minutes."),
    "median_time_min": ("float", "Median journey time over the distinct journeys, minutes."),
    "n_first_legs": ("int", "Distinct first trains behind the journeys (inbound: departures from the unit; outbound: departures from the hub)."),
    "n_second_legs": ("int", "Distinct second trains behind the journeys."),
    "n_shared_leg": ("int", "Journeys sharing their first or second train with another journey to the same unit (transfer alternatives on one physical train)."),
    "n_hubs": ("int", "Transfer stations used."),
    "median_wait_min": ("float", "Median wait at the transfer station, minutes."),
}
_SCHEMAS.update({
    "domestic_one_transfer_itins": {
        "title": "One-transfer itineraries between the Košice hub and every station of the domestic feed",
        "produced_by": "notebooks/02b_domestic_one_transfer.ipynb",
        "row": "one itinerary (first train + second train, paired at one transfer station) with the dates both run",
        "columns": {
            "direction": _COUNTS["direction"],
            "station_key": ("str", "Origin (inbound) or destination (outbound) station."),
            "group": ("str", "Its station_group_id."),
            "T": ("str", "station_group_id of the transfer station."),
            "T_key": ("str", "Transfer station."),
            "leg1_feed": ("str", "Feed of the first train."), "leg1_trip": ("str", "trip_id of the first train."),
            "leg2_feed": ("str", "Feed of the second train."), "leg2_trip": ("str", "trip_id of the second train."),
            "start_s": ("int", "Departure of the first train (seconds of the service day, no wrap)."),
            "t_arr_s": ("int", "Arrival at the transfer station."), "t_dep_s": ("int", "Departure from it."),
            "end_s": ("int", "Arrival of the second train."),
            "ride_s": ("int", "Time on board (total - wait), seconds."), "wait_s": ("int", "Wait at the transfer station, seconds."),
            "next_day": ("bool", "True if the second train leaves after midnight on the next service date (times then run past 24:00 on the first train's clock; PIP-6)."),
            "total_s": ("int", "end_s - start_s, seconds."),
            "n_days": ("int", "Days both trains run (bitmask AND)."), "mask": ("str", "Those days, '0'/'1' per window day."),
            "has_direct": ("bool", "True if the station also has a direct train in this direction (02a)."),
            "nuts_rg_01_country_id": ("str", "Country of the station."),
            "lau_gisco_id": ("str", "LAU of the station."),
        },
    },
    "domestic_one_transfer_station": {
        "title": "One-transfer connections to / from Košice per Slovak station",
        "produced_by": "notebooks/02b_domestic_one_transfer.ipynb",
        "row": "one Slovak station in one direction with at least one one-transfer journey",
        "columns": {**_STATION, "direction": _COUNTS["direction"], **_TRANSFER,
                    "has_direct": ("bool", "The station also has a direct train in this direction."),
                    "rail_km": ("float", "Shortest track distance from the Košice station (01c)."), **_WINDOW},
    },
    "domestic_one_transfer_lau": {
        "title": "One-transfer connections to / from Košice per Slovak LAU, with hub dependence",
        "produced_by": "notebooks/02b_domestic_one_transfer.ipynb",
        "row": "one Slovak LAU in one direction with at least one one-transfer journey",
        "columns": {"lau_gisco_id": _STATION["lau_gisco_id"], "lau_name_national": _STATION["lau_name_national"],
                    "nuts3_id": _STATION["nuts3_id"], "degurba": _STATION["degurba"],
                    "lau_pop_2025": ("float", "LAU population end-2025 (00_b5)."),
                    "direction": _COUNTS["direction"], **_TRANSFER,
                    "has_direct": ("bool", "The LAU also has a direct train in this direction."),
                    "main_hub": ("str", "Transfer station carrying most of the LAU's journeys per day."),
                    "main_hub_share": ("float", "Its share of the LAU's journeys per day."),
                    "hubs_for_90": ("int", "Fewest transfer stations carrying 90 % of the LAU's journeys per day (1 = one hub carries 90 %)."),
                    **_WINDOW},
    },
    "domestic_one_transfer_hubs": {
        "title": "Transfer hubs of the domestic one-transfer network: volume and exclusive catchment",
        "produced_by": "notebooks/02b_domestic_one_transfer.ipynb",
        "row": "one transfer station in one direction",
        "columns": {"direction": _COUNTS["direction"], "T_key": ("str", "Transfer station."),
                    "stop_name": _STATION["stop_name"],
                    "journeys_per_day": ("float", "One-transfer journeys per day through it (Slovak LAUs)."),
                    "n_lau": ("int", "Slovak LAUs reached through it."),
                    "n_lau_only_hub": ("int", "LAUs without a direct train for which it is the only transfer station."),
                    "pop_only_hub": ("float", "Their population end-2025."), **_WINDOW},
    },
    "domestic_one_transfer_coverage": {
        "title": "Slovak LAUs and population reached directly and with one transfer, with denominators",
        "produced_by": "notebooks/02b_domestic_one_transfer.ipynb",
        "row": "one group of LAUs in one direction",
        "columns": {"direction": _COUNTS["direction"],
                    "group": ("str", "all_lau (all Slovak LAUs except the hub's), with_station, direct, one_transfer (any one-transfer journey), newly_reached (one transfer, no direct train), direct_or_one_transfer."),
                    "n_lau": ("int", "LAUs in the group."), "population": ("float", "Population end-2025."),
                    "share_lau": ("float", "n_lau / all_lau."), "share_population": ("float", "population / all_lau."),
                    **_WINDOW},
    },
    "domestic_one_transfer_sensitivity": {
        "title": "Transfer-window sensitivity of the domestic one-transfer network (Reviewer 1, VAL-2)",
        "produced_by": "notebooks/02b_domestic_one_transfer.ipynb",
        "row": "one (min, max) transfer window in one direction",
        "columns": {"direction": _COUNTS["direction"],
                    "min_connect_min": ("int", "Shortest allowed wait, minutes."), "max_connect_min": ("int", "Longest allowed wait, minutes."),
                    "is_base": ("bool", "The configuration of the main results."),
                    "n_lau_newly_reached": ("int", "LAUs reached with one transfer and no direct train."),
                    "pop_newly_reached": ("float", "Their population end-2025."),
                    "journeys_per_day_median": ("float", "Median journeys per day over those LAUs."),
                    "median_time_min": ("float", "Median of the LAUs' median journey time, minutes."),
                    "single_hub_share": ("float", "Share of those LAUs where one hub carries >= 90 % of the journeys."),
                    **_WINDOW},
    },
})

_DAYTRIP = {
    "n_daytrip_days": ("int", "Days of the window on which a same-day visit to Košice is possible (rule in the notebook / config)."),
    "daytrip_share": ("float", "n_daytrip_days / window_days."),
}


def _daytrip_schemas(kind: str, nb: str, what: str):
    return {
        f"domestic_daytrip_{kind}_station": {
            "title": f"Same-day visits to Košice by {what} trains, per Slovak station",
            "produced_by": f"notebooks/{nb}",
            "row": "one Slovak station with at least one day-trip day",
            "columns": {**_STATION, **_DAYTRIP, "rail_km": ("float", "Shortest track distance from the Košice station (01c)."), **_WINDOW},
        },
        f"domestic_daytrip_{kind}_lau": {
            "title": f"Same-day visits to Košice by {what} trains, per Slovak LAU",
            "produced_by": f"notebooks/{nb}",
            "row": "one Slovak LAU with at least one day-trip day (going out from and coming back to any of its stations)",
            "columns": {"lau_gisco_id": _STATION["lau_gisco_id"], "lau_name_national": _STATION["lau_name_national"],
                        "nuts3_id": _STATION["nuts3_id"], "degurba": _STATION["degurba"],
                        "lau_pop_2025": ("float", "LAU population end-2025 (00_b5)."), **_DAYTRIP, **_WINDOW},
        },
        f"domestic_daytrip_{kind}_coverage": {
            "title": f"Slovak LAUs and population with a same-day visit to Košice by {what} trains, with denominators",
            "produced_by": f"notebooks/{nb}",
            "row": "one group of LAUs",
            "columns": {"group": ("str", "all_lau (except the hub's), served (a train both ways), daytrip_any (>= 1 day), daytrip_50 (>= 50 % of days), daytrip_90 (>= 90 % of days)."),
                        "n_lau": ("int", "LAUs in the group."), "population": ("float", "Population end-2025."),
                        "share_lau": ("float", "n_lau / all_lau."), "share_population": ("float", "population / all_lau."),
                        **_WINDOW},
        },
        f"domestic_daytrip_{kind}_sensitivity": {
            "title": f"Dwell-time sensitivity of same-day visits by {what} trains (Reviewer 1, VAL-3)",
            "produced_by": f"notebooks/{nb}",
            "row": "one minimum dwell in Košice",
            "columns": {"dwell_min": ("int", "Minimum time in Košice between arrival and return departure, minutes."),
                        "is_base": ("bool", "The configuration of the main results."),
                        "n_lau_any": ("int", "LAUs with >= 1 day-trip day."), "pop_any": ("float", "Their population."),
                        "n_lau_50": ("int", "LAUs with day trips on >= 50 % of days."), "pop_50": ("float", "Their population."),
                        **_WINDOW},
        },
    }


_SCHEMAS.update(_daytrip_schemas("direct", "02c_domestic_daytrip_direct.ipynb", "direct"))
_SCHEMAS.update(_daytrip_schemas("one_transfer", "02d_domestic_daytrip_one_transfer.ipynb", "direct or one-transfer"))
