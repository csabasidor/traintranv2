"""
Tests for the GeoJSON-based station tagging and the feed helpers.

Small synthetic inputs only (a three-polygon LAU subset written to a temp GeoJSON, a tiny GTFS
zip), so they pin the behaviour without the real subset or feeds.
"""

import pandas as pd
import pytest

from traintranv2.config import default_config
from traintranv2.nb01b_stations import (
    _LAU_CACHE, _name_contains, _name_score, _ua_fallback, tag_points, tag_stops,
)
from traintranv2.nb01a_feeds import norm_name


# --- norm_name (CF-27) -------------------------------------------------------

@pytest.mark.parametrize("raw,folded", [
    ("Łódź Fabryczna", "lodz fabryczna"), ("Gießen", "giessen"), ("Ørsted", "orsted"),
    ("Đakovo", "dakovo"), ("Košice", "kosice"), ("  Ostrava-Svinov ", "ostrava-svinov"),
])
def test_norm_name_folds_letters_nfd_leaves_alone(raw, folded):
    assert norm_name(raw) == folded


# --- name check against national and Latin names ------------------------------

def test_name_score_takes_the_best_of_several_names():
    assert _name_score("Chop", ("Чопська", "Chopska")) > _name_score("Chop", "Чопська")
    assert _name_score("Chop", ("Чопська", "Chopska")) == _name_score("Chop", "Chopska")


def test_name_contains_matches_city_prefix_of_station_name():
    assert _name_contains("Łódź Fabryczna", "Łódź") is True
    assert _name_contains("Wien Hbf", ("Wien", "Wien")) is True
    assert _name_contains("Barca", "Bar") is False          # whole tokens only
    assert _name_contains("Barca", "Košice - mestská časť Barca") is True


def test_ua_fallback_only_knows_the_three_stations():
    assert _ua_fallback("Chop")["lau_gisco_id"] == "UA_ZAK_1"
    assert _ua_fallback("Mukatschewo") is not None
    assert _ua_fallback("Košice") is None


# --- tag_points / tag_stops on a synthetic subset ------------------------------

# Synthetic LAUs in Slovak coordinates (the neighbour search measures km in EPSG:5514).
@pytest.fixture()
def cfg(tmp_path):
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    lau = gpd.GeoDataFrame({
        "GISCO_ID": ["SK_1", "SK_2", "DE_1"], "CNTR_CODE": ["SK", "SK", "DE"],
        "LAU_CODE": ["1", "2", "1"], "LAU_NAME_NATIONAL": ["Alfa", "Beta", "Gamma"],
        "LAU_NAME_LATIN": ["Alfa", "Beta", "Gamma"], "NUTS3_ID": ["SK010", "SK010", "DE111"],
        "NUTS2_ID": ["SK01", "SK01", "DE11"], "DGURBA": [1, 3, 2], "POP_2024": [100, 50, 10],
        "AREA_KM2": [1.0, 1.0, 1.0], "POP_2025": [101, 51, 11], "POP_15_64_2025": [70, 30, 7],
        "POP_65PLUS_2025": [20, 15, 3],
    }, geometry=[box(20, 48, 21, 49), box(21, 48, 22, 49), box(25, 53, 26, 54)], crs=4326)
    path = tmp_path / "lau.geojson"
    lau.to_file(path, driver="GeoJSON")
    c = default_config()
    c.lau_subset = str(path)
    c.lau_manual_matches_file = str(tmp_path / "none.csv")
    _LAU_CACHE.clear()
    return c


def test_tag_points_scope_and_outside(cfg):
    pts = pd.DataFrame({"stop_id": ["a", "b", "c", "d"], "stop_name": ["x"] * 4,
                        "stop_lat": [48.5, 53.5, 57.0, None], "stop_lon": [20.5, 25.5, 29.0, None]})
    t = tag_points(pts, cfg).set_index("stop_id")
    assert t.at["a", "GISCO_ID"] == "SK_1" and bool(t.at["a", "in_scope"])
    assert t.at["b", "GISCO_ID"] == "DE_1" and not bool(t.at["b", "in_scope"])   # DE not a study country
    assert not bool(t.at["c", "in_scope"]) and not bool(t.at["d", "in_scope"])


def test_tag_stops_moves_station_to_neighbour_by_name(cfg):
    # 'Beta' station sits just inside Alfa's polygon -> the neighbour Beta wins on its name.
    pts = pd.DataFrame({"stop_id": ["s"], "stop_name": ["Beta"], "stop_lat": [48.5], "stop_lon": [20.98]})
    t = tag_stops(pts, cfg).iloc[0]
    assert t["lau_gisco_id"] == "SK_2" and t["lau_match_method"] == "contains_neighbor"
    assert t["nuts3_id"] == "SK010" and t["lau_code"] == "2" and int(t["degurba"]) == 3


def test_manual_correction_keyed_on_member_stop_id(cfg, tmp_path):
    pd.DataFrame({"stop_id": ["999"], "gisco_id": ["SK_2"], "conversion": ["ok"]}).to_csv(
        tmp_path / "manual.csv", index=False)
    cfg.lau_manual_matches_file = str(tmp_path / "manual.csv")
    pts = pd.DataFrame({"stop_id": ["S00001"], "stop_name": ["Alfa"], "stop_lat": [48.5],
                        "stop_lon": [20.5], "stop_ids": ["111;999"]})
    t = tag_stops(pts, cfg).iloc[0]
    assert t["lau_gisco_id"] == "SK_2" and t["lau_match_method"] == "manual"


def test_lau_neighbor_finder_uses_metric_radius():
    """Search radius is a true km circle in the metric CRS (Kosice latitude, east-west)."""
    import geopandas as gpd
    from shapely.geometry import box
    from traintranv2.config import default_config
    from traintranv2.nb01b_stations import lau_neighbor_finder

    cfg = default_config()
    assert cfg.lau_metric_crs == "EPSG:5514" and cfg.lau_neighbor_radius_km == 2.0
    # a small square around 21.30E 48.70N; 1 deg longitude here is ~73.5 km
    lau = gpd.GeoDataFrame({"GISCO_ID": ["X"]}, geometry=[box(21.30, 48.70, 21.31, 48.71)], crs=4326)
    near = lau_neighbor_finder(lau, cfg)
    assert near(21.30 - 1.5 / 73.5, 48.705) == ["X"]     # 1.5 km west of the edge
    assert near(21.30 - 2.5 / 73.5, 48.705) == []        # 2.5 km west: outside (0.05 deg would have found it)


def test_polygon_only_country_keeps_polygon_lau(cfg):
    """In a lau_polygon_only_countries country the polygon LAU is taken without a name check."""
    cfg.lau_polygon_only_countries = ["SK"]
    pts = pd.DataFrame({"stop_id": ["s"], "stop_name": ["Beta"], "stop_lat": [48.5], "stop_lon": [20.98]})
    t = tag_stops(pts, cfg).iloc[0]
    assert t["lau_gisco_id"] == "SK_1" and t["lau_match_method"] == "polygon_accepted"
    assert t["lau_tag_source"] == "polygon"
