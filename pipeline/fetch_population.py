"""
Fetch Census Population Estimates Program (PEP) data.

Pulls:
  1. Total population 2000–present (annual, per county) — time series

Sources:
  - 2020–present: Census PEP charv API endpoint, latest available vintage
                  (tries PEP_END_YEAR first, walks back up to 4 years on 404).
                  Falls back to direct CSV file download from census.gov if all
                  charv vintages return 404 (API often lags behind file releases).
  - 2010–2019:    Census PEP vintage 2019, pep/population API
  - 2000–2009:    Census intercensal estimates (downloaded CSV)

Note: race/ethnicity and age breakdowns are fetched from ACS in fetch_acs.py,
not from PEP. The charv endpoint is queried with AGE=0000 & SEX=0 for total
population only.

Outputs:
  data/processed/population_timeseries.csv  (county × year, total population)
"""

import io
import requests
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    CENSUS_API_KEY, STATE_FIPS, COUNTIES,
    AGE_BINS, AGE_LABELS, DATA_PROCESSED, DATA_RAW, PEP_END_YEAR
)

ARC_COUNTY_FIPS = set(COUNTIES.values())  # 3-digit codes

# Intercensal 2000-2009 file (downloaded from Census)
INTERCENSAL_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/"
    "2000-2010/intercensal/county/co-est00int-alldata-13.csv"  # Georgia-specific file
)
INTERCENSAL_RAW = DATA_RAW / "census" / "co-est00int-alldata-13.csv"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _filter_arc(df: pd.DataFrame, county_col="county") -> pd.DataFrame:
    return df[df[county_col].isin(ARC_COUNTY_FIPS)].copy()


def _county_name(series: pd.Series) -> pd.Series:
    return series.str.replace(" County, Georgia", "", regex=False).str.strip()


def _fetch_pop_2020_from_file(vintage: int) -> pd.DataFrame | None:
    """
    Fallback: download the county-totals CSV directly from census.gov.
    Census publishes bulk files before the charv API endpoint goes live.
    File is cached in data/raw/census/ after first download.
    Returns None if the file doesn't exist for this vintage.
    """
    filename = f"co-est{vintage}-alldata.csv"
    cache_path = DATA_RAW / "census" / filename
    url = (
        f"https://www2.census.gov/programs-surveys/popest/datasets/"
        f"2020-{vintage}/counties/totals/{filename}"
    )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not cache_path.exists():
        print(f"    Downloading county totals file for vintage {vintage}...")
        r = requests.get(url, timeout=120)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        cache_path.write_bytes(r.content)

    df = pd.read_csv(cache_path, encoding="latin-1")

    # Filter to Georgia ARC counties
    df = df[(df["STATE"] == int(STATE_FIPS)) &
            (df["COUNTY"].astype(str).str.zfill(3).isin(ARC_COUNTY_FIPS))].copy()

    df["county_fips"] = STATE_FIPS + df["COUNTY"].astype(str).str.zfill(3)
    df["county_name"] = df["CTYNAME"].str.replace(" County", "", regex=False).str.strip()

    # Wide-format: POPESTIMATE2020, POPESTIMATE2021, … POPESTIMATE{vintage}
    pop_cols = [c for c in df.columns if c.startswith("POPESTIMATE") and c[11:].isdigit()]
    if not pop_cols:
        return None

    records = []
    for _, row in df.iterrows():
        for col in pop_cols:
            records.append({
                "county_fips": row["county_fips"],
                "county_name":  row["county_name"],
                "year":         int(col[11:]),
                "population":   row[col],
            })

    return pd.DataFrame(records)[["county_fips", "county_name", "year", "population"]]


# ── Total population time series ───────────────────────────────────────────────

def fetch_pop_2020_current() -> pd.DataFrame:
    """
    Returns long-format df: county_fips, county_name, year, population.

    Strategy:
    1. Try charv API (PEP_END_YEAR vintage, walking back up to 4 years on 404).
    2. If all charv vintages return 404, fall back to direct CSV download from
       census.gov (Census publishes bulk files before API endpoints go live).
    """
    params = {
        "get": "NAME,POP,YEAR",
        "for": "county:*",
        "in": f"state:{STATE_FIPS}",
        "SEX": "0",
        "AGE": "0000",
        "key": CENSUS_API_KEY,
    }
    resp = None
    found_vintage = None
    for vintage in range(PEP_END_YEAR, PEP_END_YEAR - 5, -1):
        print(f"  Fetching PEP 2020–{vintage} (vintage {vintage}) via charv API...")
        url = f"https://api.census.gov/data/{vintage}/pep/charv"
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 404:
            print(f"    charv vintage {vintage} not available, trying {vintage - 1}...")
            continue
        r.raise_for_status()
        resp = r
        found_vintage = vintage
        break

    if resp is not None:
        if found_vintage != PEP_END_YEAR:
            print(f"  charv API only has through vintage {found_vintage}; "
                  f"checking census.gov files for newer vintages...")
            # charv is behind — try direct file download for more recent vintages
            for vintage in range(PEP_END_YEAR, found_vintage, -1):
                file_df = _fetch_pop_2020_from_file(vintage)
                if file_df is not None:
                    print(f"  Using county-totals file for vintage {vintage} "
                          f"(more recent than charv API).")
                    return file_df
            print(f"  No newer file found; using charv vintage {found_vintage}.")

        data = resp.json()
        df = pd.DataFrame(data[1:], columns=data[0])
        df = _filter_arc(df)

        df["county_fips"] = STATE_FIPS + df["county"]
        df["county_name"] = _county_name(df["NAME"])
        df["year"] = pd.to_numeric(df["YEAR"], errors="coerce").astype(int)
        df["population"] = pd.to_numeric(df["POP"], errors="coerce")

        # 2020 has two rows (April 1 census + July 1 estimate); keep the max (July 1)
        df = (
            df.groupby(["county_fips", "county_name", "year"])["population"]
            .max()
            .reset_index()
        )
        return df[["county_fips", "county_name", "year", "population"]]

    # ── All charv vintages 404 — fall back to direct file download ────────────
    print(f"  charv API returned 404 for all vintages {PEP_END_YEAR}–{PEP_END_YEAR - 4}.")
    print(f"  Falling back to direct census.gov file download...")
    for vintage in range(PEP_END_YEAR, PEP_END_YEAR - 5, -1):
        file_df = _fetch_pop_2020_from_file(vintage)
        if file_df is not None:
            print(f"  Using county-totals file for vintage {vintage}.")
            return file_df

    raise RuntimeError(
        f"PEP data not available via charv API or direct file download "
        f"for vintages {PEP_END_YEAR} through {PEP_END_YEAR - 4}."
    )


