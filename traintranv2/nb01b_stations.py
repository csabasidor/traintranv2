"""
Notebook 01b -- stations of every feed: polygon check, station catalogs, tagging, cross-feed
identity and foreign-station matching.

Used by notebooks/01b_stations_tag_match.ipynb.

* **Polygon check** (``tag_points`` / ``tag_feed_stops``): every stop of every feed located in the LAU
  subset (CZ, SK, AT, HU, PL LAU 2024 + UA hromadas), GeoJSON only.
* **Station catalog** (``build_station_catalog``): stops merged into stations -- a platform belongs to
  its GTFS parent station; stops without a parent are merged by the same rule as the domestic run
  (same ``norm_name`` within 2 km). Entrances, nodes and boarding areas are dropped, and so are a
  parent's children that no kept trip calls at (AT bus / tram / U-Bahn bays under a rail station).
* **Tagging** (``tag_stops``): point in polygon -> name check against the LAU's national and Latin
  name (a nearby LAU whose name fits better takes over) -> manual corrections keyed on
  (feed_key, stop_id) -> UA fallback for a UA station outside every polygon.
* **Cross-feed identity** (``link_station_groups``): the same physical station in several feeds gets
  one ``station_group_id``, linked by UIC code, by place + name (same LAU, within
  ``cfg.match_auto_max_km``), by an accepted match, or by a reviewed manual pair; close same-LAU pairs
  whose names differ are queued for review.
* **Foreign matching** (``match_foreign_stations``): a domestic station located in another study
  country is matched to that country's feed; accepted automatically only if the name (or UIC code)
  matches AND the foreign station lies in the same LAU AND within ``cfg.match_auto_max_km``.
  Everything else is queued for manual review, with the feed's stations within
  ``cfg.match_candidate_km`` (same LAU first) as position candidates.
"""

import csv
import io
import os
import re
import zipfile
from difflib import SequenceMatcher
from typing import List, Optional

from .config import RunConfig
from .nb01a_feeds import feed_exists, feed_zip_path, haversine_km, norm_name, read_table


# Hard-coded Zakarpattia attributes, used only as a fallback (see _ua_fallback). Populations are
# rough legacy figures; the area is not known here.
def _fb(gid, degurba, latin, national, pop):
    return {
        "nuts_rg_01_country_id":   "UA",
        "nuts_rg_01_country_name": "Ukraine",
        "nuts_rg_01_region_id":    "UA_ZAK",
        "nuts_rg_01_region_name":  "Zakarpatia",
        "lau_gisco_id":            gid,
        "lau_code":                gid,
        "lau_name_national":       national,
        "lau_name_latin":          latin,
        "degurba":                 degurba,
        "lau_pop_2024":            pop,
    }


MANUAL_ENRICHMENT = {
    "chop":        _fb("UA_ZAK_1", 2, "Chop", "Чоп", 8600),
    "mukatschewo": _fb("UA_ZAK_2", 1, "Mukachevo", "Мукачево", 86000),
    "ujgorod":     _fb("UA_ZAK_3", 1, "Uzhhorod", "Ужгород", 115000),
}

UNKNOWN = "??"

NUTS_COLS = [
    "nuts_rg_01_country_id", "nuts_rg_01_country_name",
    "nuts_rg_01_region_id",  "nuts_rg_01_region_name",
    "nuts3_id", "nuts3_name",
]
# LAU columns: identity and names, then how the station was matched to it, then its attributes.
LAU_ID_COLS = ["lau_gisco_id", "lau_code", "lau_name_national", "lau_name_latin", "degurba"]
LAU_SCORE_COL = "lau_name_score"
LAU_MATCH_METHOD_COL = "lau_match_method"
LAU_NAME_IN_POLY_COL = "lau_name_in_polygon"
LAU_ATTR_COLS = [
    "lau_pop_2024", "lau_area_km2", "lau_pop_2025", "lau_pop_15_64_2025", "lau_pop_65plus_2025",
]
EXTRA_TAG_COLS = ["in_scope", "nuts2_id", "lau_tag_source"]
ALL_TAG_COLS = (
    NUTS_COLS + LAU_ID_COLS
    + [LAU_SCORE_COL, LAU_MATCH_METHOD_COL, LAU_NAME_IN_POLY_COL]
    + LAU_ATTR_COLS + EXTRA_TAG_COLS
)

# Columns the LAU subset must carry (00_extract_base_data_eu.ipynb §2a-2d).
LAU_SUBSET_COLS = [
    "GISCO_ID", "CNTR_CODE", "LAU_CODE", "LAU_NAME_NATIONAL", "LAU_NAME_LATIN", "NUTS3_ID",
    "NUTS2_ID", "DGURBA", "POP_2024", "AREA_KM2", "POP_2025", "POP_15_64_2025", "POP_65PLUS_2025",
]


def tag_stops(stops_df, cfg: RunConfig):
    """
    Tag a stops/stations DataFrame with country, NUTS, LAU, DEGURBA and population.

    Parameters
    ----------
    stops_df : pd.DataFrame with columns stop_id, stop_name, stop_lat, stop_lon and optionally
               ``stop_ids`` (';'-joined feed stop_ids of a deduplicated station), used to apply the
               manual corrections keyed on the feed stop_id.
    cfg      : RunConfig (lau_subset, nuts_dir, study_countries, lau_* settings)

    Returns the input with ``ALL_TAG_COLS`` appended. Unlike the shapefile version this does not
    swallow errors: a missing subset or a broken PROJ setup raises instead of tagging everything '??'.
    """
    return _run_tagging(stops_df, cfg)


# --------------------------------------------------------------------------
# GeoJSON inputs
# --------------------------------------------------------------------------

_LAU_CACHE: dict = {}
_NUTS_NAME_CACHE: dict = {}


def load_lau_subset(cfg: RunConfig, countries=None):
    """The LAU subset (EPSG:4326), optionally restricted to some CNTR_CODEs; cached per path."""
    import geopandas as gpd

    key = (cfg.lau_subset, tuple(sorted(countries)) if countries else None)
    if key not in _LAU_CACHE:
        where = None
        if countries:
            where = "CNTR_CODE IN (" + ", ".join(f"'{c}'" for c in countries) + ")"
        gdf = gpd.read_file(cfg.lau_subset, where=where)
        gdf = gdf.set_crs(4326) if gdf.crs is None else gdf.to_crs(4326)
        missing = [c for c in LAU_SUBSET_COLS if c not in gdf.columns]
        if missing:
            raise ValueError(f"{cfg.lau_subset} lacks {missing} -- run notebooks/"
                             "00_extract_base_data_eu.ipynb §2b-2d")
        _LAU_CACHE[key] = gdf.reset_index(drop=True)
    return _LAU_CACHE[key]


def _nuts_names(cfg: RunConfig) -> dict:
    """{NUTS_ID: name} for levels 0, 2 and 3 of the NUTS subset."""
    if cfg.nuts_dir not in _NUTS_NAME_CACHE:
        names = {}
        for level in (0, 2, 3):
            n = load_nuts_level(cfg, level)
            col = "name_latn" if "name_latn" in n.columns else "nuts_name"
            names.update(dict(zip(n["nuts_id"], n[col])))
        _NUTS_NAME_CACHE[cfg.nuts_dir] = names
    return _NUTS_NAME_CACHE[cfg.nuts_dir]


