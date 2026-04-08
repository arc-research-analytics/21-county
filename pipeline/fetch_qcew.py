"""
Fetch BLS Quarterly Census of Employment and Wages (QCEW) annual data.

Source: https://www.bls.gov/cew/data/files/{year}/csv/{year}_annual_singlefile.zip
  - One ZIP per year containing a single CSV with all US counties and industries
  - Streamed in chunks and filtered to ARC counties to keep memory footprint low
  - ZIPs are cached in data/raw/qcew/ so subsequent runs don't re-download

Fetches a 10-year rolling window ending at the latest available year
(auto-discovered via HEAD request; independent of ARC_VINTAGE).

agglvl_code key:
  70 = county total (all ownerships, all industries) → wages + establishment counts
  72 = county by supersector (all ownerships)        → wages by industry

Outputs:
  data/processed/qcew_wages.csv
    county_name, year, avg_annual_pay, annual_avg_estabs

  data/processed/qcew_wages_by_industry.csv
    county_name, year, supersector, avg_annual_pay
"""

import io
import zipfile
import requests
import pandas as pd
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import COUNTIES, STATE_FIPS, DATA_RAW, DATA_PROCESSED

QCEW_BASE  = "https://data.bls.gov/cew/data/files"
QCEW_CACHE = DATA_RAW / "qcew"
SERIES_YEARS = 10

ARC_FIPS_5   = {STATE_FIPS + v for v in COUNTIES.values()}
FIPS_TO_NAME = {STATE_FIPS + v: k for k, v in COUNTIES.items()}

