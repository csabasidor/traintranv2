"""
Tests for foreign-station matching: name variants, the fuzzy tier, the automatic decision rule
(name AND same LAU AND within cfg.match_auto_max_km), position candidates, the station family
and the reviewed manual decisions.
"""

import pandas as pd
import pytest

from traintranv2.config import default_config
from traintranv2.nb01b_stations import (
    _match_station, _name_variants, evaluate_hit, load_manual_station_matches,
)


@pytest.fixture()
def cfg():
    c = default_config()
    c.fuzzy_threshold = 0.90
    c.match_auto_max_km = 0.5
    c.match_candidate_km = 1.0
    return c


def _stop(sid, name, lat, lon):
    return {"stop_id": sid, "stop_name": name, "stop_lat": str(lat), "stop_lon": str(lon),
            "location_type": "", "parent_station": ""}


def test_fuzzy_tier_fires_below_one():
    stops = [_stop("1", "Ostrava hlavni nadrazi", 49.8, 18.3)]
    assert _match_station("Ostrava hlavní nádraží", stops, 0.9)[0]["match_type"] == "exact"
    hit = _match_station("Ostrava hlavni nadrazi.", stops, 0.9)
    assert hit and hit[0]["match_type"] == "sequence"           # dead at 1.0 (CF-26)
    assert _match_station("Ostrava hlavni nadrazi.", stops, 1.0) == []


def test_country_rewrites(cfg):
    assert "Brno hlavní nádraží" in _name_variants("Brno hl.n.", "CZ", cfg)
    assert "Lipník nad Bečvou" in _name_variants("Lipník n.Bečvou", "CZ", cfg)
    assert "Baden Bahnhof" in _name_variants("Baden b.Wien", "AT", cfg)
    assert "Innsbruck Hauptbahnhof" in _name_variants("Innsbruck Hbf", "AT", cfg)


def _hit(sid, lat, lon, mtype="exact", score=1.0):
    return {"feed_stop_id": sid, "feed_stop_name": "x", "feed_stop_lat": str(lat), "feed_stop_lon": str(lon),
            "feed_location_type": "", "feed_parent_station": "", "match_type": mtype, "score": score}


def test_rule_same_lau_and_close_is_auto(cfg):
    e = evaluate_hit(_hit("A", 48.0005, 21.0), 48.0, 21.0, "SK_1", {"A": "SK_1"}, cfg, 0.9)
    assert e["auto_ok"] and e["reason"] == ""


def test_rule_same_name_far_away_goes_to_review(cfg):
    e = evaluate_hit(_hit("A", 48.45, 21.0), 48.0, 21.0, "SK_1", {"A": "SK_1"}, cfg, 0.9)
    assert not e["auto_ok"] and "too_far" in e["reason"]


def test_rule_exact_name_close_but_other_lau_goes_to_review(cfg):
    e = evaluate_hit(_hit("A", 48.001, 21.0), 48.0, 21.0, "SK_1", {"A": "SK_2"}, cfg, 0.9)
    assert not e["auto_ok"] and e["reason"] == "different_lau" and not e["same_lau"]


def test_rule_exact_name_same_lau_but_over_half_a_km_goes_to_review(cfg):
    e = evaluate_hit(_hit("A", 48.0054, 21.0), 48.0, 21.0, "SK_1", {"A": "SK_1"}, cfg, 0.9)   # 0.6 km
    assert not e["auto_ok"] and e["reason"] == "too_far"


def test_rule_fuzzy_name_close_but_other_lau_goes_to_review(cfg):
    e = evaluate_hit(_hit("A", 48.001, 21.0, "sequence", 0.95), 48.0, 21.0, "SK_1", {"A": "SK_2"}, cfg, 0.9)
    assert not e["auto_ok"] and e["reason"] == "different_lau"


def test_rule_exact_name_other_lau_and_far_goes_to_review(cfg):
    e = evaluate_hit(_hit("A", 48.45, 21.0), 48.0, 21.0, "SK_1", {"A": "SK_2"}, cfg, 0.9)
    assert not e["auto_ok"] and e["reason"] == "too_far;different_lau"


