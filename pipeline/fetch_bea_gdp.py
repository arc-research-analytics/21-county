"""
Fetch BEA Real GDP by County (Table CAGDP9) via the BEA Regional API.

Source: https://apps.bea.gov/api/data
  - Dataset: Regional
  - Table: CAGDP9 (Real GDP by County and Metro Area, chained 2017 dollars)
  - LineCode 1: All-industry total
  - Returns all available years for all 21 ARC counties in one API call
  - Real GDP available from 2017 onward at county level

Output: data/processed/bea_gdp.csv
  county_name, year, gdp_thousands  (real GDP in thousands of chained 2017 dollars)
"""

import requests
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import COUNTIES, STATE_FIPS, BEA_API_KEY, DATA_PROCESSED

BEA_API      = "https://apps.bea.gov/api/data"
FIPS_TO_NAME = {STATE_FIPS + v: k for k, v in COUNTIES.items()}
ARC_GEOFIPS  = ",".join(FIPS_TO_NAME.keys())


def fetch_bea_gdp():
    print("Fetching BEA Real GDP by county (CAGDP9)...")

    params = {
        "UserID":      BEA_API_KEY,
        "method":      "GetData",
        "datasetname": "Regional",
        "TableName":   "CAGDP9",
        "LineCode":    "1",        # All-industry total real GDP
        "GeoFips":     ARC_GEOFIPS,
        "Year":        "ALL",
        "ResultFormat": "JSON",
    }

    resp = requests.get(BEA_API, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    if "BEAAPI" not in payload or "Results" not in payload["BEAAPI"]:
        raise RuntimeError(f"Unexpected BEA API response structure: {payload}")

    results = payload["BEAAPI"]["Results"]
    if "Data" not in results:
        notes = results.get("Notes", "")
        raise RuntimeError(f"No data returned from BEA API. Notes: {notes}")

    df = pd.DataFrame(results["Data"])

    # Filter to ARC counties only (BEA may return state-level rows too)
    df = df[df["GeoFips"].isin(FIPS_TO_NAME)].copy()
    df["county_name"] = df["GeoFips"].map(FIPS_TO_NAME)
    df["year"] = pd.to_numeric(df["TimePeriod"], errors="coerce")

    # DataValue contains commas and "(D)" for suppressed entries
    df["gdp_thousands"] = pd.to_numeric(
        df["DataValue"].str.replace(",", "", regex=False),
        errors="coerce"
    )

    out = (
        df[df["gdp_thousands"].notna()][["county_name", "year", "gdp_thousands"]]
        .sort_values(["county_name", "year"])
        .reset_index(drop=True)
    )

    years = sorted(out["year"].dropna().unique().astype(int))
    print(f"  Years available: {years[0]}–{years[-1]}")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "bea_gdp.csv"
    out.to_csv(out_path, index=False)
    print(f"  Saved {len(out)} rows → {out_path}")
    return out


if __name__ == "__main__":
    fetch_bea_gdp()