def tag_points(points, cfg: RunConfig, lau=None):
    """Point-in-polygon of stops against the LAU subset (no name check).

    points : DataFrame with stop_lat / stop_lon (any other columns are kept).
    Returns a copy with GISCO_ID, CNTR_CODE, LAU_CODE, NUTS2_ID, NUTS3_ID, DGURBA and ``in_scope``
    (inside a polygon of one of ``cfg.study_countries``). Stops without coordinates or outside every
    polygon get in_scope = False and empty ids.
    """
    import geopandas as gpd
    import pandas as pd

    lau = load_lau_subset(cfg) if lau is None else lau
    df = points.copy()
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    has_xy = df["stop_lat"].notna() & df["stop_lon"].notna()
    out_cols = ["GISCO_ID", "CNTR_CODE", "LAU_CODE", "NUTS2_ID", "NUTS3_ID", "DGURBA"]
    for c in out_cols:
        df[c] = None
    if has_xy.any():
        pts = gpd.GeoDataFrame(df.loc[has_xy, []], crs=4326,
                               geometry=gpd.points_from_xy(df.loc[has_xy, "stop_lon"], df.loc[has_xy, "stop_lat"]))
        j = gpd.sjoin(pts, lau[out_cols + ["geometry"]], how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        for c in out_cols:
            df.loc[j.index, c] = j[c].to_numpy()
    df["in_scope"] = df["GISCO_ID"].notna() & df["CNTR_CODE"].isin(list(cfg.study_countries))
    return df


def tag_feed_stops(cfg: RunConfig, keys=None):
    """Polygon check of every stop of every (or the given) feed.

    Returns one row per feed stop: feed_key, stop_id, stop_name, stop_lat, stop_lon,
    location_type, parent_station, plus the ``tag_points`` columns (GISCO_ID, CNTR_CODE, LAU_CODE,
    NUTS2_ID, NUTS3_ID, DGURBA, in_scope).
    """
    import pandas as pd

    lau = load_lau_subset(cfg)
    frames = []
    for key in (keys or list(cfg.feeds)):
        if not feed_exists(cfg, key):
            print(f"  [tag] {key}: feed file missing, skipped")
            continue
        rows = [{"stop_id": r.get("stop_id", "").strip(), "stop_name": r.get("stop_name", ""),
                 "stop_lat": r.get("stop_lat", ""), "stop_lon": r.get("stop_lon", ""),
                 "location_type": r.get("location_type", ""), "parent_station": r.get("parent_station", "")}
                for r in read_table(feed_zip_path(cfg, key), "stops.txt") if r.get("stop_id", "").strip()]
        df = pd.DataFrame(rows).drop_duplicates("stop_id")
        df.insert(0, "feed_key", key)
        frames.append(tag_points(df, cfg, lau=lau))
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------
# NUTS names
# --------------------------------------------------------------------------

NUTS_FILE_PATTERN = "NUTS_RG_01M_2024_4326_LEVL_{level}.geojson"


def load_nuts_level(cfg: RunConfig, level, bbox=None, countries=None):
    """NUTS polygons at one level from the GeoJSON subset in cfg.nuts_dir.

    Columns are lowercased and the geometry column is named ``geom``, the same
    shape the old PostGIS table returned, so callers keep using
    ``nuts_id`` / ``nuts_name`` / ``levl_code`` / ``cntr_code`` / ``geom``.

    bbox      : optional (minx, miny, maxx, maxy) in EPSG:4326
    countries : optional iterable of CNTR_CODE values, e.g. ['SK', 'UA']
    """
    import os
    import geopandas as gpd
    path = os.path.join(cfg.nuts_dir, NUTS_FILE_PATTERN.format(level=int(level)))
    gdf = gpd.read_file(path, bbox=bbox)
    gdf = gdf.set_crs(4326) if gdf.crs is None else gdf.to_crs(4326)
    gdf.columns = [c if c == "geometry" else c.lower() for c in gdf.columns]
    gdf = gdf.rename_geometry("geom")
    if countries is not None:
        gdf = gdf[gdf["cntr_code"].isin(list(countries))]
    return gdf.reset_index(drop=True)



# --------------------------------------------------------------------------
# Name check
# --------------------------------------------------------------------------

def _names(lau_name):
    if lau_name is None:
        return []
    if isinstance(lau_name, (list, tuple, set)):
        return [n for n in lau_name if isinstance(n, str) and n]
    return [lau_name] if isinstance(lau_name, str) and lau_name else []


def _name_score(stop_name, lau_name):
    """Similarity of a stop name to a LAU name, or the best over several names (national, Latin)."""
    names = _names(lau_name)
    if not stop_name or not names:
        return 0.0
    q = norm_name(stop_name)
    return max(SequenceMatcher(None, q, norm_name(n)).ratio() for n in names)


def _tokens(s):
    import re
    return re.findall(r"[a-z0-9]+", norm_name(s))


def _name_contains(stop_name, lau_name):
    """True if the stop name and (one of) the LAU name(s) contain each other.

    Two directions:
    * the normalized stop name appears literally inside the LAU name -- e.g. "Barca" in
      "Košice - mestská časť Barca", a village surviving as a suffix of the municipality that
      absorbed it;
    * the LAU name forms the leading whole word(s) of the stop name -- e.g. "Łódź" for
      "Łódź Fabryczna", "Wien" for "Wien Hbf" (station suffixes). Whole tokens only, so "Bar"
      does not match "Barca".
    """
    needle = norm_name(stop_name) if stop_name else ""
    if not needle:
        return False
    st = _tokens(stop_name)
    for n in _names(lau_name):
        if needle in norm_name(n):
            return True
        lt = _tokens(n)
        if lt and len(lt) <= len(st) and st[:len(lt)] == lt:
            return True
    return False



def _best_lau_match(stop_name, primary_gisco_id, candidate_gisco_ids, name_by_gisco, threshold):
    """Pick the LAU to tag a stop with, and document how it was picked.

    Preference order:
      1. keep primary_gisco_id if stop_name is literally contained in its LAU
         display name                                    -> "contains_primary"
      2. switch to a nearby candidate whose display name literally contains
         stop_name                                        -> "contains_neighbor"
      3. keep primary_gisco_id if its fuzzy name-similarity score already
         clears `threshold`                                -> "fuzzy_primary"
      4. switch to the nearby candidate with the best fuzzy score, if it beats
         the primary's score and clears `threshold`         -> "fuzzy_neighbor"
      5. otherwise keep primary_gisco_id, unresolved         -> "unresolved"

    Returns (gisco_id, overridden, method, score), where score is the
    name-similarity ratio of the returned gisco_id (kept for the record even
    when the match was decided by containment, not by score).
    """
    primary_name = name_by_gisco.get(primary_gisco_id)
    primary_score = _name_score(stop_name, primary_name)

    if _name_contains(stop_name, primary_name):
        return primary_gisco_id, False, "contains_primary", primary_score

    for cand in candidate_gisco_ids:
        cand_name = name_by_gisco.get(cand)
        if _name_contains(stop_name, cand_name):
            return cand, cand != primary_gisco_id, "contains_neighbor", _name_score(stop_name, cand_name)

    if primary_score >= threshold:
        return primary_gisco_id, False, "fuzzy_primary", primary_score

    best_gisco_id, best_score = primary_gisco_id, primary_score
    for cand in candidate_gisco_ids:
        s = _name_score(stop_name, name_by_gisco.get(cand))
        if s > best_score:
            best_gisco_id, best_score = cand, s

    if best_gisco_id != primary_gisco_id and best_score >= threshold:
        return best_gisco_id, True, "fuzzy_neighbor", best_score
    return primary_gisco_id, False, "unresolved", primary_score



# --------------------------------------------------------------------------
# Manual corrections and the UA fallback
# --------------------------------------------------------------------------

MANUAL_OK = {"ok", "ok_near"}


def _load_manual_lau_matches(path):
    """Human-reviewed LAU corrections, {(feed_key, stop_id): GISCO_ID}.

    Expects ``stop_id, gisco_id`` (+ ``feed_key``, ``conversion``, ``note`` …). Rows without a
    ``feed_key`` belong to the domestic feed ``ZSR_SK`` (the converted legacy rows). Only rows whose
    ``conversion`` is 'ok' / 'ok_near' (or that have no ``conversion`` column) are used. Returns {} if
    the file is not set or does not exist yet.
    """
    import os
    import pandas as pd

    if not path or not os.path.exists(path):
        return {}
    m = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    if "stop_id" not in m.columns or "gisco_id" not in m.columns:
        raise ValueError(f"{path}: expected columns stop_id, gisco_id (re-keyed v2 format)")
    if "conversion" in m.columns:
        m = m[m["conversion"].isin(MANUAL_OK)]
    m = m.dropna(subset=["stop_id", "gisco_id"])
    feed = m["feed_key"].fillna("ZSR_SK") if "feed_key" in m.columns else pd.Series("ZSR_SK", index=m.index)
    return {(f.strip(), s.strip()): g.strip() for f, s, g in zip(feed, m["stop_id"], m["gisco_id"])}


def _ua_fallback(stop_name):
    """The old hard-coded Zakarpattia attributes for a station name, or None."""
    nm = str(stop_name or "").lower()
    for frag, vals in MANUAL_ENRICHMENT.items():
        if frag in nm:
            return vals
    return None


# --------------------------------------------------------------------------
# Tagging
# --------------------------------------------------------------------------

def lau_neighbor_finder(lau, cfg: RunConfig):
    """Return ``near(lon, lat) -> [GISCO_ID, ...]``: LAUs whose polygon lies within
    ``cfg.lau_neighbor_radius_km`` of the point, measured in metres in ``cfg.lau_metric_crs``."""
    from pyproj import Transformer
    from shapely.geometry import Point

    lau_m = lau[["GISCO_ID", "geometry"]].to_crs(cfg.lau_metric_crs)
    sidx = lau_m.sindex
    to_m = Transformer.from_crs(4326, cfg.lau_metric_crs, always_xy=True)
    radius_m = cfg.lau_neighbor_radius_km * 1000.0
    ids = lau_m["GISCO_ID"].to_numpy()

    def near(lon, lat):
        x, y = to_m.transform(float(lon), float(lat))
        return ids[sidx.query(Point(x, y).buffer(radius_m), predicate="intersects")].tolist()

    return near


def _run_tagging(stops_df, cfg):
    import pandas as pd

    lau = load_lau_subset(cfg)
    attrs = lau.drop(columns="geometry").set_index("GISCO_ID")
    names = _nuts_names(cfg)
    name_by_gisco = {g: (r["LAU_NAME_NATIONAL"], r["LAU_NAME_LATIN"]) for g, r in attrs.iterrows()}

    df = tag_points(stops_df, cfg, lau=lau)
    df[LAU_SCORE_COL] = None
    df[LAU_MATCH_METHOD_COL] = None
    df[LAU_NAME_IN_POLY_COL] = None
    df["lau_tag_source"] = None

    # ---- name check: keep the polygon's LAU unless a nearby LAU's name fits clearly better ----
    near_laus = lau_neighbor_finder(lau, cfg)
    polygon_only = set(getattr(cfg, "lau_polygon_only_countries", []) or [])
    n_moved = n_unresolved = n_poly = 0
    for idx, row in df.iterrows():
        if pd.isna(row["stop_lat"]) or pd.isna(row["stop_lon"]):
            continue
        primary = row["GISCO_ID"] if isinstance(row["GISCO_ID"], str) else None
        primary_names = name_by_gisco.get(primary)
        if primary and attrs.at[primary, "CNTR_CODE"] in polygon_only:
            # PL / AT: the polygon decides; the name score is kept for information only.
            df.at[idx, LAU_SCORE_COL] = _name_score(row["stop_name"], primary_names)
            df.at[idx, LAU_MATCH_METHOD_COL] = "polygon_accepted"
            df.at[idx, LAU_NAME_IN_POLY_COL] = _name_contains(row["stop_name"], primary_names)
            df.at[idx, "lau_tag_source"] = "polygon"
            n_poly += 1
            continue
        if (_name_contains(row["stop_name"], primary_names)
                or _name_score(row["stop_name"], primary_names) >= cfg.lau_fuzzy_threshold):
            cands = []
        else:
            cands = near_laus(row["stop_lon"], row["stop_lat"])
        best, moved, method, score = _best_lau_match(row["stop_name"], primary, cands,
                                                     name_by_gisco, cfg.lau_fuzzy_threshold)
        df.at[idx, LAU_SCORE_COL] = score
        df.at[idx, LAU_MATCH_METHOD_COL] = method
        df.at[idx, LAU_NAME_IN_POLY_COL] = method == "contains_primary"
        df.at[idx, "lau_tag_source"] = "name_neighbor" if moved else ("polygon" if primary else None)
        if moved:
            df.at[idx, "GISCO_ID"] = best
            n_moved += 1
        elif method == "unresolved" and primary:
            n_unresolved += 1
    if n_poly:
        print(f"  [tag] {n_poly} stop(s) in {sorted(polygon_only)} keep their polygon LAU (no name check)")
    if n_moved:
        print(f"  [tag] {n_moved} stop(s) moved to a better-matching nearby LAU by name")
    if n_unresolved:
        print(f"  [tag] {n_unresolved} stop(s) have a low-confidence LAU name match -> manual review")

    # ---- manual corrections, keyed on (feed_key, stop_id) (any member of a merged station) ----
    manual = _load_manual_lau_matches(getattr(cfg, "lau_manual_matches_file", None))
    if manual:
        n_manual = 0
        members = (df["stop_ids"].fillna("").str.split(";") if "stop_ids" in df.columns
                   else df["stop_id"].astype(str).map(lambda s: [s]))
        feed_col = next((c for c in ("feed_key", "feed") if c in df.columns), None)
        feeds = df[feed_col].fillna("ZSR_SK") if feed_col else pd.Series("ZSR_SK", index=df.index)
        for idx, mem in members.items():
            fk = feeds.at[idx]
            hit = next((manual[(fk, m)] for m in mem if (fk, m) in manual), None)
            if hit is None:
                continue
            if hit not in attrs.index:
                print(f"  [tag] manual match {mem} -> {hit} not in the LAU subset; skipped")
                continue
            df.at[idx, "GISCO_ID"] = hit
            df.at[idx, LAU_SCORE_COL] = 1.0
            df.at[idx, LAU_MATCH_METHOD_COL] = "manual"
            df.at[idx, LAU_NAME_IN_POLY_COL] = False
            df.at[idx, "lau_tag_source"] = "manual"
            n_manual += 1
        print(f"  [tag] {n_manual} stop(s) set from manual LAU corrections")

    # ---- attributes of the final LAU ----
    g = df["GISCO_ID"].where(df["GISCO_ID"].isin(attrs.index))
    a = attrs.reindex(g)
    a.index = df.index
    df["in_scope"] = g.notna() & a["CNTR_CODE"].isin(list(cfg.study_countries))
    df["nuts_rg_01_country_id"] = a["CNTR_CODE"]
    df["nuts_rg_01_country_name"] = a["CNTR_CODE"].map(names)
    df["nuts_rg_01_region_id"] = a["NUTS2_ID"]
    df["nuts_rg_01_region_name"] = a["NUTS2_ID"].map(names)
    df["nuts3_id"] = a["NUTS3_ID"]
    df["nuts3_name"] = a["NUTS3_ID"].map(names)
    df["lau_gisco_id"] = g
    df["lau_code"] = a["LAU_CODE"]
    df["lau_name_national"] = a["LAU_NAME_NATIONAL"]
    df["lau_name_latin"] = a["LAU_NAME_LATIN"]
    df["degurba"] = pd.to_numeric(a["DGURBA"], errors="coerce").astype("Int64")
    df["lau_pop_2024"] = a["POP_2024"]
    df["lau_area_km2"] = a["AREA_KM2"]
    df["nuts2_id"] = a["NUTS2_ID"]
    df["lau_pop_2025"] = a["POP_2025"]
    df["lau_pop_15_64_2025"] = a["POP_15_64_2025"]
    df["lau_pop_65plus_2025"] = a["POP_65PLUS_2025"]

    # ---- UA fallback: only for a UA-named station outside every polygon ----
    n_fb = 0
    for idx in df.index[g.isna()]:
        vals = _ua_fallback(df.at[idx, "stop_name"])
        if vals is None:
            continue
        for col, val in vals.items():
            df.at[idx, col] = val
        df.at[idx, "in_scope"] = True
        df.at[idx, "nuts2_id"] = vals.get("nuts_rg_01_region_id")
        df.at[idx, "lau_tag_source"] = "ua_fallback"
        df.at[idx, LAU_MATCH_METHOD_COL] = "ua_fallback"
        n_fb += 1
        print(f"  [tag] UA fallback used for '{df.at[idx, 'stop_name']}' (no hromada polygon)")

    df["lau_tag_source"] = df["lau_tag_source"].fillna("outside")
    df = df.drop(columns=["GISCO_ID", "CNTR_CODE", "LAU_CODE", "NUTS2_ID", "NUTS3_ID", "DGURBA"])
    for col in ALL_TAG_COLS:
        if col not in ("in_scope",):
            df[col] = df[col].astype(object).where(df[col].notna(), UNKNOWN)
    n_out = int((~df["in_scope"]).sum())
    print(f"  [tag] {len(df)} stops tagged: {len(df) - n_out} in scope, {n_out} outside the six countries")
    return df


# ==========================================================================
# Foreign-station matching
# ==========================================================================

# --------------------------------------------------------------------------
# Feed stops and name matching
# --------------------------------------------------------------------------

def _load_stops_from_zip(zip_path: str) -> List[dict]:
    """Return deduplicated list of stop dicts from stops.txt in a GTFS zip."""
    seen = set()
    stops = []
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith("stops.txt")]
        if not names:
            return stops
        with zf.open(names[0]) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8-sig", newline="")
            for row in csv.DictReader(text):
                key = (row.get("stop_id", ""), row.get("stop_name", ""),
                       row.get("stop_lat", ""), row.get("stop_lon", ""))
                if row.get("stop_id", "").strip() and key not in seen:
                    seen.add(key)
                    stops.append(row)
    return stops


