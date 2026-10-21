# Observational county summaries

These are derived, shareable county-level summaries used by the real-data
benchmark. Raw rasters and the source APHIS export stay in Git-ignored
`data/raw/real/`.

## Sources and fields

- `prism_county_month.csv`: PRISM 4 km monthly mean temperature (`tmean`, °C)
  and precipitation (`ppt`, mm), area-weighted to 2024 Census county polygons.
- `fire_county_month.csv`: Terra MOD14A1.061 daily fire masks and maximum fire
  radiative power, summarized by month. Counts include nominal- and
  high-confidence pixels. Coverage fractions distinguish missing observations
  from observed zero fire.
- `ndvi_county_month.csv`: Terra MOD13A1.061 500 m NDVI. Only pixels with the
  good-quality reliability flag are included; values use the 0.0001 scale.
- `lst_county_month.csv`: Terra MOD11A2.061 1 km daytime land-surface
  temperature. Only mandatory-QA good pixels with LST error at most 1 K are
  included; values use the 0.02 K scale and are converted to °C.
- `landcover_2021.csv`: USDA Cropland Data Layer cultivated/non-cultivated
  layer, expressed as each county's cultivated fraction.
- `aphis_county_month.csv`: reported California wild-bird detections from the
  APHIS surveillance export. `h5n1` requires explicit H5N1 text; `h5_any` is the
  broader sensitivity definition. Missing reports are not proof of negative
  testing.
- `panel.csv` and `panel.parquet`: merged 58-county panel from 2022-01 through
  2025-07, with one-month lags and observational outcome labels.

`download_manifest.json` records public source URLs, access timestamps, sizes,
and SHA-256 checksums. `data_readiness.json`, `monthly_input_coverage.csv`,
`panel_missingness.csv`, and `monthly_quality_audit.csv` document completeness
and QA retention.

MODIS composites are assigned to the month in which they end. Environmental
predictors are lagged one month, so no composite extending into an outcome
month is used for that outcome. The isolated missing October 2022 NDVI month
remains missing and is imputed using training-fold medians with an explicit
missingness indicator.