# QCEW supersector codes → dashboard labels (matches QWI_INDUSTRY_CROSSWALK keys)
# agglvl 73, own_code 5 (private sector) — public administration (1028) is govt-only
# and does not appear in private-sector data; 1029 is the private "unclassified" bucket.
QCEW_SUPERSECTOR_MAP = {
    "1011": "Natural resources and mining",
    "1012": "Construction",
    "1013": "Manufacturing",
    "1021": "Trade, transportation and utilities",
    "1022": "Information",
    "1023": "Financial activities",
    "1024": "Professional and business services",
    "1025": "Education and health services",
    "1026": "Leisure and hospitality",
    "1027": "Other services",
    "1028": "Public administration",
    "1029": "Other services",   # private-sector unclassified; grouped with Other services
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _discover_end_year() -> int:
    """
    Find the latest year for which the QCEW annual singlefile ZIP is published.
    Checks the local cache first, then sends a lightweight HEAD request to BLS.
    QCEW annual files typically publish 3–6 months after year-end.
    """
    for candidate in range(date.today().year - 1, date.today().year - 4, -1):
        if (QCEW_CACHE / f"{candidate}_annual_singlefile.zip").exists():
            return candidate
        url = f"{QCEW_BASE}/{candidate}/csv/{candidate}_annual_singlefile.zip"
        try:
            resp = requests.head(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return candidate
        except requests.RequestException:
            continue
    raise RuntimeError(
        "Could not determine latest available QCEW year. Check data.bls.gov."
    )


def _download_year(year: int) -> Path:
    """Download and cache the annual singlefile ZIP for a given year."""
    cache_path = QCEW_CACHE / f"{year}_annual_singlefile.zip"
    if cache_path.exists():
        print(f"    {year}: using cache")
        return cache_path
    url = f"{QCEW_BASE}/{year}/csv/{year}_annual_singlefile.zip"
    print(f"    {year}: downloading from BLS...")
    resp = requests.get(url, headers=HEADERS, timeout=300)
    resp.raise_for_status()
    QCEW_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    return cache_path


def _read_arc_rows(zip_path: Path) -> pd.DataFrame:
    """
    Stream the singlefile ZIP in 50K-row chunks, returning only the ARC county
    rows for agglvl_code 70 (county total) and 72 (county by supersector).
    Suppressed rows (disclosure_code == 'N') are dropped.
    """
    str_cols = {"area_fips", "own_code", "industry_code", "agglvl_code",
                "size_code", "disclosure_code"}
    dtype = {c: str for c in str_cols}

    chunks = []
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
        with zf.open(csv_name) as f:
            for chunk in pd.read_csv(f, dtype=dtype, chunksize=50_000, low_memory=False):
                filtered = chunk[
                    chunk["area_fips"].isin(ARC_FIPS_5) &
                    chunk["agglvl_code"].isin(["70", "73"]) &
                    (chunk["disclosure_code"].isna() | (chunk["disclosure_code"] != "N"))
                ]
                if not filtered.empty:
                    chunks.append(filtered)

    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def fetch_qcew():
    print("Fetching QCEW wages and establishment data...")

    end_year   = _discover_end_year()
    start_year = end_year - SERIES_YEARS + 1
    print(f"  Range: {start_year}–{end_year} (latest available)")

    all_frames = []
    for year in range(start_year, end_year + 1):
        try:
            zip_path = _download_year(year)
            df_year  = _read_arc_rows(zip_path)
            if df_year.empty:
                print(f"    {year}: no ARC rows found — skipping.")
                continue
            df_year["year"] = year
            all_frames.append(df_year)
        except Exception as e:
            print(f"    WARNING: Could not load QCEW {year}: {e}")

    if not all_frames:
        raise RuntimeError("Could not load any QCEW annual data.")

    df = pd.concat(all_frames, ignore_index=True)
    df["county_name"] = df["area_fips"].map(FIPS_TO_NAME)

    # ── County totals (agglvl_code 70) ───────────────────────────────────────
    totals = df[df["agglvl_code"] == "70"].copy()
    totals["avg_annual_pay"]     = pd.to_numeric(totals["avg_annual_pay"],     errors="coerce")
    totals["annual_avg_estabs"]  = pd.to_numeric(totals["annual_avg_estabs"],  errors="coerce")
    totals["total_annual_wages"] = pd.to_numeric(totals["total_annual_wages"], errors="coerce")
    totals["annual_avg_emplvl"]  = pd.to_numeric(totals["annual_avg_emplvl"],  errors="coerce")

    ts = (
        totals[["county_name", "year", "total_annual_wages", "annual_avg_emplvl",
                "avg_annual_pay", "annual_avg_estabs"]]
        .sort_values(["county_name", "year"])
        .reset_index(drop=True)
    )

    # ── By supersector (agglvl_code 73, private sector own_code=5) ───────────
    # Private sector wages are the market-comparable figures; public administration
    # (1028) appears only under government ownership codes and is excluded here.
    sectors = df[(df["agglvl_code"] == "73") & (df["own_code"] == "5")].copy()
    sectors["supersector"]         = sectors["industry_code"].map(QCEW_SUPERSECTOR_MAP)
    sectors["avg_annual_pay"]      = pd.to_numeric(sectors["avg_annual_pay"],      errors="coerce")
    sectors["total_annual_wages"]  = pd.to_numeric(sectors["total_annual_wages"],  errors="coerce")
    sectors["annual_avg_emplvl"]   = pd.to_numeric(sectors["annual_avg_emplvl"],   errors="coerce")
    sectors = sectors[sectors["supersector"].notna() & sectors["avg_annual_pay"].notna()]

    # 1027 and 1029 both map to "Other services" — sum payroll + employment, then recompute avg pay
    sector_agg = (
        sectors
        .groupby(["county_name", "year", "supersector"])
        .agg(
            total_annual_wages=("total_annual_wages", "sum"),
            annual_avg_emplvl=("annual_avg_emplvl",   "sum"),
        )
        .reset_index()
    )
    sector_agg["avg_annual_pay"] = (
        sector_agg["total_annual_wages"] / sector_agg["annual_avg_emplvl"]
    ).round(0)
    sector_wages = (
        sector_agg
        .sort_values(["county_name", "year", "supersector"])
        .reset_index(drop=True)
    )

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    ts_path = DATA_PROCESSED / "qcew_wages.csv"
    ts.to_csv(ts_path, index=False)
    print(f"  Saved {len(ts)} rows → {ts_path}")

    sw_path = DATA_PROCESSED / "qcew_wages_by_industry.csv"
    sector_wages.to_csv(sw_path, index=False)
    print(f"  Saved {len(sector_wages)} rows → {sw_path}")

    return ts, sector_wages


if __name__ == "__main__":
    fetch_qcew()
