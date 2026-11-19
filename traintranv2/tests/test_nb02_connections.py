"""Tests for traintranv2.nb02_connections on a synthetic feed (window = 7 days, Mon 2026-01-05..)."""
import datetime as dt
import zipfile

import pandas as pd
import pytest

from traintranv2.config import default_config
from traintranv2 import nb02_connections as C

DAYS = [dt.date(2026, 1, 5) + dt.timedelta(days=k) for k in range(7)]      # Mon..Sun
WEEKDAYS, WEEKEND = 0b0011111, 0b1100000


def _csv(rows):
    cols = list(rows[0])
    return "\n".join([",".join(cols)] + [",".join(str(r[c]) for c in cols) for r in rows]) + "\n"


def _cal(sid, wd):
    names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return {"service_id": sid, **{n: int(c) for n, c in zip(names, wd)},
            "start_date": "20260101", "end_date": "20261231"}


@pytest.fixture()
def feed(tmp_path):
    """Stations: K (hub), P (hub predmestie), A, B, C. Trips (stop sequence, HH:MM):
    t1 weekdays  K 08:00 -> A 09:00 -> B 10:00
    t2 weekends  K 07:50 -> P 08:00 -> A 08:50
    t3 weekdays  A 09:20 -> C 10:00
    t4 weekends  A 09:25 -> C 10:00
    t5 weekdays  A 09:40 -> C 10:20
    t6 daily     C 17:00 -> A 17:40 -> K 18:40
    t7 weekdays  B 06:00 -> K 07:30           (inbound, early)
    t8 weekdays  K 23:00 -> B 25:10           (outbound past midnight)
    t9 weekdays  K 18:00 -> B 19:30
    bus weekdays K 08:00 -> A 08:30           (bus route: excluded)
    """
    cal = [_cal("WD", "1111100"), _cal("WE", "0000011"), _cal("ALL", "1111111")]
    trips_def = {"t1": ("WD", "R", [("K", "08:00"), ("A", "09:00"), ("B", "10:00")]),
                 "t2": ("WE", "R", [("K", "07:50"), ("P", "08:00"), ("A", "08:50")]),
                 "t3": ("WD", "R", [("A", "09:20"), ("C", "10:00")]),
                 "t4": ("WE", "R", [("A", "09:25"), ("C", "10:00")]),
                 "t5": ("WD", "R", [("A", "09:40"), ("C", "10:20")]),
                 "t6": ("ALL", "R", [("C", "17:00"), ("A", "17:40"), ("K", "18:40")]),
                 "t7": ("WD", "R", [("B", "06:00"), ("K", "07:30")]),
                 "t8": ("WD", "R", [("K", "23:00"), ("B", "25:10")]),
                 "t9": ("WD", "R", [("K", "18:00"), ("B", "19:30")]),
                 "bus": ("WD", "BUS", [("K", "08:00"), ("A", "08:30")])}
    st, tr = [], []
    for tid, (sid, rid, calls) in trips_def.items():
        tr.append({"route_id": rid, "service_id": sid, "trip_id": tid})
        for k, (s, t) in enumerate(calls):
            st.append({"trip_id": tid, "arrival_time": f"{t}:00", "departure_time": f"{t}:00",
                       "stop_id": s, "stop_sequence": k + 1})
    files = {
        "calendar.txt": _csv(cal),
        "calendar_dates.txt": _csv([{"service_id": "WD", "date": "20260107", "exception_type": 2}]),  # no t1/t3.. on Wed
        "routes.txt": _csv([{"route_id": "R", "agency_id": "1", "route_type": 2},
                            {"route_id": "BUS", "agency_id": "1", "route_type": 3}]),
        "trips.txt": _csv(tr),
        "stop_times.txt": _csv(st),
        "stops.txt": _csv([{"stop_id": s, "stop_name": s, "stop_lat": 0, "stop_lon": 0} for s in "KPABC"]),
    }
    zp = tmp_path / "F.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for n, txt in files.items():
            z.writestr(n, txt)
    cfg = default_config()
    cfg.feeds = {"F": {"filename": "F.zip", "country": "SK"}}
    cfg.feeds_dir = str(tmp_path)
    cfg.output_dir = str(tmp_path / "out")
    cfg.hub_station_keys = ["F:K", "F:P"]
    tags = pd.DataFrame({"feed_key": "F", "station_key": [f"F:{s}" for s in "KPABC"],
                         "stop_ids": list("KPABC"), "station_group_id": [f"G:{s}" for s in "KPABC"]})
    st_, trips_ = C.load_timetable(cfg, "F", tags, DAYS, cache=False)
    return cfg, tags, st_, trips_


