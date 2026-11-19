"""
Tests for notebook 01b's station catalog and cross-feed identity: parent-first merging, the
name + 2 km rule, UIC code derivation, group links per tier, the code-conflict guard, manual
corrections per feed, and the legacy alias imports.
"""

import zipfile

import pandas as pd
import pytest

from traintranv2.config import default_config
from traintranv2.nb01b_stations import (
    build_station_catalog, link_station_groups, name_dedup, uic_code,
)


def _feed(path, stops, stop_times_ids):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("stops.txt", "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
                   + "".join(f"{a},{b},{c},{d},{e},{f}\n" for a, b, c, d, e, f in stops))
        z.writestr("stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                   + "".join(f"T,08:00:00,08:00:00,{s},{i}\n" for i, s in enumerate(stop_times_ids)))


@pytest.fixture()
def cfg(tmp_path):
    c = default_config()
    c.feeds_dir = str(tmp_path)
    c.feeds = {"X": {"filename": "x.zip", "country": "AT"}}
    _feed(tmp_path / "x.zip", [
        ("P1", "Wien Hbf", 48.185, 16.376, "1", ""),           # parent
        ("c1", "Gleis 1", 48.1851, 16.3761, "0", "P1"),         # platforms
        ("c2", "Gleis 2", 48.1852, 16.3762, "", "P1"),
        ("c3", "Gleis 3", 48.1853, 16.3763, "0", "P1"),
        ("e1", "Zugang", 48.1850, 16.3760, "2", "P1"),          # entrance: dropped
        ("s1", "Dorf", 48.000, 16.000, "", ""),                 # same name, 0.5 km -> merged
        ("s2", "Dorf", 48.004, 16.000, "", ""),
        ("s3", "Dorf", 48.050, 16.000, "", ""),                 # 5.6 km -> separate
    ], ["c1", "c2", "s1", "s3"])
    return c


def test_catalog_parent_first_and_name_rule(cfg):
    c = build_station_catalog(cfg, "X").set_index("station_key")
    assert c.at["X:P1", "stop_name"] == "Wien Hbf" and c.at["X:P1", "dedup_method"] == "parent"
    assert sorted(c.at["X:P1", "stop_ids"].split(";")) == ["c1", "c2"]     # entrance and unused c3 dropped
    assert c.at["X:s1", "dedup_method"] == "name_2km" and c.at["X:s1", "stop_ids"] == "s1;s2"
    assert c.at["X:s3", "dedup_method"] == "single"
    assert len(c) == 3 and bool(c.at["X:P1", "in_trips"])


def test_catalog_keys_are_stable(cfg):
    a = build_station_catalog(cfg, "X")["station_key"].tolist()
    b = build_station_catalog(cfg, "X")["station_key"].tolist()
    assert a == b


def test_name_dedup_follows_input_order():
    stops = [{"stop_name": "A", "stop_lat": "48.0", "stop_lon": "17.0"},
             {"stop_name": "a ", "stop_lat": "48.001", "stop_lon": "17.0"},
             {"stop_name": "A", "stop_lat": "49.0", "stop_lon": "17.0"}]
    assert [len(g) for g in name_dedup(stops)] == [2, 1]


def test_uic_code_derivation():
    assert uic_code("ZSR_SK", ["5433014"]) == "5433014"
    assert uic_code("UKRZ_UA", ["x", "2238010"]) == "2238010"
    assert uic_code("DRAHY_CZ", ["czptt:stop:CZ:33014:platform:1"], "czptt:stop:CZ:33014") == "5433014"
    assert uic_code("DRAHY_CZ", ["x"], "czptt:stop:SK:16446") == "5616446"     # its Slovak stops: 56
    assert uic_code("DRAHY_CZ", ["x"], "czptt:stop:PL:05549") == "5105549"
    assert uic_code("BAHN_AT", ["at:43:3101:0:1"], "Pat:43:3101") == ""


def _tags(rows):
    cols = ["station_key", "feed_key", "stop_name", "stop_lat", "stop_lon", "stop_ids", "uic_code",
            "in_scope", "lau_gisco_id", "nuts_rg_01_country_id"]
    return pd.DataFrame(rows, columns=cols)


def test_groups_by_code_place_and_conflict():
    c = default_config()
    t = _tags([
        ("ZSR_SK:5434124", "ZSR_SK", "Bohumín", 49.904, 18.358, "5434124", "5434124", True, "CZ_599051", "CZ"),
        ("DRAHY_CZ:czptt:stop:CZ:34124", "DRAHY_CZ", "Bohumín", 49.9045, 18.3585, "a", "5434124", True, "CZ_599051", "CZ"),
        ("PL_kasznia:1", "PL_kasznia", "Bohumín", 49.9042, 18.3590, "1_RAIL", "", True, "CZ_599051", "CZ"),
        ("BAHN_AT:x", "BAHN_AT", "Bohumín", 49.95, 18.50, "x", "", True, "CZ_599051", "CZ"),      # 11 km: no place link
        ("UKRZ_UA:5434124", "UKRZ_UA", "Bohumin", 50.5, 19.0, "5434124", "5434124", True, "PL_9", "PL"),  # code, far
    ])
    out, links, conflicts, review = link_station_groups(t, c, manual_path=None)
    g = out.set_index("station_key")["station_group_id"]
    assert g["ZSR_SK:5434124"] == g["DRAHY_CZ:czptt:stop:CZ:34124"] == g["PL_kasznia:1"]
    assert g["BAHN_AT:x"] != g["ZSR_SK:5434124"]
    assert g["UKRZ_UA:5434124"] != g["ZSR_SK:5434124"] and len(conflicts) >= 1
    assert set(links["tier"]) >= {"code", "place"}


def test_manual_correction_only_for_its_feed(tmp_path):
    from traintranv2.nb01b_stations import _load_manual_lau_matches
    p = tmp_path / "m.csv"
    pd.DataFrame({"stop_id": ["1", "2"], "gisco_id": ["SK_1", "PL_1"], "feed_key": ["", "PL_kasznia"],
                  "conversion": ["ok", "ok"]}).to_csv(p, index=False)
    m = _load_manual_lau_matches(str(p))
    assert m == {("ZSR_SK", "1"): "SK_1", ("PL_kasznia", "2"): "PL_1"}


def test_package_is_independent_of_traintran():
    import sys
    import traintranv2.nb01a_feeds, traintranv2.nb01b_stations  # noqa: F401
    for mod in ("traintranv2.nb01a_feeds", "traintranv2.nb01b_stations", "traintranv2.config"):
        src = open(sys.modules[mod].__file__, encoding="utf-8").read()
        assert "from traintran" not in src and "import traintran\n" not in src, mod


def test_relative_imports_resolve_inside_traintranv2():
    """Every `from .x import` (also lazy ones inside functions) names a module of this package."""
    import os, re
    pkg = os.path.dirname(os.path.dirname(__file__))
    have = {f[:-3] for f in os.listdir(pkg) if f.endswith(".py")}
    for f in have:
        src = open(os.path.join(pkg, f + ".py"), encoding="utf-8").read()
        for mod in re.findall(r"from \.(\w+) import", src):
            assert mod in have, f"{f}.py imports missing module .{mod}"


def test_unused_children_kept_when_the_station_has_no_used_stop(tmp_path):
    c = default_config()
    c.feeds_dir = str(tmp_path)
    c.feeds = {"Y": {"filename": "y.zip", "country": "AT"}}
    _feed(tmp_path / "y.zip", [
        ("P", "Graz Hauptbahnhof", 47.07, 15.42, "1", ""),
        ("g1", "Graz Hbf", 47.0701, 15.4201, "0", "P"),        # used, other name: kept
        ("b1", "Bus", 47.0702, 15.4202, "0", "P"),             # unused: dropped
        ("Q", "Leer", 47.5, 15.5, "1", ""),
        ("q1", "Leer", 47.5001, 15.5001, "0", "Q"),            # station without trips keeps its stop
    ], ["g1"])
    cat = build_station_catalog(c, "Y").set_index("station_key")
    assert cat.at["Y:P", "stop_ids"] == "g1"
    assert cat.at["Y:Q", "stop_ids"] == "q1" and not cat.at["Y:Q", "in_trips"]


def _pair_tags():
    return _tags([
        ("ZSR_SK:5609451", "ZSR_SK", "Skalité p.Poľanou", 49.5000, 18.9000, "5609451", "5609451", True, "SK_509451", "SK"),
        ("PL_REG:9", "PL_REG", "Skalité pod Poľanou", 49.5015, 18.9010, "9", "", True, "SK_509451", "SK"),
        ("ZSR_SK:5613556", "ZSR_SK", "Bratislava predm.", 48.1880, 17.1300, "5613556", "5613556", True, "SK_529346", "SK"),
        ("UKRZ_UA:5613596", "UKRZ_UA", "Bratislava-Vinohrady", 48.1868, 17.1336, "5613596", "5613596", True, "SK_529346", "SK"),
    ])


def test_place_link_with_slovak_abbreviations_and_review_of_close_pairs():
    c = default_config()
    out, links, _, review = link_station_groups(_pair_tags(), c, manual_path=None)
    g = out.set_index("station_key")["station_group_id"]
    assert g["ZSR_SK:5609451"] == g["PL_REG:9"]
    assert g["ZSR_SK:5613556"] != g["UKRZ_UA:5613596"]
    assert len(review) == 1 and set(review.iloc[0][["a", "b"]]) == {"ZSR_SK:5613556", "UKRZ_UA:5613596"}


def test_manual_group_pairs_accept_and_reject(tmp_path):
    c = default_config()
    p = tmp_path / "g.csv"
    pd.DataFrame({"a": ["ZSR_SK:5613556", "PL_REG:9"], "b": ["UKRZ_UA:5613596", "ZSR_SK:5609451"],
                  "decision": ["accept", "reject"], "note": ["", ""]}).to_csv(p, index=False)
    out, links, _, review = link_station_groups(_pair_tags(), c, manual_path=str(p))
    g = out.set_index("station_key")["station_group_id"]
    assert g["ZSR_SK:5613556"] == g["UKRZ_UA:5613596"] and "manual" in set(links["tier"])
    assert g["ZSR_SK:5609451"] != g["PL_REG:9"] and review.empty
