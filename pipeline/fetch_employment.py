"""
Fetch Quarterly Workforce Indicators (QWI) employment data.

Pulls per-county, per-year employment totals and employment by BLS supersector
(the 11 industry groups shown in the dashboard).

Strategy:
  - Query QWI API for each NAICS 2-digit sector code + the all-industry aggregate
  - Aggregate quarterly Beginning-of-Quarter Employment (Emp) to annual average
  - Map NAICS codes → dashboard supersector labels using QWI_INDUSTRY_CROSSWALK

Outputs:
  data/processed/employment_timeseries.csv  (county × year, total employment)
  data/processed/employment_by_industry.csv (county × industry, 2023 snapshot)
"""

import requests
import pandas as pd
import time
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    CENSUS_API_KEY, STATE_FIPS, COUNTIES,
    QWI_INDUSTRY_CROSSWALK, QWI_NAICS_CODES,
    DATA_PROCESSED,
)

QWI_BASE = "https://api.census.gov/data/timeseries/qwi/sa"  # sex-by-age endpoint

# Year range for the time series (QWI data begins ~2000 for most states).
# QWI typically lags ~18 months; if the requested end year has no data yet,
# _fetch_qwi_industry will fall back to QWI_END_YEAR - 1 automatically.
START_YEAR = 2000
# QWI lags ~18 months. Try the previous calendar year; the existing 204 fallback
# in _fetch_qwi_industry() will drop back one more year if needed.
END_YEAR   = date.today().year - 1

ARC_COUNTY_FIPS = set(COUNTIES.values())  # 3-digit codes

# Reverse map: NAICS code → supersector label
NAICS_TO_SUPERSECTOR = {
    code: label
    for label, codes in QWI_INDUSTRY_CROSSWALK.items()
    for code in codes
}


def _qwi_url(industry: str, start: int, end: int, ind_level: str = "S") -> str:
    """
    Build the full QWI API URL.

    The Census timeseries API requires the time range to use literal '+' as
    spaces (e.g. 'from+2000-Q1+to+2023-Q4'). The requests library encodes '+'
    to '%2B' when passed via params=, which breaks the API. Solution: embed
    the time parameter directly in the URL string and pass the rest via params.
    """
    time_str = f"from+{start}-Q1+to+{end}-Q4"
    ind_level_str = f"&ind_level={ind_level}" if ind_level != "S" else ""
    return (
        f"{QWI_BASE}?time={time_str}{ind_level_str}"
        f"&get=Emp"
        f"&for=county:*"
        f"&in=state:{STATE_FIPS}"
        f"&industry={industry}"
        f"&ownercode=A05"
        f"&sex=0"
        f"&agegrp=A00"
        f"&race=A0"
        f"&ethnicity=A0"
        f"&key={CENSUS_API_KEY}"
    )


def _fetch_qwi_industry(industry: str, ind_level: str = "S") -> pd.DataFrame:
    """
    Fetch QWI data for a single NAICS code, all years, all ARC counties.
    If END_YEAR data isn't available yet (204 or empty), retries with END_YEAR-1.
    """
    url = _qwi_url(industry, START_YEAR, END_YEAR, ind_level=ind_level)
    resp = requests.get(url, timeout=300)

    # QWI returns 204 (no content) when the requested time range has no data yet.
    if resp.status_code == 204 and END_YEAR > START_YEAR:
        print(f"    QWI {END_YEAR} not available for NAICS {industry}, trying {END_YEAR-1}...")
        url = _qwi_url(industry, START_YEAR, END_YEAR - 1, ind_level=ind_level)
        resp = requests.get(url, timeout=300)

    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])

    # Filter to ARC counties
    df = df[df["county"].isin(ARC_COUNTY_FIPS)].copy()
    df["county_fips"] = STATE_FIPS + df["county"]
    df["Emp"] = pd.to_numeric(df["Emp"], errors="coerce")
    df["industry"] = industry

    # Parse year and quarter from "time" column (format: "YYYY-QN")
    df["year"]    = df["time"].str[:4].astype(int)
    df["quarter"] = df["time"].str[6].astype(int)

    return df[["county_fips", "county", "year", "quarter", "industry", "Emp"]]


def fetch_employment():
    print("Fetching QWI employment data...")

    # ── Total employment: industry "00" + ind_level="A" = all industries ────
    print(f"  Fetching all-industry totals ({START_YEAR}–{END_YEAR})...")
    df_total = _fetch_qwi_industry("00", ind_level="A")

    ts = (
        df_total
        .groupby(["county_fips", "year"])["Emp"]
        .mean()                    # average of 4 quarters = annual average
        .round(0)
        .astype("Int64")           # nullable integer
        .reset_index()
        .rename(columns={"Emp": "employment"})
    )

    # Add county names
    fips_to_name = {STATE_FIPS + v: k for k, v in COUNTIES.items()}
    ts["county_name"] = ts["county_fips"].map(fips_to_name)

    ts = ts[["county_fips", "county_name", "year", "employment"]].sort_values(
        ["county_fips", "year"]
    )

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    ts_path = DATA_PROCESSED / "employment_timeseries.csv"
    ts.to_csv(ts_path, index=False)
    print(f"  Saved {len(ts)} rows → {ts_path}")

    # ── Industry breakdown: fetch each NAICS 2-digit code ────────────────────
    print(f"  Fetching {len(QWI_NAICS_CODES)} NAICS sector codes for industry breakdown...")
    industry_dfs = []
    for i, naics in enumerate(QWI_NAICS_CODES, 1):
        print(f"    [{i}/{len(QWI_NAICS_CODES)}] NAICS {naics}...")
        try:
            df_ind = _fetch_qwi_industry(naics)
            industry_dfs.append(df_ind)
        except Exception as e:
            print(f"    WARNING: Failed for NAICS {naics}: {e}")
        time.sleep(0.3)  # gentle rate limiting

    all_industries = pd.concat(industry_dfs, ignore_index=True)

    # Map NAICS → supersector label
    all_industries["supersector"] = all_industries["industry"].map(NAICS_TO_SUPERSECTOR)

    # Annual average per county × NAICS, then sum by supersector
    annual_by_naics = (
        all_industries
        .groupby(["county_fips", "year", "supersector"])["Emp"]
        .mean()   # average quarters within each NAICS
        .reset_index()
    )
    annual_by_supersector = (
        annual_by_naics
        .groupby(["county_fips", "year", "supersector"])["Emp"]
        .sum()   # sum NAICS codes within each supersector
        .round(0)
        .reset_index()
        .rename(columns={"Emp": "employment"})
    )

    annual_by_supersector["county_name"] = annual_by_supersector["county_fips"].map(fips_to_name)

    # Pivot to wide format: one column per supersector
    industry_wide = annual_by_supersector.pivot_table(
        index=["county_fips", "county_name", "year"],
        columns="supersector",
        values="employment",
        aggfunc="sum"
    ).reset_index()
    industry_wide.columns.name = None

    # Compute supersector shares within each county-year
    supersector_cols = list(QWI_INDUSTRY_CROSSWALK.keys())
    present_cols = [c for c in supersector_cols if c in industry_wide.columns]
    row_total = industry_wide[present_cols].sum(axis=1)
    for col in present_cols:
        industry_wide[f"{col}_pct"] = (industry_wide[col] / row_total).round(4)

    ind_path = DATA_PROCESSED / "employment_by_industry.csv"
    industry_wide.to_csv(ind_path, index=False)
    print(f"  Saved {len(industry_wide)} rows → {ind_path}")

    return ts, industry_wide


if __name__ == "__main__":
    fetch_employment()
