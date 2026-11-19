"""Tests for traintranv2.nb01c_rail_network on synthetic lines placed in Slovakia (EPSG:3035 metric)."""
import numpy as np
import pandas as pd
import pytest

from traintranv2.config import default_config
from traintranv2 import nb01c_rail_network as R

gpd = pytest.importorskip("geopandas")
from shapely.geometry import LineString  # noqa: E402

LAT = 48.7                       # 1 deg lon ~ 73.6 km, 1 deg lat ~ 111.2 km here
KM_LON = 1 / 73.6


@pytest.fixture()
def cfg():
    return default_config()


def _ways(lines_ll, cfg, ids=None, railway="rail"):
    g = gpd.GeoDataFrame({"osm_id": ids or [str(i) for i in range(len(lines_ll))], "railway": railway},
                         geometry=[LineString(c) for c in lines_ll], crs=4326)
    return g.to_crs(cfg.rail_metric_crs).reset_index(drop=True)


def _tags(points, in_scope=True):
    return pd.DataFrame({"feed_key": "ZSR_SK", "station_key": [f"ZSR_SK:{i}" for i in range(len(points))],
                         "stop_ids": [str(i) for i in range(len(points))],
                         "stop_lon": [p[0] for p in points], "stop_lat": [p[1] for p in points],
                         "in_scope": str(in_scope)})


def test_type_filter_keeps_tez_light_rail_only_by_ref(cfg):
    raw = pd.DataFrame({"railway": ["rail", "narrow_gauge", "light_rail", "light_rail", "tram", "abandoned"],
                        "other_tags": ['"gauge"=>"1435"', None, '"ref"=>"112D","gauge"=>"1000"',
                                       '"ref"=>"U1"', None, None]})
    kept, excluded = R.select_ways(raw, cfg)
    assert kept["railway"].tolist() == ["rail", "narrow_gauge", "light_rail"]
    assert kept["ref"].tolist()[2] == "112D"
    assert set(excluded["railway"]) == {"light_rail", "tram", "abandoned"}


def test_dedupe_drops_repeated_osm_id_then_identical_geometry(cfg):
    a = [(21.0, LAT), (21.01, LAT)]
    w = _ways([a, a, list(reversed(a)), [(21.0, LAT + 0.01), (21.01, LAT + 0.01)]], cfg,
              ids=["1", "1", "2", "3"])
    out, n_id, n_geom = R.dedupe_ways(w)
    assert (n_id, n_geom) == (1, 1) and sorted(out["osm_id"]) == ["1", "3"]


def test_ways_sharing_a_vertex_form_one_component_with_geodesic_length(cfg):
    w = _ways([[(21.0, LAT), (21.0 + 10 * KM_LON, LAT)],
               [(21.0 + 10 * KM_LON, LAT), (21.0 + 10 * KM_LON, LAT + 0.05)]], cfg)
    g = R.build_graph(w, cfg)
    n, _ = g.components()
    assert n == 1 and g.n_nodes == 3
    assert g.length_m[:1].sum() == pytest.approx(10_000, rel=0.01)   # 10 km east, geodesic


def test_gap_join_closes_10m_gap_but_not_100m(cfg):
    x10 = 21.0 + 10 * KM_LON / 1000
    w = _ways([[(20.9, LAT), (21.0, LAT)], [(x10, LAT), (21.1, LAT)],              # 10 m gap
               [(20.9, LAT + 0.1), (21.0, LAT + 0.1)],
               [(21.0 + 100 * KM_LON / 1000, LAT + 0.1), (21.1, LAT + 0.1)]], cfg)  # 100 m gap
    g = R.build_graph(w, cfg)
    assert g.components()[0] == 4
    assert R.join_gaps(g, cfg) == 1
    assert g.components()[0] == 3


def test_station_links_gauge_break_and_far_station_is_discarded(cfg):
    # two lines 200 m apart (gauge break) meeting at a station; a third station 3 km from any track
    dy = 0.2 / 111.2
    w = _ways([[(21.0, LAT), (21.1, LAT)], [(21.05, LAT + dy), (21.2, LAT + dy)]], cfg)
    g = R.build_graph(w, cfg)
    assert g.components()[0] == 2
    tags = _tags([(21.06, LAT + dy / 2), (21.0, LAT), (21.1, LAT + 3 / 111.2)])
    snap = R.snap_stations(tags, g, cfg)
    assert snap["status"].tolist() == ["ok", "ok", "snap_too_far"]
    assert snap["n_components_linked"].tolist()[0] == 2
    assert g.components()[0] == 1          # the station joined the two lines


def test_distances_rail_ge_geodesic_on_a_bent_line(cfg):
    mid = (21.05, LAT + 0.03)
    w = _ways([[(21.0, LAT), mid, (21.1, LAT)]], cfg)
    g = R.build_graph(w, cfg)
    cfg.domestic_feed, cfg.hub_station_keys = "ZSR_SK", ["ZSR_SK:0"]
    tags = _tags([(21.0, LAT), (21.1, LAT)])
    snap = R.snap_stations(tags, g, cfg)
    d = R.distances_to_hub(tags, snap, g, cfg)
    assert d["rail_km"].iloc[0] == pytest.approx(0, abs=0.01)
    assert d["detour"].iloc[1] > 1.0 and d["status"].tolist() == ["ok", "ok"]
    assert bool(d["in_hub_component"].all())


