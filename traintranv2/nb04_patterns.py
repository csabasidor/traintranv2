"""
Notebook 04a -- service patterns: when the journeys run (register REP-8, CF-20, CON-8, PIP-9).

From each journey's run-date mask and its window's calendar:

* ``day_counts``     -- per journey: run days on each weekday (Mon..Sun), each month, each season, weekdays /
                        weekends; plus the number of such days in the window (the denominators).
* ``lau_patterns``   -- per LAU x direction x network x run: journeys per day for all days, weekdays, weekends, each
                        weekday, month, season = run days in that slice / days of that slice in the window. A
                        pattern class: every_day (all seven weekdays served), weekday_only, weekend_only, partial.
                        A LAU with journeys always gets a pattern (the legacy run left 517 of 559 CZ one-hop LAUs
                        with an empty weekday pattern, CF-20).
* ``recount``        -- distinct journeys recounted at a coarser level (NUTS3, NUTS2, country): a train serving
                        five LAUs of one region counts once for the region (never a sum of LAU counts).
* ``coverage_curve`` -- LAUs and population with at least k journeys per day (CON-8: 1, 2, 5).
"""

import datetime as dt
from typing import List

import numpy as np

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SEASONS = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA",
           9: "SON", 10: "SON", 11: "SON"}


def slices(days: List[dt.date]) -> dict:
    """{slice name: boolean array over the window's days}: weekdays, months, seasons, weekday / weekend, all."""
    wd = np.array([d.weekday() for d in days])
    mo = np.array([d.month for d in days])
    se = np.array([SEASONS[d.month] for d in days])
    out = {"all": np.ones(len(days), bool), "weekday": wd < 5, "weekend": wd >= 5}
    for k, n in enumerate(WEEKDAYS):
        out[n] = wd == k
    for m in range(1, 13):
        if (mo == m).any():
            out[f"m{m:02d}"] = mo == m
    for s in ("DJF", "MAM", "JJA", "SON"):
        if (se == s).any():
            out[s] = se == s
    return out


def day_counts(masks, days: List[dt.date]):
    """Per mask ('0'/'1' string, day 0 first): run days in every slice. Returns (DataFrame, days per slice)."""
    import pandas as pd
    sl = slices(days)
    m = np.frombuffer("".join(masks).encode(), dtype=np.uint8).reshape(len(masks), len(days)) == ord("1")
    counts = {k: (m & v).sum(axis=1) for k, v in sl.items()}
    return pd.DataFrame(counts), {k: int(v.sum()) for k, v in sl.items()}


def classify(row) -> str:
    """every_day: every weekday of the week served at least once; weekday_only / weekend_only; else partial."""
    served = [row[w] > 0 for w in WEEKDAYS]
    if all(served):
        return "every_day"
    if any(served[:5]) and not any(served[5:]):
        return "weekday_only"
    if any(served[5:]) and not any(served[:5]):
        return "weekend_only"
    return "partial"


def lau_patterns(j, days_by_run: dict, keys=("network", "run", "direction", "lau_gisco_id")):
    """Journeys per day in every slice per LAU (j: nb04_frame.journeys; days_by_run: run -> window dates)."""
    import pandas as pd
    out = []
    for run, g in j.groupby("run", sort=False):
        days = days_by_run[run]
        c, n = day_counts(g["mask"].tolist(), days)
        c.index = g.index
        x = pd.concat([g[list(keys)], c], axis=1).groupby(list(keys), sort=False).sum().reset_index()
        for k, d in n.items():
            x[k] = x[k] / d if d else np.nan              # journeys per day of that slice
        x["pattern"] = x.apply(classify, axis=1)
        out.append(x)
    return pd.concat(out, ignore_index=True)


def recount(j, unit_col: str, keys=("network", "run", "direction")):
    """Distinct journeys and journeys per day at a coarser unit (NUTS3 / NUTS2 / country)."""
    by = list(keys) + [unit_col]
    n_lau = j.groupby(by, sort=False)["lau_gisco_id"].nunique().rename("n_lau")
    u = j.drop_duplicates(by + ["journey"])
    g = u.groupby(by, sort=False)
    out = g.agg(n_journeys=("journey", "size"), run_days=("n_days", "sum"),
                window_days=("window_days", "first")).join(n_lau).reset_index()
    out["f_per_day"] = out["run_days"] / out["window_days"]
    return out


def coverage_curve(lau, thresholds=(1, 2, 5), keys=("network", "run", "direction", "country")):
    """LAUs and population with f_per_day >= k (lau: nb04_frame.lau_table)."""
    import pandas as pd
    rows = []
    for k_, g in lau.groupby(list(keys), sort=False):
        for t in (0,) + tuple(thresholds):
            x = g[g["f_per_day"] >= t] if t else g
            rows.append({**dict(zip(keys, k_)), "min_per_day": t, "n_lau": len(x), "population": x["population"].sum()})
    return pd.DataFrame(rows)