def _mask(trips, tid):
    return C.str_to_mask(trips.set_index("trip_id").loc[tid, "mask"])


def test_timetable_masks_exceptions_and_bus(feed):
    cfg, tags, st, trips = feed
    assert "bus" not in set(trips.trip_id)
    wd_wo_wed = WEEKDAYS & ~(1 << 2)
    assert _mask(trips, "t1") == wd_wo_wed and _mask(trips, "t2") == WEEKEND
    assert _mask(trips, "t6") == 0b1111111
    t8 = st[st.trip_id == "t8"].set_index("station_key")
    assert t8.loc["F:B", "arr_s"] == 25 * 3600 + 10 * 60          # not wrapped at 24:00


def test_direct_hub_group_counts_a_trip_once(feed):
    cfg, tags, st, trips = feed
    hubs = C.hub_groups(cfg, tags)
    out = C.direct_legs(st, trips, hubs, "outbound", "F")
    a = out[out.station_key == "F:A"]
    assert sorted(a.trip_id) == ["t1", "t2"]                       # t2 calls at K and P: one row
    assert a.set_index("trip_id").loc["t2", "hub_key"] == "F:P"    # the last hub call before A
    inn = C.direct_legs(st, trips, hubs, "inbound", "F")
    assert set(inn.station_key) == {"F:C", "F:A", "F:B"}


def test_one_transfer_dated_finds_weekend_connection_legacy_misses_it(feed):
    cfg, tags, st, trips = feed
    hubs = C.hub_groups(cfg, tags)
    first = C.direct_legs(st, trips, hubs, "outbound", "F")
    first = first[first.group == "G:A"]
    second = C.attach_trips(C.od_pairs(st, from_groups={"G:A"}, not_to_groups=hubs), trips, "F")
    dated = C.one_transfer(first, second, "outbound", 10, 90, 7, rule="dated")
    c = dated[dated.station_key == "F:C"]
    got = {(r.leg1_trip, r.leg2_trip): C.str_to_mask(r.mask) for r in c.itertuples()}
    wd = WEEKDAYS & ~(1 << 2)
    assert got == {("t1", "t3"): wd, ("t2", "t4"): WEEKEND}       # t5 later: not counted
    # legacy: t2 (weekend, arr 08:50) goes first, tries only the first train >= 09:00 (t3, weekdays)
    # and gives up; t1 then claims t3
    legacy = C.one_transfer(first, second, "outbound", 10, 90, 7, rule="legacy")
    lc = legacy[legacy.station_key == "F:C"]
    assert set(zip(lc.leg1_trip, lc.leg2_trip)) == {("t1", "t3")}


def test_one_transfer_window_limits(feed):
    cfg, tags, st, trips = feed
    hubs = C.hub_groups(cfg, tags)
    first = C.direct_legs(st, trips, hubs, "outbound", "F")
    second = C.attach_trips(C.od_pairs(st, from_groups={"G:A"}, not_to_groups=hubs), trips, "F")
    none = C.one_transfer(first[first.group == "G:A"], second, "outbound", 25, 90, 7)
    assert set(zip(none.leg1_trip, none.leg2_trip)) == {("t1", "t5"), ("t2", "t4")}   # t1->t3 20 min: too short


def test_pair_legs_dominance():
    # two first legs (arr 100, 200) both reach second leg dep 300 on the same day: only the later counts
    out = C.pair_legs([100, 200], [1, 1], [300], [1], 0, 1000, "dated")
    assert out == [(1, 0, 1)]


