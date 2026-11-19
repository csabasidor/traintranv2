"""
Notebook 01c -- the OSM rail network: source, cleaning, station snapping, distances to the hub.

Used by notebooks/01c_rail_network.ipynb. Steps (each a function, called in this order):

* ``osm_manifest``      -- what the gpkg is: size, sha256, extraction date (gpkg_contents.last_change),
                           extent, rows per ``railway`` value, duplicate rows.
* ``load_rail_ways``    -- keep ``cfg.rail_types`` (+ light_rail with ``ref`` in ``cfg.rail_extra_refs``,
                           the TEŽ); drop duplicate osm_id and identical geometries (the gpkg merges
                           several country dumps); clip to the six-country NUTS0 union + buffer.
* ``build_graph``       -- vertices on a ``cfg.rail_node_grid_m`` grid become nodes (OSM ways meet at
                           shared vertices); edge weight = geodesic length on WGS84.
* ``join_gaps``         -- a dead end is joined to the nearest node of another component within
                           ``cfg.rail_gap_join_m`` (dump seams, ways split at borders).
* ``snap_stations``     -- each station is snapped to the nearest track within ``cfg.rail_snap_max_km``
                           (farther: ``snap_too_far``, no distance) and linked to every other line (OSM
                           way) within ``cfg.rail_station_link_m``: the path may change line at a station,
                           as passengers do -- gauge breaks (the Štrba rack line, TEŽ, 1520/1435 at
                           Čierna nad Tisou / Chop) and lines ending at one station (Štrbské Pleso).
* ``distances_to_hub``  -- one Dijkstra from the Košice station node; rail_km, geodesic km, detour.

The graph is undirected (OSM rarely tags rail direction; no service pattern is modelled) and is
solved with scipy.sparse.csgraph: the six-country network has millions of vertices.
"""

import json
import os
import sqlite3
import urllib.request
from typing import Dict, Optional

import numpy as np

from .config import RunConfig
from .nb01a_feeds import _sha256

EPS_M = 1e-3   # csgraph treats explicit zeros as "no edge": zero-length edges get 1 mm


# ==========================================================================
# 1. Source
# ==========================================================================

def _ro_connect(path: str) -> sqlite3.Connection:
    """Open a GeoPackage strictly read-only (it may carry -wal / -shm files from a desktop GIS)."""
    url = "file:" + urllib.request.pathname2url(os.path.abspath(path)) + "?mode=ro&immutable=1"
    return sqlite3.connect(url, uri=True)


def manifest_path(cfg: RunConfig) -> str:
    return os.path.splitext(cfg.osm_railways_gpkg)[0] + ".manifest.json"


def osm_manifest(cfg: RunConfig, write: bool = True) -> dict:
    """Describe the OSM gpkg: size, sha256, extraction date, extent, rows per railway value."""
    path = cfg.osm_railways_gpkg
    con = _ro_connect(path)
    try:
        table, last_change, minx, miny, maxx, maxy, srs = con.execute(
            "SELECT table_name, last_change, min_x, min_y, max_x, max_y, srs_id FROM gpkg_contents "
            "WHERE data_type = 'features'").fetchone()
        n_rows, n_ids = con.execute(f'SELECT count(*), count(DISTINCT osm_id) FROM "{table}"').fetchone()
        by_type = {(k or "(none)"): n for k, n in con.execute(
            f'SELECT railway, count(*) FROM "{table}" GROUP BY 1 ORDER BY 2 DESC')}
        cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
    finally:
        con.close()
    m = {
        "file": path.replace("\\", "/"),
        "bytes": os.path.getsize(path),
        "sha256": _sha256(path),
        "layer": table,
        "extraction_date": last_change,
        "extraction_date_source": "gpkg_contents.last_change: when the layer was written from the OSM "
                                  "country dumps (the dumps' own dates are not recorded in the file)",
        "srs_id": srs,
        "extent_wgs84": [minx, miny, maxx, maxy],
        "columns": cols,
        "rows": n_rows,
        "distinct_osm_id": n_ids,
        "duplicate_rows": n_rows - n_ids,
        "rows_by_railway": by_type,
    }
    if write:
        with open(manifest_path(cfg), "w", encoding="utf-8") as fh:
            json.dump(m, fh, ensure_ascii=False, indent=1)
    return m


# ==========================================================================
# 2. Ways: type filter, de-duplication, clip
# ==========================================================================

def study_area(cfg: RunConfig):
    """Union of the study countries' NUTS0 polygons, buffered, in cfg.rail_metric_crs (shapely geometry)."""
    from .nb01b_stations import load_nuts_level

    n0 = load_nuts_level(cfg, 0, countries=cfg.study_countries).to_crs(cfg.rail_metric_crs)
    return n0.geometry.simplify(100).union_all().buffer(cfg.rail_clip_buffer_km * 1000)


