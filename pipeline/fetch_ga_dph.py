"""
Parse manually downloaded GA DPH OASIS health indicator files.

Expected files in data/raw/ga_dph/:
  low_birthweight_[YEAR].csv     — low birthweight births (< 5 lb 8 oz)
  teen_pregnancy_[YEAR].csv      — birth rate, mothers ages 15–19
  hospital_discharges_[YEAR].csv — discharge rates per 100K by condition

See data/raw/ga_dph/README.md for download instructions.

Output: data/processed/health_indicators.csv
  county_name, year,
  low_birthweight_pct, teen_preg_rate,
  discharge_cancer, discharge_cardiovascular, discharge_endocrine,
  discharge_external, discharge_infectious, discharge_mental, discharge_respiratory
"""

import pandas as pd
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import COUNTIES, DATA_RAW, DATA_PROCESSED

GA_DPH_DIR = DATA_RAW / "ga_dph"
ARC_COUNTY_NAMES = set(COUNTIES.keys())

# Map OASIS condition labels (flexible match) to output column names
DISCHARGE_LABEL_MAP = {
    r"cancer|neoplasm":                             "discharge_cancer",
    r"cardiovascular|circulatory":                  "discharge_cardiovascular",
    r"endocrine|nutritional|metabolic":             "discharge_endocrine",
    r"external":                                    "discharge_external",
    r"infectious|parasitic":                        "discharge_infectious",
    r"mental|behavioral":                           "discharge_mental",
    r"respiratory":                                 "discharge_respiratory",
}


def _extract_year_from_filename(path: Path) -> int | None:
    m = re.search(r"(\d{4})", path.name)
    return int(m.group(1)) if m else None


def _normalize_county(name: str) -> str | None:
    """Strip 'County' suffix and check if it's an ARC county."""
    clean = re.sub(r"\s*county\s*", "", name, flags=re.IGNORECASE).strip()
    if clean in ARC_COUNTY_NAMES:
        return clean
    # Try case-insensitive match
    for c in ARC_COUNTY_NAMES:
        if c.lower() == clean.lower():
            return c
    return None


def _find_county_col(df: pd.DataFrame) -> str | None:
    """Find which column contains county names."""
    for col in df.columns:
        if re.search(r"county|jurisdiction|area|geography", col, re.IGNORECASE):
            return col
    # Fall back: first string column
    for col in df.columns:
        if df[col].dtype == object:
            return col
    return None


def _find_value_col(df: pd.DataFrame, exclude: list[str]) -> str | None:
    """Find the main numeric value column (rate or percent)."""
    for col in df.columns:
        if col in exclude:
            continue
        if re.search(r"rate|percent|pct|value", col, re.IGNORECASE):
            return col
    # Fall back: first numeric column not in exclude list
    for col in df.columns:
        if col not in exclude and pd.api.types.is_numeric_dtype(df[col]):
            return col
    return None


def _load_indicator_file(path: Path) -> pd.DataFrame:
    """
    Load an OASIS-exported CSV. Returns df with columns:
      county_name (str), value (float)
    """
    df = pd.read_csv(path, skiprows=0)
    # OASIS files sometimes have metadata rows at top — drop rows with all nulls
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    county_col = _find_county_col(df)
    if county_col is None:
        raise ValueError(f"Cannot find county column in {path.name}")

    value_col = _find_value_col(df, exclude=[county_col])
    if value_col is None:
        raise ValueError(f"Cannot find value column in {path.name}")

    df["county_name"] = df[county_col].astype(str).apply(_normalize_county)
    df["value"] = pd.to_numeric(df[value_col], errors="coerce")
    df = df[df["county_name"].notna() & df["value"].notna()]
    return df[["county_name", "value"]]


