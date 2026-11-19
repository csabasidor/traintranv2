"""
Centralised configuration for a traintran analysis run.

All previously hardcoded values live here. Create a RunConfig with
default_config() and override individual fields before calling the
analysis functions.

Environment-variable overrides (all prefixed TRAINTRAN_):
  TRAINTRAN_CITY_SLUG, TRAINTRAN_FEEDS_DIR, TRAINTRAN_OUTPUT_DIR,
  TRAINTRAN_CACHE_DIR, TRAINTRAN_PG_URL (optional database; never stored in this file),
  TRAINTRAN_DGURBA_SHP,
  TRAINTRAN_LAU_FILE, TRAINTRAN_NUTS_DIR, TRAINTRAN_MAX_WINDOW_DAYS
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


def _parse_hhmm(s: str) -> int:
    """GTFS 'HH:MM[:SS]' -> minutes; hours are not wrapped at 24 (validation of the day-trip fields)."""
    parts = str(s).strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"not a valid GTFS HH:MM[:SS] time string: {s!r}")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= m < 60):
        raise ValueError(f"not a valid GTFS HH:MM[:SS] time string: {s!r}")
    return h * 60 + m


@dataclass
class RunConfig:
    # ---- feed registry -------------------------------------------------------
    feeds: dict = field(default_factory=dict)
    enabled: List[str] = field(default_factory=list)

    # ---- hub station matching -----------------------------------------------
    hub_include: List[str] = field(default_factory=list)
    hub_exclude: List[str] = field(default_factory=list)
    hub_latlon: Tuple[float, float] = (0.0, 0.0)
    hub_prox_km: float = 0.0
    city_slug: str = "kosice"

    # ---- transfer parameters ------------------------------------------------
    min_connect_min: int = 10
    max_connect_min: int = 90
    sensitivity_grid: List[Tuple[int, int]] = field(default_factory=list)

    # ---- analysis window ----------------------------------------------------
    max_window_days: Optional[int] = None

    # ---- directory paths ----------------------------------------------------
    feeds_dir: str = "data/feeds"
    output_dir: str = "output"
    cache_dir: str = "data/cache"

    # ---- spatial enrichment -------------------------------------------------
    dgurba_shp: str = "data/eu/ref-dgurba-2021-01m/DGURBA_RG_01M_2021_4258.shp"
    lau_file: str = "data/eu/EU-27-LAU-2025-NUTS-2024.xlsx"
    # NUTS 2024 polygons (GISCO), CZ/SK/AT/HU/PL/UA subset built by
    # notebooks/00_extract_base_data_eu.ipynb; one NUTS_RG_01M_2024_4326_LEVL_<n>.geojson
    # per level. UA level 2 = oblasts from ukr_admin1 (GISCO has UA at level 0 only).
    nuts_dir: str = "data/eu/ref-nuts-2024-01m/subsetv4atua"
    # Optional PostgreSQL/PostGIS connection. No traintranv2 module or notebook reads it: every input
    # (GTFS, LAU, NUTS, DEGURBA, population, OSM) is read from files under data/. It is kept only for
    # anyone who prefers to load the reference layers from a database.
    #
    # Never write credentials here (this file is published). To use a database, set the URL in the
    # environment before starting Python / Jupyter, e.g.
    #     PowerShell:  $env:TRAINTRAN_PG_URL = "postgresql+psycopg2://USER:PASSWORD@localhost:5432/DBNAME"
    #     bash:        export TRAINTRAN_PG_URL="postgresql+psycopg2://USER:PASSWORD@localhost:5432/DBNAME"
    # or a ~/.pgpass file with a URL without the password; then in code:
    #     from sqlalchemy import create_engine
    #     engine = create_engine(cfg.pg_url)        # cfg.pg_url is None when the variable is unset
    pg_url: Optional[str] = None
    lau_fuzzy_threshold: float = 0.6      # min name-similarity ratio to accept a LAU match
    # Nearby-LAU search for the name check: a true circle of lau_neighbor_radius_km around the stop,
    # measured in lau_metric_crs (S-JTSK / Krovak East North, metres).
    lau_neighbor_radius_km: float = 2.0
    lau_metric_crs: str = "EPSG:5514"
    # Countries whose stations keep the LAU of the polygon they lie in, with no name check: their
    # stations are named after villages / localities / parts of a municipality (gmina, Gemeinde, hromada,
    # část obce, településrész), so the station name rarely contains the LAU name (method
    # "polygon_accepted"). Only the domestic SK stations keep the name check.
    lau_polygon_only_countries: List[str] = field(default_factory=lambda: ["PL", "AT", "UA", "CZ", "HU"])
    # Human-reviewed corrections ((feed_key, stop_id) -> lau_gisco_id), applied after
    # and on top of the automated match. Optional: fine if the file is empty
    # or doesn't exist yet. See data/manual/lau_manual_matching_sample.csv for
    # the review process that feeds this file.
    lau_manual_matches_file: str = "data/manual/lau_manual_matches_v2.csv"
    # Station tagging reads only GeoJSON: the LAU subset (polygons, DEGURBA, population,
    # LAU/NUTS identifiers) built by notebooks/00_extract_base_data_eu.ipynb, plus the NUTS
    # subset in nuts_dir. dgurba_shp / lau_file remain for the prep notebooks and population.py.
    lau_subset: str = "data/eu/ref-lau-2024-01m/subsetv4atua/LAU_RG_01M_2024_4326.geojson"
    study_countries: List[str] = field(default_factory=lambda: ["CZ", "SK", "AT", "HU", "PL", "UA"])
    # The domestic feed: analysed on its full calendar; every other feed is foreign and is analysed
    # on its own overlap with this one (nb01a_feeds.pair_windows / feed_roles).
    domestic_feed: str = "ZSR_SK"

    # ---- foreign-station matching -------------------------------------------
    search_countries: List[str] = field(default_factory=list)
    country_feeds: dict = field(default_factory=dict)
    ua_name_map: dict = field(default_factory=dict)
    fuzzy_threshold: float = 0.90
    fuzzy_threshold_grid: List[float] = field(default_factory=lambda: [0.80, 0.85, 0.90, 0.95, 1.0])
    # A name hit is accepted automatically only if the name matches AND the foreign station lies in
    # the same LAU as the domestic one AND within match_auto_max_km of it (99 % of the accepted
    # matches are within 0.44 km); everything else goes to manual review. The same limit applies to
    # the 'place' links between feeds (01b link_station_groups).
    match_auto_max_km: float = 0.5
    # Without an automatic hit, the foreign feed's stations within this radius (same LAU first) are
    # offered as position candidates in the review file.
    match_candidate_km: float = 1.0
    # Reviewed decisions for matches outside the automatic rule (accept / reject per stop pair).
    station_feed_manual_file: str = "data/manual/station_feed_manual.csv"
    # Reviewed decisions on cross-feed station pairs (accept = same station, reject = not).
    station_group_manual_file: str = "data/manual/station_group_manual.csv"
    # Agencies whose stops are dropped from the station catalog (a stop also served by another
    # agency stays). MAV_HU 1743 = Gyermekvasút, the Budapest Children's Railway (heritage line run
    # by children, no link to the network).
    # PL_REG IC = PKP Intercity, taken from PL_IC instead (longer window; no train in both Polish feeds).
    excluded_agencies: dict = field(default_factory=lambda: {"MAV_HU": ["1743"], "PL_REG": ["IC"]})
    # Drop stops whose every trip is a bus (route_type 3 / 700-799): rail-replacement stops
    # (NAD, ZKA, SEV) and bus-only "stations"; a stop also served by a train stays.
    drop_bus_only_stops: bool = True
    # Analysis windows (01a pair_windows) come from the days a feed's trains actually run: from the
    # first to the last day with at least this share of the feed's median daily trains. A calendar's
    # declared span is not used: late snapshots keep it while dropping services already run.
    window_min_share: float = 0.5

    # ---- OSM rail network (notebook 01c) ----------------------------------------
    # One gpkg built from several OSM country dumps (ogr2ogr 'lines' layer); its extraction date is
    # gpkg_contents.last_change, recorded in data/osm/v4_railways.manifest.json.
    osm_railways_gpkg: str = "data/osm/v4_railways.gpkg"
    rail_types: List[str] = field(default_factory=lambda: ["rail", "narrow_gauge"])
    # light_rail ways kept by OSM ref: 112D = Tatranské elektrické železnice (TEŽ), run by ŽSR / ZSSK.
    rail_extra_refs: List[str] = field(default_factory=lambda: ["112D"])
    # ... and light_rail ways with one of these gauges inside the country (NUTS0 polygon): the TEŽ
    # stretches that carry no ref tag (e.g. at Tatranská Lesná). SK has no other 1000 mm light rail.
    rail_light_rail_gauge_by_country: dict = field(default_factory=lambda: {"SK": ["1000"]})
    rail_clip_buffer_km: float = 5.0      # buffer around the six-country NUTS0 union
    rail_metric_crs: str = "EPSG:3035"    # ETRS89-LAEA: covers AT..UA; lengths are geodesic anyway
    rail_node_grid_m: float = 0.5         # vertices within this grid cell become one node
    rail_gap_join_m: float = 25.0         # dead end -> nearest node of another component
    rail_station_link_m: float = 300.0    # a station joins every component within this distance
    rail_snap_max_km: float = 2.0         # farther from any track: no rail distance (snap_too_far)
    # Bridges: a cut-off piece of network carrying stations is joined to the main network by the
    # shortest path over these railway= values (lines under reconstruction in OSM while trains run),
    # at most rail_bridge_max_km long. Only that path is added; no other construction track is used.
    rail_bridge_types: List[str] = field(default_factory=lambda: ["construction"])
    rail_bridge_max_km: float = 15.0
    # Each entry: {station_id, station_name, country, feed_key, search_name}
    # Adds a station to the match table via a specific foreign feed regardless
    # of what country the station belongs to in the main analysis.
    manual_station_matches: List[dict] = field(default_factory=list)

    # ---- destination (see DESTINATIONS / TRAINTRAN_DESTINATION) ---------------
    destination: str = "kosice"
    hub_label: str = "Košice"             # name used in prints, captions and figures
    hub_nuts3: str = "SK042"              # NUTS3 of the hub city (region rank in 05)
    validation_sheet: str = "data/manual/validation_journeys.csv"
    legacy_dir: Optional[str] = "output/ke"   # the legacy traintran run, compared against in 01b-04b; None = none
    visitors_file: Optional[str] = "data/eu/ref-national-statistical-offices/sk/tourism/kosice_visitors_origin_2025_monthly.csv"

    # ---- ZSSK-specific ------------------------------------------------------
    # Kept for old code; the rail distances of 01c use hub_stop_id (derived from hub_station_keys[0]).
    kosice_stop_id: str = "5613600"
    # The hub of notebooks 02 / 03: the Košice main station and every station grouped with it
    # (station_group_id, 01b) in any feed. One station: all 101 trains at Košice predmestie also call at
    # the main station, so no train is lost; journeys are measured to / from the main station.
    hub_station_keys: List[str] = field(default_factory=lambda: ["ZSR_SK:5613600"])
    # Cities split into district LAUs (Slovak mestské časti) count as one unit: one row in every LAU
    # table, coverage figure and model (register T8 / CF-16). Only SK LAUs whose national name starts
    # with the prefix match (two Czech villages are also called Košice). Stations stay separate for
    # transfers. The hub city is excluded from every catchment and denominator.
    city_units: dict = field(default_factory=lambda: {"Košice": "Košice - mestská časť ",
                                                      "Bratislava": "Bratislava - mestská časť "})
    hub_city: str = "Košice"
    # One-transfer pairing: "dated" (per service date, each first leg takes the earliest connection
    # running that day; of first legs sharing a connection on a day only the latest counts) or
    # "legacy" (traintran.analysis.feasible_itineraries: one attempt per first leg).
    transfer_pairing: str = "dated"

    # ---- day-trip feasibility ------------------------------------------------
    # See traintran/daytrip.py for the metric definition. Times are "HH:MM"
    # GTFS-style strings (parsed via parse_gtfs_time_to_min, no 24h wrap).
    daytrip_min_dwell_min: int = 360
    daytrip_max_arrival: str = "11:00"
    daytrip_min_departure: str = "17:00"
    daytrip_max_return: str = "23:59"
    daytrip_dwell_sensitivity: List[int] = field(default_factory=lambda: [240, 360, 480])

    def __post_init__(self):
        # Only the day-trip fields are validated here -- no other RunConfig field
        # has a construction-time check today, so this is scoped narrowly rather
        # than retrofitting validation onto the whole dataclass.
        for field_name in ("daytrip_max_arrival", "daytrip_min_departure", "daytrip_max_return"):
            value = getattr(self, field_name)
            try:
                _parse_hhmm(value)
            except ValueError as exc:
                raise ValueError(f"RunConfig.{field_name}={value!r} is not a valid HH:MM[:SS] time") from exc
        if self.daytrip_min_dwell_min <= 0:
            raise ValueError(f"RunConfig.daytrip_min_dwell_min must be positive, got {self.daytrip_min_dwell_min}")
        if not self.daytrip_dwell_sensitivity:
            raise ValueError("RunConfig.daytrip_dwell_sensitivity must not be empty")
        if self.daytrip_min_dwell_min not in self.daytrip_dwell_sensitivity:
            raise ValueError(
                "RunConfig.daytrip_dwell_sensitivity must include the base "
                f"daytrip_min_dwell_min value ({self.daytrip_min_dwell_min}), got "
                f"{self.daytrip_dwell_sensitivity}"
            )

    @property
    def out_dir(self) -> str:
        return os.path.join(self.output_dir, self.city_slug)

    @property
    def hub_stop_id(self) -> str:
        """stop_id of the first hub station in the domestic feed: the point rail distances are measured from."""
        return self.hub_station_keys[0].split(":", 1)[1]

    @property
    def shared_dir(self) -> str:
        """Where the destination-independent products of 01a / 01b live (feeds, windows, station catalog, tags,
        matches): output/kosice/. Other destinations copy them (nb01a_feeds.shared_inputs)."""
        return os.path.join(self.output_dir, DESTINATIONS["kosice"]["city_slug"])


# Destinations: one profile per hub city. default_config() applies the one named by the environment variable
# TRAINTRAN_DESTINATION (default "kosice"); every notebook then writes to output/<city_slug>/. The hub city's
# LAUs form one unit (city_units) excluded from every catchment; hub_station_keys are the stations a journey
# must reach / leave (each with every station grouped with it across feeds, 01b).
DESTINATIONS = {
    "kosice": {
        "city_slug": "kosice", "hub_station_keys": ["ZSR_SK:5613600"], "hub_city": "Košice", "hub_label": "Košice",
        "hub_nuts3": "SK042", "hub_latlon": (48.72351, 21.268602),
        "hub_include": ["Košice", "kosice"],
        "hub_exclude": ["Košice predmestie, košice predmestie", "košice-", "kosice-", "Barca"],
        "validation_sheet": "data/manual/validation_journeys.csv", "legacy_dir": "output/ke",
        "visitors_file": "data/eu/ref-national-statistical-offices/sk/tourism/kosice_visitors_origin_2025_monthly.csv",
    },
    # Second destination (register VAL-6): the stations where trains into the city end, so every train reaching
    # Bratislava calls at a hub station (682 of 682 ZSR trips) and no journey needs a change inside the city:
    # hl.st.; Petržalka (the Wien trains, about 24 a day, only ~1 continues to hl.st.); Nové Mesto (the 30
    # Prievidza trips end there). Distances are measured from hl.st.
    "bratislava": {
        "city_slug": "bratislava", "hub_station_keys": ["ZSR_SK:5613206", "ZSR_SK:5614576", "ZSR_SK:5614616"],
        "hub_city": "Bratislava", "hub_label": "Bratislava", "hub_nuts3": "SK010", "hub_latlon": (48.159843, 17.10638),
        "hub_include": ["Bratislava hl.st.", "Bratislava-Petržalka", "Bratislava-N.Mesto"], "hub_exclude": [],
        "validation_sheet": "data/manual/validation_journeys_bratislava.csv", "legacy_dir": None,
        "visitors_file": None,
    },
}


_ALL_FEEDS = {
    "ZSR_SK": {
        "country": "SK",
        "provider": "Transitious",
        "provider_url": "https://transitous.org/sources/",
        "url": "https://api.transitous.org/gtfs/sk_zsr.gtfs.zip",
        "filename": "sk_zsr.gtfs.zip",
        "snapshot": "Older snapshot, feed_version 2026-05-13 (sha256 9dc3c38b05fb..., the file of the legacy run): the current file (feed_version 2026-10-27) dropped most services that ran before its publication; it is kept as sk_zsr_new.gtfs.zip and not used.",
        "version": "2026-05-13",
        "data_origin": "Železnice Slovenskej Republiky (ŽSR)",
        "data_origin_url": "https://data.slovensko.sk/datasety/ebeeedf1-aca2-451a-bdc0-35d536714888",
        "operators": ["Železničná spoločnosť Slovensko, a.s.", "RegioJet,a.s.", "Leo Express s.r.o.", "Leo Express Slovensko s.r.o."],
        "license": "CC0-1.0",
        "Notes": "By default the processed Transitous version is used.",
    },


    "MAV_HU": {
        "country": "HU",
        "provider": "Transitious",
        "provider_url": "https://transitous.org/sources/",
        "url": "https://api.transitous.org/gtfs/hu_mav.gtfs.zip",
        "filename": "hu_mav.gtfs.zip",
        "snapshot": "Older snapshot, valid 2026-01-19 .. 2026-11-15 (301-day overlap with ZSR_SK); the current Transitous file is kept as hu_mav_new.gtfs.zip and not used.",
        "version": "2026-05-19",          # feed_info.txt feed_version 20260519 (file saved 2026-05-20)
        "data_origin": "MÁV Személyszállítási Zrt.",
        "data_origin_url": "https://jbb.ghsq.de/gtfs/hu-m%C3%A1v_szem%C3%A9lysz%C3%A1ll%C3%ADt%C3%A1si_zrt..gtfs.zip",
        "operators": ["MÁV Személyszállítási Zrt."],
        "license": "CC0-1.0",
        "Notes": "By default the processed Transitous version is used. MÁV Személyszállítási Zrt. provides the GTFS only via written request.",
    },
    "UKRZ_UA": {
        "country": "UA",
        "provider": "Transitious",
        "provider_url": "https://transitous.org/sources/",
        "url": "https://api.transitous.org/gtfs/ua_ukrzaliznytsya.gtfs.zip",
        "filename": "ua-ukrzaliznytsya.gtfs.zip",
        "snapshot": "Older snapshot, valid 2025-12-14 .. 2026-12-12; the current file is kept as ua-ukrzaliznytsya_new.gtfs.zip and not used.",
        "version": "2026-07-09",          # no feed_info.txt: the date the snapshot was saved
        "data_origin": "OpenStreetMap contributors",
        "data_origin_url": "https://jbb.ghsq.de/gtfs/ua-ukrzaliznytsya.gtfs.zip",
        "operators": ["PKP Intercity", "MÁV Személyszállítási Zrt.", "Železničná spoločnosť Slovensko, a.s.", "Ukrzaliznytsya"],
        "license": "CC0-1.0",
        "Notes": "By default the processed Transitous version is used. Ukrzaliznytsya does not have any obligations under EU legislation with regard to providing open data.",
    },
    "BAHN_AT": {
        "country": "AT",
        "provider": "Transitious",
        "provider_url": "https://transitous.org/sources/",
        "url": "https://api.transitous.org/gtfs/at_Railway-Current-Reference-Data-2026.gtfs.zip",
        "filename": "BAHN_AT.zip",
        "snapshot": "Older snapshot, feed_version 2026-05-19: trains from March 2026; the current file (at_Railway-Current-Reference-Data-2026.gtfs.zip, 2026-11-03) has none before September and is not used.",
        "version": "2026-05-19",
        "data_origin": "Mobilitätsverbünde Österreich OG.",
        "data_origin_url": "https://data.mobilitaetsverbuende.at/api/public/v1/data-sets/66/2026/file",
        "operators": ["OEBB Personenverkehr AG Kundenservice", "WESTbahn Management GmbH", "Raaberbahn AG GYSEV Zrt.", "Deutsche Bahn AG", "City Air Terminal Betriebsgesellschaft m.b.H.", "Montafonerbahn AG", "PKP Intercity", "Ceske Drahy", "Magyar Allamvasutak", "Slovenske zeleznice", "Schweizerische Bundesbahnen", "Österreichische Postbus Aktiengesellschaft"],
        "license": "CC0-1.0",
        "Notes": "By default the processed Transitous version is used. Official schedules are not distributed via governmental channels. Mobilitätsverbünde Österreich OG. provides the GTFS only via written request.",
    },
    "DRAHY_CZ": {
        "country": "CZ",
        "provider": "JrUtil via Transitious",
        "provider_url": "https://transitous.org/sources/",
        "url": "https://api.transitous.org/gtfs/cz_CZPTT.gtfs.zip",
        "filename": "cz_CZPTT_new.gtfs.zip",
        "snapshot": "Snapshot of 2026-11-03 (sha256 9d4dbb07a60c...): unlike the SK and AT files it keeps the whole timetable year (8,050-8,965 trains a day every month, 7-9 % more than the May file) and carries parent stations and UIC codes; the May file (cz_CZPTT.gtfs.zip, no UIC codes, fewer parents) is not used.",
        "version": "2026-11-03",
        "data_origin": "JrUtil",
        "data_origin_url": "https://motis.obehy.cz/get-feeds/cz-czptt-gtfs.zip",
        "operators": ["Železnice Slovenskej Republiky", "České dráhy, a.s.", "Železničná spoločnosť Slovensko, a.s.", "ÖBB-Personenverkehr AG", "PKP INTERCITY S.A.", "SKPL Cargo sp. z o.o.", "ČESKÁ ZÁPADNÍ DRÁHA s. r. o.", "DB Fernverkehr AG", "DB Regio AG", "agilis Verkehrsgesellschaft mbH & Co. KG", "ARRIVA vlaky s.r.o.", "METRANS Rail s.r.o.", "Die Länderbahn GmbH DLB", "RegioJet a.s., Koleje Dolnośląskie S.A.", "Rail system s.r.o.", "GW Train Regio a.s.", "KŽC Doprava, s.r.o.", "MBM rail s.r.o.", "CityRail, a.s.", "AŽD Praha, s.r.o.", "Leo Express s.r.o.", "Lokálka Group, spolek, Railway Capital a.s.", "Slezské zemské dráhy, o.p.s.", "Kladenská dopravní a strojní s.r.o.", "Leo Express Tenders s.r.o.", "Die Länderbahn CZ s.r.o.", "RegioJet ÚK a.s.", "Východočeská dráha s.r.o.", "Gepard Express, SE", "Train Charter Services B.V.", "RegioJet AT GmbH", "Koleje Śląskie Sp. z o.o.", "RegioJet a. s.", "Unknown 51", "Osoblažská úzkorozchodná dráha o.p.s.", "Fundacja Bieszczadzkiej Kolejki Leśnej", "Zubačka provoz s.r.o., nabídková trasa", "Správa Ústecké dráhy s.r.o.", "Unknown 9995"],
        "license": "CC0-1.0",
        "Notes": "By default the processed Transitous version is used. Official schedules are not distributed in GTFS.",
    },

    "PL_IC": {
        "country": "PL",
        "provider": "gtfs.kasznia.net (kasmar00), remix of the mkuran.pl PKP Intercity feed",
        "provider_url": "https://gtfs.kasznia.net/",
        "url": "https://gtfs.kasznia.net/static/pkp-ic.zip",
        "filename": "PL_kasznia.zip",
        "snapshot": "PKP Intercity only (feed_version 2026-05-18, 109,649,923 B): trains on every day 2026-05-18 .. 2026-08-26 (101 days). One of two Polish feeds: PKP Intercity comes from here, every other carrier from PL_REG (no train is in both). How the two windows are combined is decided in notebooks 03.",
        "version": "2026-05-18",
        "data_origin": "PKP Intercity (via mkuran.pl / gtfs.kasznia.net)",
        "data_origin_url": "https://gtfs.kasznia.net/static/pkp-ic.zip",
        "operators": ["PKP Intercity"],
        "license": "CC-BY-4.0",
        "Notes": "Official schedules are not distributed via governmental channels.",
    },
    "PL_REG": {
        "country": "PL",
        "provider": "Mikolaj Kuranowski (PolishTrainsGTFS, schedules from PKP PLK)",
        "provider_url": "https://mkuran.pl/gtfs/",
        "url": "https://gtfs.kasznia.net/static/polish-trains.zip",
        "filename": "polish-trains.zip",
        "snapshot": "All-carrier PolishTrainsGTFS, a rolling one-month feed: this snapshot (feed_version 2026-06-06) runs 2026-06-06 .. 2026-07-06. PKP Intercity (agency IC) is excluded here (excluded_agencies) because it comes from PL_IC with a longer window; the 12 other carriers remain, incl. the regional lines toward the Slovak border (Muszyna - Plavec, Zwardon - Skalite, seasonal Krakow - Poprad).",
        "version": "2026-06-06",
        "data_origin": "PKP PLK (Otwarte Dane Kolejowe), via PolishTrainsGTFS",
        "data_origin_url": "https://gtfs.kasznia.net/static/polish-trains.zip",
        "operators": ["Arriva RP", "Koleje Dolnośląskie", "Koleje Mazowieckie", "Koleje Małopolskie", "Koleje Śląskie", "Koleje Wielkopolskie", "Leo Express", "Łódzka Kolej Aglomeracyjna", "PolRegio", "RegioJet", "SKM Warszawa", "PKP SKM Trójmiasto"],
        "license": "CC-BY-4.0",
        "Notes": "Official schedules are not distributed via governmental channels.",
    },
}


def default_config(destination: str = None) -> RunConfig:
    """Return a RunConfig for a destination: the argument, else TRAINTRAN_DESTINATION, else Košice."""
    env = os.environ.get
    destination = (destination or env("TRAINTRAN_DESTINATION") or "kosice").strip().lower()
    if destination not in DESTINATIONS:
        raise ValueError(f"unknown destination {destination!r}; known: {sorted(DESTINATIONS)}")
    d = DESTINATIONS[destination]

    cfg = RunConfig(
        feeds=_ALL_FEEDS,
        enabled=["ZSR_SK"],

        destination=destination,
        hub_include=list(d["hub_include"]),
        hub_exclude=list(d["hub_exclude"]),
        hub_latlon=tuple(d["hub_latlon"]),
        hub_prox_km=0.0,
        city_slug=env("TRAINTRAN_CITY_SLUG", d["city_slug"]),   # output/<city_slug>/
        hub_station_keys=list(d["hub_station_keys"]),
        hub_city=d["hub_city"], hub_label=d["hub_label"], hub_nuts3=d["hub_nuts3"],
        validation_sheet=d["validation_sheet"], legacy_dir=d["legacy_dir"], visitors_file=d["visitors_file"],

        min_connect_min=10,
        max_connect_min=90,
        sensitivity_grid=[(10, 60), (15, 60), (20, 60), (20, 90), (20, 120), (30, 120)],

        # No cap: the domestic run uses the full feed span; foreign feeds use their own
        # overlap with ZSR_SK (feeds.pair_windows). Set the env var to cap explicitly.
        max_window_days=(int(env("TRAINTRAN_MAX_WINDOW_DAYS")) if env("TRAINTRAN_MAX_WINDOW_DAYS") else None),

        feeds_dir=env("TRAINTRAN_FEEDS_DIR", "data/feeds"),
        output_dir=env("TRAINTRAN_OUTPUT_DIR", "output"),
        cache_dir=env("TRAINTRAN_CACHE_DIR", "data/cache"),

        dgurba_shp=env(
            "TRAINTRAN_DGURBA_SHP",
            "data/eu/ref-dgurba-2021-01m/DGURBA_RG_01M_2021_4258.shp",
        ),
        lau_file=env(
            "TRAINTRAN_LAU_FILE",
            "data/eu/EU-27-LAU-2025-NUTS-2024.xlsx",
        ),
        nuts_dir=env(
            "TRAINTRAN_NUTS_DIR",
            "data/eu/ref-nuts-2024-01m/subsetv4atua",
        ),
        pg_url=env("TRAINTRAN_PG_URL", None),     # from the environment only; see RunConfig.pg_url

        search_countries=["CZ", "HU", "UA", "PL", "AT"],
        country_feeds={
            # country -> the feeds its stations are matched against (several feeds per country allowed)
            "CZ": ["DRAHY_CZ"],
            "HU": ["MAV_HU"],
            "UA": ["UKRZ_UA"],
            "PL": ["PL_IC", "PL_REG"],
            "AT": ["BAHN_AT"],
        },
        ua_name_map={
            "ujgorod":     "Ужгород",
            "mukatschewo": "Мукачево",
            "chop":        "Чоп",
        },
        fuzzy_threshold=0.90,

        kosice_stop_id="5613600",
    )
    if cfg.hub_city not in cfg.city_units:
        raise ValueError(f"hub_city {cfg.hub_city!r} is not a key of city_units {sorted(cfg.city_units)}")
    return cfg
