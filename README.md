# Wildfire-Associated Environmental Disturbance and H5N1 Detection Risk in California
### A remote sensing and machine learning analysis at the county-month scale (2022–2025)

**Author:** Mariati Messinger, PhD, MPH — infectious disease epidemiologist (One Health, spatial epidemiology)
**Purpose:** Independent portfolio project demonstrating the full workflow the UC Davis EpiPandit Lab postdoc calls for: climate/environmental data integration, remote sensing, spatiotemporal ML, spatially explicit validation, uncertainty communication, and translation into decision-relevant outputs.

---

## Background and rationale

Highly pathogenic avian influenza (HPAI) H5N1 clade 2.3.4.4b has circulated continuously in North American wild birds since 2021, with California a recurring epicenter spanning wild birds, poultry, dairy cattle, and human spillover events [1,2]. Genomic evidence shows migratory waterfowl — especially Anseriformes — drive continental dissemination and repeatedly seed Pacific Flyway introductions [2].

Wildfire is a plausible but under-tested modifier of this system. California telemetry work showed that when wild waterfowl encounter dense wildfire smoke during migration, they stop, alter direction and altitude, use non-traditional stopovers, and take substantially longer to migrate [3]. Other California studies show smoke exposure affects bird body condition and capture rates [4] and that burn severity reshapes bird occupancy and community composition [5]. Separately, Central Valley studies show wild waterfowl directly use poultry farm landscapes, creating a wild–domestic interface whose intensity varies by species, space, and time of day [1], and that empirical bird-movement models can sharpen H5N1 spread predictions [6].

**The gap:** to my knowledge there is no peer-reviewed California study testing whether wildfire-associated disturbance — measured with satellite remote sensing — improves prediction of where H5N1 is subsequently detected in wild birds. A 2026 US-wide preprint found county-level *acres burned* added little to an H5N1 outbreak model [7]; but acres burned is a coarse proxy that ignores smoke plumes (which displaced birds far outside burn perimeters [3]), vegetation condition, and land-surface temperature. This project tests the more biologically informative version of the question.

### Conceptual model

```
Wildfire / smoke disturbance (FIRMS, VIIRS)
        |
        v
Habitat & environmental change (NDVI anomaly, LST anomaly)
        |
        v
Redistribution of migratory waterfowl (stopovers, concentration)
        |
        v
Shifted wild-bird / wild-bird and wild-bird / agriculture interfaces
        |
        v
Subsequent H5N1 detection risk (USDA APHIS wild-bird surveillance)
```

We explicitly do **not** claim wildfire *causes* H5N1. We test whether disturbance information improves *prediction* of detections one month later.

## Research questions and hypothesis

- **RQ1 (primary):** Does incorporating satellite-derived wildfire and environmental disturbance indicators (1-month lagged) improve prediction of reported H5N1 detection in California wild birds beyond conventional climate and seasonal predictors?
- **RQ2 (secondary):** Which environmental features contribute most strongly to predicted H5N1 detection risk?

**H1:** Models including wildfire activity and remotely sensed vegetation/land-surface conditions will show better discrimination (ROC-AUC / PR-AUC) than models using climate and seasonality alone.

**H0:** Adding remote-sensing disturbance variables does not improve predictive discrimination.

A null result is scientifically informative and will be reported as such.

## Study design

- **Design:** retrospective ecological study; county-month panel, 58 California counties × 48 months (Jan 2022 – Dec 2025).
- **Outcome:** binary — ≥1 confirmed HPAI H5N1 detection in wild birds in county *c*, month *t* (USDA APHIS wild-bird surveillance).
- **Exposure window:** all disturbance variables enter at **lag 1 month**, matching the hypothesized sequence disturbance → habitat change → bird redistribution → detection.
- **Validation:** GroupKFold by county (spatial holdout — a model must generalize to *unseen counties*, not just unseen months), with pooled ROC/PR curves from out-of-fold predictions, and bootstrap CIs on AUC.
- **Models:** (1) logistic regression baseline (epidemiologic interpretability); (2) Random Forest (non-linear interactions, benchmarked against baseline).

