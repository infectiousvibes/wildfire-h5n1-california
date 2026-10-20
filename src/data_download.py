# Documented fetch/aggregation code for the REAL datasets (see data/README.md).
# Requires network access and the optional packages in requirements.txt.
# Functions are intentionally explicit so each step can be audited/re-run.
import pandas as pd


def fetch_aphis_wildbird(raw_dir):
    # USDA APHIS: HPAI detections in wild birds (CSV).
    # Download current CSV from:
    #   https://www.aphis.usda.gov/livestock-poultry-disease/avian/avian-influenza/hpai-detections/wild-birds
    # Then standardize to: date, county, state, species, virus.
    df = pd.read_csv(raw_dir / "aphis_wildbird_detections.csv")
    df["date"] = pd.to_datetime(df["Date Confirmed"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    out = (df[(df["State"] == "California") & df["Virus"].str.contains("H5N1", na=False)]
           .groupby(["County", "month"]).size().rename("n_detections").reset_index())
    return out  # one row per detected county-month; merge onto full panel and fill 0


def fetch_firms_viirs(raw_dir):
    # NASA FIRMS VIIRS 375 m active fire (free MAP_KEY required):
    #   https://firms.modaps.eosdis.nasa.gov/api/area/csv/YOUR_MAP_KEY/VIIRS_SNPP_NRT/CA,1
    # Use the archived science-quality series for complete 2022-2025 coverage.
    import glob
    frames = [pd.read_csv(f) for f in sorted(glob.glob(str(raw_dir / "firms_viirs_ca_*.csv")))]
    df = pd.concat(frames, ignore_index=True)
    df["acq_date"] = pd.to_datetime(df["acq_date"])
    df["month"] = df["acq_date"].dt.to_period("M").astype(str)
    return df[["latitude", "longitude", "frp", "month"]]


def firms_to_county_month(firms, counties_gdf):
    # Spatial join fire points to counties, then aggregate to county-month.
    import geopandas as gpd
    pts = gpd.GeoDataFrame(firms, geometry=gpd.points_from_xy(firms.longitude, firms.latitude), crs="EPSG:4326")
    pts = gpd.sjoin(pts, counties_gdf[["NAME", "geometry"]], predicate="within")
    out = (pts.groupby(["NAME", "month"])
              .agg(fire_count=("frp", "size"), frp=("frp", "sum"))
              .reset_index().rename(columns={"NAME": "county"}))
    return out


def fetch_modis_via_earthaccess(short_name, version="061"):
    # NASA Earthdata login required (free). Example for MOD13A2 NDVI / MOD11A2 LST:
    #   import earthaccess
    #   earthaccess.login()
    #   results = earthaccess.search_data(short_name=short_name, version=version,
    #                                     bounding_box=(-124.5, 32.5, -114.0, 42.1),
    #                                     temporal=("2022-01-01", "2025-12-31"))
    #   files = earthaccess.download(results, local_dir="data/raw/modis")
    # Then mask quality flags, compute county-month means (rasterstats zonal stats),
    # and convert to anomalies vs. county calendar-month climatology.
    raise NotImplementedError("Run interactively with your Earthdata credentials; see docstring.")


def fetch_prism_monthly(raw_dir):
    # PRISM monthly precip/Tmean, 800 m: https://prism.oregonstate.edu
    # Direct monthly archives; compute county-month means via zonal stats, same as MODIS.
    raise NotImplementedError("Download monthly PRISM grids, then zonal-mean to counties (rasterstats).")


def fetch_cdl_county_shares(raw_dir, counties_gdf, years=(2022, 2023, 2024)):
    # USDA NASS Cropland Data Layer via CropScape (https://nassgeodata.gmu.edu/CropScape/).
    # For each year: download CA raster, reclassify ag classes, zonal mean to counties,
    # then average county shares across years for a static landscape covariate.
    raise NotImplementedError("Download CDL rasters and compute county zonal means (rasterstats).")