def select_ways(raw, cfg: RunConfig):
    """Type filter on a frame with railway / other_tags: returns (kept frame with ``ref``, excluded counts)."""
    import pandas as pd

    ref = raw["other_tags"].fillna("").str.extract(r'"ref"=>"([^"]*)"', expand=False)
    keep = raw["railway"].isin(list(cfg.rail_types)) | (
        raw["railway"].eq("light_rail") & ref.isin(list(cfg.rail_extra_refs)))
    kept = raw[keep].copy()
    kept["ref"] = ref[keep]
    excluded = (raw.loc[~keep, "railway"].fillna("(none)").value_counts()
                .rename_axis("railway").reset_index(name="ways"))
    return kept, pd.DataFrame(excluded)


def add_light_rail_by_gauge(raw, kept, cfg: RunConfig):
    """Add light_rail ways whose gauge is listed for the country they lie in (cfg.rail_light_rail_gauge_by_country).

    Returns (kept + added, number added)."""
    import pandas as pd
    from .nb01b_stations import load_nuts_level

    rules = getattr(cfg, "rail_light_rail_gauge_by_country", None) or {}
    if not rules:
        return kept, 0
    gauge = raw["other_tags"].fillna("").str.extract(r'"gauge"=>"([^"]*)"', expand=False)
    cand = raw[raw["railway"].eq("light_rail") & ~raw.index.isin(kept.index)]
    n0 = load_nuts_level(cfg, 0, countries=list(rules))
    add = []
    for country, gauges in rules.items():
        poly = n0.loc[n0["cntr_code"] == country].geometry.union_all()
        c = cand[gauge.reindex(cand.index).isin(list(gauges))]
        c = c[c.intersects(poly)]
        add.append(c)
    add = pd.concat(add) if add else cand.iloc[:0]
    add = add[~add.index.duplicated()].copy()
    add["ref"] = raw["other_tags"].fillna("").str.extract(r'"ref"=>"([^"]*)"', expand=False).reindex(add.index)
    return pd.concat([kept, add]), len(add)


def dedupe_ways(ways):
    """Drop repeated osm_id (same way in two country dumps), then identical geometries.

    Returns (frame, n dropped as repeated osm_id, n dropped as identical geometry)."""
    import pandas as pd
    import shapely

    has_id = ways["osm_id"].notna()
    out = pd.concat([ways[has_id].drop_duplicates("osm_id"), ways[~has_id]])
    n_id = len(ways) - len(out)
    wkb = pd.Series(shapely.to_wkb(shapely.normalize(np.asarray(out.geometry.values))), index=out.index)
    out = out[~wkb.duplicated().to_numpy()]
    return out, n_id, len(ways) - n_id - len(out)


def clip_ways(ways_metric, area):
    """Keep ways inside ``area``; cut those crossing its edge (both in the same metric CRS)."""
    import shapely

    geoms = np.asarray(ways_metric.geometry.values)
    shapely.prepare(area)
    inside = shapely.contains(area, geoms)
    cross = ~inside & shapely.intersects(area, geoms)
    keep = inside | cross
    out = ways_metric[keep].copy()
    g = geoms[keep].copy()
    sel = cross[keep]
    g[sel] = shapely.intersection(g[sel], area)
    out = out.set_geometry(g, crs=ways_metric.crs)
    return out[~out.geometry.is_empty]


def _km(gdf_metric) -> float:
    return float(gdf_metric.length.sum() / 1000)


