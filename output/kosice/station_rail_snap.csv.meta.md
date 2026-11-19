# station_rail_snap.csv — Every station of the six feeds on the cleaned OSM rail network: snap, component, rail distance to Košice

- **Produced by:** notebooks/01c_rail_network.ipynb, sections 5-6
- **Generated:** 2026-11-17T11:23:14
- **One row is:** one station of one feed (same rows as station_tags.csv)
- **Rows:** 9,614
- **OSM extraction date:** 2026-05-28T08:42:21.097Z
- **gpkg sha256:** 965df123e363e68c6f32afede42ceb3195bda6394859896a574daca25917ab70

| column | type | description |
|---|---|---|
| `feed_key` | str | Feed of the station. |
| `station_key` | str | Station id (see station_tags). |
| `stop_name` | str | Station name. |
| `nuts_rg_01_country_id` | str | Country of the station's LAU ('??' outside the study area). |
| `status` | str | ok (on the network, distance computed); snap_too_far (no track within rail_snap_max_km: no distance); outside_network (station outside the six countries: not snapped); other_component (snapped, but its network piece does not reach Košice); no_coords. |
| `snap_m` | float | Distance from the station point to the nearest track (m), the projection onto the segment, not the nearest vertex. |
| `n_lines_linked` | int | Lines (OSM ways) the station node is joined to: its nearest track plus the nearest segment of every other way within rail_station_link_m. The shortest path may change line at the station. |
| `n_components_linked` | int | Distinct network components among those lines (> 1: the station joins otherwise separate networks, e.g. a gauge break). |
| `node` | int | Station node id in this run's graph (-1 if not on the network); run-specific, not a stable key. |
| `component_id` | int | Connected component after cleaning (rail_network_components.csv); -1 if not on the network. |
| `component_km` | float | Track length of that component, km. |
| `in_hub_component` | bool | True if the station is on the component that contains the Košice station. |
| `rail_km` | float | Shortest path along the network from the Košice station, km, both station snaps included; empty if unreachable. |
| `geo_km` | float | Geodesic (great-circle, WGS84) distance from the Košice station, km. |
| `detour` | float | rail_km / geo_km (>= 1 by construction; < 1 would be a bug); empty within 0.5 km of the hub. |
