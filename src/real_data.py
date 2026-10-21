"""Auditable public-source extraction for the observational county-month panel.

Raw downloads stay under data/raw/real; only aggregate summaries are shared.
MODIS extraction uses a single platform (Terra), QA masks and actual county
geometry. Pixel-center zonal assignment approximates polygon coverage.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import rasterio
from rasterio.features import rasterize
from rasterio.transform import Affine
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from shapely.geometry import shape

from .config import OBS_END, OBS_ENV_START, OBS_START, ROOT

RAW = ROOT / "data/raw/real"
OUT = ROOT / "data/processed/real"
BOUNDARY = ROOT / "data/reference/ca_counties_2024.gpkg"
# Extract all source months available in the original study request so later
# archive repairs do not require redesigning the acquisition code. Panel and
# readiness checks use the narrower, pre-declared observational window.
MONTHS = pd.period_range(OBS_ENV_START, "2025-12", freq="M").astype(str)
ANALYSIS_MONTHS = pd.period_range(OBS_START, OBS_END, freq="M").astype(str)
REQUIRED_ENV_MONTHS = pd.period_range(
    OBS_ENV_START, str(pd.Period(OBS_END, freq="M") - 1), freq="M"
).astype(str)
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
LOCK = threading.RLock()
MANIFEST: dict[str, dict] = {}
LOCAL = threading.local()


def session():
    if not hasattr(LOCAL, "http"):
        s = requests.Session()
        retry = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.headers["User-Agent"] = "wildfire-h5n1-research/real-data-1.0"
        LOCAL.http = s
    return LOCAL.http


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def record(path, source, **extra):
    row = dict(path=str(Path(path).relative_to(ROOT)), source=source,
               sha256=digest(path), bytes=Path(path).stat().st_size,
               accessed_utc=pd.Timestamp.now(tz="UTC").isoformat(), **extra)
    with LOCK:
        MANIFEST[row["path"]] = row
    return path


def download(url, path, sign=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        actual = planetary_computer.sign(url) if sign else url
        with session().get(actual, timeout=(30, 180), stream=True) as response:
            response.raise_for_status()
            tmp = path.with_suffix(path.suffix + ".part")
            with tmp.open("wb") as f:
                for block in response.iter_content(1024 * 1024):
                    f.write(block)
            tmp.replace(path)
    return record(path, url)


@lru_cache(maxsize=1)
def counties():
    ca = gpd.read_file(BOUNDARY).sort_values("GEOID").reset_index(drop=True)
    assert len(ca) == 58 and ca.GEOID.is_unique and set(ca.STATEFP) == {"06"}
    return ca


@lru_cache(maxsize=12)
def projected(crs):
    return counties().to_crs(crs)


@lru_cache(maxsize=32)
def county_mask(crs, transform, height, width):
    ca = projected(crs)
    mask = rasterize(((g, i + 1) for i, g in enumerate(ca.geometry)),
                     out_shape=(height, width), transform=Affine(*transform),
                     fill=0, dtype="uint8", all_touched=False)
    return mask


def labels_for(src):
    # Lock cache creation to avoid duplicate large rasterizations across threads.
    with LOCK:
        return county_mask(src.crs.to_wkt(), tuple(src.transform)[:6], src.height, src.width)


def sums(labels, values=None, valid=None):
    if valid is None:
        valid = labels > 0
    else:
        valid = valid & (labels > 0)
    return np.bincount(labels[valid].ravel(),
                       weights=values[valid].ravel() if values is not None else None,
                       minlength=59)[1:]


def catalog(collection, assets, start="2021-11-01", end="2025-12-31", extra=None):
    suffix = ("_" + hashlib.md5(json.dumps(extra, sort_keys=True).encode()).hexdigest()[:8]) if extra else ""
    path = RAW / "catalog" / (collection + suffix + ".json")
    if path.exists():
        return json.loads(path.read_text())
    payload = dict(collections=[collection], bbox=[-124.6, 32.4, -113.9, 42.1],
                   datetime=start + "T00:00:00Z/" + end + "T23:59:59Z", limit=1000)
    if extra:
        payload["query"] = extra
    url, method = STAC + "/search", "POST"
    result = []
    area = counties().to_crs(4326).geometry.union_all()
    while url:
        response = session().request(method, url, json=payload if method == "POST" else None, timeout=120)
        response.raise_for_status()
        data = response.json()
        for item in data["features"]:
            if not shape(item["geometry"]).intersects(area):
                continue
            result.append({"id": item["id"], "properties": item["properties"],
                           "assets": {a: item["assets"][a] for a in assets}})
        nxt = next((x for x in data.get("links", []) if x["rel"] == "next"), None)
        if nxt is None:
            break
        url, method = nxt["href"], nxt.get("method", "GET")
        if method == "POST":
            payload = {**payload, **nxt.get("body", {})} if nxt.get("merge") else nxt.get("body", payload)
    # Latest reprocessing only for any duplicate tile/composite date.
    unique = {}
    for item in sorted(result, key=lambda x: x["id"]):
        prop = item["properties"]
        key = (prop.get("modis:horizontal-tile"), prop.get("modis:vertical-tile"),
               prop.get("start_datetime"), item["id"] if collection == "usda-cdl" else "")
        unique[key] = item
    result = list(unique.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result))
    print(collection, "catalog:", len(result), "California-intersecting items", flush=True)
    return result


def asset(item, name):
    url = item["assets"][name]["href"]
    return download(url, RAW / "modis" / Path(url).name, sign=True)


def archive_catalog(collection, assets):
    """Repair incomplete STAC indexing using the same public Azure archive.

    URLs are discovered by authenticated *public* container listings, not by
    assuming unlisted files exist. The service's anonymous SAS allows read/list.
    Only unsigned discovered asset URLs are saved.
    """
    path = RAW / "catalog" / (collection + "_archive_v1.json")
    if path.exists():
        return json.loads(path.read_text())
    indexed = catalog(collection, assets, extra={"platform": {"eq": "terra"}})
    example = indexed[0]["assets"][assets[0]]["href"]
    parsed = urllib.parse.urlsplit(planetary_computer.sign(example))
    container = "https://" + parsed.netloc + "/" + parsed.path.strip("/").split("/")[0]
    sas = dict(urllib.parse.parse_qsl(parsed.query))
    product = indexed[0]["id"].split(".")[0]
    tiles = sorted({(i["properties"]["modis:horizontal-tile"], i["properties"]["modis:vertical-tile"]) for i in indexed})
    entries = {}
    for h, v in tiles:
        for year in range(2021, 2026):
            prefix = f"{product}/{h:02d}/{v:02d}/{year}"
            marker = ""
            while True:
                query = dict(sas, restype="container", comp="list", prefix=prefix, maxresults="5000")
                if marker:
                    query["marker"] = marker
                response = session().get(container, params=query, timeout=90)
                response.raise_for_status()
                tree = ET.fromstring(response.content)
                for node in tree.findall(".//Blob/Name"):
                    name = node.text
                    key = next((a for a in assets if name.endswith("_" + a + ".tif")), None)
                    if key is None:
                        continue
                    identifier = Path(name).name[:-(len(key) + 5)]
                    yday = identifier.split(".")[1][1:]
                    start = pd.Timestamp(year=int(yday[:4]), month=1, day=1) + pd.Timedelta(days=int(yday[4:]) - 1)
                    if not pd.Timestamp("2021-11-01") <= start <= pd.Timestamp("2025-12-31"):
                        continue
                    item = entries.setdefault(identifier, dict(id=identifier, properties={
                        "platform": "terra", "start_datetime": start.strftime("%Y-%m-%dT00:00:00Z"),
                        "modis:horizontal-tile": h, "modis:vertical-tile": v,
                        "discovery": "public Azure container listing; incomplete STAC index repaired"}, assets={}))
                    item["assets"][key] = {"href": container + "/" + name}
                marker = tree.findtext("NextMarker")
                if not marker:
                    break
            print(product, f"h{h:02d}v{v:02d}", year, "archive listed", flush=True)
    unique = {}
    for item in sorted(entries.values(), key=lambda x: x["id"]):
        if not all(a in item["assets"] for a in assets):
            continue
        p = item["properties"]
        unique[(p["modis:horizontal-tile"], p["modis:vertical-tile"], p["start_datetime"])] = item
    result = list(unique.values())
    path.write_text(json.dumps(result))
    coverage = pd.DataFrame([dict(tile=f"h{i['properties']['modis:horizontal-tile']:02d}v{i['properties']['modis:vertical-tile']:02d}",
                                  start=i["properties"]["start_datetime"][:10]) for i in result])
    coverage.to_csv(OUT / (collection + "_archive_coverage.csv"), index=False)
    print(collection, "repaired archive:", len(result), "items versus", len(indexed), "indexed", flush=True)
    return result


def composite_end(start, days):
    # MODIS final annual composite is truncated at December 31.
    return min(start + pd.Timedelta(days=days - 1), pd.Timestamp(year=start.year, month=12, day=31))


def modis_item(item, product):
    start = pd.Timestamp(item["properties"]["start_datetime"]).tz_localize(None)
    rows = []
    if product == "fire":
        maskfile, frpfile = asset(item, "FireMask"), asset(item, "MaxFRP")
        with rasterio.open(maskfile) as m, rasterio.open(frpfile) as f:
            labels = labels_for(m)
            potential = sums(labels)
            for b in range(1, min(m.count, (composite_end(start, 8) - start).days + 1) + 1):
                day = start + pd.Timedelta(days=b - 1)
                month = day.strftime("%Y-%m")
                if month not in MONTHS:
                    continue
                mask = m.read(b)
                fires = (mask == 8) | (mask == 9)
                observed = np.isin(mask, [3, 5, 7, 8, 9])
                nfire, nobs = sums(labels, valid=fires), sums(labels, valid=observed)
                power = sums(labels, f.read(b).astype(float) * 0.1, valid=fires)
                for c in np.flatnonzero(potential):
                    rows.append((int(c), month, float(nfire[c]), float(power[c]), float(nobs[c]), float(potential[c])))
    else:
        days = 16 if product == "ndvi" else 8
        month = composite_end(start, days).strftime("%Y-%m")
        if month not in MONTHS:
            return []
        value_name, qa_name = (("500m_16_days_NDVI", "500m_16_days_pixel_reliability")
                               if product == "ndvi" else ("LST_Day_1km", "QC_Day"))
        with rasterio.open(asset(item, value_name)) as v, rasterio.open(asset(item, qa_name)) as q:
            labels = labels_for(v)
            raw, qa = v.read(1), q.read(1)
            if product == "ndvi":
                good = (qa == 0) & (raw >= -2000) & (raw <= 10000)
                values = raw.astype(float) * 0.0001
            else:
                good = ((qa & 3) == 0) & (((qa >> 6) & 3) == 0) & (raw >= 7500) & (raw != 65535)
                values = raw.astype(float) * 0.02 - 273.15
            nvalid, total, possible = sums(labels, valid=good), sums(labels, values, good), sums(labels)
            for c in np.flatnonzero(possible):
                rows.append((int(c), month, float(total[c]), float(nvalid[c]), float(possible[c])))
    return rows


def build_modis(product, workers=4, limit=None):
    definitions = {
        "fire": ("modis-14A1-061", ["FireMask", "MaxFRP"]),
        "ndvi": ("modis-13A1-061", ["500m_16_days_NDVI", "500m_16_days_pixel_reliability"]),
        "lst": ("modis-11A2-061", ["LST_Day_1km", "QC_Day"]),
    }
    collection, assets = definitions[product]
    items = archive_catalog(collection, assets)
    if limit:
        items = items[:limit]
    cache = RAW / "zonal" / product
    cache.mkdir(parents=True, exist_ok=True)

    def work(item):
        path = cache / (item["id"] + ".json")
        if path.exists():
            # Re-register cached source assets in the provenance manifest.
            for name in assets:
                url = item["assets"][name]["href"]
                local = RAW / "modis" / Path(url).name
                if local.exists():
                    record(local, url)
            return json.loads(path.read_text())
        rows = modis_item(item, product)
        path.write_text(json.dumps(rows))
        return rows

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, result in enumerate(pool.map(work, items), 1):
            rows.extend(result)
            if i % 25 == 0 or i == len(items):
                print(product, i, "/", len(items), "tiles summarized", flush=True)
    if limit:
        print("SMOKE TEST ONLY; no monthly product written", flush=True)
        return
    fields = (["c", "month", "fire_pixel_days", "frp_mw_sum", "observed", "possible"]
              if product == "fire" else ["c", "month", "total", "valid", "possible"])
    df = pd.DataFrame(rows, columns=fields).groupby(["c", "month"]).sum().reset_index()
    df["county_fips"] = counties().GEOID.iloc[df.c].to_numpy()
    # Expected denominator includes missing granules/days, not just files found.
    pixel_counts = np.zeros(58)
    seen_tiles = set()
    for item in items:
        prop = item["properties"]
        tile = (prop["modis:horizontal-tile"], prop["modis:vertical-tile"])
        if tile in seen_tiles:
            continue
        with rasterio.open(asset(item, assets[0])) as src:
            pixel_counts += sums(labels_for(src))
        seen_tiles.add(tile)
    if (pixel_counts == 0).any():
        raise ValueError("County absent from satellite grid")
    epochs = {m: 0 for m in MONTHS}
    if product == "fire":
        epochs = {m: pd.Period(m).days_in_month for m in MONTHS}
    else:
        for year in range(2021, 2026):
            first = pd.Timestamp(year=year, month=1, day=1)
            step = 16 if product == "ndvi" else 8
            for day in range(0, 366 if first.is_leap_year else 365, step):
                end = composite_end(first + pd.Timedelta(days=day), step)
                month = end.strftime("%Y-%m")
                if month in epochs:
                    epochs[month] += 1
    df["expected_possible"] = pixel_counts[df.c] * df.month.map(epochs)
    df["archive_fraction"] = df.possible / df.expected_possible
    if (df.archive_fraction > 1.000001).any():
        raise ValueError("Duplicated satellite dates or inconsistent grid")
    if product == "fire":
        df["fire_observed_fraction"] = df.observed / df.expected_possible
        df.loc[df.fire_observed_fraction < 0.1, ["fire_pixel_days", "frp_mw_sum"]] = np.nan
    else:
        df[product] = df.total / df.valid.replace(0, np.nan)
        df[product + "_valid_fraction"] = df.valid / df.expected_possible
    df.drop(columns="c").to_csv(OUT / (product + "_county_month.csv"), index=False)


def build_prism():
    rows = []
    for variable in ["tmean", "ppt"]:
        for month in MONTHS:
            code = month.replace("-", "")
            url = f"https://services.nacse.org/prism/data/get/us/4km/{variable}/{code}"
            archive = download(url, RAW / "prism" / f"{variable}_{code}.zip")
            with zipfile.ZipFile(archive) as z:
                tif = next(n for n in z.namelist() if n.endswith(".tif"))
                path = RAW / "prism" / tif
                if not path.exists():
                    path.write_bytes(z.read(tif))
            with rasterio.open(path) as src:
                labels = labels_for(src)
                values = src.read(1)
                good = src.read_masks(1) > 0
                if src.nodata is not None:
                    good &= values != src.nodata
                # Geographic PRISM cells vary in area; cosine latitude weights.
                lat = src.transform.f + (np.arange(src.height) + 0.5) * src.transform.e
                weights = np.broadcast_to(np.cos(np.deg2rad(lat))[:, None], values.shape)
                total = sums(labels, values * weights, good)
                denom = sums(labels, weights, good)
                for c in range(58):
                    rows.append(dict(county_fips=counties().GEOID.iloc[c], month=month,
                                     variable=variable, value=total[c] / denom[c] if denom[c] else np.nan))
            print("PRISM", variable, month, flush=True)
            time.sleep(2)  # PRISM bulk-download guidance.
    df = pd.DataFrame(rows).pivot(index=["county_fips", "month"], columns="variable", values="value").reset_index()
    df.to_csv(OUT / "prism_county_month.csv", index=False)


def build_landcover(workers=4):
    items = catalog("usda-cdl", ["cultivated"], "2021-01-01", "2021-12-31",
                    {"usda_cdl:type": {"eq": "cultivated"}})

    def work(item):
        url = item["assets"]["cultivated"]["href"]
        path = download(url, RAW / "cdl" / Path(url).name, sign=True)
        with rasterio.open(path) as src:
            labels = labels_for(src)
            values = src.read(1)
            cultivated = sums(labels, valid=values == 2)
            classified = sums(labels, valid=np.isin(values, [1, 2]))
            return cultivated, classified

    cultivated, classified = np.zeros(58), np.zeros(58)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (a, b) in enumerate(pool.map(work, items), 1):
            cultivated += a
            classified += b
            if i % 10 == 0 or i == len(items):
                print("CDL", i, "/", len(items), flush=True)
    pd.DataFrame(dict(county_fips=counties().GEOID, cultivated_fraction_2021=cultivated / classified,
                      classified_pixels=classified)).to_csv(OUT / "landcover_2021.csv", index=False)


def build_aphis(source):
    dest = RAW / "aphis_wildbird_snapshot.csv"
    if Path(source).resolve() != dest.resolve():
        shutil.copy2(source, dest)
    record(dest, "user-supplied APHIS wild-bird CSV snapshot; latest record date audited separately")
    df = pd.read_csv(dest, encoding="utf-8-sig", dtype=str).fillna("")
    required = ["State", "County", "Date Detected", "HPAI Strain", "WOAH Classification"]
    if not set(required).issubset(df):
        raise ValueError("APHIS schema changed; expected " + repr(required))
    df["date"] = pd.to_datetime(df["Date Detected"], format="%m/%d/%y", errors="coerce")
    if df.date.isna().any():
        raise ValueError("Unparsed detection dates")
    ca = df.loc[(df.State.str.strip() == "California") &
                (df["WOAH Classification"].str.strip().str.lower() == "wild bird")].copy()
    ca["county"] = ca.County.str.strip().str.replace(r" County$", "", regex=True)
    known = dict(zip(counties().NAME, counties().GEOID))
    ca["county_fips"] = ca.county.map(known)
    unmatched = ca.county_fips.isna()
    if (unmatched & ~ca.county.str.lower().isin(["unknown", "", "not available"])).any():
        raise ValueError("Unmatched California counties: " + repr(ca.loc[ca.county_fips.isna(), "county"].unique()))
    ca["month"] = ca.date.dt.strftime("%Y-%m")
    ca["h5n1"] = ca["HPAI Strain"].str.contains("H5N1", case=False).astype(int)
    ca["h5_any"] = ca["HPAI Strain"].str.contains("H5", case=False).astype(int)
    sub = ca[ca.month.between("2022-01", "2025-12")]
    unassigned = sub[sub.county_fips.isna()]
    unassigned.groupby("month")[["h5n1", "h5_any"]].sum().to_csv(OUT / "aphis_unassigned_county_month.csv")
    sub = sub[sub.county_fips.notna()]
    out = sub.groupby(["county_fips", "month"])[["h5n1", "h5_any"]].sum().reset_index()
    out.to_csv(OUT / "aphis_county_month.csv", index=False)
    audit = dict(source_rows=len(df), source_latest_date=str(df.date.max().date()),
                 california_wild_rows=len(ca), study_rows=len(sub),
                 explicit_h5n1_rows=int(sub.h5n1.sum()), inclusive_h5_rows=int(sub.h5_any.sum()),
                 excluded_unknown_county_study_rows=len(unassigned),
                 duplicate_full_rows=int(sub.duplicated(required).sum()),
                 duplicate_note="Matching fields may represent separate birds; records are not deduplicated without identifiers. Binary outcome is unaffected by exact repeats.",
                 strain_counts=sub["HPAI Strain"].value_counts().to_dict())
    (OUT / "aphis_quality_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print("APHIS", json.dumps(audit), flush=True)


def audit_inputs():
    """Report source coverage without treating absent observations as zeros."""
    ca = counties()
    known = set(ca.GEOID)
    expected = set(REQUIRED_ENV_MONTHS)
    definitions = {
        "prism": ["tmean", "ppt"],
        "fire": ["fire_pixel_days", "frp_mw_sum"],
        "ndvi": ["ndvi"],
        "lst": ["lst"],
    }
    summaries, monthly, blockers = {}, [], {}
    for name, values in definitions.items():
        path = OUT / (name + "_county_month.csv")
        if path.exists():
            frame = pd.read_csv(path, dtype={"county_fips": str})
            if frame.duplicated(["county_fips", "month"]).any():
                raise ValueError(f"Duplicate county-month keys in {path.name}")
            if not set(frame.county_fips).issubset(known):
                raise ValueError(f"Unexpected county in {path.name}")
            frame = frame[frame.month.isin(expected)].copy()
        else:
            frame = pd.DataFrame(columns=["county_fips", "month", *values])
        missing_rows = sorted(expected - set(frame.month))
        missing_values = {}
        for value in values:
            usable = frame.groupby("month")[value].count()
            missing_values[value] = [month for month in REQUIRED_ENV_MONTHS if usable.get(month, 0) == 0]
            # Isolated absent composites remain missing and are imputed inside
            # each training fold. A wholly absent predictor blocks the panel.
            if frame[value].notna().sum() == 0:
                blockers[value] = missing_values[value]
        summaries[name] = dict(path=str(path.relative_to(ROOT)), rows=len(frame),
                               counties=frame.county_fips.nunique(), months=frame.month.nunique(),
                               absent_months=missing_rows, entirely_missing_months=missing_values,
                               missing_values={value: int(frame[value].isna().sum()) for value in values})
        for month in REQUIRED_ENV_MONTHS:
            subset = frame.loc[frame.month == month]
            entry = dict(dataset=name, month=month, expected_counties=58,
                         available_county_rows=len(subset))
            for value in values:
                entry[value + "_usable_counties"] = int(subset[value].notna().sum())
            for column in ["archive_fraction", "fire_observed_fraction", "ndvi_valid_fraction", "lst_valid_fraction"]:
                if column in subset:
                    entry[column + "_mean"] = float(subset[column].mean()) if len(subset) else None
            monthly.append(entry)
    land = pd.read_csv(OUT / "landcover_2021.csv", dtype={"county_fips": str})
    land_ok = (len(land) == 58 and land.county_fips.is_unique and set(land.county_fips) == known
               and land.cultivated_fraction_2021.between(0, 1).all())
    if not land_ok:
        raise ValueError("Landcover must supply a valid cultivated fraction for all 58 counties")
    aphis = pd.read_csv(OUT / "aphis_county_month.csv", dtype={"county_fips": str})
    if aphis.duplicated(["county_fips", "month"]).any() or not set(aphis.county_fips).issubset(known):
        raise ValueError("Invalid APHIS county-month keys")
    report = dict(
        audited_utc=datetime.now(timezone.utc).isoformat(),
        outcome_window=[OBS_START, OBS_END],
        environmental_window=[OBS_ENV_START, REQUIRED_ENV_MONTHS[-1]],
        expected_counties=58, expected_environmental_months=len(REQUIRED_ENV_MONTHS),
        environmental_datasets=summaries,
        aphis=dict(rows=len(aphis), counties_with_reports=aphis.county_fips.nunique(),
                   explicit_h5n1_records=int(aphis.h5n1.sum()), inclusive_h5_records=int(aphis.h5_any.sum()),
                   note="Sparse report counts; absent reports do not establish tested-negative surveillance."),
        landcover=dict(rows=len(land), complete=bool(land_ok)),
        county_reference=dict(rows=len(ca), source="2024 Census TIGER/Line counties, STATEFP == 06"),
        inputs_ready_for_panel=not blockers,
        blocking_entirely_missing_predictors=blockers,
        missing_month_policy=("Absent or QA-filtered satellite composites remain missing and are "
                              "imputed from training-fold medians with missingness indicators."),
        note=("The analysis ends in July 2025 because the public MODIS COG archive has contiguous "
              "multi-product gaps after that point. The separate SNPP VIIRS detections are not "
              "substituted into Terra MODIS features."))
    (OUT / "data_readiness.json").write_text(json.dumps(report, indent=2) + "\n")
    pd.DataFrame(monthly).to_csv(OUT / "monthly_input_coverage.csv", index=False)
    print(json.dumps(report, indent=2), flush=True)
    return report


def build_panel():
    ca = counties()
    source_months = pd.period_range(OBS_ENV_START, OBS_END, freq="M").astype(str)
    panel = pd.MultiIndex.from_product([ca.GEOID, source_months], names=["county_fips", "month"]).to_frame(index=False)
    for name in ["aphis_county_month", "prism_county_month", "fire_county_month", "ndvi_county_month", "lst_county_month"]:
        part = pd.read_csv(OUT / (name + ".csv"), dtype={"county_fips": str})
        if name.startswith("fire"):
            cols = ["county_fips", "month", "fire_pixel_days", "frp_mw_sum", "fire_observed_fraction"]
        elif name.startswith("ndvi") or name.startswith("lst"):
            col = name.split("_")[0]
            cols = ["county_fips", "month", col, col + "_valid_fraction"]
        else:
            cols = list(part)
        assert not part.duplicated(["county_fips", "month"]).any()
        panel = panel.merge(part[cols], on=["county_fips", "month"], how="left", validate="1:1")
    land = pd.read_csv(OUT / "landcover_2021.csv", dtype={"county_fips": str})
    panel = panel.merge(land, on="county_fips", how="left", validate="m:1")
    panel[["h5n1", "h5_any"]] = panel[["h5n1", "h5_any"]].fillna(0).astype(int)
    panel["county"] = panel.county_fips.map(dict(zip(ca.GEOID, ca.NAME)))
    panel["y"] = (panel.h5n1 > 0).astype(int)
    panel["y_h5_inclusive"] = (panel.h5_any > 0).astype(int)
    environmental = ["tmean", "ppt", "fire_pixel_days", "frp_mw_sum", "fire_observed_fraction", "ndvi", "lst", "ndvi_valid_fraction", "lst_valid_fraction"]
    if panel[environmental].notna().sum().eq(0).any():
        raise ValueError("At least one required environmental predictor is entirely absent")
    panel = panel.sort_values(["county_fips", "month"]).reset_index(drop=True)
    for col in environmental:
        panel[col + "_lag1"] = panel.groupby("county_fips")[col].shift(1)
    panel["fire_pixel_days_lag1_log"] = np.log1p(panel.fire_pixel_days_lag1)
    panel["frp_mw_sum_lag1_log"] = np.log1p(panel.frp_mw_sum_lag1)
    panel["month_num"] = pd.to_datetime(panel.month + "-01").dt.month
    panel["sin_month"] = np.sin(2 * np.pi * panel.month_num / 12)
    panel["cos_month"] = np.cos(2 * np.pi * panel.month_num / 12)
    panel = panel[panel.month.isin(ANALYSIS_MONTHS)].copy()
    assert len(panel) == 58 * len(ANALYSIS_MONTHS) and panel.county_fips.nunique() == 58
    assert not panel.duplicated(["county_fips", "month"]).any()
    panel["data_type"] = "observational"
    panel.to_csv(OUT / "panel.csv", index=False)
    panel.to_parquet(OUT / "panel.parquet", index=False)
    audit = pd.DataFrame({"variable": panel.columns, "missing": panel.isna().sum().to_numpy(),
                          "missing_fraction": panel.isna().mean().to_numpy()})
    audit.to_csv(OUT / "panel_missingness.csv", index=False)
    panel.groupby("month").agg(counties=("county_fips", "nunique"),
                               reported_h5n1_rows=("h5n1", "sum"), positive_counties=("y", "sum"),
                               ndvi_coverage=("ndvi_valid_fraction", "mean"),
                               lst_coverage=("lst_valid_fraction", "mean"),
                               fire_coverage=("fire_observed_fraction", "mean")).to_csv(OUT / "monthly_quality_audit.csv")
    print("REAL PANEL", panel.shape, "positive county-months", panel.y.sum(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["aphis", "prism", "fire", "ndvi", "lst", "landcover", "audit", "panel"])
    parser.add_argument("--aphis-csv")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, help="Smoke test first N MODIS tiles; never writes a monthly summary")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "download_manifest.json"
    if manifest.exists():
        MANIFEST.update(json.loads(manifest.read_text()))
    try:
        if args.stage in ["fire", "ndvi", "lst"]:
            build_modis(args.stage, args.workers, args.limit)
        elif args.stage == "aphis":
            if not args.aphis_csv:
                parser.error("--aphis-csv is required")
            build_aphis(args.aphis_csv)
        elif args.stage == "prism":
            build_prism()
        elif args.stage == "landcover":
            build_landcover(args.workers)
        elif args.stage == "audit":
            audit_inputs()
        else:
            readiness = audit_inputs()
            if not readiness["inputs_ready_for_panel"]:
                raise SystemExit("Observational panel blocked by missing environmental months; "
                                 "see data/processed/real/data_readiness.json.")
            build_panel()
    finally:
        # Public URLs only, never signed URLs or credentials.
        with (RAW / "manifest.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            merged = json.loads(manifest.read_text()) if manifest.exists() else {}
            merged.update(MANIFEST)
            tmp = manifest.with_suffix(".tmp")
            tmp.write_text(json.dumps(merged, indent=2) + "\n")
            tmp.replace(manifest)


if __name__ == "__main__":
    main()