def _stop_to_candidate(stop: dict, mtype: str, score: float) -> dict:
    return {
        "feed_stop_id":        stop.get("stop_id", ""),
        "feed_stop_name":      stop.get("stop_name", ""),
        "feed_stop_lat":       stop.get("stop_lat", ""),
        "feed_stop_lon":       stop.get("stop_lon", ""),
        "feed_location_type":  stop.get("location_type", ""),
        "feed_parent_station": stop.get("parent_station", ""),
        "match_type":          mtype,
        "score":               round(score, 4),
    }


def _expand_station_family(best_stop_id: str, feed_stops: List[dict]) -> List[dict]:
    """Return all stops in the same station family as best_stop_id.

    Uses the parent_station hierarchy: if best is a parent, returns parent + children.
    If best is a child, finds its parent and returns parent + all siblings.
    Falls back to all stops sharing the same normalised name when no hierarchy exists.
    """
    best = next((s for s in feed_stops if s.get("stop_id", "").strip() == best_stop_id), None)
    if not best:
        return []

    parent_id = best.get("parent_station", "").strip()
    if not parent_id:
        parent_id = best_stop_id  # best is a parent (or standalone)

    family = [
        s for s in feed_stops
        if s.get("stop_id", "").strip() == parent_id
        or s.get("parent_station", "").strip() == parent_id
    ]

    if not family:
        q = norm_name(best.get("stop_name", ""))
        family = [s for s in feed_stops if norm_name(s.get("stop_name", "")) == q]

    # Keep the station (location_type 1) and its boarding stops (empty / 0); drop entrances, generic
    # nodes and boarding areas (2 / 3 / 4: "Zugang", "P+R", "Bus" ...), as the station catalog does.
    return [s for s in family if str(s.get("location_type", "") or "").strip() in ("", "0", "1")]


