# Bratislava — second destination (register VAL-6)

The same pipeline and rules as Košice, with only the destination changed. The point is to show the method
transfers to another city. Run with

    TRAINTRAN_DESTINATION=bratislava python notebooks/run_destination.py

The profile is `traintranv2/config.py`, `DESTINATIONS["bratislava"]`. The executed notebooks, with their printed
output, are in `notebooks/runs/bratislava/`. The Košice notebooks and outputs (`output/kosice/`) are not changed by
this run.

## What differs from the Košice run

| | Košice | Bratislava |
|---|---|---|
| hub stations | Košice (main station) | hl.st. + Petržalka + Nové Mesto |
| hub city (one unit, out of every catchment) | Košice, 22 districts | Bratislava, 17 districts |
| other city counted as one unit | Bratislava | Košice |
| rail distances measured from | Košice station | Bratislava hl.st. |
| NUTS3 of the hub | SK042 | SK010 |
| legacy comparison | `output/ke` | none (those cells are skipped) |
| visitors-by-origin data (05 §6) | ŠÚ SR file | none (section not computed) |

**Why three hub stations.** They are the stations where trains into the city end:
- **Petržalka:** about 24 Wien trains a day end here; only ~1 continues to hl.st.
- **Nové Mesto:** all 30 Prievidza trips end here.

With all three, every ŽSR trip that reaches Bratislava calls at a hub station (682 of 682), so no journey depends on
a change of trains inside the city. The other city stations (predmestie, Vinohrady, Rača, Lamač, Vajnory, Vrakuňa,
Železná studienka) are inside the hub city, so they are not origins. They can still be transfer stations.

**Shared inputs.** 01a and 01b do not depend on the destination: feeds, analysis windows, station catalog, LAU
tags and cross-feed station groups. Their outputs were copied from the Košice run, with SHA-256 values listed in
`SHARED_INPUTS.md`, and were not re-run. 01c (rail distances) and 02a–07 were run for Bratislava.

**Foreign journeys: the same rule as Košice.** The train that reaches the hub comes from the ZSR_SK feed. ZSR_SK
carries the Wien–Bratislava trains (Wien Hbf, Meidling, and others appear as direct origins). A train that exists only
in a foreign feed (BAHN_AT, MAV_HU) is not seen. This limit applies to both destinations.

**Route km missing for 213 journeys**, about 0.04 % of rows. These are trains whose track leaves the six-country
network:
- ZSR trains on to Berlin, Hamburg, Dresden and Zürich;
- the Czech Šluknov line, which runs through German territory.

They keep their journey time and frequency, but are left out of distance-based measures. Košice has none.

## Headline comparison (`explore/destination_comparison.csv`)

**Slovak catchment:** all LAUs except the hub city, inbound.

| | Košice | Bratislava |
|---|---|---|
| base population | 5,187,121 | 4,928,505 |
| direct train | 27.3 % (107 LAUs) | 29.6 % (105) |
| newly reached by one transfer | 28.8 % (356) | 23.8 % (354) |
| direct or one transfer | 56.0 % | 53.5 % |
| same-day visit possible, direct / direct or one transfer | 25.5 % / 41.1 % | 27.6 % / 46.1 % |
| rail travellers (M2, beyond 50 km, same-day) | 837,001 | 867,602 |
| newly reached LAUs depending on exactly one transfer station | 65.2 % | 30.5 % |
| transfer penalty (pooled, route km) | 63 min [58, 68] | 35 min [28, 41] |
| domestic direct efficiency | 1.015 min/km, 59 km/h | 1.005 min/km, 60 km/h |

**Abroad:** share of each country's population, inbound.

| | Košice: direct | Košice: direct or one transfer | Bratislava: direct | Bratislava: direct or one transfer |
|---|---|---|---|---|
| CZ | 19.4 % | 55.6 % | 24.4 % | 61.5 % |
| HU | 19.7 % | 40.5 % | 18.2 % | 38.8 % |
| AT | 0 | 34.3 % | 31.2 % | 60.6 % |
| PL (32 days) | 0 | 11.2 % | 7.3 % | 41.6 % |
| UA | 0.6 % | 0.6 % | 0 | 10.0 % |

**Purchasing power:** the Bratislava region (SK010) ranks 1st of 8 in Slovakia and 6th of 150 pooled NUTS3 regions
(2023). As for Košice, this is a characteristic of the region, never a weight.

**Reading.** The method runs unchanged on a second, very different hub: the capital, at the western border, with
direct international trains to Austria and Poland. The domestic picture is close to Košice's. The differences are
where geography predicts them:
- Austria and Poland are reachable directly.
- Gateway dependence is half as strong (30 % vs 65 % of newly reached LAUs on one transfer station). Bratislava sits
  at the meeting point of several lines, while Košice's one-transfer reach funnels through a few junctions.
- The transfer penalty is lower.
