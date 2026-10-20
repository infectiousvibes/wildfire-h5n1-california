# Feature engineering: seasonality, transforms, lags, design matrices.
import numpy as np
import pandas as pd


def add_seasonality(df):
    df = df.copy()
    df["sin_month"] = np.sin(2 * np.pi * df["month_num"] / 12)
    df["cos_month"] = np.cos(2 * np.pi * df["month_num"] / 12)
    df["is_winter"] = df["month_num"].isin([11, 12, 1, 2]).astype(int)
    return df


def add_transforms(df):
    df = df.copy()
    df["fire_lag1_log"] = np.log1p(df["fire_count_lag1"].fillna(0))
    df["frp_lag1_log"] = np.log1p(df["frp_lag1"].fillna(0))
    # NDVI/LST anomalies enter at lag 1 as-is; missing first-month lags -> 0 (no prior exposure window)
    df["ndvi_anom_lag1"] = df["ndvi_anom_lag1"].fillna(0.0)
    df["lst_anom_lag1"] = df["lst_anom_lag1"].fillna(0.0)
    return df


def build_xy(df, features, target="y", group="county"):
    d = df.dropna(subset=features + [target]).reset_index(drop=True)
    X = d[features]
    y = d[target].astype(int)
    groups = d[group]
    return X, y, groups, d


# Robust panel IO: parquet when pyarrow is available, pickle fallback otherwise.
def save_panel(df, path=None):
    from . import config
    path = path or config.PANEL_FILE
    try:
        df.to_parquet(path)
    except ImportError:
        df.to_pickle(path.with_suffix(".pkl"))


def load_panel(path=None):
    from . import config
    path = path or config.PANEL_FILE
    if path.exists():
        return pd.read_parquet(path)
    return pd.read_pickle(path.with_suffix(".pkl"))
