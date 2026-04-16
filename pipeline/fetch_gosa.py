"""
Fetch and parse GOSA (Governor's Office of Student Achievement) graduation rate data.

Discovery strategy:
  - GOSA publishes annual data at https://download.gosa.ga.gov/{year}/
    where {year} is the graduation year (e.g. 2025 for the 2024-25 school year).
  - The directory listing is open, so we scrape it for the Graduation_Rate_*.csv
    filename (the timestamp suffix in the name is unpredictable).
  - Tries the most recently completed school year first, falls back one year if
    the file isn't posted yet. Falls back to a locally cached copy if offline.

Output: data/processed/graduation_rates.csv
  county_name, district_name, school_year, grad_rate_pct, cohort_total
"""

import re
import io
import requests
import pandas as pd
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import COUNTIES, DATA_RAW, DATA_PROCESSED

GOSA_BASE   = "https://download.gosa.ga.gov"
GOSA_CACHE  = DATA_RAW / "gosa"
ARC_COUNTY_NAMES = set(COUNTIES.keys())

# GOSA district names → ARC county mapping.
# Single-county districts that don't follow "{County} County" naming pattern.
# Value is a string (single county) or list (district spans multiple counties).
DISTRICT_COUNTY_MAP = {
    # Fulton / DeKalb
    "Atlanta Public Schools":        "Fulton",
    "City Schools of Decatur":       "DeKalb",
    # Cobb
    "Marietta City":                 "Cobb",
    # Bartow
    "Cartersville City":             "Bartow",
    # Carroll
    "Carroll County":                "Carroll",
    "Carrollton City":               "Carroll",
    "Villa Rica City":               "Carroll",
    # Spalding — GOSA names the district "Griffin-Spalding County"
    "Griffin-Spalding County":       "Spalding",
    # Hall
    "Gainesville City":              "Hall",
    # Buford City School System spans Hall and Gwinnett — show under both
    "Buford City":                   ["Hall", "Gwinnett"],
    # Walton
    "Social Circle City":            "Walton",
}


def _county_from_district(district_name: str) -> str | list | None:
    """
    Infer the ARC county (or counties) a district belongs to.
    Returns a str for single-county districts, a list for multi-county districts,
    or None if the district is not in the ARC region.
    """
    if district_name in DISTRICT_COUNTY_MAP:
        return DISTRICT_COUNTY_MAP[district_name]
    for county in ARC_COUNTY_NAMES:
        if district_name.startswith(county):
            return county
    return None


def _candidate_years() -> list[int]:
    """
    Return the two most likely directory years to check, most recent first.
    The directory year = graduation year = second year of the school year.
    GOSA typically publishes data in January/February after the school year ends,
    so current_year - 1 is the safe first guess year-round.
    """
    current = datetime.now().year
    return [current - 1, current - 2]


def _find_file_url(year: int) -> str | None:
    """
    Fetch the GOSA directory listing for {year} and return the full URL of the
    most recently published Graduation_Rate_*.csv (excluding 5-Year variant).
    Returns None if the directory is unreachable or no matching file is found.
    """
    dir_url = f"{GOSA_BASE}/{year}/"
    resp = None
    for attempt in range(3):
        try:
            resp = requests.get(dir_url, timeout=15)
            break
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError):
            if attempt < 2:
                time.sleep(2.0 ** attempt)
                continue
            return None
        except requests.RequestException:
            return None
    if resp is None or resp.status_code != 200:
        return None

    # Parse all href links matching Graduation_Rate_*.csv (not 5-Year_*)
    filenames = re.findall(
        r'href="(Graduation_Rate_[^"]+\.csv)"',
        resp.text
    )
    if not filenames:
        return None

    # If multiple files exist, take the last one alphabetically (latest timestamp)
    filename = sorted(filenames)[-1]
    return f"{GOSA_BASE}/{year}/{filename}"


def _download(url: str) -> pd.DataFrame:
    """Stream a CSV directly from URL into a DataFrame."""
    last_exc = None
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            return pd.read_csv(io.StringIO(resp.text), low_memory=False)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            last_exc = e
            if attempt < 2:
                time.sleep(2.0 ** attempt)
    raise last_exc


def _load_cached() -> tuple[pd.DataFrame, str]:
    """Fall back to the most recently downloaded local GOSA file."""
    cached = sorted(GOSA_CACHE.glob("Graduation_Rate_*.csv"), reverse=True)
    if not cached:
        raise FileNotFoundError(
            f"No GOSA file found locally in {GOSA_CACHE} and remote fetch failed.\n"
            "Download manually from: https://gosa.georgia.gov/report-card-dashboards-data/downloadable-data"
        )
    path = cached[0]
    return pd.read_csv(path, low_memory=False), path.name


def fetch_gosa():
    print("Fetching GOSA graduation rates...")

    df = None
    source_label = None

    for year in _candidate_years():
        school_year = f"{year-1}-{str(year)[2:]}"   # e.g. 2025 → "2024-25"
        print(f"  Trying {year} directory (school year {school_year})...")
        url = _find_file_url(year)
        if url is None:
            print(f"    Not found in {year} directory.")
            continue
        try:
            df = _download(url)
            source_label = url.split("/")[-1]
            print(f"  Downloaded: {source_label}")
            # Cache locally so the pipeline can run offline
            GOSA_CACHE.mkdir(parents=True, exist_ok=True)
            cache_path = GOSA_CACHE / source_label
            if not cache_path.exists():
                cache_path.write_bytes(requests.get(url, timeout=120).content)
                print(f"  Cached to {cache_path}")
            break
        except requests.RequestException as e:
            print(f"    Download failed: {e}")

    if df is None:
        print("  Remote fetch failed — falling back to local cache...")
        df, source_label = _load_cached()
        print(f"  Using cached: {source_label}")

    # ── Filter to district-level, all-students graduation rate ───────────────
    df = df[
        (df["DETAIL_LVL_DESC"] == "District") &
        (df["LABEL_LVL_1_DESC"] == "Grad Rate -ALL Students")
    ].copy()

    # ── Map each district to its ARC county (or counties) ───────────────────
    df["_county_raw"] = df["SCHOOL_DSTRCT_NM"].apply(_county_from_district)
    df = df[df["_county_raw"].notna()].copy()

    # Expand multi-county districts (e.g. Buford City → Hall + Gwinnett)
    rows = []
    for _, row in df.iterrows():
        counties = row["_county_raw"]
        if isinstance(counties, list):
            for county in counties:
                rows.append({**row.to_dict(), "county_name": county})
        else:
            rows.append({**row.to_dict(), "county_name": counties})
    df = pd.DataFrame(rows)

    # ── Clean up rate column ─────────────────────────────────────────────────
    df["grad_rate_pct"] = pd.to_numeric(df["PROGRAM_PERCENT"], errors="coerce")
    df = df[df["grad_rate_pct"].notna()].copy()

    out = df[[
        "county_name",
        "SCHOOL_DSTRCT_NM",
        "LONG_SCHOOL_YEAR",
        "grad_rate_pct",
        "TOTAL_COUNT",
    ]].rename(columns={
        "SCHOOL_DSTRCT_NM": "district_name",
        "LONG_SCHOOL_YEAR": "school_year",
        "TOTAL_COUNT":      "cohort_total",
    }).sort_values(["county_name", "district_name"]).reset_index(drop=True)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "graduation_rates.csv"
    out.to_csv(out_path, index=False)
    print(f"  Saved {len(out)} districts → {out_path}")
    return out


if __name__ == "__main__":
    fetch_gosa()