def load_rail_ways(cfg: RunConfig):
    """Read the gpkg and return (ways in cfg.rail_metric_crs, stage counts, excluded railway values)."""
    import geopandas as gpd
    import pandas as pd

    raw = gpd.read_file(cfg.osm_railways_gpkg, layer="railways",
                        columns=["osm_id", "name", "railway", "other_tags"])
    raw = raw[raw.geometry.notna() & raw.geom_type.isin(["LineString", "MultiLineString"])]
    stages = [{"step": "gpkg line features", "ways": len(raw), "note": "all railway= values"}]

    kept, excluded = select_ways(raw, cfg)
    n_ref = int((kept["railway"] == "light_rail").sum())
    kept, n_gauge = add_light_rail_by_gauge(raw, kept, cfg)
    if n_gauge:
        lr = excluded["railway"] == "light_rail"
        excluded.loc[lr, "ways"] -= n_gauge
    gauges = "; ".join(f"{c}: {g}" for c, g in (cfg.rail_light_rail_gauge_by_country or {}).items())
    stages.append({"step": "type filter", "ways": len(kept),
                   "note": f"railway in {list(cfg.rail_types)} + light_rail (TEŽ): {n_ref} ways with ref in "
                           f"{list(cfg.rail_extra_refs)}, {n_gauge} more by gauge inside the country ({gauges} mm)"})

    ded, n_id, n_geom = dedupe_ways(kept)
    stages.append({"step": "duplicate osm_id dropped", "ways": len(kept) - n_id,
                   "note": f"{n_id:,} rows repeated a way already present (overlapping country dumps)"})
    stages.append({"step": "identical geometry dropped", "ways": len(ded),
                   "note": f"{n_geom:,} further rows with a geometry identical to another way"})

    metric = ded.to_crs(cfg.rail_metric_crs)
    stages[-1]["km"] = round(_km(metric), 1)
    area = study_area(cfg)
    clipped = clip_ways(metric, area)
    stages.append({"step": "clipped to study area", "ways": len(clipped), "km": round(_km(clipped), 1),
                   "note": f"NUTS0 union of {list(cfg.study_countries)} + {cfg.rail_clip_buffer_km:g} km buffer"})
    clipped = clipped.reset_index(drop=True)
    clipped["length_km"] = clipped.length / 1000

    # candidate bridge track (used only along a bridge path, see bridge_components)
    btypes = list(getattr(cfg, "rail_bridge_types", []) or [])
    bridge = raw[raw["railway"].isin(btypes)].copy()
    bridge["ref"] = bridge["other_tags"].fillna("").str.extract(r'"ref"=>"([^"]*)"', expand=False)
    bridge, _, _ = dedupe_ways(bridge)
    bridge = clip_ways(bridge.to_crs(cfg.rail_metric_crs), area).reset_index(drop=True)
    bridge["length_km"] = bridge.length / 1000
    return clipped, pd.DataFrame(stages), excluded, bridge


# ==========================================================================
# 3. Graph
# ==========================================================================

class RailGraph:
    """Undirected rail graph: node coordinates (metric + WGS84) and an edge list with kinds."""

    def __init__(self, node_xy, node_ll, u, v, length_m, kind, way):
        self.node_xy = node_xy            # (N, 2) in cfg.rail_metric_crs
        self.node_ll = node_ll            # (N, 2) lon, lat
        self.u, self.v = u, v
        self.length_m = length_m
        self.kind = kind                  # object array: track / gap_join / track_split / snap / station_link
        self.way = way                    # index into the ways frame, -1 for added edges
        self.n_track = len(u)             # the first n_track edges are track segments
        self.n_base_nodes = len(node_xy)  # nodes from way vertices (later ones: stations, snaps, bridges)

    @property
    def n_nodes(self) -> int:
        return len(self.node_xy)

    def add_nodes(self, xy, ll) -> np.ndarray:
        start = self.n_nodes
        self.node_xy = np.vstack([self.node_xy, xy])
        self.node_ll = np.vstack([self.node_ll, ll])
        return np.arange(start, self.n_nodes)

    def add_edges(self, u, v, length_m, kind: str):
        u, v = np.asarray(u, dtype=np.int64), np.asarray(v, dtype=np.int64)
        self.u = np.concatenate([self.u, u])
        self.v = np.concatenate([self.v, v])
        self.length_m = np.concatenate([self.length_m, np.maximum(np.asarray(length_m, float), EPS_M)])
        self.kind = np.concatenate([self.kind, np.full(len(u), kind, dtype=object)])
        self.way = np.concatenate([self.way, np.full(len(u), -1, dtype=np.int64)])

    def save(self, path: str, extra: Optional[dict] = None):
        """The final graph as one .npz (node coordinates, edge list with lengths and kinds), so later notebooks
        (route distances, 04b) reuse it instead of rebuilding it from the gpkg."""
        np.savez_compressed(path, node_xy=self.node_xy, node_ll=self.node_ll, u=self.u, v=self.v,
                            length_m=self.length_m, kind=self.kind.astype(str), way=self.way,
                            n_track=np.int64(self.n_track), n_base_nodes=np.int64(self.n_base_nodes),
                            meta=np.array(json.dumps(extra or {})))

    @classmethod
    def load(cls, path: str) -> "RailGraph":
        z = np.load(path, allow_pickle=False)
        g = cls(z["node_xy"], z["node_ll"], z["u"], z["v"], z["length_m"], z["kind"].astype(object), z["way"])
        g.n_track, g.n_base_nodes = int(z["n_track"]), int(z["n_base_nodes"])
        g.meta = json.loads(str(z["meta"]))
        return g

    def csr(self):
        """Symmetric adjacency (min length where an edge repeats)."""
        import pandas as pd
        from scipy.sparse import csr_matrix
        a, b = np.minimum(self.u, self.v), np.maximum(self.u, self.v)
        e = pd.DataFrame({"a": a, "b": b, "w": self.length_m}).groupby(["a", "b"], sort=False)["w"].min()
        a, b = e.index.get_level_values(0).to_numpy(), e.index.get_level_values(1).to_numpy()
        n = self.n_nodes
        return csr_matrix((e.to_numpy(), (a, b)), shape=(n, n))

    def components(self):
        from scipy.sparse.csgraph import connected_components
        return connected_components(self.csr(), directed=False)

    def component_km(self, labels) -> np.ndarray:
        """Track (+ gap join) length per component, km."""
        sel = np.isin(self.kind, ["track", "gap_join", "bridge"])
        return np.bincount(labels[self.u[sel]], weights=self.length_m[sel], minlength=labels.max() + 1) / 1000