def test_daytrip_rule_and_midnight(feed):
    cfg, tags, st, trips = feed
    hubs = C.hub_groups(cfg, tags)
    inn = C.direct_legs(st, trips, hubs, "inbound", "F")
    out = C.direct_legs(st, trips, hubs, "outbound", "F")
    ren = lambda d: d.rename(columns={"dep_s": "start_s", "arr_s": "end_s"})
    d = C.daytrip_days(ren(inn), ren(out), cfg, 7).set_index("station_key")
    # B: in t7 (arr 07:30) out t9 (18:00, back 19:30) on weekdays except Wed; t8 returns 25:10 (too late)
    assert C.str_to_mask(d.loc["F:B", "mask"]) == WEEKDAYS & ~(1 << 2)
    assert "F:C" not in d.index                                     # no outbound to C after 17:00


def test_summarise_counts_distinct_trips_and_service_days(feed):
    cfg, tags, st, trips = feed
    hubs = C.hub_groups(cfg, tags)
    out = C.direct_legs(st, trips, hubs, "outbound", "F")
    out["lau"] = "L1"                                               # A and B in one LAU
    s = C.summarise(out[out.station_key.isin(["F:A", "F:B"])], "lau", ["trip_id"], 7).iloc[0]
    assert s.n_journeys == 4                                        # t1 (A and B) counted once
    assert s.service_days == 6                                      # Wednesday removed by calendar_dates


def _zip(tmp_path, name, files):
    zp = tmp_path / name
    with zipfile.ZipFile(zp, "w") as z:
        for n, txt in files.items():
            z.writestr(n, txt)
    return zp


def _legs_feed(tmp_path, transfers=True, agency_of_l1="1"):
    """Through train split into legs: L0 K 08:00 -> X 09:00 (weekdays), L1 X 09:05 -> Y 10:00 (daily)."""
    cal = [_cal("WD", "1111100"), _cal("ALL", "1111111")]
    st = [{"trip_id": "L0", "arrival_time": "08:00:00", "departure_time": "08:00:00", "stop_id": "K", "stop_sequence": 1},
          {"trip_id": "L0", "arrival_time": "09:00:00", "departure_time": "09:00:00", "stop_id": "X", "stop_sequence": 2},
          {"trip_id": "L1", "arrival_time": "09:05:00", "departure_time": "09:05:00", "stop_id": "X", "stop_sequence": 1},
          {"trip_id": "L1", "arrival_time": "10:00:00", "departure_time": "10:00:00", "stop_id": "Y", "stop_sequence": 2}]
    files = {"calendar.txt": _csv(cal),
             "routes.txt": _csv([{"route_id": "R0", "agency_id": "1", "route_type": 2},
                                 {"route_id": "R1", "agency_id": agency_of_l1, "route_type": 2}]),
             "trips.txt": _csv([{"route_id": "R0", "service_id": "WD", "trip_id": "L0"},
                                {"route_id": "R1", "service_id": "ALL", "trip_id": "L1"}]),
             "stop_times.txt": _csv(st),
             "stops.txt": _csv([{"stop_id": s, "stop_name": s, "stop_lat": 0, "stop_lon": 0} for s in "KXY"])}
    if transfers:
        files["transfers.txt"] = _csv([{"from_stop_id": "X", "to_stop_id": "X", "from_trip_id": "L0",
                                        "to_trip_id": "L1", "transfer_type": 1}])
    _zip(tmp_path, "G.zip", files)
    cfg = default_config()
    cfg.feeds = {"G": {"filename": "G.zip", "country": "PL"}}
    cfg.feeds_dir, cfg.output_dir = str(tmp_path), str(tmp_path / "out")
    tags = pd.DataFrame({"feed_key": "G", "station_key": [f"G:{s}" for s in "KXY"], "stop_ids": list("KXY"),
                         "station_group_id": [f"G:{s}" for s in "KXY"]})
    return cfg, tags


