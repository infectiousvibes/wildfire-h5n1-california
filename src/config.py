# Central configuration: paths, study window, feature definitions.
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROC = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
RESULTS = ROOT / "results"
for _p in (DATA_RAW, DATA_PROC, FIGURES, RESULTS):
    _p.mkdir(parents=True, exist_ok=True)

# Study window: 48 complete months, Jan 2022 - Dec 2025
START = "2022-01"
N_MONTHS = 48
N_COUNTIES = 58

# Set False once real data are dropped into data/raw/ per data/README.md
USE_SYNTHETIC = True

RANDOM_STATE = 42
TARGET = "y"  # 1 = >=1 confirmed H5N1 wild-bird detection in county-month

# Observational analysis window. The public MODIS COG archive used by the
# reproducible workflow has multi-month gaps after July 2025. The real-data
# benchmark therefore ends at the latest outcome month whose lagged inputs are
# available, rather than treating absent satellite observations as zeros.
OBS_START = "2022-01"
OBS_END = "2025-07"
OBS_ENV_START = "2021-12"

PANEL_FILE = DATA_PROC / "panel.parquet"

# Model feature sets -------------------------------------------------------
# Baseline: conventional climate + seasonality + landscape (no remote sensing)
BASELINE_FEATURES = ["tmean", "precip", "ag_prop", "sin_month", "cos_month"]

# Full model adds 1-month-lagged wildfire + remote-sensing disturbance terms
REMOTE_FEATURES = ["fire_lag1_log", "frp_lag1_log", "ndvi_anom_lag1", "lst_anom_lag1"]
FULL_FEATURES = BASELINE_FEATURES + REMOTE_FEATURES