def _to_ll(xy, cfg: RunConfig):
    from pyproj import Transformer
    t = Transformer.from_crs(cfg.rail_metric_crs, 4326, always_xy=True)
    lon, lat = t.transform(xy[:, 0], xy[:, 1])
    return np.column_stack([lon, lat])


def _to_xy(lon, lat, cfg: RunConfig):
    from pyproj import Transformer
    t = Transformer.from_crs(4326, cfg.rail_metric_crs, always_xy=True)
    x, y = t.transform(np.asarray(lon, float), np.asarray(lat, float))
    return np.column_stack([x, y])


def _geodesic_m(ll_a, ll_b):
    from pyproj import Geod
    return np.asarray(Geod(ellps="WGS84").inv(ll_a[:, 0], ll_a[:, 1], ll_b[:, 0], ll_b[:, 1])[2])


def grid_key(xy, cfg: RunConfig) -> np.ndarray:
    """One int64 per point: its cell on the cfg.rail_node_grid_m grid (same key in any graph built
    with the same cfg). EPSG:3035 coordinates are positive and < 2^24 cells at 0.5 m."""
    q = np.round(np.asarray(xy, float) / cfg.rail_node_grid_m).astype(np.int64)
    return q[:, 0] * (1 << 25) + q[:, 1]


def build_graph(ways_metric, cfg: RunConfig) -> RailGraph:
    """Vertices on a cfg.rail_node_grid_m grid become nodes; consecutive vertices of a way become edges."""
    import shapely

    parts, part_way = shapely.get_parts(np.asarray(ways_metric.geometry.values), return_index=True)
    is_line = shapely.get_type_id(parts) == 1
    parts, part_way = parts[is_line], part_way[is_line]
    coords, vtx_part = shapely.get_coordinates(parts, return_index=True)

    key = grid_key(coords, cfg)
    _, first, inv = np.unique(key, return_index=True, return_inverse=True)
    inv = inv.ravel()
    node_xy = coords[first]

    same = vtx_part[:-1] == vtx_part[1:]
    u, v = inv[:-1][same], inv[1:][same]
    way = part_way[vtx_part[:-1][same]]
    ok = u != v
    u, v, way = u[ok], v[ok], way[ok]
    # each undirected edge once (the same segment can come from two overlapping ways)
    a, b = np.minimum(u, v), np.maximum(u, v)
    _, keep = np.unique(a * (len(node_xy) + 1) + b, return_index=True)
    u, v, way = a[keep], b[keep], way[keep]

    node_ll = _to_ll(node_xy, cfg)
    length = np.maximum(_geodesic_m(node_ll[u], node_ll[v]), EPS_M)
    return RailGraph(node_xy, node_ll, u.astype(np.int64), v.astype(np.int64), length,
                     np.full(len(u), "track", dtype=object), way.astype(np.int64))


# ==========================================================================
# 4. Topology cleaning: gap joins
# ==========================================================================

def join_gaps(g: RailGraph, cfg: RunConfig) -> int:
    """Join each dead end to the nearest node of another component within cfg.rail_gap_join_m."""
    from scipy.spatial import cKDTree

    _, lab = g.components()
    deg = np.bincount(np.concatenate([g.u, g.v]), minlength=g.n_nodes)
    ends = np.flatnonzero(deg == 1)
    tree = cKDTree(g.node_xy)
    pairs = set()
    for e, cand in zip(ends, tree.query_ball_point(g.node_xy[ends], r=cfg.rail_gap_join_m)):
        cand = np.asarray(cand, dtype=np.int64)
        cand = cand[lab[cand] != lab[e]]
        if len(cand):
            j = int(cand[np.argmin(np.hypot(*(g.node_xy[cand] - g.node_xy[e]).T))])
            pairs.add((min(int(e), j), max(int(e), j)))
    if pairs:
        a = np.array([p[0] for p in pairs]); b = np.array([p[1] for p in pairs])
        g.add_edges(a, b, np.hypot(*(g.node_xy[a] - g.node_xy[b]).T), "gap_join")
    return len(pairs)


