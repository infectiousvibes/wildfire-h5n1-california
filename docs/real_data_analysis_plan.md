# Real-data analysis plan

Recorded before fitting the real-data models. Study: 58 California counties,
January 2022–July 2025. December 2021 environmental data supply the first lag.
The endpoint was fixed before fitting because the public MODIS COG mirror has
contiguous multi-product gaps after the lag needed for July 2025. Source years
and missingness are audited before fitting.

Primary outcome: at least one reported APHIS wild-bird record explicitly typed
H5N1, by detection month; captive wild birds excluded. H5 records without N1
subtyping are not automatically called H5N1. An inclusive HPAI H5 sensitivity
outcome will assess this ascertainment choice. Zero means no reported record,
not a tested-negative county. Source records may not distinguish unique birds.

Environmental sources: PRISM monthly temperature/precipitation at 4km, Terra
MODIS 6.1 daily fire (MOD14A1; nominal/high confidence), 500m vegetation
(MOD13A1; good-quality NDVI), and 1km daytime temperature (MOD11A2; good QA).
Use one Terra sensor consistently. Public Planetary Computer cloud-optimized
copies avoid NASA credentials. This replaces the prototype's proposed VIIRS
sensor; fire pixels represent thermal activity, including potential prescribed
or agricultural burning, not enumerated wildfire incidents. A 2021 USDA CDL
landscape reference precedes all model outcome months.

MODIS multi-day composites are assigned to the month in which they END, so
no composite used for a lagged predictor extends into the outcome month.
No future-referenced anomaly climatology is computed. Raw NDVI and daytime
LST are used with seasonality instead. Missing QA-filtered values and isolated
unavailable composites remain missing and are imputed using training folds
only, with missing indicators.
Climate and all disturbance variables are lagged one month. This is a
retrospective hindcast using final products, not an operational as-of forecast.

Evaluation: matched climate/landscape/seasonality versus full-environment
predictors for both logistic regression and random forest, with identical
county GroupKFold splits. Secondary temporal holdout: train 2022–2024 and
evaluate January–July 2025. Models and thresholds are fixed before outcome inspection;
no tuning on held-out outcomes. Report ROC-AUC, average precision, Brier
score, precision/recall at 0.5, and no-skill prevalence. Quantify metric and
paired-difference uncertainty by resampling whole counties, keeping their
months together. Compute permutation importance on held-out folds. These
analyses assess predictive associations and do not establish causation.

Commit shareable county summaries, data dictionary, input checksums and source
URLs, quality audit, out-of-fold predictions, model results, and figures.
Keep raw rasters, tokens, and large downloads out of Git. Synthetic results
remain explicitly separate. Any source or design changes discovered during
acquisition will be documented before fitting.