def test_rule_fuzzy_below_threshold_goes_to_review(cfg):
    e = evaluate_hit(_hit("A", 48.0, 21.0, "sequence", 0.85), 48.0, 21.0, "SK_1", {"A": "SK_1"}, cfg, 0.9)
    assert not e["auto_ok"] and "name_below_threshold" in e["reason"]


def test_manual_decisions_file(tmp_path):
    p = tmp_path / "m.csv"
    pd.DataFrame({"station_stop_id": ["5613600", "123"], "feed_key": ["BAHN_AT", "DRAHY_CZ"],
                  "feed_stop_id": ["Pat:1", "cz:9"], "decision": ["accept", "reject"], "note": ["", ""]}).to_csv(p, index=False)
    m = load_manual_station_matches(str(p))
    assert m[("5613600", "BAHN_AT")]["decision"] == "accept"
    assert m[("123", "DRAHY_CZ")]["decision"] == "reject"
    pd.DataFrame({"station_stop_id": ["1"], "feed_key": ["X"], "feed_stop_id": ["y"],
                  "decision": ["maybe"]}).to_csv(p, index=False)
    with pytest.raises(ValueError):
        load_manual_station_matches(str(p))


def test_matching_takes_inputs_not_files():
    import inspect
    from traintranv2.nb01b_stations import match_foreign_stations
    params = inspect.signature(match_foreign_stations).parameters
    assert {"stations", "feed_stop_tags"} <= set(params)          # CF-24: no hard-coded input file


def test_station_family_keeps_only_station_and_boarding_stops():
    from traintranv2.nb01b_stations import _expand_station_family
    stops = [
        {"stop_id": "P", "stop_name": "Bruck/Leitha Bahnhof", "location_type": "1", "parent_station": ""},
        {"stop_id": "P1", "stop_name": "Bruck/Leitha Bahnhof", "location_type": "0", "parent_station": "P"},
        {"stop_id": "P2", "stop_name": "Bruck/Leitha Bahnhof", "location_type": "", "parent_station": "P"},
        {"stop_id": "E1", "stop_name": "Zugang Bahnhof", "location_type": "2", "parent_station": "P"},
        {"stop_id": "N1", "stop_name": "P+R", "location_type": "3", "parent_station": "P"},
    ]
    assert sorted(s["stop_id"] for s in _expand_station_family("P1", stops)) == ["P", "P1", "P2"]


def test_country_tag_and_polish_abbreviations():
    from traintranv2.nb01b_stations import _name_hits
    stops = [_stop("76869", "Zwardoń", 49.5, 19.0), _stop("68403", "Wodzisław Śląski", 50.0, 18.4)]
    c = default_config()
    assert _name_hits("Zwardon(PL)", "PL", stops, 0.9, c)[0]["feed_stop_id"] == "76869"
    hit = _name_hits("Wodzislaw Sl.", "PL", stops, 0.9, c)[0]
    assert hit["feed_stop_id"] == "68403" and hit["match_type"] == "exact"


def test_core_name_tier_drops_generic_station_words():
    from traintranv2.nb01b_stations import core_name
    assert core_name("Szombathely pályaudvar") == core_name("Szombathely")
    assert core_name("Šatov, železniční stanice") == "satov"
    assert core_name("Lysá pod Makytou z") == "lysa pod makytou"
    assert core_name("Skalité zastávka") != core_name("Skalité")          # zastávka is not generic
    hit = _match_station("Sopron", [_stop("1", "Sopron pályaudvar", 47.68, 16.58)], 0.9)
    assert hit and hit[0]["match_type"] == "core"


