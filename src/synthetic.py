# Offline synthetic county-month panel with a planted disturbance -> detection signal.
# Lets the entire pipeline and every figure run with zero downloads.
# All synthetic outputs are labeled as such in the figures.
import numpy as np
import pandas as pd

CA_COUNTIES = [
    "Alameda", "Alpine", "Amador", "Butte", "Calaveras", "Colusa",
    "Contra Costa", "Del Norte", "El Dorado", "Fresno", "Glenn", "Humboldt",
    "Imperial", "Inyo", "Kern", "Kings", "Lake", "Lassen", "Los Angeles",
    "Madera", "Marin", "Mariposa", "Mendocino", "Merced", "Modoc", "Mono",
    "Monterey", "Napa", "Nevada", "Orange", "Placer", "Plumas", "Riverside",
    "Sacramento", "San Benito", "San Bernardino", "San Diego", "San Francisco",
    "San Joaquin", "San Luis Obispo", "San Mateo", "Santa Barbara",
    "Santa Clara", "Santa Cruz", "Shasta", "Sierra", "Siskiyou", "Solano",
    "Sonoma", "Stanislaus", "Sutter", "Tehama", "Trinity", "Tulare",
    "Tuolumne", "Ventura", "Yolo", "Yuba",
]


def _county_positions(n, rng):
    # Place counties on a coarse grid shaped roughly like CA so demo maps read naturally.
    rows, cols = 9, 9
    cells = [(r, c) for r in range(rows) for c in range(cols)]
    # drop NW ocean corner and far SE corner cells to mimic the CA outline
    cells = [rc for rc in cells if not (rc[0] < 2 and rc[1] < 2) and not (rc[0] > 6 and rc[1] > 6)]
    idx = np.sort(rng.choice(len(cells), size=n, replace=False))
    out = []
    for k in idx:
        r, c = cells[k]
        lat = 42.0 - r * 1.1 + rng.normal(0, 0.15)
        lon = -124.5 + c * 1.25 + rng.normal(0, 0.15)
        out.append((lat, lon))
    return out


def make_panel(seed=42, n_months=48, start="2022-01"):
    from .config import N_COUNTIES
    rng = np.random.default_rng(seed)
    counties = CA_COUNTIES[:N_COUNTIES]
    pos = _county_positions(len(counties), rng)
    months = pd.period_range(start=start, periods=n_months, freq="M")

    rows = []
    for i, c in enumerate(counties):
        ce = rng.normal(0, 0.6)                    # persistent county effect (heterogeneity)
        ag = float(np.clip(rng.beta(2.2, 3.0), 0.05, 0.95))  # agricultural land share
        lat, lon = pos[i]
        for t, m in enumerate(months):
            mo = m.month
            fire = rng.poisson(np.exp(-1.3 + 1.1 * np.sin(2 * np.pi * (mo - 7) / 12) + 0.45 * ce))
            frp = fire * rng.lognormal(1.1, 0.4) if fire > 0 else 0.0
            ndvi = 0.9 * np.sin(2 * np.pi * (mo - 4) / 12) + rng.normal(0, 0.15)
            ndvi -= 0.25 * min(fire, 5) / 5.0      # fire suppresses vegetation
            lst = 8 * np.sin(2 * np.pi * (mo - 7) / 12) + rng.normal(0, 1.0) + 0.30 * min(fire, 5)
            precip = max(0.0, rng.normal(55 + 45 * np.sin(2 * np.pi * (mo - 1) / 12), 28))
            tmean = 15 + 8 * np.sin(2 * np.pi * (mo - 7) / 12) + rng.normal(0, 1.5) - 0.6 * (lat - 37)
            rows.append(dict(
                county=c, fips=str(6000 + i + 1).zfill(5), lat=lat, lon=lon,
                month=str(m), month_idx=t, month_num=mo,
                ag_prop=ag, county_effect=ce,
                fire_count=fire, frp=frp,
                ndvi_anom=ndvi, lst_anom=lst,
                precip=precip, tmean=tmean,
            ))
    df = pd.DataFrame(rows).sort_values(["county", "month_idx"]).reset_index(drop=True)

    # 1-month lags: disturbance precedes detection (conceptual model)
    for col in ["fire_count", "frp", "ndvi_anom", "lst_anom"]:
        df[col + "_lag1"] = df.groupby("county")[col].shift(1)

    # Planted signal: disturbance + greener/wetter winters + agriculture raise risk
    z = lambda s: (s - s.mean()) / s.std()
    eta = (
        -2.3
        + 0.2 * z(df["fire_count_lag1"].fillna(0))
        + 1.4 * z(df["fire_count_lag1"].fillna(0)) * df["month_num"].isin([11, 12, 1, 2]).astype(float)
        + 0.5 * z(df["ndvi_anom_lag1"].fillna(0))
        + 0.3 * z(df["lst_anom_lag1"].fillna(0))
        + 0.4 * z(df["precip"])
        + 0.5 * z(df["ag_prop"])
        + 0.6 * df["month_num"].isin([11, 12, 1, 2]).astype(float)
        + 0.5 * df["county_effect"]
    )
    p = 1.0 / (1.0 + np.exp(-eta))
    df["y"] = rng.binomial(1, p)
    return df
