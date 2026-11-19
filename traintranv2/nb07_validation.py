"""
Notebook 07 -- a stratified sample of computed itineraries to check against the operators' journey planners
(register VAL-1, T12; Reviewer 1: "A sample set of computed itineraries should be checked against official journey
planners or operator timetables. Validation metrics should be reported").

* ``sample``          -- inbound journeys (to Košice) drawn per country / feed run with a fixed seed, one per LAU,
                         on upcoming dates only (2026-11-17 .. 2026-12-12): a run date from the feed, or, for feeds
                         whose window ended earlier (HU, PL), the same weekday projected forward when the journey ran
                         on at least 80 % of that weekday's dates; with times, the transfer station, the train numbers
                         and the planner to query.
* ``recording_sheet`` -- the same rows with empty columns for the planner's answer.
* ``score``           -- once filled: match rate per stratum, time differences, reasons for misses.
"""

import datetime as dt
import zipfile

import numpy as np

from .config import RunConfig

PLANNER = {"SK": "ZSSK (cp.sk / zssk.sk)", "CZ": "ČD (cd.cz) / IDOS", "HU": "MÁV (jegy.mav.hu)",
           "AT": "ÖBB Scotty (fahrplan.oebb.at)", "PL": "PKP (portalpasazera.pl)", "UA": "UZ (booking.uz.gov.ua) / ZSSK"}
# train number field per feed: the route name carries it in ZSR_SK, MÁV and UZ, the trip name elsewhere
NUMBER_FROM_ROUTE = {"ZSR_SK", "MAV_HU", "UKRZ_UA"}


def train_numbers(cfg: RunConfig) -> dict:
    """{(feed, trip_id): 'train number (headsign)'} for every feed."""
    import pandas as pd
    from .nb01a_feeds import feed_zip_path
    out = {}
    for f in cfg.feeds:
        with zipfile.ZipFile(feed_zip_path(cfg, f)) as z:
            tr = pd.read_csv(z.open("trips.txt"), dtype=str).fillna("")
            ro = pd.read_csv(z.open("routes.txt"), dtype=str).fillna("")
        tr = tr.merge(ro[["route_id"] + [c for c in ("route_short_name", "route_long_name") if c in ro]], on="route_id", how="left")
        for _, r in tr.iterrows():
            first = ("route_short_name", "trip_short_name") if f in NUMBER_FROM_ROUTE else ("trip_short_name", "route_short_name")
            num = next((r.get(c, "") for c in first + ("route_long_name",) if r.get(c, "")), "")
            head = r.get("trip_headsign", "")
            out[(f, r["trip_id"])] = f"{num} ({head})" if head else num
    return out


def _label(numbers, feed, trip):
    first = str(trip).split("+")[0]                      # joined pieces / stay-seated legs: the first piece's number
    return numbers.get((feed, first), str(trip))


DATE_FROM = dt.date(2026, 11, 17)
DATE_TO = dt.date(2026, 12, 12)          # end of the ZSR_SK window = end of the 2025/26 timetable year
REGULAR_SHARE = 0.8                      # projection only for a train running on >= 80 % of its weekday's dates


def _pick_date(mask: str, start: str, date_from: dt.date, date_to: dt.date, shift: int = 0):
    """(service date, basis, projected_from) for a planner check on an upcoming date.

    feed      -- the first run date in the mask within [date_from, date_to] (calendar date after ``shift``);
    projected -- the window ends before date_from: the weekday the journey runs on most, if it ran on at least
                 REGULAR_SHARE of that weekday's dates in the window; the first such weekday from date_from;
    (None, "", "") -- not eligible (no upcoming run date and no regular weekday).
    """
    d0 = dt.date.fromisoformat(start)
    last = d0 + dt.timedelta(days=len(mask) - 1)
    lo, hi = date_from - dt.timedelta(days=shift), date_to - dt.timedelta(days=shift)
    days = [d0 + dt.timedelta(days=k) for k, c in enumerate(mask) if c == "1"]
    upcoming = [d for d in days if lo <= d <= hi]
    if upcoming:
        return upcoming[0], "feed", ""
    if last >= lo or not days:              # the window reaches the period: it simply does not run then
        return None, "", ""
    best, share = None, 0.0
    for wd in range(7):
        n_all = sum(1 for k in range(len(mask)) if (d0 + dt.timedelta(days=k)).weekday() == wd)
        n_run = sum(1 for d in days if d.weekday() == wd)
        if n_all and n_run / n_all > share:
            best, share = wd, n_run / n_all
    if best is None or share < REGULAR_SHARE:
        return None, "", ""
    d = lo + dt.timedelta(days=(best - lo.weekday()) % 7)
    if d > hi:
        return None, "", ""
    src = max(x for x in days if x.weekday() == best)
    return d, "projected", str(src)