def fetch_pop_2010_2019() -> pd.DataFrame:
    """Returns long-format df: county_fips, county_name, year, population."""
    print("  Fetching PEP 2010–2019...")
    url = "https://api.census.gov/data/2019/pep/population"
    # DATE_CODE: 2=4/1/2010 (census), 3=7/1/2010 ... 12=7/1/2019
    # We want July 1 estimates: DATE_CODE 3–12 → years 2010–2019
    date_codes = list(range(3, 13))  # 3..12
    params = {
        "get": "NAME,POP",  # DATE_CODE returned automatically as filter var; don't include it or it duplicates
        "for": "county:*",
        "in": f"state:{STATE_FIPS}",
        "DATE_CODE": ",".join(str(d) for d in date_codes),
        "key": CENSUS_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df = _filter_arc(df)

    df["county_fips"] = STATE_FIPS + df["county"]
    df["county_name"] = _county_name(df["NAME"])
    df["population"] = pd.to_numeric(df["POP"], errors="coerce")
    # DATE_CODE 3 → 2010, 4 → 2011, ..., 12 → 2019
    df["year"] = pd.to_numeric(df["DATE_CODE"], errors="coerce") + 2007

    return df[["county_fips", "county_name", "year", "population"]]


def fetch_pop_2000_2009() -> pd.DataFrame:
    """
    Download intercensal estimates (2000–2009) from Census.gov.
    File is cached in data/raw/census/ after first download.
    Returns long-format df: county_fips, county_name, year, population.
    """
    print("  Fetching PEP 2000–2009 (intercensal)...")
    INTERCENSAL_RAW.parent.mkdir(parents=True, exist_ok=True)

    if not INTERCENSAL_RAW.exists():
        print(f"    Downloading intercensal file...")
        resp = requests.get(INTERCENSAL_URL, timeout=120)
        resp.raise_for_status()
        INTERCENSAL_RAW.write_bytes(resp.content)

    df = pd.read_csv(INTERCENSAL_RAW, encoding="latin-1")

    # File is long-format: one row per county × YEAR × AGEGRP
    # AGEGRP 99 = total population (all ages); AGEGRP 0 is a sub-group, NOT the total
    # YEAR codes: 1=4/1/2000, 2=7/1/2000, 3=7/1/2001, ..., 11=7/1/2009, 12=4/1/2010
    # We want July 1 estimates for 2000–2009 → YEAR 2–11
    df = df[(df["AGEGRP"] == 99) & (df["YEAR"].between(2, 11))].copy()

    # Filter to ARC counties
    df = df[df["COUNTY"].astype(str).str.zfill(3).isin(ARC_COUNTY_FIPS)].copy()
    df["county_fips"] = "13" + df["COUNTY"].astype(str).str.zfill(3)
    df["county_name"] = df["CTYNAME"].str.replace(" County", "", regex=False).str.strip()

    # Map YEAR code → calendar year: YEAR 2 → 2000, YEAR 3 → 2001, …, YEAR 11 → 2009
    df["year"] = df["YEAR"] + 1998
    df["population"] = pd.to_numeric(df["TOT_POP"], errors="coerce")

    return df[["county_fips", "county_name", "year", "population"]].reset_index(drop=True)


# ── Main ────────────────────────────────────────────────────────────────────────
# Note: race/ethnicity and age profile are fetched from ACS (B03002 + B01001)
# in fetch_acs.py, not from PEP. The 2023 PEP charv endpoint does not expose
# race/age breakdown variables.

def fetch_population():
    print("Fetching Population Estimates Program (PEP) data...")

    # Time series only: stack all three vintage periods
    dfs_ts = [
        fetch_pop_2000_2009(),
        fetch_pop_2010_2019(),
        fetch_pop_2020_current(),
    ]
    ts = (
        pd.concat(dfs_ts, ignore_index=True)
        .sort_values(["county_fips", "year"])
        .reset_index(drop=True)
    )

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    ts_path = DATA_PROCESSED / "population_timeseries.csv"
    ts.to_csv(ts_path, index=False)
    print(f"  Saved {len(ts)} rows → {ts_path}")

    return ts


if __name__ == "__main__":
    fetch_population()
