"""
Notebook 01a -- GTFS feeds: download, manifest, roles and analysis windows.

Used by notebooks/01a_feeds_download.ipynb. Also holds the helpers every later notebook of the new
pipeline shares (nb01b and onwards import them from here):

* GTFS reading, time / date parsing, service calendars, validity windows, ``norm_name``;
* feeds: ``feed_zip_path``, ``download_feeds``, ``feed_manifest``, ``pair_windows``, ``feed_roles``;
* the domestic network loader (``load_calendars``, ``load_network``, ``stations_frame``);
* data dictionaries for every output (``SCHEMAS``, ``write_meta``).
"""

import csv
import datetime as dt
import hashlib
import io
import json
import os
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from math import asin, cos, radians, sin, sqrt
from typing import Dict, Iterator, List, Optional, Set, Tuple

from .config import RunConfig


# ==========================================================================
# GTFS helpers
# ==========================================================================

# --------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------

def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(h))


# --------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------

def gtfs_seconds(s: Optional[str]) -> Optional[int]:
    """Parse GTFS 'HH:MM:SS' (hours may exceed 24) to seconds after midnight."""
    if not s:
        return None
    parts = s.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        hh = int(parts[0])
        mm = int(parts[1])
        ss = int(parts[2]) if len(parts) > 2 and parts[2] != "" else 0
    except ValueError:
        return None
    return hh * 3600 + mm * 60 + ss


def fmt_time(sec: Optional[int]) -> str:
    """Format seconds-after-midnight back to HH:MM:SS."""
    if sec is None:
        return ""
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_date(s: str) -> dt.date:
    return dt.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


# --------------------------------------------------------------------------
# GTFS ZIP reading
# --------------------------------------------------------------------------

def read_gtfs_table(zf: zipfile.ZipFile, name: str) -> Iterator[dict]:
    """Yield dict rows from a GTFS .txt table, or nothing if absent."""
    candidates = [n for n in zf.namelist() if n.lower().endswith(name.lower())]
    if not candidates:
        return
    with zf.open(candidates[0]) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8-sig", newline="")
        yield from csv.DictReader(text)


def read_table(zip_path: str, filename: str) -> Iterator[dict]:
    """Open a zip by path and yield rows from the named GTFS file."""
    with zipfile.ZipFile(zip_path) as zf:
        yield from read_gtfs_table(zf, filename)


def load_stops_from_zip(zip_path: str) -> Dict[str, dict]:
    """Return {stop_id: {stop_name, stop_lat, stop_lon}} from a GTFS zip."""
    stops = {}
    for r in read_table(zip_path, "stops.txt"):
        sid = r.get("stop_id", "").strip()
        if sid:
            stops[sid] = {
                "stop_name": r.get("stop_name", ""),
                "stop_lat":  r.get("stop_lat", ""),
                "stop_lon":  r.get("stop_lon", ""),
            }
    return stops


def load_service_info(zip_path: str) -> Dict[str, dict]:
    """
    Return {trip_id: {service_id, service_start, service_end, weekdays}}.
    weekdays is a 7-char '0'/'1' string Mon–Sun.
    """
    WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    trip_service: Dict[str, str] = {}
    for r in read_table(zip_path, "trips.txt"):
        tid = r.get("trip_id", "").strip()
        sid = r.get("service_id", "").strip()
        if tid and sid:
            trip_service[tid] = sid

    cal: Dict[str, dict] = {}
    for r in read_table(zip_path, "calendar.txt"):
        sid = r.get("service_id", "").strip()
        if sid:
            cal[sid] = {
                "start": r.get("start_date", ""),
                "end":   r.get("end_date", ""),
                "wd":    "".join(r.get(d, "0") for d in WD),
            }

    cal_dates: Dict[str, List[str]] = defaultdict(list)
    for r in read_table(zip_path, "calendar_dates.txt"):
        sid = r.get("service_id", "").strip()
        if sid and r.get("exception_type") == "1":
            cal_dates[sid].append(r.get("date", ""))

    result: Dict[str, dict] = {}
    for tid, sid in trip_service.items():
        if sid in cal:
            c = cal[sid]
            result[tid] = {
                "service_id":    sid,
                "service_start": c["start"],
                "service_end":   c["end"],
                "weekdays":      c["wd"],
            }
        elif sid in cal_dates:
            dates = sorted(cal_dates[sid])
            result[tid] = {
                "service_id":    sid,
                "service_start": dates[0] if dates else "",
                "service_end":   dates[-1] if dates else "",
                "weekdays":      "",
            }
        else:
            result[tid] = {
                "service_id":    sid,
                "service_start": "",
                "service_end":   "",
                "weekdays":      "",
            }
    return result


# --------------------------------------------------------------------------
# Calendar / window helpers
# --------------------------------------------------------------------------

def service_rundates_in_window(
    calendar: List[dict],
    calendar_dates: List[dict],
    window_days: List[dt.date],
) -> Dict[str, Set[dt.date]]:
    """For each service_id, the set of dates within window_days on which it runs."""
    window_set = set(window_days)
    wd_names = ["monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday"]
    runs: Dict[str, Set[dt.date]] = defaultdict(set)
    cal_index: Dict[str, tuple] = {}
    for r in calendar:
        try:
            start = parse_date(r["start_date"])
            end   = parse_date(r["end_date"])
        except (KeyError, ValueError):
            continue
        cal_index[r["service_id"]] = (
            start, end,
            [r.get(n, "0") == "1" for n in wd_names],
        )
    for d in window_days:
        wi = d.weekday()
        for sid, (start, end, flags) in cal_index.items():
            if start <= d <= end and flags[wi]:
                runs[sid].add(d)
    for r in calendar_dates:
        try:
            d = parse_date(r["date"])
        except (KeyError, ValueError):
            continue
        if d not in window_set:
            continue
        sid = r.get("service_id")
        if r.get("exception_type") == "1":
            runs[sid].add(d)
        elif r.get("exception_type") == "2":
            runs[sid].discard(d)
    return runs


def feed_validity_interval(
    calendar: List[dict],
    calendar_dates: List[dict],
) -> Tuple[Optional[dt.date], Optional[dt.date]]:
    """Return (min_date, max_date) spanned by a feed's service calendar."""
    dates: List[dt.date] = []
    for r in calendar:
        try:
            dates += [parse_date(r["start_date"]), parse_date(r["end_date"])]
        except (KeyError, ValueError):
            pass
    for r in calendar_dates:
        try:
            dates.append(parse_date(r["date"]))
        except (KeyError, ValueError):
            pass
    if not dates:
        return None, None
    return min(dates), max(dates)


def overlap_window(
    intervals: List[Tuple[Optional[dt.date], Optional[dt.date]]],
    max_days: Optional[int] = None,
) -> List[dt.date]:
    """Dates in the common intersection of all feed validity intervals."""
    valid = [(lo, hi) for (lo, hi) in intervals if lo is not None]
    if not valid:
        return []
    lo = max(x[0] for x in valid)
    hi = min(x[1] for x in valid)
    if lo > hi:
        return []
    days: List[dt.date] = []
    d = lo
    while d <= hi:
        days.append(d)
        d += dt.timedelta(days=1)
    if max_days is not None and len(days) > max_days:
        days = days[:max_days]
    return days