def test_stay_seated_legs_become_one_through_train(tmp_path):
    cfg, tags = _legs_feed(tmp_path)
    st, trips = C.load_timetable(cfg, "G", tags, DAYS, cache=False)
    t = trips.set_index("trip_id")
    assert C.str_to_mask(t.loc["L0+L1", "mask"]) == WEEKDAYS          # both legs run
    assert C.str_to_mask(t.loc["L1", "mask"]) == WEEKEND              # L1 alone at weekends
    assert "L0" not in t.index                                         # L0 never runs alone
    th = st[st.trip_id == "L0+L1"].sort_values("seq")
    assert th.station_key.tolist() == ["G:K", "G:X", "G:Y"]
    x = th.set_index("station_key").loc["G:X"]
    assert (x.arr_s, x.dep_s) == (9 * 3600, 9 * 3600 + 300)          # arrival of L0, departure of L1


def test_legs_without_stay_seated_link_stay_separate(tmp_path):
    cfg, tags = _legs_feed(tmp_path, transfers=False)
    st, trips = C.load_timetable(cfg, "G", tags, DAYS, cache=False)
    assert set(trips.trip_id) == {"L0", "L1"}


def test_excluded_agency_trips_are_left_out(tmp_path):
    cfg, tags = _legs_feed(tmp_path, transfers=False, agency_of_l1="IC")
    cfg.excluded_agencies = {"G": ["IC"]}
    st, trips = C.load_timetable(cfg, "G", tags, DAYS, cache=False)
    assert set(trips.trip_id) == {"L0"} and set(st.trip_id) == {"L0"}


def test_summarise_one_transfer_and_hub_dependence():
    it = pd.DataFrame({
        "station_key": ["X"] * 3, "T": ["T1", "T1", "T2"], "T_key": ["F:T1", "F:T1", "F:T2"],
        "leg1_trip": ["a", "b", "a"], "leg2_trip": ["c", "c", "d"],
        "total_s": [3600, 4000, 5000], "wait_s": [600, 300, 900],
        "n_days": [7, 7, 7], "mask": ["1111111"] * 3})
    s = C.summarise_one_transfer(it, "station_key", 7).iloc[0]
    assert (s.n_journeys, s.n_first_legs, s.n_second_legs, s.n_hubs) == (3, 2, 2, 2)
    assert s.n_shared_leg == 3                   # a shared by (a,c),(a,d); c shared by (a,c),(b,c)
    per, summ = C.hub_dependence(it, "station_key", 7)
    r = summ.iloc[0]
    assert r.main_hub == "F:T1" and abs(r.main_hub_share - 2 / 3) < 0.01 and r.hubs_for_share == 2


def _legs_for_midnight(second_mask):
    first = pd.DataFrame([{"feed_key": "F", "trip_id": "late", "direction": "outbound", "station_key": "F:T",
                           "group": "G:T", "hub_key": "F:K", "dep_s": 22 * 3600, "arr_s": 23 * 3600 + 50 * 60,
                           "ride_s": 6600, "route_type": "2", "n_days": 3, "mask": "111"}])
    second = pd.DataFrame([{"feed_key": "G", "trip_id": "night", "from_key": "G:T", "from_group": "G:T",
                            "dep_s": 20 * 60, "to_key": "G:X", "to_group": "G:X", "arr_s": 3600, "ride_s": 2400,
                            "route_type": "2", "n_days": second_mask.count("1"), "mask": second_mask}])
    return first, second


def test_transfer_across_midnight_pairs_with_the_next_date():
    first, second = _legs_for_midnight("010")          # the 00:20 train runs on day 1 only
    it = C.one_transfer(first, second, "outbound", 10, 90, 3)
    assert len(it) == 1
    r = it.iloc[0]
    assert r["mask"] == "100" and bool(r["next_day"])       # dated by the first train: day 0
    assert r.wait_s == 30 * 60 and r.end_s == 25 * 3600  # 01:00 next day = 25:00 on day 0's clock
    assert C.one_transfer(first, second, "outbound", 10, 90, 3, cross_midnight=False).empty


