"""Tests for traintranv2.nb03_foreign: country runs and windows, cross-feed dedup, same-train filter,
first legs from the domestic feed only, transfers between feeds at a shared station group, city transfers."""
import datetime as dt
import json

import pandas as pd
import pytest

from traintranv2.config import default_config
from traintranv2 import nb02_connections as C
from traintranv2 import nb03_foreign as F

DAYS = [dt.date(2026, 6, 1) + dt.timedelta(days=k) for k in range(3)]


def _hm(s):
    h, m = s.split(":")
    return int(h) * 3600 + int(m) * 60


def _feed(trips_def):
    """trips_def: {trip: (mask, [(station_key, group, 'HH:MM'), ...])} -> (stop_times, trips)."""
    st, tr = [], []
    for tid, (mask, calls) in trips_def.items():
        for k, (key, grp, t) in enumerate(calls):
            st.append({"trip_id": tid, "seq": k, "station_key": key, "group": grp, "arr_s": _hm(t), "dep_s": _hm(t)})
        tr.append({"trip_id": tid, "route_id": "R", "route_type": "2", "agency_id": "1", "service_id": "S",
                   "n_days": mask.count("1"), "mask": mask, "window": ""})
    return pd.DataFrame(st), pd.DataFrame(tr)


@pytest.fixture()
def world():
    """K = Košice (hub, SK). T = border station in SK, in both feeds (one group). Y = Czech town in both feeds.
    X = Czech town only in the Czech feed. M = second station of X's LAU (city-transfer test).
    ZSR_SK:  z1 K 08:00 -> T 09:00 (daily)
             z2 T 09:30 -> Y 10:30 (daily)           = the Czech feed's c1 (same train)
             z3 K 08:00 -> T 09:00 -> Y 10:00 -> X? no: K..Y through train, days 1-2
    DRAHY_CZ: c1 T 09:31 -> Y 10:31 (days 0-1)
              c2 T 09:40 -> X 10:20 (daily)
              c3 T 09:20 -> M 09:50 (daily); c4 M 10:40 -> X2 11:00 (city test)
    """
    zsr = _feed({"z1": ("111", [("ZSR_SK:K", "G:K", "08:00"), ("ZSR_SK:T", "G:T", "09:00")]),
                 "z2": ("111", [("ZSR_SK:T", "G:T", "09:30"), ("ZSR_SK:Y", "G:Y", "10:30")]),
                 "z4": ("111", [("ZSR_SK:K", "G:K", "08:00"), ("ZSR_SK:M", "G:M", "09:50")])})
    cz = _feed({"c1": ("110", [("DRAHY_CZ:T", "G:T", "09:31"), ("DRAHY_CZ:Y", "G:Y", "10:31")]),
                "c2": ("111", [("DRAHY_CZ:T", "G:T", "09:40"), ("DRAHY_CZ:X", "G:X", "10:20")]),
                "c3": ("111", [("DRAHY_CZ:T", "G:T", "09:20"), ("DRAHY_CZ:M", "G:M", "09:50")]),
                "c4": ("111", [("DRAHY_CZ:N", "G:N", "10:40"), ("DRAHY_CZ:X2", "G:X2", "11:00")])})
    tags = pd.DataFrame([
        ("ZSR_SK", "ZSR_SK:K", "G:K", "SK", "SK_K"), ("ZSR_SK", "ZSR_SK:T", "G:T", "SK", "SK_T"),
        ("ZSR_SK", "ZSR_SK:Y", "G:Y", "CZ", "CZ_Y"), ("DRAHY_CZ", "DRAHY_CZ:T", "G:T", "SK", "SK_T"),
        ("DRAHY_CZ", "DRAHY_CZ:Y", "G:Y", "CZ", "CZ_Y"), ("DRAHY_CZ", "DRAHY_CZ:X", "G:X", "CZ", "CZ_X"),
        ("DRAHY_CZ", "DRAHY_CZ:M", "G:M", "CZ", "CZ_C"), ("ZSR_SK", "ZSR_SK:M", "G:M", "CZ", "CZ_C"), ("DRAHY_CZ", "DRAHY_CZ:N", "G:N", "CZ", "CZ_C"),
        ("DRAHY_CZ", "DRAHY_CZ:X2", "G:X2", "CZ", "CZ_X2"),
    ], columns=["feed_key", "station_key", "station_group_id", "nuts_rg_01_country_id", "lau_gisco_id"])
    cfg = default_config()
    run = {"run": "CZ", "country": "CZ", "feeds": ["DRAHY_CZ"], "days": DAYS, "headline": True}
    return cfg, run, {"ZSR_SK": zsr, "DRAHY_CZ": cz}, tags, {"G:K"}