def _load_discharge_file(path: Path) -> pd.DataFrame:
    """
    Load hospital discharge file. Expected to have a 'condition' or
    category column plus a rate column, one row per county × condition.
    Returns df: county_name, condition_col, value
    """
    df = pd.read_csv(path)
    df.dropna(how="all", inplace=True)

    county_col = _find_county_col(df)
    # Find condition label column
    condition_col = None
    for col in df.columns:
        if re.search(r"condition|diagnosis|cause|category", col, re.IGNORECASE):
            condition_col = col
            break
    value_col = _find_value_col(df, exclude=[county_col, condition_col] if condition_col else [county_col])

    df["county_name"] = df[county_col].astype(str).apply(_normalize_county)
    df["value"] = pd.to_numeric(df[value_col], errors="coerce")
    df = df[df["county_name"].notna() & df["value"].notna()]

    if condition_col:
        df["condition"] = df[condition_col].astype(str)
        return df[["county_name", "condition", "value"]]
    else:
        # Single-condition file — caller handles the label
        return df[["county_name", "value"]]


def fetch_ga_dph():
    print("Processing GA DPH health indicators...")

    # Check for required files
    lbw_files   = sorted(GA_DPH_DIR.glob("low_birthweight_*.csv"), reverse=True)
    teen_files  = sorted(GA_DPH_DIR.glob("teen_pregnancy_*.csv"),  reverse=True)
    disch_files = sorted(GA_DPH_DIR.glob("hospital_discharges_*.csv"), reverse=True)

    if not any([lbw_files, teen_files, disch_files]):
        print(
            "  WARNING: No GA DPH files found in data/raw/ga_dph/\n"
            "  Health tab data will be incomplete. See data/raw/ga_dph/README.md."
        )
        return pd.DataFrame()

    all_counties = pd.DataFrame({"county_name": sorted(ARC_COUNTY_NAMES)})
    result = all_counties.copy()

    # ── Low birthweight ───────────────────────────────────────────────────────
    if lbw_files:
        print(f"  Loading {lbw_files[0].name}...")
        lbw = _load_indicator_file(lbw_files[0])
        lbw = lbw.rename(columns={"value": "low_birthweight_pct"})
        result = result.merge(lbw, on="county_name", how="left")
    else:
        print("  WARNING: No low_birthweight file found.")
        result["low_birthweight_pct"] = None

    # ── Teen pregnancy ────────────────────────────────────────────────────────
    if teen_files:
        print(f"  Loading {teen_files[0].name}...")
        teen = _load_indicator_file(teen_files[0])
        teen = teen.rename(columns={"value": "teen_preg_rate"})
        result = result.merge(teen, on="county_name", how="left")
    else:
        print("  WARNING: No teen_pregnancy file found.")
        result["teen_preg_rate"] = None

    # ── Hospital discharges ───────────────────────────────────────────────────
    discharge_cols = {v: None for v in DISCHARGE_LABEL_MAP.values()}

    if disch_files:
        print(f"  Loading {disch_files[0].name}...")
        try:
            disch = _load_discharge_file(disch_files[0])
            if "condition" in disch.columns:
                # Pivot: one row per county, one column per condition
                for pattern, col_name in DISCHARGE_LABEL_MAP.items():
                    mask = disch["condition"].str.contains(pattern, case=False, na=False)
                    sub = disch[mask][["county_name", "value"]].rename(columns={"value": col_name})
                    result = result.merge(sub, on="county_name", how="left")
            else:
                print("  WARNING: Discharge file has no condition column — cannot parse conditions.")
        except Exception as e:
            print(f"  WARNING: Could not parse discharge file: {e}")

    for col in discharge_cols:
        if col not in result.columns:
            result[col] = None

    # ── Add year ──────────────────────────────────────────────────────────────
    # Use year from first available file
    year = None
    for f in [*lbw_files, *teen_files, *disch_files]:
        year = _extract_year_from_filename(f)
        if year:
            break
    result["year"] = year

    col_order = [
        "county_name", "year",
        "low_birthweight_pct", "teen_preg_rate",
        "discharge_cancer", "discharge_cardiovascular", "discharge_endocrine",
        "discharge_external", "discharge_infectious", "discharge_mental",
        "discharge_respiratory",
    ]
    result = result[[c for c in col_order if c in result.columns]]

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "health_indicators.csv"
    result.to_csv(out_path, index=False)
    print(f"  Saved {len(result)} counties → {out_path}")
    return result


if __name__ == "__main__":
    fetch_ga_dph()
