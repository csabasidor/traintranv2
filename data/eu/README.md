# Reference data (`data/eu/`)

Four of the reference datasets are too large for the repository, so they are hosted separately as zip archives. Download each archive and unzip it into `data/eu/`. Each archive unpacks to a folder of the same name, which gives the paths the pipeline expects (set in `traintranv2/config.py`).

| Archive | Size | SHA-256 (first 12) | Contents | Used for |
|---|---:|---|---|---|
| [ref-dgurba-2021-01m.zip](https://cases.idoaba.eu/traintranv2/data/eu/ref-dgurba-2021-01m.zip) | 45.7 MB | `0313dde57a6c` | Eurostat/GISCO Degree of Urbanisation 2021, 1:1 million (`DGURBA_RG_01M_2021_4258.shp`, ETRS89) | DEGURBA class (city, town/suburb, rural) of each municipality |
| [ref-lau-2024-01m.zip](https://cases.idoaba.eu/traintranv2/data/eu/ref-lau-2024-01m.zip) | 63.3 MB | `31d0238eb539` | GISCO Local Administrative Units 2024, 1:1 million (`LAU_RG_01M_2024_4326.geojson`), its release notes, and `subsetv4atua/`, the study-area subset (AT, CZ, HU, PL, SK, UA) | Municipality polygons, the unit of analysis |
| [ref-national-statistical-offices.zip](https://cases.idoaba.eu/traintranv2/data/eu/ref-national-statistical-offices.zip) | 38.5 MB | `09db96906b5c` | Municipal population tables from the national statistical offices, one folder per country (`at/`, `cz/`, `hu/`, `pl/`, `sk/`): the original downloads plus the harmonised `lau_population_2025_<cc>.csv`; `sk/tourism/` holds the Košice visitor-origin statistics for 2025 | Population and age structure per municipality (pop 15+, FL551 age bands); visitor-origin comparison |
| [ref-nuts-2024-01m.zip](https://cases.idoaba.eu/traintranv2/data/eu/ref-nuts-2024-01m.zip) | 68.6 MB | `235df49522dc` | GISCO NUTS 2024, 1:1 million, levels 0–3 (`NUTS_RG_01M_2024_4326_LEVL_*.geojson`), the LAU 2025 – NUTS 2024 correspondence table (`EU-27-LAU-2025-NUTS-2024.xlsx`), metadata, and `subsetv4atua/`, the study-area subset | NUTS3 regions (PPS, kraj colouring), country outlines, the Europe locator map |

## Setup

```bash
cd data/eu
for f in ref-dgurba-2021-01m ref-lau-2024-01m ref-national-statistical-offices ref-nuts-2024-01m; do
  curl -LO https://cases.idoaba.eu/traintranv2/data/eu/$f.zip
  sha256sum $f.zip   # compare with the prefix in the table above
  unzip -q $f.zip
done
```

After unzipping, the pipeline expects these paths:

```
data/eu/ref-dgurba-2021-01m/DGURBA_RG_01M_2021_4258.shp
data/eu/ref-lau-2024-01m/subsetv4atua/LAU_RG_01M_2024_4326.geojson
data/eu/ref-national-statistical-offices/<cc>/lau_population_2025_<cc>.csv
data/eu/ref-nuts-2024-01m/subsetv4atua/NUTS_RG_01M_2024_4326_LEVL_<n>.geojson
```

## Sources and licences

- **DEGURBA, LAU and NUTS:** © EuroGeographics for the administrative boundaries; distributed by Eurostat/GISCO under the [GISCO terms of use](https://ec.europa.eu/eurostat/web/gisco/geodata/administrative-units).
- **Population tables:** taken from Statistik Austria, the Czech Statistical Office (ČSÚ), the Hungarian Central Statistical Office (KSH), Statistics Poland (GUS) and the Statistical Office of the Slovak Republic (ŠÚ SR), under each office's open-data terms.