# ==========================================================================
# 5. Stations: snap, link components, discard
# ==========================================================================

def _truthy(s):
    return s.astype(str).str.lower().isin(["true", "1"])


def snap_stations(tags, g: RailGraph, cfg: RunConfig):
    """Snap every station of ``tags`` (station_tags.csv) onto the graph; mutates ``g``.

    Returns a frame (one row per station, same index as ``tags``) with ``status``, ``snap_m``,
    ``n_components_linked`` and the station's node id (``node``, -1 if not on the network).
    """
    import pandas as pd
    import shapely
    from shapely import STRtree

    lat = pd.to_numeric(tags["stop_lat"], errors="coerce").to_numpy()
    lon = pd.to_numeric(tags["stop_lon"], errors="coerce").to_numpy()
    has_xy = ~(np.isnan(lat) | np.isnan(lon))
    in_scope = _truthy(tags["in_scope"]).to_numpy() if "in_scope" in tags else np.ones(len(tags), bool)
    todo = np.flatnonzero(has_xy & in_scope)

    status = np.where(~has_xy, "no_coords", np.where(~in_scope, "outside_network", "")).astype(object)
    snap_m = np.full(len(tags), np.nan)
    n_linked = np.zeros(len(tags), dtype=int)
    n_lines = np.zeros(len(tags), dtype=int)
    node = np.full(len(tags), -1, dtype=np.int64)

    nt = g.n_track
    seg_u, seg_v = g.u[:nt], g.v[:nt]
    segs = shapely.linestrings(np.stack([g.node_xy[seg_u], g.node_xy[seg_v]], axis=1))
    tree = STRtree(segs)
    _, lab = g.components()
    seg_comp = lab[seg_u]

    xy = _to_xy(lon[todo], lat[todo], cfg)
    pts = shapely.points(xy)

    # nearest track within the discard distance
    (pi, ei), dist = tree.query_nearest(pts, max_distance=cfg.rail_snap_max_km * 1000, return_distance=True)
    first = np.unique(pi, return_index=True)[1]
    near = {int(pi[k]): (int(ei[k]), float(dist[k])) for k in first}
    # every line (OSM way) within the link distance: its nearest segment. A station is where trains
    # of all its lines meet, so the path may change line there (gauge breaks, two lines ending at
    # one station such as Štrbské Pleso: TEŽ and the Štrba rack line).
    seg_way = g.way[:nt]
    lp, le = tree.query(pts, predicate="dwithin", distance=cfg.rail_station_link_m)
    ld = shapely.distance(pts[lp], segs[le])
    lk = pd.DataFrame({"p": lp, "e": le, "d": ld, "way": seg_way[le]}).sort_values("d")
    lk = lk.drop_duplicates(["p", "way"])
    links: Dict[int, list] = {p: list(zip(grp["e"].tolist(), grp["d"].tolist()))
                              for p, grp in lk.groupby("p", sort=False)}

    attach_s, attach_e, attach_d, attach_kind = [], [], [], []
    for k, row in enumerate(todo):
        if k not in near:
            status[row] = "snap_too_far"
            continue
        e0, d0 = near[k]
        snap_m[row] = d0
        status[row] = "ok"
        chosen = {int(seg_way[e0]): (e0, d0, "snap")}
        for e, d in links.get(k, []):
            w = int(seg_way[e])
            if w not in chosen:
                chosen[w] = (e, d, "station_link")
        n_lines[row] = len(chosen)
        n_linked[row] = len({int(seg_comp[e]) for e, _, _ in chosen.values()})
        for e, d, kind in chosen.values():
            attach_s.append(k); attach_e.append(e); attach_d.append(d); attach_kind.append(kind)

    if attach_s:
        attach_s = np.array(attach_s); attach_e = np.array(attach_e)
        attach_d = np.array(attach_d); attach_kind = np.array(attach_kind, dtype=object)
        # one node per snapped station, at the station point
        snapped_k = np.unique(attach_s)
        st_nodes = g.add_nodes(xy[snapped_k], np.column_stack([lon[todo][snapped_k], lat[todo][snapped_k]]))
        st_node_of = dict(zip(snapped_k.tolist(), st_nodes.tolist()))
        # a node on each chosen segment, splitting it in proportion
        seg = segs[attach_e]
        along = shapely.line_locate_point(seg, pts[attach_s])
        seg_len = shapely.length(seg)
        frac = np.clip(np.where(seg_len > 0, along / np.where(seg_len > 0, seg_len, 1), 0.0), 0, 1)
        on_xy = shapely.get_coordinates(shapely.line_interpolate_point(seg, along))
        on_nodes = g.add_nodes(on_xy, _to_ll(on_xy, cfg))
        w = g.length_m[attach_e]
        g.add_edges(seg_u[attach_e], on_nodes, w * frac, "track_split")
        g.add_edges(on_nodes, seg_v[attach_e], w * (1 - frac), "track_split")
        st = np.array([st_node_of[s] for s in attach_s.tolist()])
        for kind in ("snap", "station_link"):
            sel = attach_kind == kind
            g.add_edges(st[sel], on_nodes[sel], attach_d[sel], kind)
        for k, n_ in st_node_of.items():
            node[todo[k]] = n_

    return pd.DataFrame({"status": status, "snap_m": np.round(snap_m, 1), "n_lines_linked": n_lines,
                         "n_components_linked": n_linked, "node": node}, index=tags.index)


