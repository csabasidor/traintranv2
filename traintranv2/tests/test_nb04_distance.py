"""Tests for traintranv2.nb04_distance: route km along the calls of a trip on a toy track graph."""
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

from traintranv2 import nb04_distance as D


def _graph():
    """Line A(0) - 1 km - B(1) - 1 km - C(2), plus a 10 km detour A - D(3) - C, and an island E(4) - F(5)."""
    edges = [(0, 1, 1000), (1, 2, 1000), (0, 3, 5000), (3, 2, 5000), (4, 5, 1000)]
    a = np.array([min(u, v) for u, v, _ in edges])
    b = np.array([max(u, v) for u, v, _ in edges])
    return csr_matrix((np.array([w for *_, w in edges], float), (a, b)), shape=(6, 6))


NODES = {"A": (0, 48.000, 21.000), "B": (1, 48.009, 21.000), "C": (2, 48.018, 21.000),
         "D": (3, 48.040, 21.030), "E": (4, 49.000, 21.000), "F": (5, 49.009, 21.000)}


def test_pair_km_is_the_shortest_track_path_and_nan_across_components():
    adj = _graph()
    got = D.pair_km(adj, NODES, [("A", "B"), ("A", "C"), ("C", "E"), ("A", "X")])
    assert got[0] == 1.0 and got[1] == 2.0
    assert np.isnan(got[2]) and np.isnan(got[3])          # other component; station without a node


def test_route_follows_the_calls_not_the_shortest_path():
    adj = _graph()
    # the train calls A -> D -> C: its route is 10 km, although the shortest A-C path is 2 km
    st = pd.DataFrame({"trip_id": ["t"] * 3, "seq": [0, 1, 2], "station_key": ["A", "D", "C"]})
    cum = D.trip_cum_km(st, adj, NODES)
    legs = pd.DataFrame({"trip_id": ["t", "t"], "f": ["A", "D"], "t": ["C", "C"]}, index=[5, 9])
    km = D.leg_route_km(legs, cum, "f", "t")
    assert list(km) == [10.0, 5.0]
    assert D.pair_km(adj, NODES, [("A", "C")])[0] == 2.0      # rail_km-like shortest path: a lower bound


def test_undefined_pair_makes_the_leg_undefined():
    adj = _graph()
    st = pd.DataFrame({"trip_id": ["t"] * 3, "seq": [0, 1, 2], "station_key": ["A", "B", "E"]})
    cum = D.trip_cum_km(st, adj, NODES)
    km = D.leg_route_km(pd.DataFrame({"trip_id": ["t", "t"], "f": ["A", "A"], "t": ["B", "E"]}), cum, "f", "t")
    assert km[0] == 1.0 and np.isnan(km[1])


def test_search_cap_does_not_cut_a_normal_pair():
    adj = _graph()
    # A-D straight line ~4 km, track 5 km: within 3 x geodesic + 20 km
    assert D.pair_km(adj, NODES, [("A", "D")])[0] == 5.0