def test_position_candidates_same_lau_first():
    from traintranv2.nb01b_stations import position_candidates
    st = [{"rep": "far", "name": "B", "lat": 48.0080, "lon": 21.0, "lau": "SK_1"},     # 0.9 km, same LAU
          {"rep": "near", "name": "A", "lat": 48.0010, "lon": 21.0, "lau": "SK_2"},    # 0.1 km, other LAU
          {"rep": "out", "name": "C", "lat": 48.0200, "lon": 21.0, "lau": "SK_1"}]     # 2.2 km
    got = position_candidates(48.0, 21.0, "SK_1", st, 1.0)
    assert [s["rep"] for _, _, s in got] == ["far", "near"]


def _cat_and_tags():
    feed = [
        {"stop_id": "P", "stop_name": "Wien Meidling", "stop_lat": "48.1743", "stop_lon": "16.3319",
         "location_type": "1", "parent_station": ""},
        {"stop_id": "P1", "stop_name": "Wien Meidling", "stop_lat": "48.1743", "stop_lon": "16.3319",
         "location_type": "", "parent_station": "P"},
        {"stop_id": "PB", "stop_name": "Bus an", "stop_lat": "48.1745", "stop_lon": "16.3322",
         "location_type": "", "parent_station": "P"},                        # not in the catalog
        {"stop_id": "Q", "stop_name": "Wien Grillgasse", "stop_lat": "48.1735", "stop_lon": "16.4170",
         "location_type": "", "parent_station": ""},
    ]
    stations = pd.DataFrame([
        {"station_key": "ZSR_SK:1", "feed_key": "ZSR_SK", "stop_name": "Wien Meidling", "stop_lat": 48.1758,
         "stop_lon": 16.3359, "stop_ids": "1", "nuts_rg_01_country_id": "AT", "lau_gisco_id": "AT_90001", "uic_code": ""},
        {"station_key": "ZSR_SK:2", "feed_key": "ZSR_SK", "stop_name": "Wien Simmering Ost", "stop_lat": 48.1736,
         "stop_lon": 16.4180, "stop_ids": "2", "nuts_rg_01_country_id": "AT", "lau_gisco_id": "AT_90001", "uic_code": ""},
        {"station_key": "BAHN_AT:P", "feed_key": "BAHN_AT", "stop_name": "Wien Meidling", "stop_lat": 48.1743,
         "stop_lon": 16.3319, "stop_ids": "P1", "nuts_rg_01_country_id": "AT", "lau_gisco_id": "AT_90001", "uic_code": ""},
        {"station_key": "BAHN_AT:Q", "feed_key": "BAHN_AT", "stop_name": "Wien Grillgasse", "stop_lat": 48.1735,
         "stop_lon": 16.4170, "stop_ids": "Q", "nuts_rg_01_country_id": "AT", "lau_gisco_id": "AT_90001", "uic_code": ""},
    ])
    return feed, stations


def test_match_expands_to_catalog_station_and_offers_position_candidates(monkeypatch):
    import traintranv2.nb01b_stations as m
    feed, stations = _cat_and_tags()
    monkeypatch.setattr(m, "_load_stops_from_zip", lambda p: [dict(s) for s in feed])
    c = default_config()
    c.domestic_feed, c.search_countries = "ZSR_SK", ["AT"]
    c.country_feeds = {"AT": ["BAHN_AT"]}
    c.feeds = {"ZSR_SK": {"filename": "x"}, "BAHN_AT": {"filename": "y"}}
    tags = pd.DataFrame({"feed_key": ["BAHN_AT"] * 4, "stop_id": ["P", "P1", "PB", "Q"], "GISCO_ID": ["AT_90001"] * 4})
    out = m.match_foreign_stations(c, stations, tags, manual_path=None)
    acc = out[out.station_id == "ZSR_SK:1"]
    assert set(acc.feed_stop_id) == {"P", "P1"} and set(acc.status) == {"auto"}      # no "Bus an"
    assert set(acc.feed_station_name) == {"Wien Meidling"}
    rev = out[out.station_id == "ZSR_SK:2"].iloc[0]
    assert rev.status == "review" and rev.reason == "position_candidate" and rev.suggested_feed_stop_id == "Q"
