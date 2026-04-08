"""
Fetch and parse ARC Series forecast files directly from atlantaregional.org.

Discovery strategy:
  - Tries Series 18 URLs first, falls back to Series 17 on 404.
  - For the employment file, tries both the corrected and original (typo) spellings.
  - Sheet names and decade columns are detected dynamically so the script works
    regardless of whether the file is S17 (2020-2050) or S18 (unknown decades).
  - Downloads are cached locally so the pipeline can run offline.

Outputs:
  data/processed/forecast_totals.csv
    county_name, pop_{y0}, pop_{y1}, emp_{y0}, emp_{y1}, hh_{y0}, hh_{y1},
    pop_net_increase, pop_pct_increase, emp_net_increase, emp_pct_increase

  data/processed/forecast_by_sector.csv
    county_name, year, supersector, employment
"""

import io
import re
import requests
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import COUNTIES, QWI_INDUSTRY_CROSSWALK, DATA_RAW, DATA_PROCESSED

ARC_BASE      = "https://atlantaregional.org/wp-content/uploads"
FORECAST_CACHE = DATA_RAW / "forecasts"
ARC_COUNTY_NAMES = set(COUNTIES.keys())

# Candidate URLs for each file — tried in order, first success wins.
# Employment URL has a known typo ("empployment") in S17; try corrected spelling
# for S18, then the typo variant in case ARC preserved it.
POP_URLS = [
    f"{ARC_BASE}/s18-arc-forecasts.xlsx",
    f"{ARC_BASE}/s17-arc-forecasts.xlsx",
]
EMP_URLS = [
    f"{ARC_BASE}/s18-arc-employment-forecasts-bysector.xlsx",   # S18 (spelling corrected)
    f"{ARC_BASE}/s17-arc-empployment-forecasts-bysector.xlsx",  # S17 exact URL
]

# NAICS column prefix → NAICS code (columns named N{prefix}_{YY} in the XLSX)
COL_TO_NAICS = {
    "N11": "11", "N21": "21", "N22": "22", "N23": "23",
    "N313233": "31",
    "N42": "42", "N4445": "44", "N4849": "48",
    "N51": "51", "N52": "52", "N53": "53",
    "N54": "54", "N55": "55", "N56": "56",
    "N61": "61", "N62": "62",
    "N71": "71", "N72": "72",
    "N81": "81", "N92": "92",
}

NAICS_TO_SUPERSECTOR = {
    code: label
    for label, codes in QWI_INDUSTRY_CROSSWALK.items()
    for code in codes
}


# ── Download helpers ───────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _try_download(url: str) -> bytes | None:
    """Attempt GET on url; return raw bytes on 200, None otherwise."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 200:
            return resp.content
    except requests.RequestException:
        pass
    return None


def _fetch_first(urls: list[str], label: str) -> tuple[bytes, str]:
    """
    Try each URL in order; return (content, url) for the first that succeeds.
    Falls back to the local cache if all remote URLs fail.
    """
    for url in urls:
        filename = url.split("/")[-1]
        print(f"  Trying {filename}...")
        content = _try_download(url)
        if content is not None:
            print(f"  Downloaded: {filename}")
            # Cache locally
            FORECAST_CACHE.mkdir(parents=True, exist_ok=True)
            cache_path = FORECAST_CACHE / filename
            cache_path.write_bytes(content)
            return content, url

    # Remote failed — try local cache (most recently modified matching file)
    print(f"  Remote fetch failed for {label}, checking local cache...")
    candidates = sorted(FORECAST_CACHE.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    pop_candidates = [p for p in candidates if "forecast" in p.name and "sector" not in p.name and "emp" not in p.name]
    emp_candidates = [p for p in candidates if "emp" in p.name]
    pool = pop_candidates if label == "pop" else emp_candidates
    if pool:
        path = pool[0]
        print(f"  Using cached: {path.name}")
        return path.read_bytes(), str(path)

    raise RuntimeError(
        f"Could not fetch {label} forecast file from any URL and no local cache found.\n"
        f"Tried: {urls}"
    )


# ── Sheet / column detection ───────────────────────────────────────────────────

def _find_county_sheet(xl: pd.ExcelFile) -> str:
    """Find the sheet named S##_byCounty (e.g. S17_byCounty or S18_byCounty)."""
    for name in xl.sheet_names:
        if re.match(r"S\d+_byCounty", name):
            return name
    raise ValueError(f"No S##_byCounty sheet found. Available: {xl.sheet_names}")


def _find_emp_sheets(xl: pd.ExcelFile) -> dict[int, str]:
    """
    Find all employment-by-decade sheets (e.g. Emp2020_byTract2010).
    Returns {decade_year: sheet_name} sorted by year.
    """
    sheets = {}
    for name in xl.sheet_names:
        m = re.match(r"Emp(\d{4})_byTract", name)
        if m:
            sheets[int(m.group(1))] = name
    if not sheets:
        raise ValueError(f"No Emp####_byTract sheets found. Available: {xl.sheet_names}")
    return dict(sorted(sheets.items()))