# Generic station words a feed appends to the place name ("Szombathely pályaudvar", "Katowice stacja
# kolejowa", "Šatov, železniční stanice", "Bratislava-Petržalka stanica", "Achau Bahnhof") and the CZ
# request-stop flag " z" ("Lysá pod Makytou z"). Matched on norm_name output (lower case, no
# diacritics). "zastávka" is NOT generic: "Skalité zast." and "Skalité" are different stops.
_GENERIC_TAIL = re.compile(r"[\s,]+(bahnhof|bhf\.?|palyaudvar|stacja kolejowa|zeleznicni stanice|stanica|z)$")


def core_name(name: str) -> str:
    """norm_name without the generic station words at the end (used on both names compared)."""
    n = norm_name(name)
    while True:
        m = _GENERIC_TAIL.search(n)
        if not m or m.start() == 0:
            return n
        n = n[:m.start()].strip()


def _stop_names(stop: dict):
    """(norm_name, core_name) of a stop, cached on the dict (the same stops are searched many times)."""
    c = stop.get("_names")
    if c is None:
        sn = norm_name(stop.get("stop_name", ""))
        c = stop["_names"] = (sn, core_name(stop.get("stop_name", "")) if sn else "")
    return c


def _match_station(station_name: str, feed_stops: List[dict], threshold: float) -> List[dict]:
    """Return candidate matches sorted by score descending.

    Tiers: exact (equal norm_name), core (equal after dropping generic station words such as
    "Bahnhof", "pályaudvar", "stanica"; score 1.0), sequence (fuzzy >= threshold).
    Exact / core matches are NOT deduplicated -- every stop sharing the name is returned so
    callers can expand to the station. Sequence matches are deduplicated by normalised name.
    """
    q = norm_name(station_name)
    qc = core_name(station_name)
    exact, seq_results = [], []
    for stop in feed_stops:
        sn, sc = _stop_names(stop)
        if not sn:
            continue
        if q == sn:
            exact.append(_stop_to_candidate(stop, "exact", 1.0))
        elif qc and qc == sc:
            exact.append(_stop_to_candidate(stop, "core", 1.0))
        elif threshold < 1.0:
            sm = SequenceMatcher(None, q, sn)
            if sm.real_quick_ratio() >= threshold and sm.quick_ratio() >= threshold:
                score = sm.ratio()
                if score >= threshold:
                    seq_results.append(_stop_to_candidate(stop, "sequence", score))

    exact.sort(key=lambda r: (r["match_type"] != "exact", 1 if r.get("feed_parent_station", "").strip() else 0))
    seq_results.sort(key=lambda r: (-r["score"], 1 if r.get("feed_parent_station", "").strip() else 0))
    seen_names: set = set()
    deduped_seq = []
    for r in seq_results:
        key = norm_name(r["feed_stop_name"])
        if key not in seen_names:
            seen_names.add(key)
            deduped_seq.append(r)
    return exact + deduped_seq


# The SK feed abbreviates Czech names; the Czech feed spells them out.
_CZ_ABBREV = [
    (r"\bhl\. ?n\.", "hlavní nádraží"), (r"\bn\.(?=\s?\S)", "nad "), (r"\bp\.(?=\s?\S)", "pod "),
    (r"\bzast\.?$", "zastávka"), (r"\bz\.$", "zastávka"), (r"\bSv\.", "Svatým "),
    (r"\bČ\.\s?Těš\.", "Českého Těšína"),
]
# The SK feed's Austrian qualifiers that the Austrian feed drops.
_AT_QUALIFIERS = r"\s+(b\.\s?\S+|NÖ|am\s+\S+|bei\s+\S+)$|/\S+$"
# A country tag in brackets after the name, any country ("Zwardon(PL)", "Rybnik(PL)").
_COUNTRY_TAG = re.compile(r"\s*\((?:PL|CZ|SK|HU|AT|UA|DE|D|A|CH)\)\s*$", re.IGNORECASE)
# The SK feed abbreviates Polish names ("Wodzislaw Sl."); the Polish feeds spell them out.
_PL_ABBREV = [(r"\bSl\.", "Śląski"), (r"\bGl\.", "Główny"), (r"\bPd\.", "Południe"), (r"\bPn\.", "Północ")]
# The SK feed abbreviates Slovak names ("Lúky p.Makytou", "Devínska N.Ves", "Spišská Belá zast.");
# the CZ / PL / AT feeds carry the full names. Case-sensitive: "N." is Nová, "n." is nad.
_SK_ABBREV = [(r"\bp\.\s?(?=\S)", "pod "), (r"\bn\.\s?(?=\S)", "nad "), (r"\bN\.\s?(?=\S)", "Nová "),
              (r"\bzast\.?$", "zastávka")]


def _apply(name, rules):
    out = name
    for pat, rep in rules:
        out = re.sub(pat, rep, out)
    return " ".join(out.split())


def _name_variants(name: str, country: str, cfg: RunConfig) -> List[str]:
    """The station name plus country-specific rewrites (all are tried; duplicates dropped).

    Rewrites only widen the *name* search; every hit still has to pass the same-LAU and
    distance test before it is accepted automatically.
    """
    original = name
    tagless = _COUNTRY_TAG.sub("", name).strip()
    if tagless and tagless != name:
        name = tagless          # every rewrite below works on the name without its country tag
    out = [name, original]
    low = name.lower()
    if country == "PL":
        out.append(_apply(name, _PL_ABBREV))
    if country == "SK":
        out.append(_apply(name, _SK_ABBREV))
    if country == "CZ":
        if "hl.n." in low:
            out.append(low.replace("hl.n.", "hl. n."))
        if "(" in name:
            out.append(re.sub(r"\s*\([^)]*\)", "", name).strip())
        exp = re.sub(r"\s*\([^)]*\)", "", name).strip()
        for pat, rep in _CZ_ABBREV:
            exp = re.sub(pat, rep, exp)
        out.append(" ".join(exp.split()))
    if country == "HU":
        if low.endswith(" pu"):
            out.append(name[:-3])
        if "miskolc tiszai pu" in low:
            out.append(re.sub(r"(?i)miskolc tiszai pu", "Miskolc-Tiszai", name))
    if country == "AT":
        base = re.sub(r"\s+Hbf$", " Hauptbahnhof", name)
        out += [base, f"{name} Bahnhof"]
        core = re.sub(_AT_QUALIFIERS, "", name).strip()
        if core and core != name:
            out += [core, f"{core} Bahnhof"]
    if country == "UA" and cfg.ua_name_map.get(low):
        out.append(cfg.ua_name_map[low])
    seen, uniq = set(), []
    for v in out:
        k = norm_name(v)
        if k and k not in seen:
            seen.add(k)
            uniq.append(v)
    return uniq


def _name_hits(name, country, feed_stops, threshold, cfg):
    """Union of the hits of every name variant (exact first, then by score), one per feed stop."""
    hits, seen = [], set()
    for variant in _name_variants(name, country, cfg):
        for h in _match_station(variant, feed_stops, threshold):
            if h["feed_stop_id"] not in seen:
                seen.add(h["feed_stop_id"])
                hits.append(h)
    hits.sort(key=lambda h: (h["match_type"] != "exact", -h["score"]))
    return hits


# --------------------------------------------------------------------------
# Decision rule
# --------------------------------------------------------------------------

def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _distance_km(lat, lon, hit):
    a, b = _f(lat), _f(lon)
    c, d = _f(hit.get("feed_stop_lat")), _f(hit.get("feed_stop_lon"))
    if None in (a, b, c, d):
        return None
    return haversine_km((a, b), (c, d))