# ==========================================================================
# 5b. Bridges over construction track
# ==========================================================================

def bridge_components(g: RailGraph, ways, bridge_ways, tags, snap, cfg: RunConfig):
    """Join each cut-off component that carries stations to the hub's component by the shortest
    path over track + ``cfg.rail_bridge_types`` ways (<= cfg.rail_bridge_max_km); mutates ``g``.

    Only the edges of that path are added (kind ``bridge``), so construction track elsewhere cannot
    shorten any distance. Returns one row per cut-off component (bridged or not).
    """
    import pandas as pd
    from scipy.sparse.csgraph import dijkstra

    cols = ["component_id", "stations", "n_stations", "bridged", "bridge_km", "construction_km", "note"]
    _, lab = g.components()
    hub_node = int(snap["node"].iloc[hub_row(tags, cfg)])
    hub_c = lab[hub_node]
    st = snap[(snap["status"] == "ok") & (snap["node"] >= 0)]
    st_comp = pd.Series(lab[st["node"].to_numpy()], index=st.index)
    cut = st_comp[st_comp != hub_c]
    if cut.empty or bridge_ways is None or bridge_ways.empty:
        return pd.DataFrame(columns=cols)

    both = pd.concat([ways[["railway", "geometry"]], bridge_ways[["railway", "geometry"]]], ignore_index=True)
    g2 = build_graph(both.set_geometry("geometry", crs=ways.crs), cfg)
    is_con = both["railway"].isin(list(cfg.rail_bridge_types)).to_numpy()[g2.way]
    join_gaps(g2, cfg)
    adj2 = g2.csr()

    # g2 edge lookup (u < v) -> construction flag
    eu, ev = np.minimum(g2.u, g2.v), np.maximum(g2.u, g2.v)
    con_full = np.concatenate([is_con, np.zeros(len(g2.u) - len(is_con), bool)])
    ekey = eu * (g2.n_nodes + 1) + ev
    eorder = np.argsort(ekey)

    # node correspondence by grid cell (base nodes of both graphs)
    k1 = grid_key(g.node_xy[:g.n_base_nodes], cfg)
    k2 = grid_key(g2.node_xy[:g2.n_base_nodes], cfg)
    o1, o2 = np.argsort(k1), np.argsort(k2)

    def lookup(keys, k, o):
        pos = np.clip(np.searchsorted(k[o], keys), 0, len(o) - 1)
        hit = k[o][pos] == keys
        return o[pos], hit

    hub_base = np.flatnonzero(lab[:g.n_base_nodes] == hub_c)
    t2, ok = lookup(k1[hub_base], k2, o2)
    target = np.zeros(g2.n_nodes, bool)
    target[t2[ok]] = True

    rows = []
    names = tags["stop_name"] if "stop_name" in tags else pd.Series("", index=tags.index)
    for c, idx in cut.groupby(cut).groups.items():
        label = ", ".join(sorted(set(names.loc[idx]))[:6])
        src1 = np.flatnonzero(lab[:g.n_base_nodes] == c)
        s2, ok = lookup(k1[src1], k2, o2)
        s2 = np.unique(s2[ok])
        if not len(s2):
            rows.append({"component_id": int(c), "stations": label, "n_stations": len(idx), "bridged": False,
                         "note": "no track vertex of the component in the bridge graph"})
            continue
        dist, pred, _ = dijkstra(adj2, directed=False, indices=s2, min_only=True, return_predecessors=True,
                                 limit=cfg.rail_bridge_max_km * 1000)
        cand = np.flatnonzero(target & np.isfinite(dist))
        if not len(cand):
            rows.append({"component_id": int(c), "stations": label, "n_stations": len(idx), "bridged": False,
                         "note": f"no path to the main network within {cfg.rail_bridge_max_km:g} km over "
                                 f"track + {list(cfg.rail_bridge_types)}"})
            continue
        t = int(cand[np.argmin(dist[cand])])
        path = [t]
        while pred[path[-1]] >= 0:
            path.append(int(pred[path[-1]]))
        path = np.array(path[::-1])
        a, b = path[:-1], path[1:]
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        pos = eorder[np.searchsorted(ekey[eorder], lo * (g2.n_nodes + 1) + hi)]
        seg_m = np.asarray(adj2[lo, hi]).ravel()
        con_m = float(seg_m[con_full[pos]].sum())
        # path nodes -> g nodes (existing by grid cell, else new)
        g1, hit = lookup(grid_key(g2.node_xy[path], cfg), k1, o1)
        ids = np.where(hit, g1, -1)
        new = np.flatnonzero(~hit)
        if len(new):
            ids[new] = g.add_nodes(g2.node_xy[path[new]], g2.node_ll[path[new]])
        g.add_edges(ids[:-1], ids[1:], seg_m, "bridge")
        rows.append({"component_id": int(c), "stations": label, "n_stations": len(idx), "bridged": True,
                     "bridge_km": round(float(seg_m.sum()) / 1000, 3), "construction_km": round(con_m / 1000, 3),
                     "note": f"shortest path over track + {list(cfg.rail_bridge_types)}"})
    return pd.DataFrame(rows, columns=cols)