def _detect_forecast_decades(df: pd.DataFrame) -> tuple[int, int]:
    """
    From the county totals sheet, detect the first and last forecast decades
    by looking for Population#### columns.
    """
    years = sorted(
        int(m.group(1))
        for col in df.columns
        if (m := re.match(r"Population(\d{4})", col))
    )
    if len(years) < 2:
        raise ValueError(f"Could not detect forecast decades from columns: {list(df.columns)}")
    return years[0], years[-1]


# ── Main fetch ─────────────────────────────────────────────────────────────────

def fetch_forecast():
    print("Fetching ARC forecast data...")

    # ── County-level totals ───────────────────────────────────────────────────
    pop_bytes, pop_url = _fetch_first(POP_URLS, "pop")
    series_label = re.search(r"s(\d+)-arc", pop_url.split("/")[-1]).group(0).upper().replace("-ARC", "")  # e.g. "S17" or "S18"

    print(f"  Reading {series_label} county totals sheet...")
    xl_pop = pd.ExcelFile(io.BytesIO(pop_bytes))
    county_sheet = _find_county_sheet(xl_pop)
    county_df = pd.read_excel(xl_pop, sheet_name=county_sheet)
    county_df.columns = county_df.columns.str.strip()
    county_df = county_df[county_df["County"].isin(ARC_COUNTY_NAMES)].copy()

    y0, y1 = _detect_forecast_decades(county_df)
    print(f"  Detected forecast period: {y0} – {y1}")

    totals = pd.DataFrame()
    totals["county_name"]      = county_df["County"].values
    totals[f"pop_{y0}"]        = county_df[f"Population{y0}"].values
    totals[f"pop_{y1}"]        = county_df[f"Population{y1}"].values
    totals[f"emp_{y0}"]        = county_df[f"Employment{y0}"].values
    totals[f"emp_{y1}"]        = county_df[f"Employment{y1}"].values
    totals[f"hh_{y0}"]         = county_df[f"Households{y0}"].values
    totals[f"hh_{y1}"]         = county_df[f"Households{y1}"].values

    totals["pop_net_increase"] = totals[f"pop_{y1}"] - totals[f"pop_{y0}"]
    totals["pop_pct_increase"] = ((totals["pop_net_increase"] / totals[f"pop_{y0}"]) * 100).round(1)
    totals["emp_net_increase"] = totals[f"emp_{y1}"] - totals[f"emp_{y0}"]
    totals["emp_pct_increase"] = ((totals["emp_net_increase"] / totals[f"emp_{y0}"]) * 100).round(1)

    totals = totals.sort_values("county_name").reset_index(drop=True)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    totals_path = DATA_PROCESSED / "forecast_totals.csv"
    totals.to_csv(totals_path, index=False)
    print(f"  Saved {len(totals)} counties → {totals_path}")

    # ── Employment by sector (tract → county aggregate) ───────────────────────
    print("  Fetching employment-by-sector file...")
    emp_bytes, _ = _fetch_first(EMP_URLS, "emp")
    xl_emp = pd.ExcelFile(io.BytesIO(emp_bytes))
    decade_sheets = _find_emp_sheets(xl_emp)
    print(f"  Found decade sheets: {list(decade_sheets.keys())}")

    sector_dfs = []
    for year, sheet in decade_sheets.items():
        df = pd.read_excel(xl_emp, sheet_name=sheet)
        df = df[df["County"].isin(ARC_COUNTY_NAMES)].copy()

        year_suffix = str(year)[2:]
        naics_cols = {
            col: COL_TO_NAICS[col.replace(f"_{year_suffix}", "")]
            for col in df.columns
            if col.endswith(f"_{year_suffix}") and col.replace(f"_{year_suffix}", "") in COL_TO_NAICS
        }

        county_agg = df.groupby("County")[list(naics_cols.keys())].sum().reset_index()
        melted = county_agg.melt(id_vars="County", var_name="naics_col", value_name="employment")
        melted["naics_code"]  = melted["naics_col"].map(naics_cols)
        melted["supersector"] = melted["naics_code"].map(NAICS_TO_SUPERSECTOR)
        melted = melted[melted["supersector"].notna()]

        sector_county = (
            melted
            .groupby(["County", "supersector"])["employment"]
            .sum()
            .reset_index()
            .rename(columns={"County": "county_name"})
        )
        sector_county["year"] = year
        sector_dfs.append(sector_county)

    sector_df = pd.concat(sector_dfs, ignore_index=True)
    sector_df = sector_df[["county_name", "year", "supersector", "employment"]] \
        .sort_values(["county_name", "year", "supersector"]).reset_index(drop=True)

    sector_path = DATA_PROCESSED / "forecast_by_sector.csv"
    sector_df.to_csv(sector_path, index=False)
    print(f"  Saved {len(sector_df)} rows → {sector_path}")

    return totals, sector_df


if __name__ == "__main__":
    fetch_forecast()