def evaluate_hit(hit, st_lat, st_lon, st_lau, feed_lau, cfg, threshold):
    """Annotate one name hit with distance / same-LAU and whether it passes the automatic rule.

    Automatic only if the name matches (exact, core, UIC code, or fuzzy >= threshold) AND the foreign
    station lies in the same LAU AND within ``cfg.match_auto_max_km``. A pair whose points fall either
    side of a municipal border goes to review even with an exact name (decided once, by hand).
    """
    dist = _distance_km(st_lat, st_lon, hit)
    same_lau = bool(st_lau) and st_lau == feed_lau.get(hit["feed_stop_id"])
    name_ok = (hit["match_type"] in ("exact", "core", "code")
               or (hit["match_type"] == "sequence" and hit["score"] >= threshold))
    reasons = []
    if not name_ok:
        reasons.append("name_below_threshold")
    if dist is None:
        reasons.append("no_coordinates")
    elif dist > cfg.match_auto_max_km:
        reasons.append("too_far")
    if not same_lau:
        reasons.append("different_lau")
    return {**hit, "match_distance_km": None if dist is None else round(dist, 3),
            "same_lau": same_lau, "feed_gisco_id": feed_lau.get(hit["feed_stop_id"], ""),
            "auto_ok": not reasons, "reason": ";".join(reasons)}


def position_candidates(st_lat, st_lon, st_lau, feed_stations, radius_km, k=3):
    """The feed's catalog stations within radius_km of the point: same LAU first, then by distance.

    feed_stations: list of dicts with rep (stop_id to put in the manual file), name, lat, lon, lau.
    Returns [(distance_km, same_lau, station dict)], at most k.
    """
    a, b = _f(st_lat), _f(st_lon)
    if a is None or b is None:
        return []
    box = radius_km / 111.0 * 2
    found = []
    for s in feed_stations:
        c, d = s["lat"], s["lon"]
        if c is None or d is None or abs(c - a) > box or abs(d - b) > box * 1.6:
            continue
        dkm = haversine_km((a, b), (c, d))
        if dkm <= radius_km:
            found.append((dkm, bool(st_lau) and s["lau"] == st_lau, s))
    found.sort(key=lambda t: (not t[1], t[0]))
    return found[:k]


def _feed_station_index(fk, stops, feed_cat, feed_stop_tags):
    """Index one foreign feed by its catalog stations (station_tags rows of that feed).

    by_id    : every stops.txt row by stop_id;
    station  : stop_id (station rep and every member) -> station {rep, name, lat, lon, lau, members};
    search   : the stops a name hit may land on -- boarding stops and parents that belong to a
               catalog station (directly or through their parent); entrances, dropped bus stops and
               stops of excluded agencies are left out;
    lau      : stop_id -> its station's LAU (stops outside every station: their polygon LAU);
    uic      : UIC code -> station rep; stations: list of station dicts (position candidates).
    """
    by_id = {s.get("stop_id", ""): s for s in stops}
    t = feed_stop_tags[feed_stop_tags["feed_key"] == fk]
    lau = dict(zip(t["stop_id"].astype(str), t["GISCO_ID"].fillna("").astype(str)))
    station, uic, stations = {}, {}, []
    for _, fr in feed_cat.iterrows():
        g = str(fr.get("lau_gisco_id", "") or "")
        g = "" if g == UNKNOWN else g
        rep = str(fr["_sid"]).split(":", 1)[1] if ":" in str(fr["_sid"]) else str(fr["_sid"])
        members = [m for m in str(fr.get("stop_ids", "")).split(";") if m]
        rec = {"rep": rep, "name": fr.get("stop_name", ""), "lat": _f(fr.get("stop_lat")),
               "lon": _f(fr.get("stop_lon")), "lau": g, "members": members}
        stations.append(rec)
        for m in [rep] + members:
            station[m] = rec
            lau[m] = g
        if fr.get("uic_code"):
            uic.setdefault(fr["uic_code"], rep)
    fx = {"by_id": by_id, "station": station, "lau": lau, "uic": uic, "stations": stations}
    search = []
    for s in stops:
        sid = s.get("stop_id", "")
        rec = _station_for(sid, fx)
        if rec is not None and str(s.get("location_type", "") or "").strip() in ("", "0", "1"):
            lau[sid] = rec["lau"]
            search.append(s)
    fx["search"] = search
    return fx


def _station_for(stop_id, fx):
    """The catalog station a stop belongs to: itself a rep / member, or a child of one."""
    rec = fx["station"].get(stop_id)
    if rec is None:
        parent = str(fx["by_id"].get(stop_id, {}).get("parent_station", "") or "").strip()
        rec = fx["station"].get(parent) if parent else None
    return rec


def _catalog_family(stop_id, fx):
    """(stops, station name) an accepted hit expands to: the station's parent (if it is a GTFS
    parent) and its catalog members -- the stops trains use, nothing else."""
    rec = _station_for(stop_id, fx)
    if rec is None:
        fam = _expand_station_family(stop_id, list(fx["by_id"].values())) or [fx["by_id"][stop_id]]
        return fam, ""
    ids = ([rec["rep"]] if str(fx["by_id"].get(rec["rep"], {}).get("location_type", "")).strip() == PARENT_TYPE else [])
    ids += [m for m in rec["members"] if m not in ids]
    return [fx["by_id"][i] for i in ids if i in fx["by_id"]], rec["name"]


def _fmt_candidates(cands):
    return " | ".join(f"{s['name']} [{s['rep']}] {dkm:.2f} km, {'same LAU' if same else 'LAU ' + (s['lau'] or '?')}"
                      for dkm, same, s in cands)


def load_manual_station_matches(path: Optional[str]):
    """Reviewed decisions: {(station member stop_id, feed_key): row}; empty if the file is absent."""
    import pandas as pd
    if not path or not os.path.exists(path):
        return {}
    m = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    need = {"station_stop_id", "feed_key", "feed_stop_id", "decision"}
    if not need <= set(m.columns):
        raise ValueError(f"{path}: expected columns {sorted(need)}")
    bad = set(m["decision"]) - {"accept", "reject", ""}
    if bad:
        raise ValueError(f"{path}: decision must be accept / reject, found {sorted(bad)}")
    m = m[m["decision"] != ""]
    return {(r["station_stop_id"].strip(), r["feed_key"].strip()): r.to_dict() for _, r in m.iterrows()}


