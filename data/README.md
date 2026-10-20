# Data sources and access

The analysis panel is built at the **county-month** level (58 CA counties × 48 months, Jan 2022 – Dec 2025).
The pipeline runs end-to-end on **synthetic data** (`src/synthetic.py`) out of the box. To use real data,
download the files below into `data/raw/` with the exact filenames shown, then set `USE_SYNTHETIC = False`
in `src/config.py`.

| Layer | Filename in `data/raw/` | Source & access |
|---|---|---|
| H5N1 wild-bird detections | `aphis_wildbird_detections.csv` | USDA APHIS, "HPAI Detections in Wild Birds" — downloadable CSV from https://www.aphis.usda.gov/livestock-poultry-disease/avian/avian-influenza/hpai-detections/wild-birds . Keep columns: detection date, county, state, species, virus/strain. |
| Active fire | `firms_viirs_ca_2022_2025.csv` | NASA FIRMS API, VIIRS 375 m: https://firms.modaps.eosdis.nasa.gov/api/area/csv/YOUR_MAP_KEY/VIIRS_SNPP_NRT/CA,1 (free MAP_KEY after signup; use the archived science-quality product for complete 2022–2025 coverage). Keep: `acq_date`, `latitude`, `longitude`, `frp`. |
| NDVI | `modis_mod13a2_ca.nc` (or per-year GeoTIFFs) | NASA Earthdata, MOD13A2 v061 (16-day, 1 km). Python access via `earthaccess` (see `src/data_download.py`). |
| Land-surface temperature | `modis_mod11a2_ca.nc` | NASA Earthdata, MOD11A2 v061 (8-day, 1 km daytime LST). Same access pattern as NDVI. |
| PRISM climate | `prism_monthly_ca/` | PRISM Climate Group, monthly precipitation / Tmean, 800 m: https://prism.oregonstate.edu (direct download; monthly 2022–2025). |
| Cropland Data Layer | `cdl_ca_2022_2024/` | USDA NASS CropScape: https://nassgeodata.gmu.edu/CropScape/ — CA rasters for 2022–2024; aggregate to county shares (e.g., `rasterstats` zonal means). |
| County boundaries | `tl_2024_us_county.shp` (+ sidecars) | US Census TIGER/Line: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html — filter `STATEFP == '06'`. |

## Processing steps (implemented in `src/data_download.py` and `notebooks/01`)

1. **Outcome:** county-month indicator = 1 if ≥1 confirmed H5N1 detection (wild birds) that county-month (APHIS).
2. **Fire:** aggregate FIRMS points to county-month (count of detections, mean/sum FRP).
3. **NDVI / LST:** aggregate rasters to county-month means; then compute anomalies (value − county calendar-month climatology).
4. **Climate:** county-month mean precipitation and temperature from PRISM grids.
5. **Landscape:** static county shares of agricultural land (CDL), pooled 2022–2024.
6. **Panel assembly:** one row per county-month; all disturbance predictors lagged by 1 month before modeling.

## Notes

- `data/raw/` is git-ignored; only `data/processed/` (small parquet) may be committed, and even that only if sharing
  processed data is appropriate. Check data-use terms before committing anything derived from restricted sources.
- Filenames above match the loader expectations in `src/data_download.py`; rename your downloads accordingly.
