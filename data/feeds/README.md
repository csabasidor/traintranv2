### GTFS feeds

The analysis uses seven GTFS snapshots. Their file names, sizes, SHA-256 checksums and calendar spans are recorded in `data/feeds/feeds.manifest.json`.

| Key | Country | File | Size | Timetable span | Data origin | Retrieved via | Licence | SHA-256 (first 12) |
|---|---|---|---:|---|---|---|---|---|
| ZSR_SK | SK | `sk_zsr.gtfs.zip` | 0.3 MB | 2025-12-14 – 2026-12-12 | Železnice Slovenskej republiky ([data.slovensko.sk](https://data.slovensko.sk/datasety/ebeeedf1-aca2-451a-bdc0-35d536714888)) | Transitous | CC0-1.0 | `9dc3c38b05fb` |
| MAV_HU | HU | `hu_mav.gtfs.zip` | 2.3 MB | 2026-01-19 – 2026-11-15 | MÁV Személyszállítási Zrt. | Transitous | CC0-1.0 | `18aa41295c0d` |
| UKRZ_UA | UA | `ua-ukrzaliznytsya.gtfs.zip` | 3.5 MB | 2025-12-14 – 2026-12-12 | OpenStreetMap contributors | Transitous | CC0-1.0 | `0eecc9437741` |
| BAHN_AT | AT | `BAHN_AT.zip` | 5.2 MB | 2025-12-14 – 2026-12-12 | Mobilitätsverbünde Österreich OG ([data.mobilitaetsverbuende.at](https://data.mobilitaetsverbuende.at/)) | Transitous | CC0-1.0 | `58e7a3839d53` |
| DRAHY_CZ | CZ | `cz_CZPTT_new.gtfs.zip`¹ | 50.2 MB | 2025-12-14 – 2026-12-12 | CZPTT timetable, converted by JrUtil | Transitous | CC0-1.0 | `9d4dbb07a60c` |
| PL_IC | PL | `PL_kasznia.zip`¹ | 109.6 MB | 2026-05-18 – 2026-08-26 | PKP Intercity (via mkuran.pl) | gtfs.kasznia.net | CC-BY-4.0 | `f835b03a7812` |
| PL_REG | PL | `polish-trains.zip` | 10.1 MB | 2026-06-05 – 2026-07-06² | PKP PLK Otwarte Dane Kolejowe (PolishTrainsGTFS) | gtfs.kasznia.net | CC-BY-4.0 | `a07734e3bf29` |

¹ Because of their size, these two files are not in the repository. Download them from:
- Czech feed: <https://cases.idoaba.eu/traintranv2/data/feeds/cz_CZPTT_new.gtfs.zip>
- Polish feed: <https://cases.idoaba.eu/traintranv2/data/feeds/PL_kasznia.zip>

Put both files in `data/feeds/`. Check each against the SHA-256 in `feeds.manifest.json` before running the pipeline.

² The 32-day analysis window of the headline Polish run. PKP Intercity trains are taken from PL_IC and excluded from PL_REG, so no train is in both feeds.