# --------------------------------------------------------------------------
# Text normalisation
# --------------------------------------------------------------------------

# Letters that NFD does not decompose into base + combining mark, so the mark-stripping pass
# below would leave them untouched (CF-27: 'Łódź' normalised to 'łodz', never matching 'lodz').
_FOLD = str.maketrans({
    "ł": "l", "Ł": "l", "ø": "o", "Ø": "o", "đ": "d", "Đ": "d", "ı": "i",
    "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe", "þ": "th", "ð": "d",
})


def norm_name(s: str) -> str:
    """Lowercase, fold diacritics (two passes), collapse whitespace.

    Pass 1 maps the letters NFD cannot decompose (ł ø đ ß æ œ ı …); pass 2 strips the
    combining marks NFD exposes (š -> s, ő -> o, ž -> z).
    """
    s = str(s or "").strip().translate(_FOLD).lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


# ==========================================================================
# Feeds: files, download, manifest, windows, roles
# ==========================================================================

def feed_zip_path(cfg: RunConfig, key: str) -> str:
    fname = cfg.feeds.get(key, {}).get("filename") or f"{key}.zip"
    return os.path.join(cfg.feeds_dir, fname)


def feed_exists(cfg: RunConfig, key: str) -> bool:
    p = feed_zip_path(cfg, key)
    return os.path.exists(p) and os.path.getsize(p) > 0


def download_feeds(cfg: RunConfig, keys: List[str] = None) -> None:
    """Download GTFS ZIP files for the enabled feeds (or a specific key list); skip if present."""
    try:
        import requests
    except ImportError:
        sys.exit("Install requests:  pip install requests")

    os.makedirs(cfg.feeds_dir, exist_ok=True)
    targets = keys if keys is not None else cfg.enabled

    for key in targets:
        if key not in cfg.feeds:
            print(f"  [warn] Unknown feed key: {key}")
            continue
        f = cfg.feeds[key]
        dest = feed_zip_path(cfg, key)
        if feed_exists(cfg, key):
            print(f"  [skip] {key} already at {dest}")
            continue
        print(f"  [get ] {key} <- {f['url']}")
        r = requests.get(f["url"], timeout=300)
        r.raise_for_status()
        with open(dest, "wb") as fh:
            fh.write(r.content)
        print(f"         {len(r.content) / 1e6:.1f} MB -> {dest}")


def list_feeds(cfg: RunConfig) -> None:
    """Print status of all feeds in the registry."""
    for key in cfg.feeds:
        status = "OK" if feed_exists(cfg, key) else "missing"
        enabled = "enabled" if key in cfg.enabled else "disabled"
        print(f"  {key:12s}  [{enabled:8s}]  [{status}]  {feed_zip_path(cfg, key)}")


def feed_span(cfg: RunConfig, key: str):
    """(first, last) service date of a feed from calendar.txt + calendar_dates.txt."""
    with zipfile.ZipFile(feed_zip_path(cfg, key)) as zf:
        names = set(zf.namelist())
        cal = list(read_gtfs_table(zf, "calendar.txt")) if "calendar.txt" in names else []
        cdt = list(read_gtfs_table(zf, "calendar_dates.txt")) if "calendar_dates.txt" in names else []
    return feed_validity_interval(cal, cdt)


def daily_rail_trips(cfg: RunConfig, key: str, days: List[dt.date]):
    """Trips running on each of ``days`` (pd.Series indexed by date), from calendar.txt +
    calendar_dates.txt. Bus routes (with cfg.drop_bus_only_stops) and cfg.excluded_agencies are left
    out, as in the station catalog and the timetable of notebooks 02 / 03.

    A feed's calendar can claim a span its trips do not fill: a snapshot published late in the year
    keeps the calendar but drops services already run. Counting trips per day shows it.
    """
    import numpy as np
    import pandas as pd
    from .nb01b_stations import _is_bus_route_type

    zp = feed_zip_path(cfg, key)
    routes = pd.DataFrame(list(read_table(zp, "routes.txt")))
    for c in ("agency_id", "route_type"):
        if c not in routes:
            routes[c] = ""
    trips = pd.DataFrame(list(read_table(zp, "trips.txt")))[["trip_id", "route_id", "service_id"]]
    trips = trips.merge(routes[["route_id", "route_type", "agency_id"]], on="route_id", how="left")
    excluded = set((getattr(cfg, "excluded_agencies", {}) or {}).get(key, []))
    keep = ~trips["agency_id"].astype(str).isin(excluded)
    if getattr(cfg, "drop_bus_only_stops", False):
        keep &= ~trips["route_type"].map(_is_bus_route_type)
    n_by_svc = trips[keep].groupby("service_id").size()

    n, d0 = len(days), days[0]
    wd = np.array([(d0.weekday() + k) % 7 for k in range(n)])
    names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    on: Dict[str, np.ndarray] = {}
    for r in read_table(zp, "calendar.txt"):
        sid = r.get("service_id")
        if sid not in n_by_svc.index:
            continue
        try:
            a, b = (parse_date(r["start_date"]) - d0).days, (parse_date(r["end_date"]) - d0).days
        except (KeyError, ValueError):
            continue
        a, b = max(a, 0), min(b, n - 1)
        arr = on.setdefault(sid, np.zeros(n, bool))
        if a <= b:
            flags = np.array([r.get(x, "0") == "1" for x in names])
            arr[a:b + 1] |= flags[wd[a:b + 1]]
    for r in read_table(zp, "calendar_dates.txt"):
        sid = r.get("service_id")
        if sid not in n_by_svc.index:
            continue
        try:
            k = (parse_date(r["date"]) - d0).days
        except (KeyError, ValueError):
            continue
        if 0 <= k < n:
            on.setdefault(sid, np.zeros(n, bool))[k] = r.get("exception_type") == "1"
    cnt = np.zeros(n)
    for sid, arr in on.items():
        cnt += arr * n_by_svc[sid]
    return pd.Series(cnt.astype(int), index=pd.to_datetime(days), name=key)


def service_span(cfg: RunConfig, key: str, days: List[dt.date], min_share: float = None):
    """(first, last) day of ``days`` whose trips reach ``min_share`` x the median of the days with
    service (cfg.window_min_share, default 0.5). None if the feed runs nothing in ``days``."""
    import numpy as np

    s = daily_rail_trips(cfg, key, days)
    share = min_share if min_share is not None else getattr(cfg, "window_min_share", 0.5)
    nz = s[s > 0]
    if nz.empty:
        return None
    ok = np.flatnonzero(s.to_numpy() >= share * float(nz.median()))
    return days[int(ok[0])], days[int(ok[-1])]