def match_foreign_stations(cfg: RunConfig, stations, feed_stop_tags, manual_path: Optional[str] = "default",
                           threshold: Optional[float] = None, home_country: str = "SK"):
    """
    Match the catalog's stations in other study countries to their national feeds.

    stations       : tagged station catalog (``station_tags``): station_key (or stop_id), stop_name,
                     stop_lat, stop_lon, stop_ids (';'-joined feed stop_ids), feed_key,
                     nuts_rg_01_country_id, lau_gisco_id (its LAU) and uic_code. Candidates are the
                     domestic feed's stations; the other feeds' stations give each foreign stop its
                     name-checked station LAU and the UIC codes.
    feed_stop_tags : DataFrame with feed_key, stop_id, GISCO_ID (raw polygon LAU of every stop; used
                     where a stop belongs to no station, e.g. an entrance).
    manual_path    : reviewed decisions CSV; "default" -> cfg.station_feed_manual_file, None -> none.
    threshold      : fuzzy threshold override (sweeps); default cfg.fuzzy_threshold.

    Returns a DataFrame: accepted rows expanded to the stop family (best_match = 1) plus one row per
    review / rejected / unmatched station (best_match = 0), each with status and reason.
    """
    import pandas as pd

    threshold = cfg.fuzzy_threshold if threshold is None else threshold
    manual = load_manual_station_matches(cfg.station_feed_manual_file if manual_path == "default" else manual_path)

    allst = stations.copy()
    id_col = "station_key" if "station_key" in allst.columns else "stop_id"
    allst["_sid"] = allst[id_col]
    if "feed_key" not in allst.columns:
        allst["feed_key"] = allst.get("feed", cfg.domestic_feed)
    if "uic_code" not in allst.columns:
        allst["uic_code"] = ""
    allst["uic_code"] = allst["uic_code"].fillna("").astype(str)
    st = allst[allst["feed_key"] == cfg.domestic_feed].copy()
    st["country"] = st["nuts_rg_01_country_id"].astype(str).str.upper()
    cand = st[st["country"].isin(set(cfg.search_countries)) & (st["country"] != home_country)]

    # a country may have several feeds (PL: PKP Intercity + the other carriers): match against each
    feeds_of_country = {c: [f for f in cfg.country_feeds[c] if f in cfg.feeds]
                        for c in cfg.search_countries if c in cfg.country_feeds}
    work = [(r, fk) for _, r in cand.iterrows() for fk in feeds_of_country.get(r["country"], [])]

    # A reviewed decision can also pair a station with a feed outside the candidate set
    # (e.g. Bratislava hl.st. -> BAHN_AT): add those pairs.
    pairs = {(r["_sid"], fk) for r, fk in work}
    row_of_member = {}
    for _, r in st.iterrows():
        for sid in str(r.get("stop_ids", "")).split(";"):
            if sid:
                row_of_member[sid] = r
    for (sid, fk) in manual:
        r = row_of_member.get(sid)
        if r is not None and (r["_sid"], fk) not in pairs:
            work.append((r, fk))
            pairs.add((r["_sid"], fk))

    cache = {}
    rows = []
    for srow, fk in work:
        if fk not in cache:
            cache[fk] = _feed_station_index(fk, _load_stops_from_zip(feed_zip_path(cfg, fk)),
                                            allst[allst["feed_key"] == fk], feed_stop_tags)
        fx = cache[fk]
        feed_stops, feed_lau = fx["search"], fx["lau"]
        st_lau = str(srow.get("lau_gisco_id", "") or "")
        st_lau = "" if st_lau == "??" else st_lau
        base = {"station_id": srow["_sid"], "station_name": srow["stop_name"],
                "station_stop_ids": srow.get("stop_ids", ""), "country": srow["country"], "feed_key": fk,
                "station_lat": srow["stop_lat"], "station_lon": srow["stop_lon"], "station_gisco_id": st_lau}

        def accepted_rows(hit_id, mtype, score, ev, status, reason):
            fam, fname = _catalog_family(hit_id, fx)
            for f in fam:
                rows.append({**base, **_stop_to_candidate(f, mtype, score), "feed_station_name": fname,
                             "match_distance_km": ev["match_distance_km"], "same_lau": ev["same_lau"],
                             "feed_gisco_id": ev["feed_gisco_id"], "status": status, "reason": reason,
                             "alternatives": "", "suggested_feed_stop_id": "", "best_match": 1})

        # Reviewed decision?
        decision = next((manual[(m, fk)] for m in str(srow.get("stop_ids", "")).split(";") if (m, fk) in manual), None)
        if decision is not None:
            hit_stop = fx["by_id"].get(decision["feed_stop_id"])
            if decision["decision"] == "accept":
                if hit_stop is None:
                    raise ValueError(f"manual accept {decision} names a stop not in {fk}")
                ev = evaluate_hit(_stop_to_candidate(hit_stop, "manual", 1.0), srow["stop_lat"], srow["stop_lon"],
                                  st_lau, feed_lau, cfg, threshold)
                accepted_rows(decision["feed_stop_id"], "manual", 1.0, ev, "manual", decision.get("note", ""))
            else:
                st_ = _station_for(decision["feed_stop_id"], fx)
                rows.append({**base, "feed_stop_id": decision["feed_stop_id"], "match_type": "none", "score": "",
                             "feed_station_name": st_["name"] if st_ else "",
                             "status": "rejected", "reason": decision.get("note", ""), "alternatives": "",
                             "suggested_feed_stop_id": "", "best_match": 0})
            continue

        hits = _name_hits(srow["stop_name"], srow["country"], feed_stops, threshold, cfg)
        # UIC code tier: the same national station number in both feeds counts as a name match.
        code_rep = fx["uic"].get(str(srow.get("uic_code", "") or ""))
        if code_rep and code_rep in fx["by_id"]:
            hits = [_stop_to_candidate(fx["by_id"][code_rep], "code", 1.0)] + [h for h in hits if h["feed_stop_id"] != code_rep]
        evals = [evaluate_hit(h, srow["stop_lat"], srow["stop_lon"], st_lau, feed_lau, cfg, threshold) for h in hits]
        ok = [e for e in evals if e["auto_ok"]]
        if ok:
            best = ok[0]
            accepted_rows(best["feed_stop_id"], best["match_type"], best["score"], best, "auto", best["reason"])
            continue
        # No automatic hit: the feed's stations near the domestic one, same LAU first.
        cands = position_candidates(srow["stop_lat"], srow["stop_lon"], st_lau, fx["stations"], cfg.match_candidate_km)
        alt, sugg = _fmt_candidates(cands), (cands[0][2]["rep"] if cands else "")
        if evals:
            best = sorted(evals, key=lambda e: (e["match_distance_km"] is None, e["match_distance_km"] or 0))[0]
            st_ = _station_for(best["feed_stop_id"], fx)
            rows.append({**base, **{k: v for k, v in best.items() if k != "auto_ok"},
                         "feed_station_name": st_["name"] if st_ else "", "status": "review",
                         "alternatives": alt, "suggested_feed_stop_id": sugg, "best_match": 0})
        else:
            rows.append({**base, "match_type": "none", "score": "", "status": "review",
                         "reason": "position_candidate" if cands else "no_name_match", "feed_station_name": "",
                         "alternatives": alt, "suggested_feed_stop_id": sugg, "best_match": 0})

    cols = ["station_id", "station_name", "station_stop_ids", "country", "feed_key", "status", "reason",
            "match_type", "score", "feed_stop_id", "feed_stop_name", "feed_station_name", "feed_stop_lat", "feed_stop_lon",
            "feed_location_type", "feed_parent_station", "match_distance_km", "same_lau",
            "station_lat", "station_lon", "station_gisco_id", "feed_gisco_id", "alternatives",
            "suggested_feed_stop_id", "best_match"]
    out = pd.DataFrame(rows)
    for c in cols:
        if c not in out.columns:
            out[c] = ""
    return out[cols]


def match_summary(matches):
    """One row per station × feed with its status (family rows collapsed)."""
    return matches.drop_duplicates(["station_id", "feed_key"])


def match_threshold_sweep(cfg: RunConfig, stations, feed_stop_tags, grid=None):
    """Status and name-tier counts per fuzzy threshold, without manual decisions (CF-26)."""
    import pandas as pd

    rows = []
    for t in (grid or cfg.fuzzy_threshold_grid):
        s = match_summary(match_foreign_stations(cfg, stations, feed_stop_tags, manual_path=None, threshold=t))
        rows.append({"threshold": t, "stations": len(s),
                     "auto": int((s["status"] == "auto").sum()),
                     "auto_exact": int(((s["status"] == "auto") & (s["match_type"] == "exact")).sum()),
                     "auto_fuzzy": int(((s["status"] == "auto") & (s["match_type"] == "sequence")).sum()),
                     "review": int((s["status"] == "review").sum()),
                     "review_no_name": int((s["reason"] == "no_name_match").sum())})
    return pd.DataFrame(rows)


# ==========================================================================
# Station catalog (every feed, same rules)
# ==========================================================================

BOARDING_TYPES = {"", "0"}           # GTFS location_type of a stop / platform where trains stop
PARENT_TYPE = "1"                    # a station (parent); never referenced by a trip
UIC_RE = re.compile(r"^\d{7}$")
_UIC_COUNTRY = {"CZ": "54", "SK": "56", "PL": "51", "AT": "81", "DE": "80"}
_CZ_NUM_RE = re.compile(r"(CZ|SK|PL|AT|DE):(\d{5})$")


