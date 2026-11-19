"""
Notebook 04e -- feed completeness (Reviewer 1: "the differences observed between countries may partly reflect data
availability and feed harmonisation … its effect is not quantified"; register REP-4, CON-10, VAL-4).

* ``feed_table``      -- per feed: agencies, routes, trips, stops, catalog stations, service span, analysis window,
                         calendar_dates exceptions (added / removed), route types.
* ``feed_effect``     -- per destination country: LAUs and population reached with one transfer using ZSR_SK alone
                         against ZSR_SK + the country's own feed(s). The difference is the measured contribution of the
                         national feed, i.e. how much of a country's figure depends on data availability.
* ``dedup_radius``    -- for the feeds without parent stations, station counts when same-name stops are merged within
                         0.5 / 1 / 2 / 5 km (01b's rule uses 2 km), and the merges that change (VAL-4).
"""

import json
import os
import zipfile

import numpy as np

from .config import RunConfig


def feed_table(cfg: RunConfig, tags):
    """One row per feed of the run."""
    import pandas as pd
    from .nb01a_feeds import feed_zip_path

    with open(os.path.join(cfg.out_dir, "windows.json"), encoding="utf-8") as fh:
        win = json.load(fh)
    rows = []
    for f in cfg.feeds:
        zp = feed_zip_path(cfg, f)
        with zipfile.ZipFile(zp) as z:
            names = {n.lower(): n for n in z.namelist()}
            rd = lambda n, **k: pd.read_csv(z.open(names[n]), dtype=str, **k) if n in names else pd.DataFrame()
            ag, ro, tr = rd("agency.txt"), rd("routes.txt"), rd("trips.txt", usecols=["trip_id"])
            stp = rd("stops.txt", usecols=["stop_id"])
            cd = rd("calendar_dates.txt")
        ex = cd["exception_type"].value_counts().to_dict() if "exception_type" in cd else {}
        w = win.get(f, {})
        rows.append({"feed_key": f, "file": os.path.basename(zp), "bytes": os.path.getsize(zp),
                     "agencies": len(ag), "routes": len(ro), "trips": len(tr), "stops": len(stp),
                     "stations": int((tags["feed_key"] == f).sum()),
                     "route_types": ";".join(sorted(ro["route_type"].dropna().unique())) if "route_type" in ro else "",
                     "calendar_dates_added": int(ex.get("1", 0)), "calendar_dates_removed": int(ex.get("2", 0)),
                     "service_start": w.get("calendar_start"), "service_end": w.get("calendar_end"),
                     "window_start": w.get("start"), "window_end": w.get("end"), "window_days": w.get("days"),
                     "role": w.get("role")})
    return pd.DataFrame(rows)


def feed_effect(cfg: RunConfig, tags, hubs, lau_pop):
    """LAUs and population reached with one transfer (inbound), ZSR_SK alone against the headline feeds.

    ``lau_pop``: GISCO_ID -> population. Headline runs only; the same window for both variants.
    """
    import pandas as pd
    from . import nb03_foreign as F

    rows = []
    for r in F.country_runs(cfg):
        if not r["headline"]:
            continue
        tt = F.load_run_timetables(cfg, r, tags)
        alone = dict(r, feeds=[])
        tt_alone = {cfg.domestic_feed: tt[cfg.domestic_feed]}
        for variant, run, t in (("ZSR_SK alone", alone, tt_alone), ("ZSR_SK + national feed", r, tt)):
            it, _, _ = F.run_one_transfer(cfg, run, t, tags, hubs)
            d = F.run_direct(cfg, run, t, tags, hubs)
            for direction in ("inbound", "outbound"):
                ol = set(it.loc[it.direction == direction, "lau_gisco_id"])
                dl = set(d.loc[d.direction == direction, "lau_gisco_id"])
                both = ol | dl
                rows.append({"country": r["country"], "variant": variant, "direction": direction,
                             "n_lau": len(both), "population": float(pd.Series(list(both)).map(lau_pop).sum()),
                             "n_lau_newly_reached": len(ol - dl),
                             "window_days": len(r["days"])})
    out = pd.DataFrame(rows)
    base = out[out.variant == "ZSR_SK alone"].set_index(["country", "direction"])
    k = list(zip(out["country"], out["direction"]))
    out["added_lau"] = out["n_lau"] - base["n_lau"].reindex(k).to_numpy()
    out["added_population"] = out["population"] - base["population"].reindex(k).to_numpy()
    return out


