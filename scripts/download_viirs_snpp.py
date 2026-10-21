"""Download archived SNPP 375 m fires with interactive Earthdata login.

Requires Python 3.11+ and packages in requirements-viirs.txt.
Run with .venv/bin/python scripts/download_viirs_snpp.py. Credentials are
prompted in the terminal and are not persisted. Reruns reuse valid downloads.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import earthaccess
import h5py
import pandas as pd
from requests.adapters import HTTPAdapter

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
DEST = RAW / "viirs_snpp_375m_202507_202510"
BBOX = (-124.6, 32.4, -113.9, 42.1)
TEMPORAL = ("2025-07-01T00:00:00Z", "2025-10-31T23:59:59Z")
COLLECTION = "C2734202914-LPCLOUD"


class TimeoutAdapter(HTTPAdapter):
    """Bound stalled transfers, including sessions earthaccess clones."""

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = (20, 60)
        return super().send(request, **kwargs)


def fire_pixel_count(data):
    value = data.attrs.get("FirePix", -1)
    return int(value.item() if hasattr(value, "item") else value)


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def status(state, **details):
    save_json(DEST / "status.json", dict(
        state=state, updated_utc=datetime.now(timezone.utc).isoformat(), **details))


def valid_nc(path):
    try:
        with h5py.File(path) as data:
            return (("FP_latitude" in data and "FP_longitude" in data) or
                    (fire_pixel_count(data) == 0 and
                     ("fire_mask" in data or "fire mask" in data)))
    except (OSError, ValueError):
        return False


def extract_points(path, granule):
    umm = granule["umm"]
    acquired = umm["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
    when = pd.Timestamp(acquired)
    columns = {
        "latitude": "FP_latitude", "longitude": "FP_longitude",
        "frp": "FP_power", "confidence": "FP_confidence",
        "bright_ti4": "FP_T4", "bright_ti5": "FP_T5",
        "line": "FP_line", "sample": "FP_sample",
    }
    with h5py.File(path) as data:
        if fire_pixel_count(data) == 0:
            frame = pd.DataFrame(columns=list(columns))
        else:
            lat = data["FP_latitude"][:].reshape(-1)
            lon = data["FP_longitude"][:].reshape(-1)
            inside = ((lon >= BBOX[0]) & (lon <= BBOX[2]) &
                      (lat >= BBOX[1]) & (lat <= BBOX[3]))
            frame = pd.DataFrame({
                label: data[name][:].reshape(-1)[inside]
                for label, name in columns.items() if name in data
            })
    frame["acq_date"] = when.strftime("%Y-%m-%d")
    frame["acq_time"] = when.strftime("%H%M")
    frame["satellite"] = "N"
    frame["instrument"] = "VIIRS"
    frame["version"] = "002"
    frame["daynight"] = umm["DataGranule"].get("DayNightFlag", "Unknown")
    frame["source_granule"] = path.name
    return frame


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    catalog = DEST / "granules.json"
    if catalog.exists():
        granules = [earthaccess.DataGranule(g) for g in json.loads(catalog.read_text())]
    else:
        granules = earthaccess.search_data(
            concept_id=COLLECTION, bounding_box=BBOX, temporal=TEMPORAL, count=-1)
        save_json(catalog, granules)
    if not granules:
        raise RuntimeError("NASA returned no matching granules.")
    for granule in granules:
        umm = granule["umm"]
        assert umm["CollectionReference"] == {"ShortName": "VNP14IMG", "Version": "002"}
        acquired = umm["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
        assert TEMPORAL[0][:10] <= acquired[:10] <= TEMPORAL[1][:10]
    print(f"{len(granules)} VNP14IMG.002 granules; CA bbox {BBOX}.", flush=True)
    print(f"Output: {DEST}", flush=True)
    status("awaiting_interactive_login", granules=len(granules))
    auth = earthaccess.login(strategy="interactive", persist=False)
    if not auth.authenticated:
        raise RuntimeError("Earthdata authentication failed; rerun to log in again.")
    original_get_session = auth.get_session

    def session_with_timeout(*args, **kwargs):
        session = original_get_session(*args, **kwargs)
        session.mount("https://", TimeoutAdapter())
        return session

    auth.get_session = session_with_timeout
    print("Earthdata login succeeded. Downloading and validating files...", flush=True)
    for start in range(0, len(granules), 16):
        batch = granules[start:start + 16]
        pending = []
        for granule in batch:
            path = DEST / (granule["umm"]["GranuleUR"] + ".nc")
            if not valid_nc(path):
                if path.exists():
                    path.unlink()
                pending.append(granule)
        if pending:
            earthaccess.download(pending, local_path=DEST, threads=4, show_progress=False)
        for granule in batch:
            path = DEST / (granule["umm"]["GranuleUR"] + ".nc")
            if not valid_nc(path):
                raise RuntimeError(f"Invalid or incomplete science file: {path.name}")
        completed = start + len(batch)
        status("downloading", completed=completed, total=len(granules))
        print(f"{completed}/{len(granules)} raw files validated", flush=True)
    frames = []
    records = []
    for index, granule in enumerate(granules, 1):
        urls = granule.data_links(access="external")
        if len(urls) != 1 or not urls[0].endswith(".nc"):
            raise RuntimeError(f"Unexpected science links for {granule['umm']['GranuleUR']}")
        path = DEST / urls[0].rsplit("/", 1)[-1]
        if not valid_nc(path):
            for attempt in range(3):
                if path.exists():
                    path.unlink()
                try:
                    earthaccess.download([granule], local_path=DEST, threads=1,
                                         show_progress=False)
                    if not valid_nc(path):
                        raise RuntimeError(f"Invalid NetCDF/HDF5 science file: {path.name}")
                    break
                except Exception:
                    if attempt == 2:
                        raise
        frame = extract_points(path, granule)
        frames.append(frame)
        with path.open("rb") as source:
            checksum = hashlib.file_digest(source, "sha256").hexdigest()
        records.append(dict(
            filename=path.name, source_url=urls[0], bytes=path.stat().st_size,
            sha256=checksum,
            ca_bbox_detections=len(frame),
            acquisition=granule["umm"]["TemporalExtent"]["RangeDateTime"]))
        status("extracting", completed=index, total=len(granules),
               ca_bbox_detections=sum(len(f) for f in frames))
        if index == 1 or index % 25 == 0 or index == len(granules):
            print(f"{index}/{len(granules)} validated; "
                  f"{sum(len(f) for f in frames):,} points within bbox", flush=True)
    points = pd.concat(frames, ignore_index=True)
    csvs = []
    for month in ("2025-07", "2025-08", "2025-09", "2025-10"):
        monthly = points[points.acq_date.str.startswith(month)].sort_values(
            ["acq_date", "acq_time", "source_granule", "latitude", "longitude"])
        output = RAW / f"firms_viirs_ca_{month.replace('-', '')}.csv"
        temporary = output.with_suffix(".csv.tmp")
        monthly.to_csv(temporary, index=False)
        temporary.replace(output)
        csvs.append(dict(path=str(output.relative_to(ROOT)), detections=len(monthly)))
    save_json(DEST / "manifest.json", dict(
        product="VNP14IMG", version="002", platform="SUOMI-NPP", resolution_m=375,
        doi="10.5067/VIIRS/VNP14IMG.002", collection_concept_id=COLLECTION,
        bounding_box_west_south_east_north=BBOX, temporal_utc=TEMPORAL,
        earthaccess_version=earthaccess.__version__,
        source_files=records, monthly_csvs=csvs,
        notes=["CMR selects swaths intersecting the bbox; NetCDF files retain full swaths.",
               "CSV points are clipped to the bbox, which includes areas outside California.",
               "All source fire confidences are retained. FP_confidence is copied unchanged.",
               "CSV dates/times use the source granule start in UTC.",
               "CSV files are extracted from VNP14IMG, not FIRMS server CSV downloads."]))
    status("complete", validated_granules=len(granules), detections=len(points), monthly_csvs=csvs)
    print(f"Complete: {len(granules)} raw files and {len(points):,} detections.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        DEST.mkdir(parents=True, exist_ok=True)
        status("failed", error_type=type(error).__name__)
        print(f"Download stopped ({type(error).__name__}). Rerun to resume.", file=sys.stderr)
        raise SystemExit(1)