## Data

| Variable | Source | Product / access |
|---|---|---|
| H5N1 wild-bird detections | USDA APHIS | Confirmed detection database (CSV), aphis.usda.gov |
| Active fire (count, FRP) | NASA FIRMS | VIIRS 375 m, firms.modaps.eosdis.nasa.gov (free API key; archive available for full study window) |
| NDVI (16-day, 1 km) | NASA MODIS | MOD13A2 via NASA Earthdata (`earthaccess`) |
| Land-surface temperature | NASA MODIS | MOD11A2/MYD11A2 via Earthdata |
| Precipitation, temperature | PRISM Climate Group | Monthly 800 m grids, prism.oregonstate.edu |
| Agricultural land cover | USDA NASS | Cropland Data Layer via CropScape (county zonal statistics) |
| County boundaries | US Census | TIGER/Line counties (for choropleth maps) |

Full access instructions and expected file layout: [`data/README.md`](data/README.md).

**Runnable today:** the repository ships with a built-in *synthetic-data fallback* that reproduces the full pipeline and every figure offline (`src/synthetic.py`). Every notebook runs end-to-end with zero downloads, and the same code paths accept the real datasets once they are dropped into `data/raw/`. All synthetic outputs are clearly labeled.

## Repository structure

```
wildfire-h5n1-california/
├── README.md                  ← you are here
├── LICENSE                    ← MIT
├── requirements.txt
├── data/
│   ├── README.md              ← data sources, access, file layout
│   └── processed/             ← analysis panel (parquet)
├── src/
│   ├── config.py              ← paths, study window, feature lists
│   ├── synthetic.py           ← offline synthetic panel generator
│   ├── data_download.py       ← documented fetch code for APHIS/FIRMS/MODIS/PRISM/CDL
│   ├── features.py            ← lags, seasonality, transforms, design matrices
│   ├── models.py              ← baseline + RF, spatial GroupKFold CV
│   ├── evaluate.py            ← metrics, bootstrap CIs, curves
│   └── viz.py                 ← maps, temporal, ROC/PR, importance, risk maps
├── notebooks/
│   ├── 01_build_dataset.ipynb
│   ├── 02_exploratory_spatial_analysis.ipynb
│   ├── 03_machine_learning.ipynb
│   └── 04_model_interpretation.ipynb
├── figures/                   ← example outputs (synthetic run shown)
└── results/
    └── cv_metrics.csv
```

## Quickstart

```bash
git clone <your-fork-url>
cd wildfire-h5n1-california
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook notebooks/01_build_dataset.ipynb   # runs on synthetic data out of the box
```

To use real data: download per `data/README.md`, place files in `data/raw/`, then in `src/config.py` set `USE_SYNTHETIC = False` and rerun the notebooks in order.

## Key results (synthetic demonstration run)

Spatially explicit cross-validation comparing the climate/seasonality baseline against the model adding 1-month-lagged wildfire and remote-sensing disturbance variables. See `figures/` for the example outputs and `results/cv_metrics.csv` for the full table. Interpretation template for the real-data run:

- If remote-sensing features improve out-of-fold ROC-AUC/PR-AUC → disturbance carries signal usable for early-warning targeting.
- If they do not → consistent with [7] at coarse scales; fine-scale mechanisms (smoke plumes, telemetry-tracked displacement [3]) would then be the priority for future work.

## Limitations

1. **Ecological design:** county-month aggregation cannot establish individual-level causation; results are associative.
2. **Surveillance bias:** APHIS wild-bird detections reflect where and how intensively sampling occurs; detection probability varies by county and season and is only partially captured by effort covariates.
3. **Proxy measurement:** FIRMS detects active fire, not smoke plume exposure or burn severity; NDVI/LST are coarse habitat proxies for waterfowl distribution.
4. **Residual spatial dependence:** county-grouped CV mitigates leakage but does not remove unmeasured spatial confounding.
5. **Temporal alignment:** a 1-month lag is a pragmatic compromise; mechanistic alignment (bird movement timescales) needs telemetry data.