def _sha256(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _feed_info_version(path: str):
    """feed_version (and feed_start/end_date) from feed_info.txt, if the feed has one."""
    import csv, io, zipfile
    with zipfile.ZipFile(path) as z:
        if "feed_info.txt" not in z.namelist():
            return None
        row = next(csv.DictReader(io.TextIOWrapper(z.open("feed_info.txt"), encoding="utf-8-sig")), None)
    if not row:
        return None
    parts = [row.get(k, "").strip() for k in ("feed_version", "feed_start_date", "feed_end_date")]
    return " / ".join(p for p in parts if p) or None


def feed_manifest(cfg: RunConfig, keys: List[str] = None, write: bool = True) -> List[dict]:
    """File, size, sha256 and calendar span of every (or the given) feed.

    Written to ``<feeds_dir>/feeds.manifest.json`` so the provenance of a run is machine-readable
    rather than notebook output (register REP-2).
    """
    rows = []
    for key in (keys or list(cfg.feeds)):
        path = feed_zip_path(cfg, key)
        if not feed_exists(cfg, key):
            rows.append({"key": key, "file": os.path.basename(path), "present": False})
            continue
        lo, hi = feed_span(cfg, key)
        f = cfg.feeds[key]
        rows.append({
            "key": key, "country": f.get("country"), "file": os.path.basename(path),
            "present": True, "bytes": os.path.getsize(path), "sha256": _sha256(path),
            # the file's modification time on disk: the date the snapshot was saved (no download log exists)
            "file_date": dt.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds"),
            "feed_info_version": _feed_info_version(path),
            "version": f.get("version"), "url": f.get("url"), "provider": f.get("provider"),
            "provider_url": f.get("provider_url"), "data_origin": f.get("data_origin"),
            "data_origin_url": f.get("data_origin_url"), "license": f.get("license"),
            "span_start": lo.isoformat() if lo else None, "span_end": hi.isoformat() if hi else None,
            "span_days": (hi - lo).days + 1 if lo and hi else None,
            "snapshot": f.get("snapshot"),
            "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
        })
    if write:
        with open(os.path.join(cfg.feeds_dir, "feeds.manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2, ensure_ascii=False)
    return rows


# Products of 01a / 01b that do not depend on the destination (feeds, windows, station catalog, LAU tags, matches,
# cross-feed groups) plus the timetable cache of 02 / 03 (keyed by feed and window only). 01c is re-run per
# destination: its rail distances are measured from the hub.
SHARED_FILES = ["windows.json", "feed_roles.csv", "feed_monthly_trains.csv", "feed_stop_tags.parquet",
                "station_tags.csv", "station_tags_review.csv", "station_feed_matches.csv", "station_feed_review.csv",
                "station_group_links.csv", "station_group_conflicts.csv", "station_group_review.csv"]


def shared_inputs(cfg: RunConfig, overwrite: bool = False) -> List[str]:
    """Copy the destination-independent products from the Košice run (cfg.shared_dir) into cfg.out_dir.

    Does nothing for Košice itself. Each file's .meta.md travels with it; SHARED_INPUTS.md records the source,
    the files and their SHA-256, so a destination's run shows exactly which station identity it used.
    """
    import shutil
    src, dst = cfg.shared_dir, cfg.out_dir
    if os.path.abspath(src) == os.path.abspath(dst):
        return []
    os.makedirs(dst, exist_ok=True)
    done, lines, copied = [], [], 0
    for name in SHARED_FILES:
        for f in (name, name + ".meta.md"):
            s, d = os.path.join(src, f), os.path.join(dst, f)
            if not os.path.exists(s):
                if f == name:
                    raise FileNotFoundError(f"{s} missing: run 01a / 01b for Košice first")
                continue
            if overwrite or not os.path.exists(d):
                shutil.copy2(s, d)
                copied += 1
            done.append(f)
            if f == name:
                lines.append(f"| `{f}` | `{_sha256(d)[:16]}` |")
    tsrc, tdst = os.path.join(src, "timetable"), os.path.join(dst, "timetable")
    if os.path.isdir(tsrc):
        for f in os.listdir(tsrc):
            os.makedirs(tdst, exist_ok=True)
            if overwrite or not os.path.exists(os.path.join(tdst, f)):
                shutil.copy2(os.path.join(tsrc, f), os.path.join(tdst, f))
                copied += 1
        done.append("timetable/")
    note = os.path.join(dst, "SHARED_INPUTS.md")
    if not copied and os.path.exists(note):      # nothing copied: keep the note (and its date) as it is
        return done
    with open(note, "w", encoding="utf-8") as fh:
        fh.write(f"# Shared inputs of the {cfg.hub_label} run\n\n"
                 f"Copied from `{src}` on {dt.datetime.now().isoformat(timespec='seconds')} by "
                 f"`nb01a_feeds.shared_inputs`. These products of notebooks 01a / 01b do not depend on the "
                 f"destination (feeds, analysis windows, station catalog, LAU tags, cross-feed station groups), so "
                 f"they are identical for every destination. The timetable cache (`timetable/`, keyed by feed and "
                 f"window) is copied too. 01c and everything after it are run for this destination.\n\n"
                 f"| file | sha256 (first 16) |\n|---|---|\n" + "\n".join(lines) + "\n")
    return done


def pair_windows(cfg: RunConfig, home: str = None, keys: List[str] = None) -> Dict[str, dict]:
    """Analysis window per feed, from the days its trains actually run (``service_span``), not the
    calendar's declared span.

    The domestic feed: its service span inside its calendar span. Every other feed: the overlap of
    its service span with the domestic one. home defaults to cfg.domestic_feed. Returns
    {key: {start, end, days, basis, calendar_start, calendar_end}} (ISO dates); a feed with no
    overlap gets days = 0.
    """
    home = home or cfg.domestic_feed
    cal = feed_span(cfg, home)
    cal_days = [cal[0] + dt.timedelta(days=k) for k in range((cal[1] - cal[0]).days + 1)]
    share = getattr(cfg, "window_min_share", 0.5)
    rule = f"days with >= {share:.0%} of the feed's median daily trains"
    hs = service_span(cfg, home, cal_days)
    out = {home: {"start": hs[0].isoformat(), "end": hs[1].isoformat(), "days": (hs[1] - hs[0]).days + 1,
                  "basis": f"service span ({rule})",
                  "calendar_start": cal[0].isoformat(), "calendar_end": cal[1].isoformat()}}
    home_days = [d for d in cal_days if hs[0] <= d <= hs[1]]
    for key in (keys or [k for k in cfg.feeds if k != home]):
        if key == home or not feed_exists(cfg, key):
            continue
        fc = feed_span(cfg, key)
        sp = service_span(cfg, key, home_days)
        days = overlap_window([hs, sp]) if sp else []
        out[key] = {"start": days[0].isoformat() if days else None,
                    "end": days[-1].isoformat() if days else None,
                    "days": len(days), "basis": f"service span ({rule}) overlapping {home}",
                    "calendar_start": fc[0].isoformat() if fc[0] else None,
                    "calendar_end": fc[1].isoformat() if fc[1] else None}
    return out


def monthly_trains(cfg: RunConfig, keys: List[str] = None):
    """Mean trains per day by month for each feed over the domestic calendar span (coverage check)."""
    import pandas as pd

    home = cfg.domestic_feed
    cal = feed_span(cfg, home)
    days = [cal[0] + dt.timedelta(days=k) for k in range((cal[1] - cal[0]).days + 1)]
    cols = {}
    for key in (keys or list(cfg.feeds)):
        if feed_exists(cfg, key):
            s = daily_rail_trips(cfg, key, days)
            cols[key] = s.groupby(s.index.to_period("M")).mean().round(0).astype(int)
    return pd.DataFrame(cols)


def feed_roles(cfg: RunConfig, keys: List[str] = None):
    """One row per feed: key, country, role (domestic / foreign), file, snapshot note and window."""
    import pandas as pd

    keys = keys or list(cfg.feeds)
    win = pair_windows(cfg, keys=keys)
    rows = []
    for key in keys:
        f = cfg.feeds[key]
        w = win.get(key, {})
        rows.append({
            "feed_key": key, "country": f.get("country"),
            "role": "domestic" if key == cfg.domestic_feed else "foreign",
            "file": os.path.basename(feed_zip_path(cfg, key)), "present": feed_exists(cfg, key),
            "provider": f.get("provider"), "data_origin": f.get("data_origin"),
            "window_start": w.get("start"), "window_end": w.get("end"), "window_days": w.get("days"),
            "window_basis": w.get("basis"), "snapshot": f.get("snapshot") or "",
        })
    return pd.DataFrame(rows)


# ==========================================================================
# Domestic network (stations as the domestic run registers them)
# ==========================================================================

# --------------------------------------------------------------------------
# Step 1: load calendars & find the common overlap window
# --------------------------------------------------------------------------

def load_calendars(cfg: RunConfig) -> Tuple[dict, dict]:
    """
    Pass 1: read each enabled feed's calendar files and compute the common
    overlap window.

    Returns
    -------
    feed_calendars : {feed_key: (calendar_list, calendar_dates_list)}
    feed_intervals : {feed_key: (min_date, max_date)}
    """
    feed_calendars: Dict[str, tuple] = {}
    feed_intervals: Dict[str, tuple] = {}

    for key in cfg.enabled:
        path = feed_zip_path(cfg, key)
        if not os.path.exists(path):
            print(f"  [warn] {key}.zip missing — run download_feeds() first")
            continue
        with zipfile.ZipFile(path) as zf:
            calendar = list(read_gtfs_table(zf, "calendar.txt"))
            cal_dates = list(read_gtfs_table(zf, "calendar_dates.txt"))
        feed_calendars[key] = (calendar, cal_dates)
        lo, hi = feed_validity_interval(calendar, cal_dates)
        feed_intervals[key] = (lo, hi)
        print(f"  {key}: valid {lo} .. {hi}")

    return feed_calendars, feed_intervals


# --------------------------------------------------------------------------
# Step 2: parse GTFS and build the link network
# --------------------------------------------------------------------------

def load_network(cfg: RunConfig, feed_calendars: dict, feed_intervals: dict) -> dict:
    """
    Pass 2: parse trips against the overlap window and build all analysis
    data structures.

    Returns a 'network' dict with keys:
      window          : List[date]
      window_set      : Set[date]
      all_stops       : {gid: {name,lat,lon,country,...}}
      link_trips      : {(src_gid,dst_gid): [trip_obs,...]}
      link_feed       : {(src_gid,dst_gid): set of feed keys}
      trip_svc_info   : {trip_id: {service_id,service_start,service_end,weekdays}}
      min_transfer_sec: {gid: int seconds}
      kosice_gids     : set of gids matching the hub station
    """
    window = overlap_window(list(feed_intervals.values()), cfg.max_window_days)

    if not window:
        print("\n  [!] No common validity window across enabled feeds.")
    else:
        full_lo = max(x[0] for x in feed_intervals.values() if x[0])
        full_hi = min(x[1] for x in feed_intervals.values() if x[1])
        capped = cfg.max_window_days is not None and (full_hi - full_lo).days + 1 > cfg.max_window_days
        print(f"\n  Common overlap window: {window[0]} .. {window[-1]} "
              f"({len(window)} days){' [capped]' if capped else ''}")

    window_set = set(window)

    all_stops: Dict[str, dict] = {}
    name_coord_index: Dict[tuple, str] = {}
    link_trips = defaultdict(list)
    link_feed = defaultdict(set)
    trip_svc_info: Dict[str, dict] = {}
    min_transfer_sec: Dict[str, int] = {}

    # CF-28: dedup on gtfs_helpers.norm_name (diacritics folded), the normaliser foreign
    # matching uses, instead of a bare strip().lower().
    _norm = norm_name

    def register_station(name, lat, lon, country):
        key_name = _norm(name)
        rc = (round(lat, 2), round(lon, 2)) if lat is not None else None
        for (nm, c), gid in name_coord_index.items():
            if nm == key_name:
                if c is None or rc is None:
                    return gid
                if haversine_km((c[0], c[1]), (rc[0], rc[1])) < 2.0:
                    return gid
        gid = f"S{len(all_stops):05d}"
        all_stops[gid] = {"name": name, "lat": lat, "lon": lon, "country": country}
        name_coord_index[(key_name, rc)] = gid
        return gid

    WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    for key in cfg.enabled:
        path = feed_zip_path(cfg, key)
        if not os.path.exists(path) or key not in feed_calendars:
            continue
        country = cfg.feeds[key]["country"]
        calendar, cal_dates = feed_calendars[key]
        print(f"\n  Parsing {key} ({cfg.feeds[key]['provider']})")

        runs = service_rundates_in_window(calendar, cal_dates, window) if window else {}

        with zipfile.ZipFile(path) as zf:
            stops = {r["stop_id"]: r for r in read_gtfs_table(zf, "stops.txt")}

            trip_service: Dict[str, str] = {}
            for r in read_gtfs_table(zf, "trips.txt"):
                trip_service[r["trip_id"]] = r.get("service_id")

            _cal_by_svc: Dict[str, dict] = {}
            for r in calendar:
                sid = r.get("service_id", "")
                if sid:
                    _cal_by_svc[sid] = {
                        "service_start": r.get("start_date", ""),
                        "service_end":   r.get("end_date", ""),
                        "weekdays":      "".join(r.get(d, "0") for d in WD),
                    }
            for tid, sid in trip_service.items():
                c = _cal_by_svc.get(sid or "", {})
                trip_svc_info[tid] = {
                    "service_id":    sid or "",
                    "service_start": c.get("service_start", ""),
                    "service_end":   c.get("service_end", ""),
                    "weekdays":      c.get("weekdays", ""),
                }

            local_to_gid: Dict[str, str] = {}
            for sid, r in stops.items():
                name = r.get("stop_name", "")
                try:
                    lat = float(r["stop_lat"]); lon = float(r["stop_lon"])
                except (KeyError, ValueError):
                    lat = lon = None
                gid = register_station(name, lat, lon, country)
                local_to_gid[sid] = gid
                all_stops[gid].setdefault("stop_ids", []).append(sid)
                all_stops[gid].setdefault("feed", key)

            for r in read_gtfs_table(zf, "transfers.txt"):
                f_id = r.get("from_stop_id"); t_id = r.get("to_stop_id")
                if f_id and t_id and f_id in local_to_gid and t_id in local_to_gid:
                    g = local_to_gid[f_id]
                    if local_to_gid.get(t_id) == g and r.get("transfer_type") == "2":
                        try:
                            min_transfer_sec[g] = int(r["min_transfer_time"])
                        except (KeyError, ValueError):
                            pass

            good_trips = {tid for tid, sid in trip_service.items() if runs.get(sid)}
            n_drop = len(trip_service) - len(good_trips)
            print(f"    trips active in window: {len(good_trips)} ({n_drop} outside window dropped)")

            seq = defaultdict(list)
            for r in read_gtfs_table(zf, "stop_times.txt"):
                tid = r["trip_id"]
                if tid not in good_trips:
                    continue
                try:
                    order = int(r["stop_sequence"])
                except (KeyError, ValueError):
                    continue
                arr = gtfs_seconds(r.get("arrival_time"))
                dep = gtfs_seconds(r.get("departure_time"))
                if arr is None: arr = dep
                if dep is None: dep = arr
                seq[tid].append((order, r["stop_id"], arr, dep))

            for tid, lst in seq.items():
                lst.sort()
                pts = [(local_to_gid[s], arr, dep)
                       for _, s, arr, dep in lst if s in local_to_gid]
                run_dates = runs.get(trip_service.get(tid), set()) & window_set
                if not run_dates:
                    continue
                for i in range(len(pts)):
                    gi, _, dep_i = pts[i]
                    for j in range(i + 1, len(pts)):
                        gj, arr_j, _ = pts[j]
                        if gi == gj or dep_i is None or arr_j is None:
                            continue
                        dur_min = (arr_j - dep_i) / 60.0
                        if dur_min < 0:
                            continue
                        link_trips[(gi, gj)].append({
                            "dep": dep_i, "arr": arr_j, "dur": dur_min,
                            "dates": run_dates, "feed": key, "trip_id": tid,
                        })
                        link_feed[(gi, gj)].add(key)

    # locate hub (Košice) stations
    kosice_gids: set = set()
    hub_inc = [t.lower() for t in cfg.hub_include]
    hub_exc = [t.lower() for t in cfg.hub_exclude]
    for gid, s in all_stops.items():
        nm = (s["name"] or "").strip().lower()
        if any(tok in nm for tok in hub_inc) and not any(tok in nm for tok in hub_exc):
            kosice_gids.add(gid)
        elif s["lat"] is not None and cfg.hub_prox_km > 0:
            if haversine_km((s["lat"], s["lon"]), cfg.hub_latlon) <= cfg.hub_prox_km:
                kosice_gids.add(gid)

    print(f"\n  Hub station candidates: {len(kosice_gids)}")
    for gid in kosice_gids:
        s = all_stops[gid]
        print(f"    {gid}  {s['name']}  ({s['lat']},{s['lon']})  {s['country']}")
    if not kosice_gids:
        print("  [!] No hub station matched. Inspect station_catalog.csv and "
              "adjust hub_include / hub_latlon in RunConfig.")

    return {
        "window":           window,
        "window_set":       window_set,
        "all_stops":        all_stops,
        "link_trips":       dict(link_trips),
        "link_feed":        dict(link_feed),
        "trip_svc_info":    trip_svc_info,
        "min_transfer_sec": min_transfer_sec,
        "kosice_gids":      kosice_gids,
    }


# --------------------------------------------------------------------------
# Step 3: spatially enrich stations
# --------------------------------------------------------------------------

def stations_frame(network: dict):
    """One row per registered station: stop_id (= station gid), name, coordinates, member stop_ids."""
    import pandas as pd
    return pd.DataFrame([
        {"stop_id": gid, "stop_name": s["name"], "stop_lat": s["lat"], "stop_lon": s["lon"],
         "stop_ids": ";".join(s.get("stop_ids", [])), "feed": s.get("feed", "")}
        for gid, s in network["all_stops"].items()
    ])



# ==========================================================================
# Data dictionaries (<file>.meta.md)
# ==========================================================================

_TAG_COLS = {
    "in_scope": ("bool", "True if the point lies in a LAU of the six study countries (CZ, SK, AT, HU, PL, UA)."),
    "nuts_rg_01_country_id": ("str", "Country code of the LAU (CNTR_CODE); '??' outside the study area."),
    "nuts_rg_01_country_name": ("str", "Country name (NUTS 2024 level 0, NAME_LATN)."),
    "nuts_rg_01_region_id": ("str", "NUTS 2024 level-2 region of the LAU (UA: oblast code UA01...)."),
    "nuts_rg_01_region_name": ("str", "Name of that NUTS2 region / oblast."),
    "nuts3_id": ("str", "NUTS 2024 level-3 region of the LAU ('??' for UA: GISCO has no UA level 3)."),
    "nuts3_name": ("str", "Name of that NUTS3 region."),
    "lau_gisco_id": ("str", "GISCO_ID of the chosen LAU in the LAU 2024 subset (EU: <CC>_<LAU code>; UA: hromada pcode)."),
    "lau_code": ("str", "National LAU code of the chosen LAU (text; leading zeros kept)."),
    "lau_name_national": ("str", "LAU name, national spelling (LAU_NAME_NATIONAL)."),
    "lau_name_latin": ("str", "LAU name, Latin spelling (LAU_NAME_LATIN)."),
    "degurba": ("int", "Degree of urbanisation of the LAU: 1 city, 2 town/suburb, 3 rural (DEGURBA 2021; UA from GHSL)."),
    "lau_name_score": ("float", "Name similarity (0-1, SequenceMatcher on norm_name) between the station name and the chosen LAU's national or Latin name, whichever is higher; 1.0 for manual corrections."),
    "lau_match_method": ("str", "How the LAU was chosen: contains_primary / fuzzy_primary (polygon LAU confirmed by name), contains_neighbor / fuzzy_neighbor (moved to a LAU within lau_neighbor_radius_km whose name fits better), unresolved (polygon LAU kept, name does not fit: review), polygon_accepted (station in a lau_polygon_only_countries country, PL / AT / UA / CZ / HU: the polygon LAU is taken without a name check), manual, ua_fallback."),
    "lau_name_in_polygon": ("bool", "True if the station lies in the LAU polygon and the names contain each other (method contains_primary)."),
    "lau_pop_2024": ("float", "LAU population from GISCO LAU 2024 (POP_2024; UA hromadas: 1 Jan 2022)."),
    "lau_area_km2": ("float", "LAU area in km2 (AREA_KM2)."),
    "lau_pop_2025": ("float", "LAU population at end-2025 from the national statistical office (00_b* notebooks); empty for UA."),
    "lau_pop_15_64_2025": ("float", "Of which aged 15-64, end-2025."),
    "lau_pop_65plus_2025": ("float", "Of which aged 65 and over, end-2025."),
    "nuts2_id": ("str", "NUTS2 code of the LAU (same as nuts_rg_01_region_id)."),
    "lau_tag_source": ("str", "Which step decided the LAU: polygon, name_neighbor, manual, ua_fallback, outside (no LAU in scope)."),
}

SCHEMAS = {
    "station_tags": {
        "title": "Station catalog of all six feeds with LAU / NUTS / DEGURBA / population tags and cross-feed groups",
        "produced_by": "notebooks/01b_stations_tag_match.ipynb, sections 3, 4 and 6",
        "row": "one station of one feed: platforms merged into their GTFS parent station; stops without a parent merged by the domestic rule (same norm_name within 2 km)",
        "columns": {
            "feed_key": ("str", "Feed the station comes from (ZSR_SK = domestic; DRAHY_CZ, MAV_HU, BAHN_AT, PL_IC, PL_REG, UKRZ_UA = foreign)."),
            "station_key": ("str", "Stable station id: <feed_key>:<parent stop_id, or the first member stop_id>."),
            "stop_name": ("str", "Station name in that feed (the parent's name where there is one)."),
            "stop_lat": ("float", "Latitude (WGS84): the parent's point, else the first member stop's."),
            "stop_lon": ("float", "Longitude (WGS84)."),
            "stop_ids": ("str", "Semicolon-joined boarding stop_ids (platforms) of the station in that feed; trips reference these. Join key together with feed_key."),
            "n_member_stops": ("int", "Number of boarding stops merged into the station."),
            "dedup_method": ("str", "parent (platforms of one GTFS parent station), name_2km (stops with the same norm_name within 2 km), single."),
            "in_trips": ("bool", "True if at least one member stop is used by a trip (stop_times.txt)."),
            "uic_code": ("str", "7-digit UIC station code where the feed carries it (ZSR_SK, UKRZ_UA stop_ids; DRAHY_CZ country prefix + national number from its parent id: CZ 54, SK 56, PL 51, AT 81, DE 80); empty for MAV_HU, BAHN_AT, PL_IC, PL_REG."),
            **_TAG_COLS,
            "station_group_id": ("str", "Cross-feed identity: the same physical station in several feeds shares this id (G: + smallest station_key of the group)."),
            "group_n_feeds": ("int", "Number of feeds the station's group spans (1 = only this feed)."),
            "link_tiers": ("str", "How the group was linked: code (same UIC code), place (same LAU, within match_auto_max_km, names match), match (accepted foreign match), manual (reviewed pair in station_group_manual.csv); semicolon-joined, empty for single-feed groups."),
        },
    },
    "station_tags_review": {
        "title": "Review list: in-scope stations whose LAU name check stayed unresolved (all feeds)",
        "produced_by": "notebooks/01b_stations_tag_match.ipynb, section 4",
        "row": "one station with lau_match_method = unresolved inside the six study countries",
        "columns": {
            "feed_key": ("str", "Feed of the station."),
            "station_key": ("str", "Station id (see station_tags)."),
            "stop_name": ("str", "Station name."),
            "stop_ids": ("str", "Member stop_ids; use one of them with feed_key in lau_manual_matches_v2.csv."),
            "nuts_rg_01_country_id": ("str", "Country of the polygon LAU."),
            "lau_gisco_id": ("str", "LAU the station was kept in (its polygon)."),
            "lau_name_national": ("str", "That LAU's national name."),
            "lau_name_score": ("float", "Best name similarity to that LAU (national / Latin)."),
            "candidates": ("str", "Up to three nearby LAUs (within lau_neighbor_radius_km, measured in lau_metric_crs) with their best name score, 'name [GISCO_ID] score', separated by ' | '."),
            "gisco_id": ("str", "Empty; the reviewer's chosen LAU."),
            "note": ("str", "Empty; the reviewer's note."),
        },
    },
    "station_group_links": {
        "title": "Cross-feed links between stations (and rejected code links)",
        "produced_by": "notebooks/01b_stations_tag_match.ipynb, section 6",
        "row": "one link between two stations of different feeds",
        "columns": {
            "a": ("str", "station_key of one station."),
            "b": ("str", "station_key of the other."),
            "tier": ("str", "code / place / match / manual (see station_tags.link_tiers); in the conflicts file: code links rejected for distance."),
            "distance_km": ("float", "Distance between the two stations, km."),
            "uic_code": ("str", "The shared UIC code (code tier)."),
        },
    },
    "feed_roles": {
        "title": "Feeds and their role in the analysis",
        "produced_by": "notebooks/01a_feeds_download.ipynb",
        "row": "one GTFS feed",
        "columns": {
            "feed_key": ("str", "Feed key used throughout the pipeline."),
            "country": ("str", "Country of the feed's operator / data origin."),
            "role": ("str", "domestic (analysed on its full calendar) or foreign (analysed on its overlap with the domestic feed)."),
            "file": ("str", "File in data/feeds/."),
            "present": ("bool", "True if the file is on disk."),
            "provider": ("str", "Who distributes the GTFS (e.g. Transitious)."),
            "data_origin": ("str", "Who produces the underlying data."),
            "window_start": ("str", "First day of the analysis window (ISO date)."),
            "window_end": ("str", "Last day of the analysis window."),
            "window_days": ("int", "Length of the window in days."),
            "window_basis": ("str", "How the window was set: the service span (first to last day with >= window_min_share of the median daily trains) for the domestic feed, its overlap with the domestic one for a foreign feed."),
            "snapshot": ("str", "Note when an older snapshot is used on purpose (HU, UA)."),
        },
    },
    "feed_stop_tags": {
        "title": "Polygon check of every stop of every feed",
        "produced_by": "notebooks/01b_stations_tag_match.ipynb, section 1",
        "row": "one stop (stops.txt row, deduplicated on stop_id) of one feed",
        "columns": {
            "feed_key": ("str", "Feed key (ZSR_SK, DRAHY_CZ, MAV_HU, BAHN_AT, PL_IC, PL_REG, UKRZ_UA)."),
            "stop_id": ("str", "stop_id in that feed."),
            "stop_name": ("str", "stop_name in that feed."),
            "stop_lat": ("float", "Latitude (WGS84); empty if the feed gives none."),
            "stop_lon": ("float", "Longitude (WGS84)."),
            "location_type": ("str", "GTFS location_type (1 = station / parent, empty or 0 = stop / platform)."),
            "parent_station": ("str", "GTFS parent_station (the station a platform belongs to)."),
            "GISCO_ID": ("str", "LAU polygon containing the stop (point in polygon, no name check); empty outside the subset."),
            "CNTR_CODE": ("str", "Country of that LAU."),
            "LAU_CODE": ("str", "National LAU code of that LAU."),
            "NUTS2_ID": ("str", "NUTS2 region (UA: oblast)."),
            "NUTS3_ID": ("str", "NUTS3 region (empty for UA)."),
            "DGURBA": ("int", "Degree of urbanisation of the LAU (1 city, 2 town/suburb, 3 rural)."),
            "in_scope": ("bool", "True if inside a LAU of the six study countries."),
        },
    },
    "station_feed_matches": {
        "title": "Foreign-station matches: domestic stations located in CZ/HU/AT/PL/UA found in their national feed",
        "produced_by": "notebooks/01b_stations_tag_match.ipynb, section 5",
        "row": "accepted matches: one row per stop of the matched foreign catalog station -- its GTFS parent and the member stops trains use (best_match = 1); review / rejected / unmatched: one row per station x feed (best_match = 0)",
        "columns": {
            "station_id": ("str", "Run-specific station id (see station_tags.stop_id)."),
            "station_name": ("str", "Station name in the ZSR_SK feed."),
            "station_stop_ids": ("str", "';'-joined ZSR_SK stop_ids of the station (stable key)."),
            "country": ("str", "Country the station is tagged in (decides which feed is searched)."),
            "feed_key": ("str", "National feed searched."),
            "status": ("str", "auto (name or UIC code + same LAU + within match_auto_max_km), manual (reviewed accept), rejected (reviewed reject), review (not used downstream until decided)."),
            "reason": ("str", "Why a row is in review: different_lau, too_far, name_below_threshold, no_coordinates (';'-joined, for a name hit), position_candidate (no name hit, but a station of the feed within match_candidate_km), no_name_match (nothing nearby either); the reviewer's note for manual / rejected."),
            "match_type": ("str", "Name tier of the hit: exact (normalised names equal), core (equal after dropping generic station words: Bahnhof, Bhf., pályaudvar, stacja kolejowa, železniční stanice, stanica, the CZ request flag z), code (same UIC code), sequence (fuzzy, SequenceMatcher ratio), manual, none."),
            "score": ("float", "Name similarity of the hit (1.0 for exact and manual)."),
            "feed_stop_id": ("str", "Matched stop_id in the national feed."),
            "feed_stop_name": ("str", "Its stop_name."),
            "feed_station_name": ("str", "Name of the foreign catalog station the stop belongs to (station_tags.stop_name of that feed)."),
            "feed_stop_lat": ("float", "Its latitude."),
            "feed_stop_lon": ("float", "Its longitude."),
            "feed_location_type": ("str", "Its GTFS location_type."),
            "feed_parent_station": ("str", "Its GTFS parent_station."),
            "match_distance_km": ("float", "Haversine distance between the domestic station and the best hit, km."),
            "same_lau": ("bool", "True if the hit's station lies in the same LAU as the domestic station (both from station_tags)."),
            "station_lat": ("float", "Latitude of the domestic station."),
            "station_lon": ("float", "Longitude of the domestic station."),
            "station_gisco_id": ("str", "LAU (GISCO_ID) of the domestic station (from station_tags)."),
            "feed_gisco_id": ("str", "LAU (GISCO_ID) of the hit's station (from station_tags)."),
            "alternatives": ("str", "For review rows: position candidates -- up to three stations of the feed within match_candidate_km, same LAU first, 'name [stop_id] distance km, same LAU | LAU <id>', ' | '-separated."),
            "suggested_feed_stop_id": ("str", "For review rows: the first position candidate's stop_id (copy into station_feed_manual.feed_stop_id to accept it)."),
            "best_match": ("int", "1 = accepted (auto / manual), read by the foreign extraction; 0 = not used."),
        },
    },
    "station_feed_review": {
        "title": "Review queue: foreign matches outside the automatic rule",
        "produced_by": "notebooks/01b_stations_tag_match.ipynb, section 5",
        "row": "one station x feed with status review",
        "columns": {
            "station_name": ("str", "Station name in the ZSR_SK feed."),
            "station_stop_ids": ("str", "ZSR_SK stop_ids of the station; copy one into station_feed_manual.station_stop_id."),
            "country": ("str", "Country of the station."),
            "feed_key": ("str", "National feed searched."),
            "reason": ("str", "Why it needs review (see station_feed_matches.reason)."),
            "match_type": ("str", "Name tier of the best hit, or none."),
            "score": ("float", "Name similarity of the best hit."),
            "feed_stop_id": ("str", "Best name hit in the feed (may be empty)."),
            "feed_stop_name": ("str", "Its name."),
            "match_distance_km": ("float", "Distance to the best hit, km."),
            "same_lau": ("bool", "True if the best hit is in the same LAU."),
            "feed_station_name": ("str", "Station the best hit belongs to."),
            "alternatives": ("str", "Position candidates: up to three feed stations within match_candidate_km, same LAU first, with stop_id, distance and LAU."),
            "suggested_feed_stop_id": ("str", "The first position candidate's stop_id."),
            "decision": ("str", "Empty; to be filled when copied into data/manual/station_feed_manual.csv (accept / reject)."),
            "note": ("str", "Empty; reviewer's note."),
        },
    },
    "station_group_review": {
        "title": "Review queue: close stations of different feeds in one LAU whose names do not match",
        "produced_by": "notebooks/01b_stations_tag_match.ipynb, section 6",
        "row": "one pair of stations (different feeds, same LAU, within match_auto_max_km) left in different groups",
        "columns": {
            "a": ("str", "station_key of one station."),
            "a_feed": ("str", "Its feed."),
            "a_name": ("str", "Its name."),
            "b": ("str", "station_key of the other station."),
            "b_feed": ("str", "Its feed."),
            "b_name": ("str", "Its name."),
            "lau_gisco_id": ("str", "The shared LAU."),
            "distance_km": ("float", "Distance between the two stations, km."),
            "decision": ("str", "Empty; accept (same station) / reject, when copied into data/manual/station_group_manual.csv."),
            "note": ("str", "Empty; reviewer's note."),
        },
    },
    "station_group_manual": {
        "title": "Reviewed cross-feed station pairs (input)",
        "produced_by": "hand-maintained from station_group_review.csv",
        "row": "one reviewed pair",
        "columns": {
            "a": ("str", "station_key of one station."),
            "a_name": ("str", "Its name (for readability)."),
            "b": ("str", "station_key of the other station."),
            "b_name": ("str", "Its name (for readability)."),
            "decision": ("str", "accept (link: same physical station) or reject (remove any direct link); empty rows are ignored."),
            "note": ("str", "Reason of the decision."),
        },
    },
    "station_feed_manual": {
        "title": "Reviewed foreign-match decisions (input)",
        "produced_by": "hand-maintained; seeded by notebooks/01b_stations_tag_match.ipynb, section 5",
        "row": "one reviewed station x feed decision",
        "columns": {
            "station_name": ("str", "Station name (for readability)."),
            "station_stop_id": ("str", "One ZSR_SK stop_id of the station (the key)."),
            "feed_key": ("str", "National feed."),
            "feed_stop_id": ("str", "The accepted (or rejected) stop_id in that feed; an accepted stop is expanded to its catalog station (parent + the member stops trains use)."),
            "feed_stop_name": ("str", "Its name (for readability)."),
            "decision": ("str", "accept or reject; empty rows are ignored."),
            "note": ("str", "Reason / source of the decision."),
        },
    },
    "lau_manual_matches_v2": {
        "title": "Manual LAU corrections, re-keyed to the ZSR_SK stop_id (input)",
        "produced_by": "converted once from data/manual/lau_manual_matches.csv by notebooks/01b_stations_tag_match.ipynb, section 2; then hand-maintained",
        "row": "one reviewed station -> LAU correction",
        "columns": {
            "feed_key": ("str", "Feed of the station (the converted legacy rows are ZSR_SK)."),
            "stop_id": ("str", "Feed stop_id the correction applies to (any member stop of a station)."),
            "stop_name": ("str", "Station name (from the legacy catalog)."),
            "gisco_id": ("str", "LAU to assign (GISCO_ID in the LAU 2024 subset)."),
            "note": ("str", "Reviewer's note from the original review."),
            "conversion": ("str", "Only ok / ok_near rows are applied. ok (same name, <= 100 m), ok_near (<= 1 km), unmatched / unmatched_far (no such stop in the current feed), dropped_out_of_scope (DE/CH), ua_review (old hard-coded UA id), gisco_not_in_subset."),
            "legacy_station_id": ("str", "The old run-specific S000nn id the row was keyed on."),
            "match_distance_km": ("float", "Distance between the legacy station and the matched feed stop, km."),
        },
    },
    "station_rail_snap": {
        "title": "Every station of the six feeds on the cleaned OSM rail network: snap, component, rail distance to Košice",
        "produced_by": "notebooks/01c_rail_network.ipynb, sections 5-6",
        "row": "one station of one feed (same rows as station_tags.csv)",
        "columns": {
            "feed_key": ("str", "Feed of the station."),
            "station_key": ("str", "Station id (see station_tags)."),
            "stop_name": ("str", "Station name."),
            "nuts_rg_01_country_id": ("str", "Country of the station's LAU ('??' outside the study area)."),
            "status": ("str", "ok (on the network, distance computed); snap_too_far (no track within rail_snap_max_km: no distance); outside_network (station outside the six countries: not snapped); other_component (snapped, but its network piece does not reach Košice); no_coords."),
            "snap_m": ("float", "Distance from the station point to the nearest track (m), the projection onto the segment, not the nearest vertex."),
            "n_lines_linked": ("int", "Lines (OSM ways) the station node is joined to: its nearest track plus the nearest segment of every other way within rail_station_link_m. The shortest path may change line at the station."),
            "n_components_linked": ("int", "Distinct network components among those lines (> 1: the station joins otherwise separate networks, e.g. a gauge break)."),
            "node": ("int", "Station node id in this run's graph (-1 if not on the network); run-specific, not a stable key."),
            "component_id": ("int", "Connected component after cleaning (rail_network_components.csv); -1 if not on the network."),
            "component_km": ("float", "Track length of that component, km."),
            "in_hub_component": ("bool", "True if the station is on the component that contains the Košice station."),
            "rail_km": ("float", "Shortest path along the network from the Košice station, km, both station snaps included; empty if unreachable."),
            "geo_km": ("float", "Geodesic (great-circle, WGS84) distance from the Košice station, km."),
            "detour": ("float", "rail_km / geo_km (>= 1 by construction; < 1 would be a bug); empty within 0.5 km of the hub."),
        },
    },
    "rail_network_components": {
        "title": "Connected components of the cleaned OSM rail network",
        "produced_by": "notebooks/01c_rail_network.ipynb, section 4",
        "row": "one connected component after gap joins and station links, longest first",
        "columns": {
            "component_id": ("int", "Component id (as in station_rail_snap.component_id)."),
            "length_km": ("float", "Track length (+ gap joins), km."),
            "n_nodes": ("int", "Graph nodes in the component."),
            "n_stations": ("int", "Stations snapped onto it."),
            "has_hub": ("bool", "True for the component holding the Košice station."),
            "centre_lon": ("float", "Mean longitude of its nodes (for mapping)."),
            "centre_lat": ("float", "Mean latitude of its nodes."),
        },
    },
    "rail_network_length": {
        "title": "Rail network length per country: track-km and line-km",
        "produced_by": "notebooks/01c_rail_network.ipynb, section 3b",
        "row": "one country (inside its border), plus the six together",
        "columns": {
            "region": ("str", "Country code, or 'all six'."),
            "track_km": ("float", "Summed length of the kept OSM ways inside the country: every mapped track counts (a double-track line about twice)."),
            "line_km": ("float", "Line length, parallel tracks counted once: (A30 - A15) / (2 x 15 m) from 15 m and 30 m flat-ended buffers (nb01c_rail_network.track_and_line_km)."),
            "track_per_line": ("float", "track_km / line_km: about 1 for single-track networks, up to 2+ for multi-track."),
        },
    },
    "rail_network_cleaning": {
        "title": "OSM rail network: every filtering and cleaning step with counts",
        "produced_by": "notebooks/01c_rail_network.ipynb, sections 2-5",
        "row": "one step of the build, in order",
        "columns": {
            "step": ("str", "What was done."),
            "ways": ("float", "OSM ways after the step (ways steps only)."),
            "km": ("float", "Track length after the step, km (where measured)."),
            "nodes": ("float", "Graph nodes after the step (graph steps only)."),
            "components": ("float", "Connected components after the step (graph steps only)."),
            "added_edges": ("float", "Edges the step added (gap joins, station snaps / links)."),
            "note": ("str", "Rule and parameters of the step."),
        },
    },
    "rail_network_ways": {
        "title": "The OSM ways that form the rail network (after type filter, de-duplication, clip)",
        "produced_by": "notebooks/01c_rail_network.ipynb, sections 2-3",
        "row": "one OSM way (clipped part) used in the graph; rebuild the network from the gpkg with this list",
        "columns": {
            "osm_id": ("str", "OSM way id."),
            "railway": ("str", "railway= value (rail, narrow_gauge, or light_rail for the TEŽ)."),
            "ref": ("str", "OSM ref (e.g. 112D for the TEŽ), where tagged."),
            "name": ("str", "OSM name, where tagged."),
            "length_km": ("float", "Length inside the study area, km (EPSG:3035)."),
        },
    },
    "rail_network_bridges": {
        "title": "Cut-off pieces of the rail network that carry stations, and whether a construction bridge joined them",
        "produced_by": "notebooks/01c_rail_network.ipynb, section 5b",
        "row": "one connected component with snapped stations that did not reach the Košice station after gap joins and station links",
        "columns": {
            "component_id": ("int", "Component id before bridging (this run's numbering)."),
            "stations": ("str", "Up to six station names on it."),
            "n_stations": ("int", "Stations (all feeds) snapped onto it."),
            "bridged": ("bool", "True if a path over track + rail_bridge_types within rail_bridge_max_km joined it to the main network."),
            "bridge_km": ("float", "Length of the added path, km."),
            "construction_km": ("float", "Of which over railway=construction (lines under reconstruction in OSM), km."),
            "note": ("str", "Rule applied, or why no bridge was found."),
        },
    },
    "rail_network_added_edges": {
        "title": "Edges added to the OSM rail network by cleaning and station snapping",
        "produced_by": "notebooks/01c_rail_network.ipynb, sections 4-5",
        "row": "one added edge",
        "columns": {
            "kind": ("str", "gap_join (dead end -> another component within rail_gap_join_m), snap (station -> its nearest track), station_link (station -> another component within rail_station_link_m: gauge breaks), bridge (segment of the shortest path joining a cut-off piece with stations to the main network over track + rail_bridge_types, see rail_network_bridges.csv)."),
            "a_lon": ("float", "Longitude of one end."),
            "a_lat": ("float", "Latitude of one end."),
            "b_lon": ("float", "Longitude of the other end."),
            "b_lat": ("float", "Latitude of the other end."),
            "length_m": ("float", "Edge length, m."),
        },
    },
}


def write_meta(path, key, frame=None, extra=None):
    """Write ``<path>.meta.md`` from SCHEMAS[key]; check the frame's columns against it."""
    s = SCHEMAS[key]
    cols = s["columns"]
    if frame is not None:
        missing = [c for c in frame.columns if c not in cols]
        stale = [c for c in cols if c not in frame.columns]
        if missing or stale:
            raise ValueError(f"{key}: undocumented columns {missing}, documented but absent {stale}")
        order = list(frame.columns)
    else:
        order = list(cols)
    lines = [
        f"# {os.path.basename(path)} — {s['title']}",
        "",
        f"- **Produced by:** {s['produced_by']}",
        f"- **Generated:** {dt.datetime.now().isoformat(timespec='seconds')}",
        f"- **One row is:** {s['row']}",
    ]
    if frame is not None:
        lines.append(f"- **Rows:** {len(frame):,}")
    for k, v in (extra or {}).items():
        lines.append(f"- **{k}:** {v}")
    lines += ["", "| column | type | description |", "|---|---|---|"]
    lines += [f"| `{c}` | {cols[c][0]} | {cols[c][1]} |" for c in order]
    meta_path = f"{path}.meta.md"
    with open(meta_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return meta_path