def dedup_radius(cfg: RunConfig, feeds=("ZSR_SK", "MAV_HU", "UKRZ_UA"), radii=(0.5, 1.0, 2.0, 5.0)):
    """Stations formed by 01b's same-name rule (``name_dedup``) at several radii, for feeds without parents."""
    import pandas as pd
    from .nb01a_feeds import feed_zip_path, read_table
    from .nb01b_stations import BOARDING_TYPES, name_dedup

    rows, changes = [], []
    for f in feeds:
        stops = [s for s in read_table(feed_zip_path(cfg, f), "stops.txt")
                 if (s.get("location_type") or "").strip() in BOARDING_TYPES and not (s.get("parent_station") or "").strip()]
        base = {tuple(sorted(x["stop_id"] for x in g)) for g in name_dedup(stops, km=2.0)}
        for km in radii:
            groups = name_dedup(stops, km=km)
            rows.append({"feed_key": f, "radius_km": km, "stops": len(stops), "stations": len(groups),
                         "merged_groups": sum(len(g) > 1 for g in groups)})
            cur = {tuple(sorted(x["stop_id"] for x in g)) for g in groups}
            for g in cur - base:
                names = sorted({x.get("stop_name", "") for x in stops if x["stop_id"] in g})
                changes.append({"feed_key": f, "radius_km": km, "stop_ids": ";".join(g), "names": "; ".join(names)})
    return pd.DataFrame(rows), pd.DataFrame(changes, columns=["feed_key", "radius_km", "stop_ids", "names"])


# ==========================================================================
# Data dictionaries of the 04e outputs
# ==========================================================================

from .nb01a_feeds import SCHEMAS as _SCHEMAS   # noqa: E402

_SCHEMAS.update({
    "explore_feed_table": {
        "title": "The seven GTFS feeds: size, coverage in time, exceptions (REP-4)",
        "produced_by": "notebooks/04e_feed_completeness.ipynb (nb04_feeds.feed_table)",
        "row": "one feed",
        "columns": {"feed_key": ("str", "Feed."), "file": ("str", "File in data/feeds/."), "bytes": ("int", "File size."),
                    "agencies": ("int", "agency.txt rows."), "routes": ("int", "routes.txt rows."),
                    "trips": ("int", "trips.txt rows."), "stops": ("int", "stops.txt rows."),
                    "stations": ("int", "Stations in the 01b catalog."),
                    "route_types": ("str", "GTFS route_type values present."),
                    "calendar_dates_added": ("int", "calendar_dates rows adding a service day (exception_type 1)."),
                    "calendar_dates_removed": ("int", "Rows removing one (exception_type 2): holidays, cancellations."),
                    "service_start": ("str", "First day of the feed's calendar."), "service_end": ("str", "Last day."),
                    "window_start": ("str", "Analysis window start (01a)."), "window_end": ("str", "Window end."),
                    "window_days": ("int", "Window length."), "role": ("str", "domestic / foreign.")},
    },
    "explore_feed_effect": {
        "title": "What each national feed adds: LAUs and population reached with ZSR_SK alone against ZSR_SK + the national feed",
        "produced_by": "notebooks/04e_feed_completeness.ipynb (nb04_feeds.feed_effect)",
        "row": "one country x variant x direction (headline runs)",
        "columns": {"country": ("str", "Destination country."),
                    "variant": ("str", "ZSR_SK alone, or ZSR_SK + national feed (the headline of 03)."),
                    "direction": ("str", "inbound / outbound."),
                    "n_lau": ("int", "LAUs reached directly or with one transfer."),
                    "population": ("float", "Their population."),
                    "n_lau_newly_reached": ("int", "Of them, reached only with a transfer."),
                    "window_days": ("int", "Days in the country window."),
                    "added_lau": ("int", "LAUs added over ZSR_SK alone: the national feed's contribution."),
                    "added_population": ("float", "Population added.")},
    },
    "explore_dedup_radius": {
        "title": "Stations formed by the same-name merge rule at several radii (VAL-4)",
        "produced_by": "notebooks/04e_feed_completeness.ipynb (nb04_feeds.dedup_radius)",
        "row": "one feed x radius",
        "columns": {"feed_key": ("str", "Feed without parent stations."), "radius_km": ("float", "Merge radius (01b uses 2 km)."),
                    "stops": ("int", "Boarding stops."), "stations": ("int", "Stations formed."),
                    "merged_groups": ("int", "Stations formed from more than one stop.")},
    },
    "explore_dedup_changes": {
        "title": "Stations that differ from the 2 km rule at another radius",
        "produced_by": "notebooks/04e_feed_completeness.ipynb (nb04_feeds.dedup_radius)",
        "row": "one station formed at a radius that the 2 km rule does not form",
        "columns": {"feed_key": ("str", "Feed."), "radius_km": ("float", "Radius."),
                    "stop_ids": ("str", "Its stops."), "names": ("str", "Their names.")},
    },
})
