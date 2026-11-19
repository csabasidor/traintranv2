"""Tests for traintranv2.config destination profiles: Košice stays the default, Bratislava is switchable."""
import pytest

from traintranv2 import config as C


def test_kosice_is_the_default_and_unchanged(monkeypatch):
    monkeypatch.delenv("TRAINTRAN_DESTINATION", raising=False)
    monkeypatch.delenv("TRAINTRAN_CITY_SLUG", raising=False)
    cfg = C.default_config()
    assert cfg.destination == "kosice" and cfg.city_slug == "kosice"
    assert cfg.hub_station_keys == ["ZSR_SK:5613600"] and cfg.hub_stop_id == "5613600"
    assert cfg.hub_city == "Košice" and cfg.hub_nuts3 == "SK042" and cfg.hub_latlon == (48.72351, 21.268602)
    assert cfg.validation_sheet == "data/manual/validation_journeys.csv" and cfg.legacy_dir == "output/ke"
    assert cfg.out_dir.replace("\\", "/").endswith("output/kosice")


def test_bratislava_by_env_and_by_argument(monkeypatch):
    monkeypatch.delenv("TRAINTRAN_CITY_SLUG", raising=False)
    monkeypatch.setenv("TRAINTRAN_DESTINATION", "Bratislava")
    for cfg in (C.default_config(), C.default_config("bratislava")):
        assert cfg.city_slug == "bratislava" and cfg.hub_city == "Bratislava" and cfg.hub_nuts3 == "SK010"
        assert cfg.hub_station_keys == ["ZSR_SK:5613206", "ZSR_SK:5614576", "ZSR_SK:5614616"]
        assert cfg.hub_stop_id == "5613206"
        assert cfg.legacy_dir is None and cfg.validation_sheet.endswith("_bratislava.csv")
        assert cfg.shared_dir.replace("\\", "/").endswith("output/kosice")


def test_unknown_destination_raises():
    with pytest.raises(ValueError):
        C.default_config("vienna")