def test_outside_scope_station_is_not_snapped(cfg):
    w = _ways([[(21.0, LAT), (21.1, LAT)]], cfg)
    g = R.build_graph(w, cfg)
    snap = R.snap_stations(_tags([(21.05, LAT)], in_scope=False), g, cfg)
    assert snap["status"].iloc[0] == "outside_network" and snap["node"].iloc[0] == -1


def test_light_rail_by_gauge_only_inside_the_country(cfg):
    lines = [[(21.25, 48.72), (21.26, 48.72)],      # Košice (SK), 1000 mm -> added
             [(19.04, 47.50), (19.05, 47.50)],      # Budapest (HU), 1000 mm -> not
             [(21.25, 48.73), (21.26, 48.73)]]      # SK, 1435 mm -> not
    raw = gpd.GeoDataFrame({"railway": ["light_rail"] * 3,
                            "other_tags": ['"gauge"=>"1000"', '"gauge"=>"1000"', '"gauge"=>"1435"']},
                           geometry=[LineString(c) for c in lines], crs=4326)
    kept, _ = R.select_ways(raw, cfg)
    out, n = R.add_light_rail_by_gauge(raw, kept, cfg)
    assert n == 1 and out.index.tolist() == [0]


def test_bridge_joins_cut_off_piece_over_construction_only_along_the_path(cfg):
    cfg.domestic_feed, cfg.hub_station_keys = "ZSR_SK", ["ZSR_SK:0"]
    main = [(21.0, LAT), (21.1, LAT), (21.2, LAT)]          # OSM junctions share a vertex
    piece = [(21.1, LAT + 0.02), (21.15, LAT + 0.02)]                 # 2.2 km north, cut off
    con_link = [(21.1, LAT + 0.02), (21.1, LAT)]                     # construction joining it
    con_shortcut = [(21.0, LAT), (21.0, LAT - 0.05), (21.2, LAT - 0.05)]   # unrelated construction
    ways = _ways([main, piece], cfg)
    bridge = _ways([con_link, con_shortcut], cfg, ids=["c1", "c2"], railway="construction")
    g = R.build_graph(ways, cfg)
    tags = _tags([(21.0, LAT), (21.15, LAT + 0.02)])
    snap = R.snap_stations(tags, g, cfg)
    assert g.components()[0] == 2
    rows = R.bridge_components(g, ways, bridge, tags, snap, cfg)
    assert rows["bridged"].tolist() == [True]
    assert rows["construction_km"].iloc[0] == pytest.approx(2.22, abs=0.05)
    assert g.components()[0] == 1
    d = R.distances_to_hub(tags, snap, g, cfg)
    assert d["status"].tolist() == ["ok", "ok"] and d["rail_km"].iloc[1] == pytest.approx(7.33 + 2.22 + 3.67, abs=0.2)


def test_station_joins_every_line_so_the_shorter_one_counts(cfg):
    # Like Štrbské Pleso: S lies on the end of a long line (nearest track) and 150 m from the end of a
    # short one; both start at the hub, so they are one component. The short line must be usable.
    cfg.domestic_feed, cfg.hub_station_keys = "ZSR_SK", ["ZSR_SK:0"]
    dy = 0.15 / 111.2
    s = (21.1, LAT + dy)
    short = [(21.0, LAT), (21.1, LAT)]                                   # ends 150 m south of S
    long_ = [(21.0, LAT), (21.0, LAT + 0.1), (21.1, LAT + 0.1), s]       # ends exactly at S
    ways = _ways([short, long_], cfg)
    g = R.build_graph(ways, cfg)
    tags = _tags([(21.0, LAT), s])
    snap = R.snap_stations(tags, g, cfg)
    assert snap["n_lines_linked"].iloc[1] == 2 and snap["n_components_linked"].iloc[1] == 1
    d = R.distances_to_hub(tags, snap, g, cfg)
    assert d["rail_km"].iloc[1] == pytest.approx(7.36 + 0.15, abs=0.1)     # via the short line


def test_graph_save_and_load_round_trip(tmp_path):
    import numpy as np
    from traintranv2.nb01c_rail_network import RailGraph
    g = RailGraph(np.array([[0.0, 0.0], [1000.0, 0.0]]), np.array([[21.0, 48.0], [21.01, 48.0]]),
                  np.array([0]), np.array([1]), np.array([1000.0]), np.array(["track"], dtype=object), np.array([7]))
    g.add_edges([1], [0], [5.0], "station_link")
    p = str(tmp_path / "g.npz")
    g.save(p, {"OSM extraction date": "2026-01-01"})
    h = RailGraph.load(p)
    assert h.n_nodes == 2 and list(h.kind) == ["track", "station_link"] and h.n_track == 1
    assert h.meta["OSM extraction date"] == "2026-01-01"
    assert (h.csr() != g.csr()).nnz == 0


def test_line_km_counts_parallel_tracks_once():
    import geopandas as gpd
    from shapely.geometry import LineString, box
    from traintranv2.nb01c_rail_network import track_and_line_km
    ways = gpd.GeoDataFrame(geometry=[
        LineString([(1000, 1000), (3000, 1000)]),            # double track: 2 km, 5 m apart
        LineString([(1000, 1005), (3000, 1005)]),
        LineString([(1000, 20000), (2000, 20000)]),          # a single 1 km line elsewhere
    ], crs="EPSG:3035")
    regions = gpd.GeoDataFrame({"region": ["X"]}, geometry=[box(0, 0, 100000, 100000)], crs="EPSG:3035")
    r = track_and_line_km(ways, regions, tile_m=10000).iloc[0]
    assert abs(r.track_km - 5.0) < 1e-6
    assert abs(r.line_km - 3.0) < 0.01                       # 2 km double track + 1 km single