# ==========================================================================
# 6. Distances to the hub
# ==========================================================================

def hub_row(tags, cfg: RunConfig) -> int:
    """Position of the domestic Košice station in ``tags``."""
    key = f"{cfg.domestic_feed}:{cfg.hub_stop_id}"
    hit = np.flatnonzero((tags["station_key"] == key).to_numpy())
    if not len(hit):
        hit = np.flatnonzero(((tags["feed_key"] == cfg.domestic_feed)
                              & tags["stop_ids"].astype(str).str.split(";").map(
                                  lambda s: cfg.hub_stop_id in s)).to_numpy())
    if not len(hit):
        raise ValueError(f"hub station {key} not in station_tags")
    return int(hit[0])


def distances_to_hub(tags, snap, g: RailGraph, cfg: RunConfig):
    """rail_km (along track, both snaps included), geodesic km and detour from the Košice station."""
    import pandas as pd
    from scipy.sparse.csgraph import dijkstra

    h = hub_row(tags, cfg)
    hub_node = int(snap["node"].iloc[h])
    if hub_node < 0:
        raise ValueError("the hub station is not on the network")
    adj = g.csr()
    d = dijkstra(adj, directed=False, indices=hub_node)
    from scipy.sparse.csgraph import connected_components
    _, lab = connected_components(adj, directed=False)
    km = g.component_km(lab)

    nodes = snap["node"].to_numpy()
    on = nodes >= 0
    rail_km = np.full(len(snap), np.nan)
    rail_km[on] = d[nodes[on]] / 1000
    rail_km[~np.isfinite(rail_km)] = np.nan
    comp = np.full(len(snap), -1)
    comp[on] = lab[nodes[on]]
    comp_km = np.full(len(snap), np.nan)
    comp_km[on] = km[comp[on]]

    lat = pd.to_numeric(tags["stop_lat"], errors="coerce").to_numpy()
    lon = pd.to_numeric(tags["stop_lon"], errors="coerce").to_numpy()
    ll = np.column_stack([lon, lat])
    ok_ll = ~np.isnan(ll).any(axis=1)
    geo_km = np.full(len(ll), np.nan)
    geo_km[ok_ll] = _geodesic_m(ll[ok_ll], np.repeat(ll[[h]], ok_ll.sum(), axis=0)) / 1000

    out = snap.copy()
    status = out["status"].to_numpy().copy()
    status[(status == "ok") & np.isnan(rail_km)] = "other_component"
    out["status"] = status
    out["component_id"] = comp
    out["component_km"] = np.round(comp_km, 1)
    out["in_hub_component"] = on & (comp == lab[hub_node])
    out["rail_km"] = np.round(rail_km, 2)
    out["geo_km"] = np.round(geo_km, 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["detour"] = np.round(np.where(geo_km > 0.5, rail_km / geo_km, np.nan), 3)
    return out


# ==========================================================================
# 7. Tables
# ==========================================================================

def track_and_line_km(ways_metric, regions, r1: float = 15.0, r2: float = 30.0, tile_m: float = 50_000.0):
    """Network length per region, as track-km and as line-km (parallel tracks of one line counted once).

    OSM maps each track of a double-track line as its own way, so the summed length of the ways is track-km.
    Line-km by a two-buffer difference: every way is buffered by r1 and by r2 (flat ends) and each set merged; a
    bundle of parallel tracks with total spacing s < 2*r1 covers L*(s + 2r), so
        L = (A(r2) - A(r1)) / (2 * (r2 - r1)),
    whatever the spacing (a plain area / width would overstate a double-track line by s / 2r). Lines closer
    than 2*r1 count once; wide yards are partly merged. Computed in square tiles of ``tile_m``.

    ``regions``: GeoDataFrame in the same metric CRS with a ``region`` column. Returns region, track_km, line_km.
    """
    import pandas as pd
    import shapely

    geoms = np.asarray(ways_metric.geometry.values)
    tree = shapely.STRtree(geoms)
    xmin, ymin, xmax, ymax = shapely.total_bounds(geoms)
    regs = list(zip(regions["region"], regions.geometry.values))
    acc = {name: {"track": 0.0, r1: 0.0, r2: 0.0} for name, _ in regs}
    # pad by the larger buffer: buffer area beyond the outermost track must fall inside a tile
    for x0 in np.arange(xmin - r2, xmax + r2, tile_m):
        for y0 in np.arange(ymin - r2, ymax + r2, tile_m):
            box = shapely.box(x0, y0, x0 + tile_m, y0 + tile_m)
            idx = tree.query(shapely.buffer(box, r2))
            if not len(idx):
                continue
            g = geoms[idx]
            parts = {}
            for name, poly in regs:
                if shapely.intersects(poly, box):
                    parts[name] = shapely.intersection(poly, box)
            if not parts:
                continue
            inside = shapely.intersection(g, box)
            for name, p in parts.items():
                acc[name]["track"] += float(shapely.length(shapely.intersection(inside, p)).sum())
            for r in (r1, r2):
                u = shapely.intersection(shapely.union_all(shapely.buffer(g, r, cap_style="flat")), box)
                for name, p in parts.items():
                    acc[name][r] += float(shapely.area(shapely.intersection(u, p)))
    rows = [{"region": n, "track_km": a["track"] / 1000, "line_km": (a[r2] - a[r1]) / (2 * (r2 - r1)) / 1000}
            for n, a in acc.items()]
    out = pd.DataFrame(rows)
    out["track_per_line"] = (out["track_km"] / out["line_km"]).round(3)
    return out


def components_table(g: RailGraph, dist):
    """One row per connected component after cleaning (track length, stations, hub, centre)."""
    import pandas as pd

    n, lab = g.components()
    km = g.component_km(lab)
    n_nodes = np.bincount(lab, minlength=n)
    nodes = dist["node"].to_numpy()
    st = np.bincount(lab[nodes[nodes >= 0]], minlength=n)
    lon = np.bincount(lab, weights=g.node_ll[:, 0], minlength=n) / np.maximum(n_nodes, 1)
    lat = np.bincount(lab, weights=g.node_ll[:, 1], minlength=n) / np.maximum(n_nodes, 1)
    hub = dist.loc[dist["in_hub_component"].astype(bool), "node"]
    hub_c = int(lab[int(hub.iloc[0])]) if len(hub) else -1
    t = pd.DataFrame({"component_id": np.arange(n), "length_km": np.round(km, 2), "n_nodes": n_nodes,
                      "n_stations": st, "has_hub": np.arange(n) == hub_c,
                      "centre_lon": np.round(lon, 5), "centre_lat": np.round(lat, 5)})
    return t.sort_values("length_km", ascending=False).reset_index(drop=True)


def added_edges_table(g: RailGraph):
    """The edges cleaning and snapping added (gap_join / snap / station_link), with coordinates."""
    import pandas as pd

    sel = np.flatnonzero(np.isin(g.kind, ["gap_join", "snap", "station_link", "bridge"]))
    return pd.DataFrame({
        "kind": g.kind[sel],
        "a_lon": np.round(g.node_ll[g.u[sel], 0], 6), "a_lat": np.round(g.node_ll[g.u[sel], 1], 6),
        "b_lon": np.round(g.node_ll[g.v[sel], 0], 6), "b_lat": np.round(g.node_ll[g.v[sel], 1], 6),
        "length_m": np.round(g.length_m[sel], 2),
    })