def test_same_date_early_departure_is_not_a_midnight_connection():
    first, second = _legs_for_midnight("100")          # 00:20 on day 0 itself: before the 23:50 arrival
    assert C.one_transfer(first, second, "outbound", 10, 90, 3).empty    # no modulo-24 h pairing (PIP-6)


def test_overnight_arrival_is_not_a_same_day_visit(feed):
    cfg, tags, st, trips = feed
    inn = pd.DataFrame([{"station_key": "F:B", "start_s": 22 * 3600, "end_s": 24 * 3600 + 30 * 60, "mask": "1111111"}])
    out = pd.DataFrame([{"station_key": "F:B", "start_s": 18 * 3600, "end_s": 20 * 3600, "mask": "1111111"}])
    assert C.daytrip_days(inn, out, cfg, 7).empty     # left home the evening before: not same-day


def test_timetable_cache_is_per_window(feed, tmp_path):
    import os
    cfg, tags, st, trips = feed
    cfg.output_dir = str(tmp_path / "cache_out")
    C.load_timetable(cfg, "F", tags, DAYS[:3])
    C.load_timetable(cfg, "F", tags, DAYS[2:])
    files = sorted(os.listdir(os.path.join(cfg.out_dir, "timetable")))
    assert len(files) == 4 and any("2026-01-05_2026-01-07" in f for f in files)


def test_staying_on_the_same_train_is_not_a_transfer():
    first, second = _legs_for_midnight("111")
    second = second.assign(feed_key="F", trip_id="late", dep_s=24 * 3600 + 5 * 60, arr_s=25 * 3600)
    assert C.one_transfer(first, second, "outbound", 10, 90, 3).empty      # 15 min stop on one train


def test_train_pieces_with_one_train_number_become_one_trip(tmp_path):
    """BAHN_AT style: RJ 1 published as A->B (daily) and B->C (Mon-Fri); RJ 2 = the vehicle turning back."""
    cal = [_cal("ALL", "1111111"), _cal("WD", "1111100")]
    trips_def = {"p1": ("ALL", "RJ 1", [("A", "10:00"), ("B", "11:00")]),
                 "p2": ("WD", "RJ 1", [("B", "11:03"), ("C", "12:00")]),
                 "p3": ("ALL", "RJ 2", [("B", "11:20"), ("A", "12:20")])}
    st, tr = [], []
    for tid, (sid, name, calls) in trips_def.items():
        tr.append({"route_id": "R", "service_id": sid, "trip_id": tid, "trip_short_name": name, "block_id": "B1"})
        for k, (stop, t) in enumerate(calls):
            st.append({"trip_id": tid, "arrival_time": f"{t}:00", "departure_time": f"{t}:00",
                       "stop_id": stop, "stop_sequence": k + 1})
    with zipfile.ZipFile(tmp_path / "F.zip", "w") as z:
        z.writestr("calendar.txt", _csv(cal))
        z.writestr("routes.txt", _csv([{"route_id": "R", "agency_id": "1", "route_type": 2}]))
        z.writestr("trips.txt", _csv(tr))
        z.writestr("stop_times.txt", _csv(st))
        z.writestr("stops.txt", _csv([{"stop_id": x, "stop_name": x, "stop_lat": 0, "stop_lon": 0} for x in "ABC"]))
    cfg = default_config()
    cfg.feeds, cfg.feeds_dir = {"F": {"filename": "F.zip", "country": "AT"}}, str(tmp_path)
    tags = pd.DataFrame({"feed_key": "F", "station_key": [f"F:{x}" for x in "ABC"], "stop_ids": list("ABC"),
                         "station_group_id": [f"G:{x}" for x in "ABC"]})
    st_, trips_ = C.load_timetable(cfg, "F", tags, DAYS, cache=False)
    t = trips_.set_index("trip_id")
    assert C.str_to_mask(t.loc["p1+p2", "mask"]) == WEEKDAYS          # joined on the days both run
    assert C.str_to_mask(t.loc["p1", "mask"]) == WEEKEND               # the first piece alone at weekends
    assert "p2" not in t.index                                         # no day of its own left
    assert "p3" in t.index and not any("p3" in x and "+" in x for x in t.index)   # turnaround: another train
    j = st_[st_.trip_id == "p1+p2"].sort_values("seq")
    assert list(j.station_key) == ["F:A", "F:B", "F:C"]
    b = j[j.station_key == "F:B"].iloc[0]
    assert (b.arr_s, b.dep_s) == (11 * 3600, 11 * 3600 + 180)        # arrival of p1, departure of p2