def _f2(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def name_dedup(stops, norm=norm_name, km=2.0):
    """Group stops into stations by the domestic run's rule (``analysis.register_station``).

    A stop joins an earlier station with the same normalised name whose (0.01-degree rounded)
    coordinates lie within ``km``; otherwise it starts a new station. Order matters exactly as in
    the domestic run: stops are taken in the given order. Returns a list of stop lists.
    """
    index, groups = [], []          # index: (name_key, rounded coord, group number)
    for s in stops:
        key = norm(s.get("stop_name", ""))
        lat, lon = _f2(s.get("stop_lat")), _f2(s.get("stop_lon"))
        rc = (round(lat, 2), round(lon, 2)) if lat is not None and lon is not None else None
        hit = None
        for nm, c, gi in index:
            if nm == key and (c is None or rc is None or haversine_km(c, rc) < km):
                hit = gi
                break
        if hit is None:
            index.append((key, rc, len(groups)))
            groups.append([s])
        else:
            groups[hit].append(s)
    return groups


def trip_stop_ids(cfg: RunConfig, key: str) -> set:
    """stop_ids referenced by at least one trip (stop_times.txt), streamed."""
    import pandas as pd

    ids = set()
    with zipfile.ZipFile(feed_zip_path(cfg, key)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith("stop_times.txt"))
        with zf.open(name) as fh:
            for ch in pd.read_csv(fh, usecols=["stop_id"], dtype=str, chunksize=500_000):
                ids.update(ch["stop_id"].dropna().str.strip())
    return ids


def _is_bus_route_type(rt) -> bool:
    """GTFS bus: basic route_type 3, or extended 700-799 (bus services)."""
    try:
        v = int(str(rt).strip())
    except ValueError:
        return False
    return v == 3 or 700 <= v <= 799


def excluded_stop_ids(cfg: RunConfig, key: str) -> dict:
    """stop_ids served only by excluded trips, by reason: {'agency': set, 'bus_only': set}.

    A trip is excluded if its route's agency is in ``cfg.excluded_agencies[key]`` (reason
    ``agency``) or, with ``cfg.drop_bus_only_stops``, its route_type is a bus type (``bus_only``).
    A stop also served by any other trip is kept.
    """
    import pandas as pd

    agencies = set((getattr(cfg, "excluded_agencies", {}) or {}).get(key, []))
    drop_bus = bool(getattr(cfg, "drop_bus_only_stops", False))
    if not agencies and not drop_bus:
        return {"agency": set(), "bus_only": set()}
    routes = pd.DataFrame(list(read_table(feed_zip_path(cfg, key), "routes.txt")))
    trips = pd.DataFrame(list(read_table(feed_zip_path(cfg, key), "trips.txt")))
    if "route_id" not in routes or "route_id" not in trips or "trip_id" not in trips:
        return {"agency": set(), "bus_only": set()}
    if "route_type" not in routes:
        routes["route_type"] = ""
    ag = routes["agency_id"].astype(str).str.strip() if "agency_id" in routes else pd.Series("", index=routes.index)
    r_agency = set(routes.loc[ag.isin(agencies), "route_id"])
    r_bus = set(routes.loc[routes["route_type"].map(_is_bus_route_type), "route_id"]) if drop_bus else set()
    t_agency = set(trips.loc[trips["route_id"].isin(r_agency), "trip_id"])
    t_bus = set(trips.loc[trips["route_id"].isin(r_bus - r_agency), "trip_id"])
    s_agency, s_bus, good = set(), set(), set()
    with zipfile.ZipFile(feed_zip_path(cfg, key)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith("stop_times.txt"))
        with zf.open(name) as fh:
            for ch in pd.read_csv(fh, usecols=["trip_id", "stop_id"], dtype=str, chunksize=500_000):
                sid = ch["stop_id"].str.strip()
                a, b = ch["trip_id"].isin(t_agency), ch["trip_id"].isin(t_bus)
                s_agency.update(sid[a]); s_bus.update(sid[b]); good.update(sid[~a & ~b])
    s_agency -= good
    return {"agency": s_agency, "bus_only": s_bus - good - s_agency}


def excluded_agency_stop_ids(cfg: RunConfig, key: str) -> set:
    """stop_ids served only by trips of ``cfg.excluded_agencies[key]``."""
    import pandas as pd

    agencies = set((getattr(cfg, "excluded_agencies", {}) or {}).get(key, []))
    if not agencies:
        return set()
    routes = pd.DataFrame(list(read_table(feed_zip_path(cfg, key), "routes.txt")))
    trips = pd.DataFrame(list(read_table(feed_zip_path(cfg, key), "trips.txt")))
    bad_routes = set(routes.loc[routes["agency_id"].astype(str).str.strip().isin(agencies), "route_id"])
    bad_trips = set(trips.loc[trips["route_id"].isin(bad_routes), "trip_id"])
    bad, good = set(), set()
    with zipfile.ZipFile(feed_zip_path(cfg, key)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith("stop_times.txt"))
        with zf.open(name) as fh:
            for ch in pd.read_csv(fh, usecols=["trip_id", "stop_id"], dtype=str, chunksize=500_000):
                m = ch["trip_id"].isin(bad_trips)
                bad.update(ch.loc[m, "stop_id"].str.strip())
                good.update(ch.loc[~m, "stop_id"].str.strip())
    return bad - good


def uic_code(feed_key: str, station_stop_ids, parent_id: str = "") -> str:
    """The station's 7-digit UIC code where the feed carries it, else ''.

    ZSR_SK and UKRZ_UA use UIC codes as stop_ids (country prefix 56 SK, 54 CZ, 55 HU, 51 PL,
    81 AT, 22 UA, … + national number); DRAHY_CZ parents carry the country and national number
    (``czptt:stop:CZ:33014`` -> ``5433014``; its foreign stops too: ``czptt:stop:SK:16446`` ->
    ``5616446``, PL 51, AT 81, DE 80). MÁV, AT and PL use internal ids.

    The SK codes were checked: every Slovak stop of the CZ feed whose code is in ZSR_SK is the same
    station. They also link a stop whose coordinates the CZ feed gets wrong ("Vrbovce zastávka z" sits
    on Vrbovce station's point, 2 km from the real stop).
    """
    if feed_key in ("ZSR_SK", "UKRZ_UA"):
        return next((s for s in station_stop_ids if UIC_RE.match(s)), "")
    if feed_key == "DRAHY_CZ" and parent_id:
        m = _CZ_NUM_RE.search(parent_id)
        return f"{_UIC_COUNTRY[m.group(1)]}{m.group(2)}" if m else ""
    return ""


def build_station_catalog(cfg: RunConfig, key: str):
    """One row per station of one feed.

    * boarding stops (location_type empty / 0) are the members; parents (1) give the station's name
      and point; entrances, nodes and boarding areas (2, 3, 4) are dropped;
    * a boarding stop with a parent_station belongs to that parent's station (``parent``) if a kept
      trip calls at it (children no trip uses are left out unless the station has no used stop);
    * boarding stops without a parent are grouped by ``name_dedup`` (``name_2km`` if merged, else
      ``single``) -- for a feed without parents (ZSR_SK, MÁV, UA) this reproduces the domestic run;
    * ``station_key = <feed_key>:<parent stop_id, or the first member's stop_id>`` (stable).
    """
    import pandas as pd

    rows = [r for r in read_table(feed_zip_path(cfg, key), "stops.txt") if r.get("stop_id", "").strip()]
    seen, stops = set(), []
    for r in rows:
        sid = r["stop_id"].strip()
        if sid not in seen:
            seen.add(sid)
            stops.append({**r, "stop_id": sid, "location_type": (r.get("location_type") or "").strip(),
                          "parent_station": (r.get("parent_station") or "").strip()})
    by_id = {s["stop_id"]: s for s in stops}
    used = trip_stop_ids(cfg, key)
    ex = excluded_stop_ids(cfg, key)
    dropped = ex["agency"] | ex["bus_only"]
    if ex["agency"]:
        print(f"  [{key}] {len(ex['agency'])} stop(s) served only by excluded agencies "
              f"{cfg.excluded_agencies[key]} dropped")
    if ex["bus_only"]:
        print(f"  [{key}] {len(ex['bus_only'])} stop(s) served only by bus routes dropped")

    boarding = [s for s in stops if s["location_type"] in BOARDING_TYPES and s["stop_id"] not in dropped]
    with_parent, loose = {}, []
    for s in boarding:
        p = s["parent_station"]
        if p and p in by_id and by_id[p]["location_type"] == PARENT_TYPE:
            with_parent.setdefault(p, []).append(s)
        else:
            loose.append(s)

    out = []

    def _row(rep_id, name, lat, lon, members, method, parent_id=""):
        ids = [m["stop_id"] for m in members]
        return {"feed_key": key, "station_key": f"{key}:{rep_id}", "stop_name": name,
                "stop_lat": lat, "stop_lon": lon, "stop_ids": ";".join(ids), "n_member_stops": len(ids),
                "dedup_method": method, "in_trips": any(i in used for i in ids),
                "uic_code": uic_code(key, ids, parent_id)}

    n_unused = 0
    for pid, members in with_parent.items():
        p = by_id[pid]
        # A parent's children that no kept trip calls at are not part of the station: in BAHN_AT the
        # bus bays, tram and U-Bahn stops ("Bus an", "86A", "U6", "Vorplatz") hang under the rail
        # station; in PL the station's own unused stop record. A station no trip uses keeps them all.
        if any(m["stop_id"] in used for m in members):
            kept = [m for m in members if m["stop_id"] in used]
            n_unused += len(members) - len(kept)
            members = kept
        lat, lon = _f2(p.get("stop_lat")), _f2(p.get("stop_lon"))
        if lat is None or lon is None:
            pts = [(_f2(m.get("stop_lat")), _f2(m.get("stop_lon"))) for m in members]
            pts = [x for x in pts if None not in x]
            lat, lon = (sum(a for a, _ in pts) / len(pts), sum(b for _, b in pts) / len(pts)) if pts else (None, None)
        out.append(_row(pid, p.get("stop_name", ""), lat, lon, members, "parent", pid))
    for grp in name_dedup(loose):
        first = grp[0]
        out.append(_row(first["stop_id"], first.get("stop_name", ""), _f2(first.get("stop_lat")),
                        _f2(first.get("stop_lon")), grp, "name_2km" if len(grp) > 1 else "single"))
    if n_unused:
        print(f"  [{key}] {n_unused} child stop(s) no trip calls at left out of their parent station")
    cat = pd.DataFrame(out)
    cat.attrs["n_stops"], cat.attrs["n_boarding"], cat.attrs["n_used"] = len(stops), len(boarding), len(used)
    cat.attrs["n_unused_children"] = n_unused
    return cat


# ==========================================================================
# Cross-feed identity
# ==========================================================================

def _union_find(keys):
    parent = {k: k for k in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return find, union


def _names_match(a, ca, b, cb, cfg):
    va = {f(v) for v in _name_variants(a, ca, cfg) for f in (norm_name, core_name)}
    vb = {f(v) for v in _name_variants(b, cb, cfg) for f in (norm_name, core_name)}
    if va & vb:
        return True
    return any(SequenceMatcher(None, x, y).ratio() >= cfg.fuzzy_threshold for x in va for y in vb)


def link_station_groups(tags, cfg: RunConfig, matches=None, conflict_km: float = 5.0,
                        manual_path: Optional[str] = "default"):
    """Give the same physical station in several feeds one ``station_group_id``.

    Links between stations of **different** feeds, three tiers:
      code   -- the same 7-digit UIC code (``uic_code``); pairs further apart than ``conflict_km`` are
                reported as conflicts and not linked;
      place  -- the same LAU, within ``cfg.match_auto_max_km``, and the names match (equal
                ``norm_name`` / ``core_name`` after the country rewrites, or fuzzy >= ``cfg.fuzzy_threshold``);
      match  -- an accepted foreign match (auto / manual) from ``match_foreign_stations``;
      manual -- a reviewed pair accepted in ``cfg.station_group_manual_file``.
    A reviewed ``reject`` there removes any direct link between the two stations.
    Groups are connected components; ``station_group_id = "G:" + smallest station_key``.

    Pairs of stations of different feeds in the same LAU within ``cfg.match_auto_max_km`` whose names
    do not match and that end up in different groups are returned for review (position only is not
    enough: Bratislava predm. / Bratislava-Vinohrady lie 0.17 km apart).

    Returns (tags with station_group_id / group_n_feeds / link_tiers, links, conflicts, review).
    """
    import pandas as pd

    t = tags.copy()
    t["uic_code"] = t.get("uic_code", "").fillna("").astype(str) if "uic_code" in t else ""
    pos = t.set_index("station_key")[["stop_lat", "stop_lon"]].astype(float)

    def dist(a, b):
        pa, pb = pos.loc[a], pos.loc[b]
        if pa.isna().any() or pb.isna().any():
            return None
        return haversine_km((pa.stop_lat, pa.stop_lon), (pb.stop_lat, pb.stop_lon))

    links, conflicts, close = [], [], []
    # tier 1: UIC code
    coded = t[t["uic_code"] != ""]
    for code, g in coded.groupby("uic_code"):
        if g["feed_key"].nunique() < 2:
            continue
        ks = g["station_key"].tolist()
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                a, b = ks[i], ks[j]
                if a.split(":", 1)[0] == b.split(":", 1)[0]:
                    continue
                d = dist(a, b)
                (conflicts if d is not None and d > conflict_km else links).append(
                    {"a": a, "b": b, "tier": "code", "distance_km": d, "uic_code": code})
    # tier 2: same LAU, close, names match
    ins = t[t["in_scope"].astype(str).isin(["True", "true", "1"])]
    for lau, g in ins.groupby("lau_gisco_id"):
        if g["feed_key"].nunique() < 2:
            continue
        recs = g[["station_key", "feed_key", "stop_name", "nuts_rg_01_country_id"]].values.tolist()
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                (a, fa, na, ca), (b, fb, nb, cb) = recs[i], recs[j]
                if fa == fb:
                    continue
                d = dist(a, b)
                if d is None or d > cfg.match_auto_max_km:
                    continue
                if _names_match(na, ca, nb, cb, cfg):
                    links.append({"a": a, "b": b, "tier": "place", "distance_km": d, "uic_code": ""})
                else:
                    close.append({"a": a, "a_feed": fa, "a_name": na, "b": b, "b_feed": fb, "b_name": nb,
                                  "lau_gisco_id": lau, "distance_km": round(d, 3)})
    # tier 3: accepted foreign matches (domestic station -> the foreign station holding the stop)
    if matches is not None and len(matches):
        member_station = {}
        for _, r in t.iterrows():
            rep = r["station_key"].split(":", 1)[1]
            for m in [rep] + str(r.get("stop_ids", "")).split(";"):
                if m:
                    member_station[(r["feed_key"], m)] = r["station_key"]
        acc = matches[(matches["best_match"].astype(str) == "1")].drop_duplicates(["station_id", "feed_key"])
        for _, r in acc.iterrows():
            b = member_station.get((r["feed_key"], str(r["feed_stop_id"])))
            if b and b != r["station_id"] and r["station_id"] in pos.index:
                links.append({"a": r["station_id"], "b": b, "tier": "match", "distance_km": dist(r["station_id"], b),
                              "uic_code": ""})

    # tier 4: reviewed pairs (accept adds a link, reject removes any direct link)
    gm = load_manual_group_pairs(cfg.station_group_manual_file if manual_path == "default" else manual_path)
    keys = set(t["station_key"])
    rejected = {p for p, r in gm.items() if r["decision"] == "reject"}
    links = [l for l in links if frozenset((l["a"], l["b"])) not in rejected]
    for p, r in gm.items():
        if r["decision"] == "accept" and r["a"] in keys and r["b"] in keys:
            links.append({"a": r["a"], "b": r["b"], "tier": "manual", "distance_km": dist(r["a"], r["b"]),
                          "uic_code": ""})

    find, union = _union_find(t["station_key"].tolist())
    for l in links:
        union(l["a"], l["b"])
    t["station_group_id"] = ["G:" + find(k) for k in t["station_key"]]
    t["group_n_feeds"] = t.groupby("station_group_id")["feed_key"].transform("nunique")
    links = pd.DataFrame(links, columns=["a", "b", "tier", "distance_km", "uic_code"])
    tiers = {}
    for _, l in links.iterrows():
        tiers.setdefault("G:" + find(l["a"]), set()).add(l["tier"])
    t["link_tiers"] = t["station_group_id"].map(lambda g: ";".join(sorted(tiers.get(g, set()))))
    review = [c for c in close if find(c["a"]) != find(c["b"]) and frozenset((c["a"], c["b"])) not in rejected]
    review = pd.DataFrame(review, columns=["a", "a_feed", "a_name", "b", "b_feed", "b_name", "lau_gisco_id",
                                           "distance_km"]).sort_values("distance_km").assign(decision="", note="")
    return (t, links, pd.DataFrame(conflicts, columns=["a", "b", "tier", "distance_km", "uic_code"]),
            review.reset_index(drop=True))


def load_manual_group_pairs(path: Optional[str]):
    """Reviewed cross-feed pairs: {frozenset({a, b}): row}; empty if the file is absent."""
    import pandas as pd
    if not path or not os.path.exists(path):
        return {}
    m = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    if not {"a", "b", "decision"} <= set(m.columns):
        raise ValueError(f"{path}: expected columns a, b, decision")
    bad = set(m["decision"]) - {"accept", "reject", ""}
    if bad:
        raise ValueError(f"{path}: decision must be accept / reject, found {sorted(bad)}")
    m = m[m["decision"] != ""]
    return {frozenset((r["a"].strip(), r["b"].strip())): {**r.to_dict(), "a": r["a"].strip(), "b": r["b"].strip()}
            for _, r in m.iterrows()}


# ==========================================================================
# Review list for unresolved LAU tags
# ==========================================================================

def unresolved_review(tags, cfg: RunConfig, k: int = 3):
    """Every in-scope station whose LAU name check stayed ``unresolved``, with the nearby LAUs.

    ``candidates`` lists up to ``k`` LAUs within ``cfg.lau_neighbor_radius_km`` with their best
    name score; ``gisco_id`` / ``note`` are left blank for the reviewer (decisions go to
    ``lau_manual_matches_v2.csv`` with ``feed_key`` and one member ``stop_id``).
    """
    lau = load_lau_subset(cfg)
    names = {g: (n, l) for g, n, l in zip(lau["GISCO_ID"], lau["LAU_NAME_NATIONAL"], lau["LAU_NAME_LATIN"])}
    near_laus = lau_neighbor_finder(lau, cfg)
    sel = tags[(tags["lau_match_method"] == "unresolved") & tags["in_scope"].astype(str).isin(["True", "true", "1"])].copy()
    cands = []
    for _, r in sel.iterrows():
        sc = sorted(((_name_score(r["stop_name"], names[g]), g) for g in near_laus(r["stop_lon"], r["stop_lat"])),
                    reverse=True)[:k]
        cands.append(" | ".join(f"{names[g][0]} [{g}] {s:.2f}" for s, g in sc))
    sel["candidates"] = cands
    sel["gisco_id"] = ""
    sel["note"] = ""
    return sel[["feed_key", "station_key", "stop_name", "stop_ids", "nuts_rg_01_country_id", "lau_gisco_id",
                "lau_name_national", "lau_name_score", "candidates", "gisco_id", "note"]]
