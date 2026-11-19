"""
Tests for notebook 01a's feed helpers: feed file names, service windows and feed roles.
"""

import zipfile

from traintranv2.config import default_config
from traintranv2.nb01a_feeds import feed_roles, feed_zip_path, pair_windows


def _zip_with_calendar(path, start, end, trips_from=None):
    """One daily rail trip on service A (start..end). With ``trips_from``, a second calendar row B
    declares start..end but carries no trips, and A only runs from ``trips_from``: a late snapshot
    whose calendar keeps the declared span while the trips of the months already run are gone."""
    cal = ("service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
           f"A,1,1,1,1,1,1,1,{trips_from or start},{end}\n")
    if trips_from:
        cal += f"B,1,1,1,1,1,1,1,{start},{end}\n"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("calendar.txt", cal)
        z.writestr("calendar_dates.txt", "service_id,date,exception_type\n")
        z.writestr("stops.txt", "stop_id,stop_name,stop_lat,stop_lon\n")
        z.writestr("routes.txt", "route_id,agency_id,route_type\nR,1,2\n")
        z.writestr("trips.txt", "route_id,service_id,trip_id\nR,A,t1\n")


def test_feed_zip_path_uses_filename_and_pair_windows(tmp_path):
    c = default_config()
    c.feeds_dir = str(tmp_path)
    c.feeds = {"HOME": {"filename": "home.gtfs.zip", "country": "SK"},
               "OTHER": {"filename": "other.zip", "country": "HU"},
               "NOOVER": {"filename": "noover.zip", "country": "PL"}}
    assert feed_zip_path(c, "HOME").endswith("home.gtfs.zip")
    _zip_with_calendar(tmp_path / "home.gtfs.zip", "20260101", "20261231")
    _zip_with_calendar(tmp_path / "other.zip", "20260201", "20270101")
    _zip_with_calendar(tmp_path / "noover.zip", "20280101", "20280201")
    c.domestic_feed = "HOME"
    w = pair_windows(c)
    assert w["HOME"]["days"] == 365
    assert (w["OTHER"]["start"], w["OTHER"]["end"], w["OTHER"]["days"]) == ("2026-02-01", "2026-12-31", 334)
    assert w["NOOVER"]["days"] == 0


def test_feed_roles_marks_the_domestic_feed(tmp_path):
    c = default_config()
    c.feeds_dir = str(tmp_path)
    c.feeds = {"HOME": {"filename": "home.gtfs.zip", "country": "SK"},
               "OTHER": {"filename": "other.zip", "country": "HU"}}
    c.domestic_feed = "HOME"
    _zip_with_calendar(tmp_path / "home.gtfs.zip", "20260101", "20261231")
    _zip_with_calendar(tmp_path / "other.zip", "20260201", "20270101")
    r = feed_roles(c).set_index("feed_key")
    assert r.at["HOME", "role"] == "domestic" and r.at["OTHER", "role"] == "foreign"
    assert r.at["HOME", "window_basis"].startswith("service span") and r.at["OTHER", "window_days"] == 334


def test_window_follows_the_trains_not_the_declared_calendar(tmp_path):
    c = default_config()
    c.feeds_dir = str(tmp_path)
    c.feeds = {"HOME": {"filename": "home.zip", "country": "SK"},
               "LATE": {"filename": "late.zip", "country": "AT"}}
    c.domestic_feed = "HOME"
    _zip_with_calendar(tmp_path / "home.zip", "20260101", "20261231")
    _zip_with_calendar(tmp_path / "late.zip", "20260101", "20261231", trips_from="20260901")
    w = pair_windows(c)
    assert (w["LATE"]["start"], w["LATE"]["days"]) == ("2026-09-01", 122)
    assert w["LATE"]["calendar_start"] == "2026-01-01"
