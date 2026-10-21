# Observed SNPP VIIRS 375 m active-fire detections, July–October 2025

These are observed fire-pixel detections from NASA's science-quality
[VNP14IMG Collection 002](https://doi.org/10.5067/VIIRS/VNP14IMG.002),
Suomi-NPP, acquired July 1–October 31, 2025 UTC. They are separate from the
synthetic county-month panel and have not been integrated into the model results.

## Spatial and temporal scope

The west/south/east/north bounding box is **(-124.6, 32.4, -113.9, 42.1)**.
Fire-pixel centers are included when they fall inside or on its edges.
The box includes areas outside California; no state-boundary clipping is applied.
The CMR query selected 707 intersecting swaths from collection
`C2734202914-LPCLOUD`. The original NetCDF files preserve full swaths.

| File | Detections |
| --- | ---: |
| [firms_viirs_ca_202507.csv](firms_viirs_ca_202507.csv) | 7,137 |
| [firms_viirs_ca_202508.csv](firms_viirs_ca_202508.csv) | 11,336 |
| [firms_viirs_ca_202509.csv](firms_viirs_ca_202509.csv) | 7,892 |
| [firms_viirs_ca_202510.csv](firms_viirs_ca_202510.csv) | 2,459 |
| Total | 28,824 |

The rows represent individual satellite fire-pixel detections. Repeated
observations of the same fire are retained; rows do not represent distinct
wildfire events, burned area, or state-only fire counts.

## Coverage and validation

[daily_catalog_coverage.csv](daily_catalog_coverage.csv) records matching
source-granule counts for all 123 requested dates. **July 5, 6, and 7, 2025
have no matching swaths.** These are missing source observations, not evidence
of zero fire activity. At least one intersecting swath exists on the other
120 dates; this does not establish complete daily coverage at every location.
NASA documents [Suomi-NPP data outages](https://modaps.modaps.eosdis.nasa.gov/services/production/outages_suomi_npp.html)
during this period.

[manifest.json](manifest.json) preserves source URLs, acquisition intervals,
byte sizes, SHA-256 checksums, and per-granule bounding-box detection counts.
[validation.json](validation.json) records independent verification of all
707 source checksums and file sizes, CSV totals, spatial and temporal limits,
confidence values, and uniqueness of source-granule/line/sample identifiers.
All CSV rows have nonmissing, nonnegative fire radiative power.
[csv_checksums.json](csv_checksums.json) records checksums for the published CSVs.

The manifest and validation JSON preserve the original download paths under
`data/raw/`. The CSVs published in this directory are byte-identical copies.
The 1,334,237,870-byte NetCDF archive remains local and can be reproduced with
the downloader; it is excluded from Git by the repository's raw-data policy.

## Fields

| Columns | Meaning |
| --- | --- |
| `latitude`, `longitude` | Fire-pixel center, decimal degrees; copied from `FP_latitude` and `FP_longitude` |
| `frp` | Fire radiative power in MW, copied from `FP_power` |
| `confidence` | Original `FP_confidence`: 7 = low, 8 = nominal, 9 = high; all levels retained |
| `bright_ti4`, `bright_ti5` | Fire-pixel I4/I5 brightness temperatures in kelvin |
| `line`, `sample` | Original source pixel indices |
| `acq_date`, `acq_time` | Source-granule start in UTC; `acq_time` is four-character HHMM |
| `satellite`, `instrument`, `version` | `N` (Suomi-NPP), `VIIRS`, and collection `002` |
| `daynight` | Source-granule day/night metadata |
| `source_granule` | Original NASA NetCDF filename |

Granules span approximately six minutes. Dates and times refer to the granule
start and are not exact per-pixel acquisition times. Read `acq_time` and
`version` as strings to preserve leading zeros.

These CSVs were extracted from VNP14IMG NetCDF arrays, rather than downloaded
from the FIRMS service. The filename prefix supports the project's existing
`fetch_firms_viirs()` loader. A later county join is required to isolate
California detections and build county-month exposures.

## Reproduce

Using Python 3.11 or newer, run from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-viirs.txt
python scripts/download_viirs_snpp.py
```

The downloader requests an interactive Earthdata login with `persist=False`.
It downloads in batches with four parallel transfers and request timeouts,
reuses valid local files on reruns, and saves original science files under
`data/raw/viirs_snpp_375m_202507_202510/`. Monthly CSVs are written to
`data/raw/firms_viirs_ca_YYYYMM.csv`. On macOS, the optional
`scripts/download_viirs_snpp.command` launcher runs the same Python script.

Source attribution: NASA VIIRS/NPP Active Fires 6-Min L2 Swath 375 m V002,
DOI [10.5067/VIIRS/VNP14IMG.002](https://doi.org/10.5067/VIIRS/VNP14IMG.002).