def _toy_lau():
    import geopandas as gpd
    from shapely.geometry import box
    rows = [("SK_1", "SK", "Košice - mestská časť Sever", 100, "SK042", 1), ("SK_2", "SK", "Košice - mestská časť Juh", 50, "SK042", 1),
            ("SK_3", "SK", "Bratislava - mestská časť Petržalka", 70, "SK010", 1), ("SK_4", "SK", "Prešov", 80, "SK041", 1),
            ("CZ_9", "CZ", "Košice", 58, "CZ020", 3)]
    return gpd.GeoDataFrame({"GISCO_ID": [r[0] for r in rows], "CNTR_CODE": [r[1] for r in rows],
                             "LAU_NAME": [r[2] for r in rows], "LAU_NAME_NATIONAL": [r[2] for r in rows],
                             "LAU_NAME_LATIN": [r[2] for r in rows], "POP_2025": [r[3] for r in rows],
                             "POP_15_64_2025": [r[3] // 2 for r in rows], "POP_2024": [r[3] for r in rows],
                             "AREA_KM2": [1.0] * 5, "POP_DENS_2024": [0.0] * 5, "NUTS3_ID": [r[4] for r in rows],
                             "NUTS2_ID": [r[4][:4] for r in rows], "DGURBA": [r[5] for r in rows],
                             "TERRITORIAL_NOTE": ""}, geometry=[box(i, 0, i + 1, 1) for i in range(5)], crs="EPSG:3035")


def test_city_units_merge_districts_and_skip_the_czech_village():
    cfg = default_config()
    L = _toy_lau()
    m = C.city_unit_map(cfg, L)
    assert m == {"SK_1": "SK_CITY_Košice", "SK_2": "SK_CITY_Košice", "SK_3": "SK_CITY_Bratislava"}   # CZ_9 not matched
    U = C.lau_with_city_units(L, cfg).set_index("GISCO_ID")
    assert U.loc["SK_CITY_Košice", "POP_2025"] == 150 and U.loc["SK_CITY_Košice", "POP_15_64_2025"] == 75
    assert U.loc["SK_CITY_Košice", "POP_DENS_2024"] == 75 and "SK_1" not in U.index and "CZ_9" in U.index
    assert C.hub_city_laus(cfg) == {"SK_CITY_Košice"}


def test_tags_take_the_city_unit():
    cfg = default_config()
    tags = pd.DataFrame({"station_key": ["a", "b", "c"], "lau_gisco_id": ["SK_2", "SK_3", "SK_4"],
                         "lau_name_national": ["Košice - mestská časť Juh", "Bratislava - mestská časť Petržalka", "Prešov"]})
    t = C.tags_with_city_units(tags, cfg, _toy_lau())
    assert list(t.lau_gisco_id) == ["SK_CITY_Košice", "SK_CITY_Bratislava", "SK_4"]
    assert list(t.lau_name_national) == ["Košice", "Bratislava", "Prešov"]


def test_tags_take_the_city_unit_from_an_already_merged_layer():
    cfg = default_config()
    tags = pd.DataFrame({"station_key": ["a", "b"], "lau_gisco_id": ["SK_2", "SK_4"],
                         "lau_name_national": ["Košice - mestská časť Juh", "Prešov"], "lau_pop_2025": [50, 80]})
    t = C.tags_with_city_units(tags, cfg, C.lau_with_city_units(_toy_lau(), cfg))
    assert list(t.lau_gisco_id) == ["SK_CITY_Košice", "SK_4"] and list(t.lau_pop_2025) == [150, 80]
