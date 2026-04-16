"""
Fetch Census Building Permits Survey (BPS) annual data.

Source: https://www2.census.gov/econ/bps/County/co{YYMM}c.txt
  - Monthly county-level file; new data posts ~2 months after month-end
  - Fetches all complete calendar years from START_YEAR through the most recently
    completed calendar year (e.g. on April 3 2026, fetches 2000–2025)
  - Monthly TXT files cached in data/raw/bps/ — ~300 files on first run,
    near-instant on subsequent runs

Output: data/processed/building_permits.csv
  county_name, year, sf_permits, mf_total_permits, total_permits
"""

import io
import requests
import pandas as pd
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import COUNTIES, STATE_FIPS, DATA_RAW, DATA_PROCESSED

BPS_BASE   = "https://www2.census.gov/econ/bps/County"
BPS_CACHE  = DATA_RAW / "bps"
START_YEAR = 2000
ARC_FIPS   = {STATE_FIPS + v for v in COUNTIES.values()}


def _target_year() -> int:
    """Latest calendar year for which all 12 monthly BPS files have been published."""
    today = datetime.today()
    # BPS posts ~2 months after month-end (1 month if past the 27th).
    lag = 1 if today.day > 27 else 2
    m, y = today.month - lag, today.year
    while m <= 0:
        m += 12
        y -= 1
    # If the latest published month is December, that year is fully complete.
    return y if m == 12 else y - 1


def _fetch_month(month_dt: datetime) -> pd.DataFrame | None:
    """
    Return filtered ARC county rows for a single month.
    Reads from cache if present; downloads and caches on miss.
    """
    yymm = month_dt.strftime("%y%m")
    cache_path = BPS_CACHE / f"co{yymm}c.txt"

    if cache_path.exists():
        raw = cache_path.read_text()
    else:
        url = f"{BPS_BASE}/co{yymm}c.txt"
        raw = None
        # Retry transient network drops; 404 (month genuinely not published)
        # falls through to return None on the last attempt.
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                raw = resp.text
                break
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.ChunkedEncodingError) as e:
                if attempt < 2:
                    time.sleep(2.0 ** attempt)
                    continue
                return None
            except requests.RequestException:
                return None
        if raw is None:
            return None
        BPS_CACHE.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(raw)

    df = pd.read_csv(io.StringIO(raw), skiprows=1)
    df = df.rename(columns={
        "Date":    "year_month",
        "Units":   "SF_permits",
        "Value":   "SF_value",
        "Units.1": "2U_permits",
        "Value.1": "2U_value",
        "Units.2": "3-4U_permits",
        "Value.2": "3-4U_value",
        "Units.3": "5+U_permits",
        "Value.3": "5+U_value",
    })
    df["FIPS"] = (
        df["State"].astype(str).str.zfill(2) +
        df["County"].astype(str).str.zfill(3)
    )
    df["MF_permits"] = df["2U_permits"] + df["3-4U_permits"] + df["5+U_permits"]
    df = df[df["FIPS"].isin(ARC_FIPS)].copy()
    return df[["FIPS", "SF_permits", "MF_permits"]] if not df.empty else None


def fetch_hud_permits():
    target_year = _target_year()
    print(f"Fetching BPS building permits {START_YEAR}–{target_year}...")

    fips_to_name = {STATE_FIPS + v: k for k, v in COUNTIES.items()}
    annual_rows = []
    cached_count = 0

    for year in range(START_YEAR, target_year + 1):
        year_frames = []
        for month in range(1, 13):
            month_dt = datetime(year, month, 1)
            yymm = month_dt.strftime("%y%m")
            from_cache = (BPS_CACHE / f"co{yymm}c.txt").exists()
            result = _fetch_month(month_dt)
            if result is not None:
                year_frames.append(result)
                if from_cache:
                    cached_count += 1

        if not year_frames:
            print(f"  WARNING: no data for {year} — skipping.")
            continue

        n = len(year_frames)
        if n < 12:
            print(f"  {year}: only {n}/12 months available")

        df_year = pd.concat(year_frames, ignore_index=True)
        annual = (
            df_year.groupby("FIPS")
            .agg(sf_permits=("SF_permits", "sum"),
                 mf_total_permits=("MF_permits", "sum"))
            .reset_index()
        )
        annual["total_permits"] = annual["sf_permits"] + annual["mf_total_permits"]
        annual["county_name"]   = annual["FIPS"].map(fips_to_name)
        annual["year"]          = year
        annual_rows.append(annual)

    if not annual_rows:
        raise RuntimeError("No BPS data fetched for any year.")

    total_months = (target_year - START_YEAR + 1) * 12
    print(f"  {cached_count}/{total_months} month-files served from cache")

    df_all = pd.concat(annual_rows, ignore_index=True)
    out = (
        df_all[["county_name", "year", "sf_permits", "mf_total_permits", "total_permits"]]
        .sort_values(["county_name", "year"])
        .reset_index(drop=True)
    )

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "building_permits.csv"
    out.to_csv(out_path, index=False)
    print(f"  Saved {len(out)} rows → {out_path}  ({START_YEAR}–{target_year})")
    return out


if __name__ == "__main__":
    fetch_hud_permits()
