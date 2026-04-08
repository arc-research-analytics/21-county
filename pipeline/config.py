"""
Shared constants for the ARC 21-County Dashboard data pipeline.
"""

import os
from datetime import datetime as _dt
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")
BEA_API_KEY    = os.getenv("BEA_API_KEY")

# ── Data vintage ───────────────────────────────────────────────────────────────
# Controls which ACS year, PEP vintage, and QWI end year are fetched.
# Override via:  python run_pipeline.py --vintage 2025
# or:            export ARC_VINTAGE=2025
#
# Default is current_year - 1 (the typical latest-available year across sources).
# fetch_acs.py probes the Census API and may fall back one additional year if the
# ACS 1-year release for this vintage hasn't been published yet (~September each year).
ACS_YEAR = int(os.getenv("ARC_VINTAGE", str(_dt.now().year - 1)))

# PEP fetches through this year using the matching vintage API
PEP_END_YEAR = ACS_YEAR

# QWI typically lags ~18 months; attempt the vintage year but fetcher will
# fall back to the previous year if the data isn't available yet.
QWI_END_YEAR = ACS_YEAR

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_OUTPUT    = ROOT / "data" / "output"

# Subdirectories for manual/downloaded files
RAW_FORECASTS = DATA_RAW / "forecasts"
RAW_GOSA      = DATA_RAW / "gosa"
RAW_GA_DPH    = DATA_RAW / "ga_dph"
RAW_HUD       = DATA_RAW / "hud"

# ── 21-County Region ───────────────────────────────────────────────────────────
# Keys are county names as they appear in source data; values are 3-digit FIPS
# Full FIPS = "13" + county_fips (Georgia state FIPS = 13)
COUNTIES = {
    "Barrow":   "013",
    "Bartow":   "015",
    "Carroll":  "045",
    "Cherokee": "057",
    "Clayton":  "063",
    "Cobb":     "067",
    "Coweta":   "077",
    "Dawson":   "085",
    "DeKalb":   "089",
    "Douglas":  "097",
    "Fayette":  "113",
    "Forsyth":  "117",
    "Fulton":   "121",
    "Gwinnett": "135",
    "Hall":     "139",
    "Henry":    "151",
    "Newton":   "217",
    "Paulding": "223",
    "Rockdale": "247",
    "Spalding": "255",
    "Walton":   "297",
}

# ── 11-County core region ──────────────────────────────────────────────────────
# The original ARC 10-county metro area + Forsyth, expanded in 2003.
# Used for 11-county aggregate views in the dashboard.
CORE_11_COUNTIES = {
    "Cherokee", "Clayton", "Cobb", "DeKalb", "Douglas",
    "Fayette", "Forsyth", "Fulton", "Gwinnett", "Henry", "Rockdale",
}

STATE_FIPS = "13"

# Full 5-digit FIPS list (used in Census API calls)
COUNTY_FIPS_LIST = [STATE_FIPS + v for v in COUNTIES.values()]

# ── QWI Industry Crosswalk ─────────────────────────────────────────────────────
# Maps BLS supersector labels (as shown in dashboard) → NAICS 2-digit sector codes.
# Used to query the QWI API (one request per NAICS code) then aggregate.
#
# QWI API "industry" parameter accepts the NAICS codes below as strings.
# After pulling each sector, rows are grouped by the supersector label.
#
# Source for groupings:
#   https://www.bls.gov/iag/tgs/iag_index_naics.htm
QWI_INDUSTRY_CROSSWALK = {
    "Natural resources and mining":       ["11", "21"],
    "Construction":                       ["23"],
    "Manufacturing":                      ["31-33"],        # QWI uses hyphenated combined code
    "Trade, transportation and utilities":["22", "42", "44-45", "48-49"],  # QWI combined codes
    "Information":                        ["51"],
    "Financial activities":               ["52", "53"],
    "Professional and business services": ["54", "55", "56"],
    "Education and health services":      ["61", "62"],
    "Leisure and hospitality":            ["71", "72"],
    "Other services":                     ["81"],
    "Public administration":              ["92"],
}

# Flat list of all NAICS codes we need to query (de-duped, sorted)
QWI_NAICS_CODES = sorted(
    {code for codes in QWI_INDUSTRY_CROSSWALK.values() for code in codes},
    key=lambda c: int(c.split("-")[0])  # sort by first number in code (handles "31-33" etc.)
)

# ── GOSA ───────────────────────────────────────────────────────────────────────
# The GOSA file covers all GA districts; filter to ARC counties using this list.
# GOSA district codes that correspond to the 21 ARC counties (3-digit GA codes).
# NOTE: Some counties have multiple districts (e.g., Fulton has Atlanta PS +
# Fulton County Schools); both are kept and displayed separately per the dashboard.
GOSA_FILE_PATTERN = "Graduation_Rate_*.csv"  # glob to find the latest downloaded file

# ── ACS variables ──────────────────────────────────────────────────────────────
# Organized by dashboard tab. Variable names are Census ACS 5-year table IDs.
# ACS_YEAR is defined at the top of this file (reads from ARC_VINTAGE env var).

ACS_VARIABLES = {
    # Housing
    "median_home_value":    "B25077_001E",
    "total_units":          "B25002_001E",
    "occupied_units":       "B25002_002E",
    "vacant_units":         "B25002_003E",
    "owner_occupied":       "B25003_002E",
    "renter_occupied":      "B25003_003E",
    # Household composition
    "hh_total":             "B11001_001E",
    "hh_married_family":    "B11001_003E",
    "hh_other_family":      "B11001_005E",  # single-parent family households
    "hh_nonfamily":         "B11001_008E",
    # Educational attainment (pop 25+)
    "edu_total_25plus":     "B15003_001E",
    "edu_less_hs":          "B15003_002E",  # No schooling through grade 11 (sum required)
    "edu_hs_grad":          "B15003_017E",  # Regular HS diploma
    "edu_ged":              "B15003_018E",
    "edu_some_college_1yr": "B15003_019E",
    "edu_some_college_1yr_plus": "B15003_020E",
    "edu_associates":       "B15003_021E",
    "edu_bachelors":        "B15003_022E",
    "edu_masters":          "B15003_023E",
    "edu_professional":     "B15003_024E",
    "edu_doctorate":        "B15003_025E",
    # Health insurance
    "uninsured_total":      "B27001_001E",  # civilian noninstitutionalized pop
    # Income & poverty
    "median_hh_income":     "B19013_001E",
    "poverty_total_pop":    "B17001_001E",
    "poverty_below":        "B17001_002E",
}

# ── Population Estimates Program ───────────────────────────────────────────────
# Annual county-level estimates; race/age characteristics
PEP_YEARS = list(range(2000, PEP_END_YEAR + 1))

# Race/ethnicity categories as returned by PEP CHARC endpoint
PEP_RACE_LABELS = {
    "1": "White",
    "2": "Black",
    "3": "Other",   # AIAN
    "4": "Asian",
    "5": "Other",   # NHPI
    "6": "Other",
    "9": "Other",
}

# Age group bins used in the dashboard (0–19, 20–34, 35–49, 50–64, 65+)
AGE_BINS = [0, 20, 35, 50, 65, 200]
AGE_LABELS = ["0 to 19", "20 to 34", "35 to 49", "50 to 64", "65+"]
