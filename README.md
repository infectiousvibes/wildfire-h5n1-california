# Wildfire, Environmental Disturbance, and H5N1 Surveillance

**Independent ML prototype | Python · scikit-learn · lagged environmental features · county-grouped validation**

A reproducible modeling prototype exploring how environmental disturbance
variables could be evaluated alongside climate and landscape predictors of
wild-bird disease detections. It complements my
[doctoral disease-ecology analysis](https://github.com/infectiousvibes/california-hpai-dissertation-code)
by developing a prediction-focused workflow with nonlinear models and
geographically grouped evaluation.

**Current status: the repository now contains separate synthetic and
observational workflows.** The observational benchmark uses public APHIS,
PRISM, Terra MODIS, USDA CDL, and Census data for 58 California counties from
January 2022 through July 2025. It is an exploratory retrospective analysis,
not evidence of a causal wildfire effect or a validated operational risk model.

## Research motivation

Land-use conditions, seasonal climate, and environmental disturbances may
influence the wildlife–agriculture interface. This prototype turns that
research question into an explicit county-month modeling design: do lagged
fire activity, vegetation condition (NDVI), and land-surface temperature provide
useful predictive information for a surveillance outcome?

The intended observational outcome is at least one reported H5N1 wild-bird
detection in a county-month. Reported detections depend on surveillance and
sampling, so they do not directly measure infection prevalence. The synthetic
dataset remains available so the teaching workflow can run without source-data
credentials or downloads.

## Observed fire detections available

[SNPP VIIRS 375 m fire detections for July–October 2025](data/processed/viirs_snpp_375m_202507_202510/README.md)
are available as four monthly CSVs: **28,824 detections** extracted from 707
NASA VNP14IMG Collection 002 granules. The data include coordinates, fire
radiative power, detection confidence, and source-granule identifiers.
The California bounding box includes areas outside the state. July 5–7 has
no matching source swaths and is documented as missing observation coverage.

The [interactive Earthdata downloader](scripts/download_viirs_snpp.py) preserves
the original NetCDF files in the Git-ignored `data/raw/` directory. Source
URLs, checksums, daily catalog coverage, and validation results accompany the
committed CSVs. These SNPP observations remain a separate dataset; the
observational benchmark uses consistent Terra MODIS fire measurements across
the full analysis window.

## Skills demonstrated in the working code

| Capability | Implementation |
| --- | --- |
| Reproducible panel construction | [Seeded synthetic generator](src/synthetic.py): 58 named counties × 48 months (2022–2025), with explicit county heterogeneity and a planted disturbance signal |
| Temporal feature engineering | One-month within-county disturbance lags, log transforms, cyclic seasonality, and reusable [design-matrix helpers](src/features.py) |
| ML benchmarking | [Scaled logistic regression and class-balanced random forest](src/models.py) with fixed seeds and reusable model functions |
| Geographic generalization assessment | Five-fold `GroupKFold` by county; each test fold contains counties excluded from its training fold |
| Evaluation and uncertainty | Pooled out-of-fold ROC-AUC, average precision, precision/recall/F1, and [bootstrap interval helpers](src/evaluate.py) |
| Model interpretation and communication | [Permutation importance, ROC/precision–recall curves, temporal plots, and illustrative probability maps](src/viz.py) |

This is a tabular ML workflow with spatial grouping. Grouping by county tests
transfer to held-out counties; it does not provide a forward-in-time forecasting
test or separate neighboring counties with a spatial buffer.

## What is implemented

| Component | Status |
| --- | --- |
| Synthetic panel, feature engineering, model fitting, and figure generation | Implemented and demonstrated in four executed notebooks |
| APHIS surveillance aggregation | Implemented with schema, subtype, county, date, and duplicate audits |
| Terra MODIS fire, NDVI, and land-surface temperature | Implemented with product QA masks, county aggregation, archive coverage, and one-month lags |
| PRISM temperature and precipitation | Implemented as county-weighted monthly summaries |
| USDA CDL cultivated-land share and Census county boundaries | Implemented for all 58 counties |
| Integrated observational panel and validation | Implemented with county-held-out and 2025 temporal evaluation |

See the [data notes](data/README.md), [observational data dictionary](data/processed/real/README.md),
and [analysis plan](docs/real_data_analysis_plan.md) for sources, processing,
coverage decisions, and interpretation limits.

## Observational benchmark results

The real panel contains **2,494 county-months**, including 280 months with at
least one explicit H5N1 wild-bird report. In county-held-out evaluation, the
random-forest climate/seasonality/land-cover baseline reached ROC-AUC 0.743 and
average precision 0.283. Adding lagged fire, NDVI, and land-surface temperature
did not improve held-out performance: ROC-AUC was 0.725 and average precision
was 0.264. The paired average-precision difference was -0.019 (95% county
bootstrap interval -0.053 to +0.015).

The January–July 2025 temporal holdout was much weaker. The baseline forest was
near chance (ROC-AUC 0.506; average precision 0.110), and the full forest was
below chance (ROC-AUC 0.462; average precision 0.099). These results do not
support forecasting use or a claim that the added environmental variables
improve prediction. Full metrics, intervals, predictions, and split audits are
in [`results/real/`](results/real/analysis_summary.md).

Run the observational workflow from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-real.txt
python -m src.real_data audit
python -m src.real_data panel
python -m unittest discover -s tests -v
python -m src.real_models --bootstrap 1000
```

## Synthetic benchmark results

The committed [`results/cv_metrics.csv`](results/cv_metrics.csv) contains these
pooled county-held-out results for **2,784 simulated county-months**, including
436 simulated positive outcomes:

| Model | ROC-AUC | Average precision | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- |
| Logistic regression | 0.740 | 0.406 | 0.636 | 0.156 | 0.250 |
| Random forest | 0.752 | 0.473 | 0.502 | 0.360 | 0.419 |

**Both models currently receive the same full nine-feature set.** The existing
comparison evaluates model classes. It does not isolate the added value of
disturbance variables over a climate-only baseline; that requires a matched
feature-set ablation using the same evaluation folds.

![Synthetic demonstration of county-held-out model performance](figures/fig4_model_performance.png)

*Illustration from the synthetic run. The synthetic generator deliberately
contains a disturbance signal; these scores cannot establish a biological
relationship in observed surveillance data.*

## Run the notebooks

```sh
git clone https://github.com/infectiousvibes/wildfire-h5n1-california.git
cd wildfire-h5n1-california
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install jupyter
cd notebooks
jupyter notebook
```

Execute in order:

1. [Build the panel](notebooks/01_build_dataset.ipynb).
2. [Explore spatial and temporal patterns](notebooks/02_exploratory_spatial_analysis.ipynb).
3. [Fit and evaluate the models](notebooks/03_machine_learning.ipynb).
4. [Interpret the fitted model](notebooks/04_model_interpretation.ipynb).

These notebooks are the synthetic teaching workflow and assume they are run
from the `notebooks/` directory. Keep `USE_SYNTHETIC = True` when running them.
The observational workflow runs separately from the repository root using the
commands above; changing the notebook flag does not invoke it. Generated
figures and metrics overwrite the corresponding synthetic example files.

## Interpretation and next research steps

- The synthetic notebook bootstrap resamples individual rows; it does not preserve county or temporal dependence and should not be used for observational inference.
- Notebook 04 computes permutation importance on the training data and maps fitted probabilities. These are exploratory interpretation outputs, not held-out importance or independently validated risk maps.
- Synthetic coordinates and identifiers are illustrative and must not be used as actual county geography or official FIPS codes.
- In the synthetic workflow, first-month missing disturbance lags are filled with zero. The observational workflow instead supplies a prior exposure month and imputes remaining missing values within each training fold.
- The observational workflow includes raster processing, surveillance-quality checks, feature-set ablation, temporal evaluation, calibration, and county-bootstrap uncertainty; its weak temporal results do not support decision-support use.

The project demonstrates research design, reproducible Python model engineering,
and geographic evaluation while making the difference between an implemented
prototype and validated surveillance evidence explicit.

## Repository contents and license

`src/` contains reusable Python modules; `notebooks/` records the synthetic
workflow; and the `real` subdirectories under `data/processed/`, `figures/`,
and `results/` contain the observational benchmark. Raw rasters, source records,
and credentials are excluded.

MIT license — see [LICENSE](LICENSE).
