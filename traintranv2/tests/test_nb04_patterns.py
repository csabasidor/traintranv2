"""Tests for traintranv2.nb04_patterns and nb04_frame.lau_table on toy journeys."""
import datetime as dt

import pandas as pd

from traintranv2 import nb04_patterns as P
from traintranv2 import nb04_frame as FR

DAYS = [dt.date(2026, 1, 5) + dt.timedelta(days=k) for k in range(14)]       # Mon 5 Jan .. Sun 18 Jan


def _j(rows):
    cols = ["network", "run", "headline", "direction", "lau_gisco_id", "station_key", "journey", "n_days", "mask",
            "time_min", "wait_min", "route_km", "rail_km", "geo_km", "has_direct", "window_days"]
    return pd.DataFrame([dict(zip(cols, r)) for r in rows])


WD = "11111001111100"          # Mon-Fri twice
WE = "00000110000011"          # Sat-Sun twice


def test_day_counts_and_slices():
    c, n = P.day_counts([WD, WE], DAYS)
    assert n["weekday"] == 10 and n["weekend"] == 4 and n["mon"] == 2 and n["m01"] == 14
    assert c.loc[0, "weekday"] == 10 and c.loc[0, "weekend"] == 0
    assert c.loc[1, "sat"] == 2 and c.loc[1, "weekday"] == 0


def test_lau_patterns_rates_and_classes():
    j = _j([("n", "R", True, "inbound", "A", "s1", "t1", 10, WD, 60, None, 50, 45, 40, True, 14),
            ("n", "R", True, "inbound", "A", "s1", "t2", 4, WE, 70, None, 50, 45, 40, True, 14),
            ("n", "R", True, "inbound", "B", "s2", "t3", 4, WE, 80, None, 90, 80, 70, True, 14)])
    p = P.lau_patterns(j, {"R": DAYS}).set_index("lau_gisco_id")
    assert p.loc["A", "weekday"] == 1.0 and p.loc["A", "weekend"] == 1.0 and p.loc["A", "all"] == 1.0
    assert p.loc["A", "pattern"] == "every_day" and p.loc["B", "pattern"] == "weekend_only"
    assert not p["pattern"].isna().any()                              # CF-20: every LAU has a pattern


def test_recount_counts_a_train_once_per_region():
    j = _j([("n", "R", True, "inbound", "A", "s1", "t1", 14, "1" * 14, 60, None, 50, 45, 40, True, 14),
            ("n", "R", True, "inbound", "B", "s2", "t1", 14, "1" * 14, 70, None, 60, 55, 50, True, 14)])
    j["nuts3_id"] = "X1"
    r = P.recount(j, "nuts3_id")
    assert r.iloc[0]["n_journeys"] == 1 and r.iloc[0]["f_per_day"] == 1.0 and r.iloc[0]["n_lau"] == 2


def test_lau_table_spec_aggregates():
    j = _j([("n", "R", True, "inbound", "A", "s1", "t1", 14, "1" * 14, 60, None, 50, 45, 40, True, 14),
            ("n", "R", True, "inbound", "A", "s2", "t2", 7, "1" * 7 + "0" * 7, 90, None, 70, 65, 60, True, 14)])
    attrs = pd.DataFrame({"lau_gisco_id": ["A"], "population": [1000.0]})
    t = FR.lau_table(j, attrs).iloc[0]
    assert t.n_journeys == 2 and t.run_days == 21 and t.f_per_day == 1.5        # f = R / W
    assert t.time_mean_min == 75 and t.route_km_mean == 60 and t.service_days == 14
    assert t.mean_days_per_journey <= t.window_days                            # R / |I| <= W


def test_coverage_curve_thresholds():
    lau = pd.DataFrame({"network": "n", "run": "R", "direction": "inbound", "country": "SK",
                        "f_per_day": [0.5, 1.5, 6.0], "population": [10, 20, 30]})
    c = P.coverage_curve(lau).set_index("min_per_day")
    assert c.loc[0, "n_lau"] == 3 and c.loc[1, "population"] == 50 and c.loc[5, "n_lau"] == 1