def test_country_runs_take_the_common_window_and_add_longer_single_feed_runs(tmp_path):
    cfg = default_config()
    cfg.output_dir = str(tmp_path)
    w = {"ZSR_SK": ("2025-12-14", "2026-12-12"), "PL_IC": ("2026-05-18", "2026-08-26"),
         "PL_REG": ("2026-06-05", "2026-07-06"), "MAV_HU": ("2026-01-19", "2026-11-15")}
    (tmp_path / "kosice").mkdir(exist_ok=True)
    with open(f"{cfg.out_dir}/windows.json", "w", encoding="utf-8") as fh:
        json.dump({k: {"start": a, "end": b} for k, (a, b) in w.items()}, fh)
    cfg.country_feeds = {"PL": ["PL_IC", "PL_REG"], "HU": ["MAV_HU"]}
    cfg.feeds = {k: {} for k in w}
    runs = {r["run"]: r for r in F.country_runs(cfg, ["PL", "HU"])}
    assert len(runs["PL"]["days"]) == 32 and runs["PL"]["headline"]
    assert len(runs["PL:PL_IC"]["days"]) == 101 and not runs["PL:PL_IC"]["headline"]
    assert "PL:PL_REG" not in runs                        # its own window is the headline window
    assert len(runs["HU"]["days"]) == 301


def test_dedupe_keeps_the_national_feed_and_ors_the_dates():
    legs = pd.DataFrame([
        {"feed_key": "ZSR_SK", "trip_id": "z2", "from_group": "G:T", "to_group": "G:Y", "dep_s": _hm("09:30"),
         "arr_s": _hm("10:30"), "mask": "111", "n_days": 3},
        {"feed_key": "DRAHY_CZ", "trip_id": "c1", "from_group": "G:T", "to_group": "G:Y", "dep_s": _hm("09:31"),
         "arr_s": _hm("10:31"), "mask": "110", "n_days": 2},
        {"feed_key": "ZSR_SK", "trip_id": "z9", "from_group": "G:T", "to_group": "G:Y", "dep_s": _hm("09:36"),
         "arr_s": _hm("10:36"), "mask": "111", "n_days": 3},                      # 5 min later: another train
    ])
    out, dup = F.dedupe_cross_feed(legs, ["DRAHY_CZ", "ZSR_SK"])
    assert sorted(out.trip_id) == ["c1", "z9"]
    c1 = out.set_index("trip_id").loc["c1"]
    assert c1["mask"] == "111" and c1["n_days"] == 3 and c1["also_in"] == "ZSR_SK"
    assert list(zip(dup.drop_trip, dup.keep_trip)) == [("z2", "c1")]


def test_dedupe_needs_a_common_date():
    legs = pd.DataFrame([
        {"feed_key": "ZSR_SK", "trip_id": "z", "from_group": "A", "to_group": "B", "dep_s": 0, "arr_s": 60,
         "mask": "001", "n_days": 1},
        {"feed_key": "DRAHY_CZ", "trip_id": "c", "from_group": "A", "to_group": "B", "dep_s": 0, "arr_s": 60,
         "mask": "110", "n_days": 2}])
    out, dup = F.dedupe_cross_feed(legs, ["DRAHY_CZ", "ZSR_SK"])
    assert len(out) == 2 and dup.empty