def sample(cfg: RunConfig, direct, itins, tags, numbers, n_per_stratum: dict, date_from: dt.date = DATE_FROM,
           date_to: dt.date = DATE_TO, seed: int = 20261116):
    """Stratified inbound sample from the 02 / 03 direct legs and one-transfer itineraries, on upcoming dates only.

    ``direct`` / ``itins``: the domestic and foreign files concatenated, with columns country, run, window_start.
    Strata: '<run> direct' and '<run> one transfer' per country / feed run (SK, CZ, HU, AT, UA, PL, PL:PL_IC), plus
    cross-feed transfer and across midnight. Only journeys with a date in [date_from, date_to] (from the feed, or
    projected to the same weekday when the feed's window ended earlier) are eligible.
    """
    import pandas as pd
    nm = tags.set_index("station_key")["stop_name"]
    hub_name = nm.get(cfg.hub_station_keys[0], "Košice")
    d = direct[direct["direction"].eq("inbound")].copy()
    d["stratum"] = d["run"] + " direct"
    i = itins[itins["direction"].eq("inbound")].copy()
    i["stratum"] = i["run"] + " one transfer"
    extra = [i[i["leg1_feed"] != i["leg2_feed"]].assign(stratum="cross-feed transfer"),
             i[i["next_day"].astype(bool)].assign(stratum="across midnight")]
    rng = np.random.default_rng(seed)
    rows = []
    for frame, kind in ((d, "direct"), (pd.concat([i] + extra, ignore_index=True), "one transfer")):
        t0 = (frame["dep_s"] if kind == "direct" else frame["start_s"]).astype(int)
        frame = frame.assign(_shift=(t0 // 86400).values)   # a GTFS time past 24:00 departs on the next calendar day
        picked = [_pick_date(m, w, date_from, date_to, s) for m, w, s in
                  zip(frame["mask"], frame["window_start"], frame["_shift"])]
        frame = frame.assign(_day=[p[0] for p in picked], _basis=[p[1] for p in picked],
                             _src=[p[2] for p in picked])
        frame = frame[frame["_day"].notna()]
        for st, g in frame.groupby("stratum"):
            k = n_per_stratum.get(st, n_per_stratum.get("default", 3))
            g = g.drop_duplicates("lau_gisco_id")
            g = g.iloc[rng.permutation(len(g))]
            # distinct trains first: a second LAU on the same train(s) is drawn only when the stratum runs out
            trains = g["trip_id"].astype(str) if kind == "direct" else g["leg1_trip"].astype(str) + "|" + g["leg2_trip"].astype(str)
            order = np.argsort(trains.groupby(trains).cumcount().to_numpy(), kind="stable")
            pick = g.iloc[order[:k]]
            for _, r in pick.iterrows():
                shift = int(r["_shift"])
                cal = r["_day"] + dt.timedelta(days=shift)
                feed = r["feed_key"] if kind == "direct" else f"{r['leg1_feed']} + {r['leg2_feed']}"
                base = {"stratum": st, "kind": kind, "country": r["country"], "run": r["run"], "feed": feed,
                        "date": str(cal), "date_basis": r["_basis"], "projected_from": r["_src"],
                        "origin": nm.get(r["station_key"], r["station_key"]), "destination": hub_name,
                        "planner": PLANNER.get(r["country"], "")}
                if kind == "direct":
                    rows.append({**base, "departure": _hm(r["dep_s"], shift), "arrival": _hm(r["arr_s"], shift),
                                 "transfer_station": "", "transfer_arrival": "", "transfer_departure": "",
                                 "trains": _label(numbers, r["feed_key"], r["trip_id"]),
                                 "journey_min": round((r["arr_s"] - r["dep_s"]) / 60)})
                else:
                    rows.append({**base, "departure": _hm(r["start_s"], shift), "arrival": _hm(r["end_s"], shift),
                                 "transfer_station": nm.get(r["T_key"], r["T_key"]),
                                 "transfer_arrival": _hm(r["t_arr_s"], shift), "transfer_departure": _hm(r["t_dep_s"], shift),
                                 "trains": f"{_label(numbers, r['leg1_feed'], r['leg1_trip'])} + {_label(numbers, r['leg2_feed'], r['leg2_trip'])}",
                                 "journey_min": round(r["total_s"] / 60)})
    out = pd.DataFrame(rows)
    out.insert(0, "sample_id", [f"V{k + 1:03d}" for k in range(len(out))])
    return out


def _hm(s, shift: int = 0) -> str:
    """Clock time on the calendar day of departure (``shift`` days after the service day); (+1) = the next day."""
    s = int(s) - 86400 * shift
    return f"{(s % 86400) // 3600:02d}:{(s % 3600) // 60:02d}" + (f" (+{s // 86400})" if s >= 86400 else "")


SHEET_COLS = ["planner_found", "planner_departure", "planner_arrival", "planner_transfer_station", "planner_trains",
              "match", "time_difference_min", "checked_on", "note"]


def recording_sheet(s):
    """The sample with empty columns for the planner's answer (match: yes / partly / no)."""
    return s.assign(**{c: "" for c in SHEET_COLS})


from .nb01a_feeds import SCHEMAS as _SCHEMAS   # noqa: E402

_SCHEMAS["explore_validation_sample"] = {
    "title": "Stratified sample of computed inbound journeys to check against the operators' planners (VAL-1)",
    "produced_by": "notebooks/07_validation_sample.ipynb (nb07_validation.sample)",
    "row": "one sampled journey (one per LAU within a stratum)",
    "columns": {"sample_id": ("str", "V001 ..."), "stratum": ("str", "'<run> direct' / '<run> one transfer' per country / feed run; cross-feed transfer; across midnight."),
                "kind": ("str", "direct or one transfer."), "country": ("str", "Origin country."), "run": ("str", "Country / feed run (PL:PL_IC = PKP-IC feed)."),
                "feed": ("str", "Feed of the train (direct) or of the two trains (one transfer)."),
                "date": ("str", "Calendar date of the departure, between 2026-11-17 and 2026-12-12 (a GTFS time past 24:00 moves to the next day)."),
                "date_basis": ("str", "feed = a run date in the feed; projected = the feed's window ended before 2026-11-17 (HU, PL), so the first date on the weekday the journey ran on in >= 80 % of cases."),
                "projected_from": ("str", "For projected rows: the last run date in the feed on that weekday."),
                "origin": ("str", "Origin station."), "destination": ("str", "Košice."),
                "planner": ("str", "Planner to query."), "departure": ("str", "Computed departure, clock time on that date."),
                "arrival": ("str", "Computed arrival at Košice; (+1) = the day after the departure."), "transfer_station": ("str", "Transfer station (one transfer)."),
                "transfer_arrival": ("str", "Arrival there."), "transfer_departure": ("str", "Departure from there."),
                "trains": ("str", "Train numbers (and headsigns) as the feeds publish them."),
                "journey_min": ("int", "Computed journey time, minutes.")},
}


def score(sheet):
    """Match rate per stratum and time differences, from a filled sheet (rows with match filled only)."""
    import pandas as pd
    f = sheet[sheet["match"].astype(str).str.strip().ne("")].copy()
    if f.empty:
        return pd.DataFrame(columns=["stratum", "checked", "match_yes", "match_partly", "match_no",
                                     "match_rate", "median_abs_diff_min", "max_abs_diff_min"])
    f["diff"] = pd.to_numeric(f["time_difference_min"], errors="coerce").abs()
    g = f.groupby("stratum")
    out = pd.DataFrame({"checked": g.size(), "match_yes": g["match"].apply(lambda s: (s == "yes").sum()),
                        "match_partly": g["match"].apply(lambda s: (s == "partly").sum()),
                        "match_no": g["match"].apply(lambda s: (s == "no").sum()),
                        "median_abs_diff_min": g["diff"].median(), "max_abs_diff_min": g["diff"].max()}).reset_index()
    out["match_rate"] = out["match_yes"] / out["checked"]
    return out