## Alignment with the EpiPandit Lab

- **WildAlert** — the lab's AI-driven, event-based wildlife-health early-warning platform [8]: this project is the same philosophy (integrating heterogeneous streams to anticipate wildlife disease signals) applied to climate-driven disturbance, and the resulting county-month risk surface is a candidate input layer for such a system.
- **AtlasArena** — the lab's climate-driven spatio-temporal disease-ecology platform using species distribution models over bioclimatic, vegetation, and land-use data: this project mirrors that architecture (occurrence/surveillance outcome + gridded environmental predictors + ML), transplanted to an avian system.
- The posting's named skills are all exercised here: gridded climate data (PRISM), remote sensing (FIRMS, MODIS NDVI/LST), land cover (CDL), ML with benchmarking against a baseline, grouped/spatial validation, uncertainty (bootstrap CIs), and translation into maps for non-specialist audiences.

## Future directions

1. Replace county centroids with **fine-scale grid cells** (1–4 km) and add surface-water extent (e.g., JRC Global Surface Water) — direct rice-field/wetland flooding signal, addressing the measurement limitation flagged in my dissertation.
2. Integrate **eBird or GPS-telemetry waterfowl occurrence** (e.g., McDuie et al. [6]) as the intermediate mechanistic layer: disturbance → redistribution → detection.
3. Extend to **H5Nx in dairy cattle** and a **One Health convergence index** (wild-bird detections × cattle density × poultry density), following my doctoral work.
4. Recalibrate as a **decision-support layer** (Streamlit dashboard) for vector/wildlife districts — I currently serve as an appointed Trustee on the Contra Costa Mosquito & Vector Control District Board, so end-user translation is a live interest.

## References

1. Teitelbaum CS, et al. (2024). Potential use of poultry farms by wild waterfowl in California's Central Valley varies across space, times of day, and species: Implications for influenza transmission risk. *Ecography* 2024(10).
2. Damodaran L, Jaeger A, Moncla LH, et al. (2025). Ecology and spread of the North American H5N1 epizootic. *Nature*.
3. Overton CT, et al. (2022). Megafires and thick smoke portend big problems for migratory birds. *Ecology* 103(1).
4. Nihei N, et al. (2024). Wildfire smoke impacts the body condition and capture rates of birds in California. *Ornithology*.
5. Ray, et al. (2025). Sierra Nevada bird responses to wildfire burn severity (hierarchical Bayesian models, 42 species). *Fire Ecology*.
6. McDuie F, et al. (2024). Mitigating risk: Predicting H5N1 avian influenza spread with an empirical model of bird movement. *Transboundary and Emerging Diseases* 2024.
7. Zou Z, Carlton E, Grover J. (2026). County-month machine learning of H5N1 outbreaks across the contiguous US (gradient boosting; wildfire acres burned contributed little). *medRxiv* preprint — not peer-reviewed; motivates our finer-grained disturbance metrics.
8. Kelly TR, Pandit PS, Carion N, et al. (2021). Early detection of wildlife morbidity and mortality through an event-based surveillance system. *Proceedings of the Royal Society B* 288(1954):20210974. (WildAlert v1.0)
9. Sullivan JD, et al. (2025). Potential impacts of 2.3.4.4b highly pathogenic H5N1 avian influenza virus infection on Snow Goose (*Anser caerulescens*) movement ecology. *PLOS ONE* 20(7).
10. Acosta S, et al. (2021). Use of satellite remote sensing, climate data, and boosted regression trees to predict waterfowl distributions around commercial poultry farms in California's Central Valley. *Avian Diseases*.

## License

MIT — see [LICENSE](LICENSE).