def test_one_transfer_across_feeds_first_leg_domestic_only(world):
    cfg, run, tt, tags, hubs = world
    it, dup, stats = F.run_one_transfer(cfg, run, tt, tags, hubs)
    out = it[it.direction == "outbound"]
    assert set(out.leg1_feed) == {"ZSR_SK"}
    assert set(out.station_key.map(dict(zip(tags.station_key, tags.nuts_rg_01_country_id)))) == {"CZ"}
    got = {(r.leg1_trip, r.leg2_feed, r.leg2_trip, r.station_key) for r in out.itertuples()}
    # X via the Czech train at the shared group T; Y via c1 only (z2 is the same train, dropped)
    assert ("z1", "DRAHY_CZ", "c2", "DRAHY_CZ:X") in got
    assert ("z1", "DRAHY_CZ", "c1", "DRAHY_CZ:Y") in got
    assert not any(t == "z2" for _, _, t, _ in got)
    assert stats["outbound"]["duplicates_dropped"] == 1
    y = out[out.station_key == "DRAHY_CZ:Y"].iloc[0]
    assert y["mask"] == "111"                            # c1's dates + its ZSR copy's


def test_city_transfer_joins_two_stations_of_one_lau(world):
    cfg, run, tt, tags, hubs = world
    # z4 reaches M (LAU CZ_C) at 09:50; c4 leaves N, another station of CZ_C, at 10:40 for X2
    head, _, _ = F.run_one_transfer(cfg, run, tt, tags, hubs)
    assert "DRAHY_CZ:X2" not in set(head.station_key)                    # different stations: no transfer
    city, _, _ = F.run_one_transfer(cfg, run, tt, tags, hubs, mn=45, transfer_unit="lau")
    x2 = city[(city.station_key == "DRAHY_CZ:X2") & (city.direction == "outbound")]
    assert len(x2) == 1 and x2.iloc[0]["wait_s"] == 50 * 60
    strict, _, _ = F.run_one_transfer(cfg, run, tt, tags, hubs, mn=60, transfer_unit="lau")
    assert "DRAHY_CZ:X2" not in set(strict.station_key)                  # 50 min < 60


def test_drop_same_train_across_feeds():
    zsr = _feed({"z": ("111", [("ZSR_SK:K", "G:K", "08:00"), ("ZSR_SK:T", "G:T", "09:00"),
                               ("ZSR_SK:Y", "G:Y", "10:00")])})
    cz = _feed({"c": ("111", [("DRAHY_CZ:T", "G:T", "09:15"), ("DRAHY_CZ:Y", "G:Y", "10:00")])})
    it = pd.DataFrame([{"direction": "outbound", "T": "G:T", "leg1_feed": "ZSR_SK", "leg1_trip": "z",
                        "leg2_feed": "DRAHY_CZ", "leg2_trip": "c", "t_arr_s": _hm("09:00"), "t_dep_s": _hm("09:00") + 60}])
    kept, n = F.drop_same_train(it, {"ZSR_SK": zsr, "DRAHY_CZ": cz})
    assert n == 1 and kept.empty                          # c is the Czech feed's copy of the train z


def test_run_direct_keeps_only_the_country(world):
    cfg, run, tt, tags, hubs = world
    d = F.run_direct(cfg, run, tt, tags, hubs)
    assert set(d.station_key) == {"ZSR_SK:M"}            # z4; z1 ends in SK, z2 does not touch the hub


def test_station_lau_abroad_comes_from_the_national_feed():
    tags = pd.DataFrame([("ZSR_SK", "ZSR_SK:H", "G:H", "HU", "HU_tornyos"),      # ZSR's point: the neighbour LAU
                         ("MAV_HU", "MAV_HU:H", "G:H", "HU", "HU_hidas"),
                         ("ZSR_SK", "ZSR_SK:S", "G:S", "SK", "SK_1"),             # at home: its own LAU
                         ("ZSR_SK", "ZSR_SK:Z", "G:Z", "HU", "HU_z")],            # no national station: its own
                        columns=["feed_key", "station_key", "station_group_id", "nuts_rg_01_country_id", "lau_gisco_id"])
    lau = F.station_lau(tags, default_config())
    assert lau["ZSR_SK:H"] == "HU_hidas" and lau["MAV_HU:H"] == "HU_hidas"
    assert lau["ZSR_SK:S"] == "SK_1" and lau["ZSR_SK:Z"] == "HU_z"
