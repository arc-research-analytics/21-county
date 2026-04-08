"""
Fetch ACS data for housing, education attainment, health insurance, and income.

Strategy: try ACS 1-year first (available for counties 65K+ pop); fall back to
ACS 5-year for any county that returns suppressed values.

Output: data/processed/acs_snapshot.csv  (one row per county)
"""

import requests
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import CENSUS_API_KEY, STATE_FIPS, COUNTIES, ACS_YEAR, DATA_PROCESSED

ACS_API_BASE = "https://api.census.gov/data"


def _discover_acs_year(start_year: int) -> int:
    """
    Find the latest year for which ACS 1-year data is actually published.
    ACS 1-year releases each September for the prior calendar year, so
    current_year - 1 may not be available if the pipeline runs before September.
    Walks back up to 2 years from start_year before raising.
    """
    for year in range(start_year, start_year - 3, -1):
        url = f"{ACS_API_BASE}/{year}/acs/acs1"
        try:
            r = requests.get(
                url,
                params={"get": "NAME", "for": f"state:{STATE_FIPS}", "key": CENSUS_API_KEY},
                timeout=15,
            )
            if r.status_code == 200:
                if year != start_year:
                    print(f"  ACS {start_year} not yet published — using {year} instead")
                return year
        except requests.RequestException:
            continue
    raise RuntimeError(
        f"No ACS 1-year data found for years {start_year} through {start_year - 2}. "
        "Check https://api.census.gov/data.html for available vintages."
    )

# ── Variable definitions ────────────────────────────────────────────────────────
# B15003: Educational Attainment for the Population 25 Years and Over
# Fetch total + HS-and-above codes; derive "less than HS" by subtraction
EDU_VARS = {
    "edu_total":        "B15003_001E",
    "edu_hs_diploma":   "B15003_017E",
    "edu_ged":          "B15003_018E",
    "edu_some_col_lt1": "B15003_019E",
    "edu_some_col_1p":  "B15003_020E",
    "edu_associates":   "B15003_021E",
    "edu_bachelors":    "B15003_022E",
    "edu_masters":      "B15003_023E",
    "edu_professional": "B15003_024E",
    "edu_doctorate":    "B15003_025E",
}

# B25002/B25003: Vacancy and Tenure
# B25077: Median Home Value
# B11001: Household Type
HOUSING_VARS = {
    "total_units":       "B25002_001E",
    "occupied_units":    "B25002_002E",
    "vacant_units":      "B25002_003E",
    "owner_occupied":    "B25003_002E",
    "renter_occupied":   "B25003_003E",
    "median_home_value": "B25077_001E",
    "hh_total":          "B11001_001E",
    "hh_married_family": "B11001_003E",
    "hh_other_family":   "B11001_005E",
    "hh_nonfamily":      "B11001_008E",
}

# B27001: Health Insurance Coverage Status (civilian noninstitutionalized pop)
# Uninsured = sum of all "no health insurance" cells across sex × age groups
# Each age group is a triplet: [group total, with insurance, no insurance]
# Male uninsured cells: 005, 008, 011, 014, 017, 020, 023, 026
# Female uninsured cells: 030, 033, 036, 039, 042, 045, 048, 051
# (Female section starts at 027=total, 028=age-group; no-insurance is the 3rd
#  element of each triplet, i.e. even-numbered cells starting at 030.)
HEALTH_VARS = {
    "pop_total":         "B27001_001E",
    "m_unins_u19":       "B27001_005E",
    "m_unins_19_25":     "B27001_008E",
    "m_unins_26_34":     "B27001_011E",
    "m_unins_35_44":     "B27001_014E",
    "m_unins_45_54":     "B27001_017E",
    "m_unins_55_64":     "B27001_020E",
    "m_unins_65_74":     "B27001_023E",
    "m_unins_75p":       "B27001_026E",
    "f_unins_u19":       "B27001_030E",
    "f_unins_19_25":     "B27001_033E",
    "f_unins_26_34":     "B27001_036E",
    "f_unins_35_44":     "B27001_039E",
    "f_unins_45_54":     "B27001_042E",
    "f_unins_55_64":     "B27001_045E",
    "f_unins_65_74":     "B27001_048E",
    "f_unins_75p":       "B27001_051E",
}

# B19013: Median Household Income
# B17001: Poverty Status in the Past 12 Months
INCOME_VARS = {
    "median_hh_income": "B19013_001E",
    "poverty_universe": "B17001_001E",
    "poverty_below":    "B17001_002E",
}

# B25075: Home Value Distribution (27 brackets, owner-occupied units with known value)
# Used to interpolate a regional median home value when aggregating counties.
# Top bracket ($1.5M+) is open-ended; frontend should treat upper bound as $2M by convention.
HOME_VALUE_DIST_VARS = {
    "homeval_total":      "B25075_001E",
    "homeval_lt10k":      "B25075_002E",
    "homeval_10k_15k":    "B25075_003E",
    "homeval_15k_20k":    "B25075_004E",
    "homeval_20k_25k":    "B25075_005E",
    "homeval_25k_30k":    "B25075_006E",
    "homeval_30k_35k":    "B25075_007E",
    "homeval_35k_40k":    "B25075_008E",
    "homeval_40k_45k":    "B25075_009E",
    "homeval_45k_50k":    "B25075_010E",
    "homeval_50k_60k":    "B25075_011E",
    "homeval_60k_70k":    "B25075_012E",
    "homeval_70k_80k":    "B25075_013E",
    "homeval_80k_90k":    "B25075_014E",
    "homeval_90k_100k":   "B25075_015E",
    "homeval_100k_125k":  "B25075_016E",
    "homeval_125k_150k":  "B25075_017E",
    "homeval_150k_175k":  "B25075_018E",
    "homeval_175k_200k":  "B25075_019E",
    "homeval_200k_250k":  "B25075_020E",
    "homeval_250k_300k":  "B25075_021E",
    "homeval_300k_400k":  "B25075_022E",
    "homeval_400k_500k":  "B25075_023E",
    "homeval_500k_750k":  "B25075_024E",
    "homeval_750k_1m":    "B25075_025E",
    "homeval_1m_1500k":   "B25075_026E",
    "homeval_1500k_plus": "B25075_027E",
}

# B19001: Household Income Distribution (16 brackets)
# Used to interpolate a true regional median when aggregating counties.
# Bracket lower bounds (dollars): 0,10k,15k,20k,25k,30k,35k,40k,45k,50k,60k,75k,100k,125k,150k,200k
# Top bracket ($200k+) is open-ended; frontend should treat upper bound as 250k by convention.
INCOME_DIST_VARS = {
    "hhinc_total":       "B19001_001E",  # total households in distribution
    "hhinc_lt10k":       "B19001_002E",  # < $10,000
    "hhinc_10k_15k":     "B19001_003E",  # $10,000 – $14,999
    "hhinc_15k_20k":     "B19001_004E",  # $15,000 – $19,999
    "hhinc_20k_25k":     "B19001_005E",  # $20,000 – $24,999
    "hhinc_25k_30k":     "B19001_006E",  # $25,000 – $29,999
    "hhinc_30k_35k":     "B19001_007E",  # $30,000 – $34,999
    "hhinc_35k_40k":     "B19001_008E",  # $35,000 – $39,999
    "hhinc_40k_45k":     "B19001_009E",  # $40,000 – $44,999
    "hhinc_45k_50k":     "B19001_010E",  # $45,000 – $49,999
    "hhinc_50k_60k":     "B19001_011E",  # $50,000 – $59,999
    "hhinc_60k_75k":     "B19001_012E",  # $60,000 – $74,999
    "hhinc_75k_100k":    "B19001_013E",  # $75,000 – $99,999
    "hhinc_100k_125k":   "B19001_014E",  # $100,000 – $124,999
    "hhinc_125k_150k":   "B19001_015E",  # $125,000 – $149,999
    "hhinc_150k_200k":   "B19001_016E",  # $150,000 – $199,999
    "hhinc_200k_plus":   "B19001_017E",  # $200,000 or more
}

# B03002: Hispanic or Latino Origin by Race
RACE_VARS = {
    "race_total":    "B03002_001E",
    "race_nh_white": "B03002_003E",
    "race_nh_black": "B03002_004E",
    "race_nh_asian": "B03002_006E",
    "race_hispanic": "B03002_012E",
}

# B01001: Sex by Age — fetch all cells needed to build 5 dashboard age groups
# Groups: 0–19, 20–34, 35–49, 50–64, 65+
AGE_VARS = {
    "pop_age_total": "B01001_001E",
    # Male 0–19
    "m_0_4": "B01001_003E", "m_5_9": "B01001_004E", "m_10_14": "B01001_005E",
    "m_15_17": "B01001_006E", "m_18_19": "B01001_007E",
    # Male 20–34
    "m_20": "B01001_008E", "m_21": "B01001_009E", "m_22_24": "B01001_010E",
    "m_25_29": "B01001_011E", "m_30_34": "B01001_012E",
    # Male 35–49
    "m_35_39": "B01001_013E", "m_40_44": "B01001_014E", "m_45_49": "B01001_015E",
    # Male 50–64
    "m_50_54": "B01001_016E", "m_55_59": "B01001_017E",
    "m_60_61": "B01001_018E", "m_62_64": "B01001_019E",
    # Male 65+
    "m_65_66": "B01001_020E", "m_67_69": "B01001_021E", "m_70_74": "B01001_022E",
    "m_75_79": "B01001_023E", "m_80_84": "B01001_024E", "m_85p_m": "B01001_025E",
    # Female 0–19
    "f_0_4": "B01001_027E", "f_5_9": "B01001_028E", "f_10_14": "B01001_029E",
    "f_15_17": "B01001_030E", "f_18_19": "B01001_031E",
    # Female 20–34
    "f_20": "B01001_032E", "f_21": "B01001_033E", "f_22_24": "B01001_034E",
    "f_25_29": "B01001_035E", "f_30_34": "B01001_036E",
    # Female 35–49
    "f_35_39": "B01001_037E", "f_40_44": "B01001_038E", "f_45_49": "B01001_039E",
    # Female 50–64
    "f_50_54": "B01001_040E", "f_55_59": "B01001_041E",
    "f_60_61": "B01001_042E", "f_62_64": "B01001_043E",
    # Female 65+
    "f_65_66": "B01001_044E", "f_67_69": "B01001_045E", "f_70_74": "B01001_046E",
    "f_75_79": "B01001_047E", "f_80_84": "B01001_048E", "f_85p_f": "B01001_049E",
}

ALL_VARS = {**EDU_VARS, **HOUSING_VARS, **HEALTH_VARS, **INCOME_VARS, **INCOME_DIST_VARS, **HOME_VALUE_DIST_VARS, **RACE_VARS, **AGE_VARS}
SUPPRESSED = -666666666  # Census sentinel for suppressed/unavailable data


def _call_acs(base_url: str, var_codes: list[str]) -> pd.DataFrame:
    """Single ACS API call. Returns raw DataFrame with all counties in GA."""
    params = {
        "get": "NAME," + ",".join(var_codes),
        "for": "county:*",
        "in": f"state:{STATE_FIPS}",
        "key": CENSUS_API_KEY,
    }
    resp = requests.get(base_url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return pd.DataFrame(data[1:], columns=data[0])


def fetch_acs_for_counties(base_url: str) -> pd.DataFrame:
    """
    Fetch all ACS variables for all GA counties. Chunk into batches of 45
    variables (ACS API limit is ~50) and merge on county/state.
    """
    var_codes = list(ALL_VARS.values())
    chunks = [var_codes[i:i+45] for i in range(0, len(var_codes), 45)]

    base_df = None
    for chunk in chunks:
        df_chunk = _call_acs(base_url, chunk)
        if base_df is None:
            base_df = df_chunk
        else:
            base_df = base_df.merge(df_chunk, on=["NAME", "state", "county"])

    # Defragment after repeated merges so subsequent column assignments are fast
    return base_df.copy()


def fetch_acs():
    print("Fetching ACS data...")

    # ── Discover the latest available ACS vintage ────────────────────────────
    acs_year = _discover_acs_year(ACS_YEAR)
    acs_1yr  = f"{ACS_API_BASE}/{acs_year}/acs/acs1"
    acs_5yr  = f"{ACS_API_BASE}/{acs_year}/acs/acs5"

    # ── Pull 1-year estimates ────────────────────────────────────────────────
    print(f"  Fetching ACS {acs_year} 1-year...")
    df_1yr = fetch_acs_for_counties(acs_1yr)

    # Filter to ARC counties
    arc_fips = set(COUNTIES.values())
    df_1yr = df_1yr[df_1yr["county"].isin(arc_fips)].copy()

    # Convert all Census value columns to numeric in one pass (avoids fragmentation)
    numeric_cols = list(ALL_VARS.values())
    df_1yr[numeric_cols] = df_1yr[numeric_cols].apply(pd.to_numeric, errors="coerce")

    # Identify counties needing 5-year fallback:
    #   (a) present in 1-year but with suppressed/null key values
    #   (b) entirely absent from 1-year results (e.g. Dawson, pop ~27K < 65K threshold)
    sentinel_mask = (
        (df_1yr["B19013_001E"] == SUPPRESSED) |
        (df_1yr["B19013_001E"].isna()) |
        (df_1yr["B25077_001E"] == SUPPRESSED) |
        (df_1yr["B25077_001E"].isna())
    )
    suppressed_counties = df_1yr.loc[sentinel_mask, "county"].tolist()
    missing_counties = list(arc_fips - set(df_1yr["county"]))  # not returned at all
    fallback_counties = list(set(suppressed_counties + missing_counties))

    if fallback_counties:
        print(f"  {len(fallback_counties)} counties need 5-year fallback "
              f"({len(missing_counties)} absent, {len(suppressed_counties)} suppressed)...")
        df_5yr = fetch_acs_for_counties(acs_5yr)
        df_5yr = df_5yr[df_5yr["county"].isin(fallback_counties)].copy()
        df_5yr[numeric_cols] = df_5yr[numeric_cols].apply(pd.to_numeric, errors="coerce")
        df_5yr = df_5yr.copy()  # defragment before adding new columns
        df_5yr["acs_vintage"] = "5yr"
        df_1yr = df_1yr[~sentinel_mask].copy()  # defragment before adding new columns
        df_1yr["acs_vintage"] = "1yr"
        df = pd.concat([df_1yr, df_5yr], ignore_index=True)
    else:
        df_1yr = df_1yr.copy()  # defragment before adding new columns
        df_1yr["acs_vintage"] = "1yr"
        df = df_1yr

    # ── Standardize identifiers ──────────────────────────────────────────────
    df["county_fips"] = STATE_FIPS + df["county"]
    df["county_name"] = (
        df["NAME"]
        .str.replace(" County, Georgia", "", regex=False)
        .str.strip()
    )

    # ── Rename columns from Census codes to friendly names ───────────────────
    code_to_name = {v: k for k, v in ALL_VARS.items()}
    df = df.rename(columns=code_to_name)

    # ── Derived education fields ─────────────────────────────────────────────
    hs_and_above = (
        df["edu_hs_diploma"] + df["edu_ged"] + df["edu_some_col_lt1"] +
        df["edu_some_col_1p"] + df["edu_associates"] + df["edu_bachelors"] +
        df["edu_masters"] + df["edu_professional"] + df["edu_doctorate"]
    )
    df["edu_less_than_hs"]     = df["edu_total"] - hs_and_above
    df["edu_hs_equiv"]         = df["edu_hs_diploma"] + df["edu_ged"]
    df["edu_some_col_assoc"]   = df["edu_some_col_lt1"] + df["edu_some_col_1p"] + df["edu_associates"]
    df["edu_bachelors_only"]   = df["edu_bachelors"]
    df["edu_grad_professional"] = df["edu_masters"] + df["edu_professional"] + df["edu_doctorate"]

    # ── Derived housing fields ───────────────────────────────────────────────
    df["vacancy_rate"] = (df["vacant_units"] / df["total_units"]).round(4)
    df["owner_pct"]    = (df["owner_occupied"] / (df["owner_occupied"] + df["renter_occupied"])).round(4)
    df["renter_pct"]   = 1 - df["owner_pct"]

    # Household composition shares
    df["hh_married_pct"]  = (df["hh_married_family"] / df["hh_total"]).round(4)
    df["hh_single_pct"]   = (df["hh_other_family"]   / df["hh_total"]).round(4)
    df["hh_nonfamily_pct"]= (df["hh_nonfamily"]       / df["hh_total"]).round(4)

    # ── Derived health insurance field ───────────────────────────────────────
    uninsured_cols = [c for c in df.columns if c.startswith(("m_unins_", "f_unins_"))]
    df["uninsured_count"] = df[uninsured_cols].sum(axis=1)
    df["uninsured_pct"]   = (df["uninsured_count"] / df["pop_total"]).round(4)

    # ── Derived income/poverty fields ────────────────────────────────────────
    df["poverty_rate"] = (df["poverty_below"] / df["poverty_universe"]).round(4)

    # ── Derived race/ethnicity shares ────────────────────────────────────────
    df["race_nh_other"] = (
        df["race_total"] - df["race_hispanic"] -
        df["race_nh_white"] - df["race_nh_black"] - df["race_nh_asian"]
    )
    for grp in ["hispanic", "nh_white", "nh_black", "nh_asian", "nh_other"]:
        df[f"race_{grp}_pct"] = (df[f"race_{grp}"] / df["race_total"]).round(4)

    # ── Derived age group shares (B01001) ─────────────────────────────────────
    df["age_0_19"] = (
        df["m_0_4"] + df["m_5_9"] + df["m_10_14"] + df["m_15_17"] + df["m_18_19"] +
        df["f_0_4"] + df["f_5_9"] + df["f_10_14"] + df["f_15_17"] + df["f_18_19"]
    )
    df["age_20_34"] = (
        df["m_20"] + df["m_21"] + df["m_22_24"] + df["m_25_29"] + df["m_30_34"] +
        df["f_20"] + df["f_21"] + df["f_22_24"] + df["f_25_29"] + df["f_30_34"]
    )
    df["age_35_49"] = (
        df["m_35_39"] + df["m_40_44"] + df["m_45_49"] +
        df["f_35_39"] + df["f_40_44"] + df["f_45_49"]
    )
    df["age_50_64"] = (
        df["m_50_54"] + df["m_55_59"] + df["m_60_61"] + df["m_62_64"] +
        df["f_50_54"] + df["f_55_59"] + df["f_60_61"] + df["f_62_64"]
    )
    df["age_65plus"] = (
        df["m_65_66"] + df["m_67_69"] + df["m_70_74"] + df["m_75_79"] + df["m_80_84"] + df["m_85p_m"] +
        df["f_65_66"] + df["f_67_69"] + df["f_70_74"] + df["f_75_79"] + df["f_80_84"] + df["f_85p_f"]
    )
    for grp in ["0_19", "20_34", "35_49", "50_64", "65plus"]:
        df[f"age_{grp}_pct"] = (df[f"age_{grp}"] / df["pop_age_total"]).round(4)

    # ── Final column selection ───────────────────────────────────────────────
    output_cols = [
        "county_fips", "county_name", "acs_vintage",
        # Housing snapshot
        "median_home_value",
        "total_units", "occupied_units", "vacant_units", "vacancy_rate",
        "owner_occupied", "renter_occupied", "owner_pct", "renter_pct",
        "hh_total", "hh_married_family", "hh_other_family", "hh_nonfamily",
        "hh_married_pct", "hh_single_pct", "hh_nonfamily_pct",
        # Home value distribution brackets (B25075) — sum across owner-occupied units then interpolate regional median
        # Top bracket ($1.5M+) is open-ended; use $2M as the conventional upper bound.
        "homeval_total",
        "homeval_lt10k", "homeval_10k_15k", "homeval_15k_20k", "homeval_20k_25k",
        "homeval_25k_30k", "homeval_30k_35k", "homeval_35k_40k", "homeval_40k_45k",
        "homeval_45k_50k", "homeval_50k_60k", "homeval_60k_70k", "homeval_70k_80k",
        "homeval_80k_90k", "homeval_90k_100k",
        "homeval_100k_125k", "homeval_125k_150k", "homeval_150k_175k", "homeval_175k_200k",
        "homeval_200k_250k", "homeval_250k_300k", "homeval_300k_400k", "homeval_400k_500k",
        "homeval_500k_750k", "homeval_750k_1m", "homeval_1m_1500k", "homeval_1500k_plus",
        # Education attainment (counts + dashboard groups)
        "edu_total",
        "edu_less_than_hs", "edu_hs_equiv", "edu_some_col_assoc",
        "edu_bachelors_only", "edu_grad_professional",
        # Health insurance
        "pop_total", "uninsured_count", "uninsured_pct",
        # Income & poverty
        "median_hh_income", "poverty_universe", "poverty_below", "poverty_rate",
        # Income distribution brackets (B19001) — sum across counties then interpolate regional median
        "hhinc_total",
        "hhinc_lt10k", "hhinc_10k_15k", "hhinc_15k_20k", "hhinc_20k_25k",
        "hhinc_25k_30k", "hhinc_30k_35k", "hhinc_35k_40k", "hhinc_40k_45k",
        "hhinc_45k_50k", "hhinc_50k_60k", "hhinc_60k_75k", "hhinc_75k_100k",
        "hhinc_100k_125k", "hhinc_125k_150k", "hhinc_150k_200k", "hhinc_200k_plus",
        # Race/ethnicity (B03002) — raw counts for regional aggregation + pct shares
        "race_total",
        "race_hispanic", "race_nh_white", "race_nh_black", "race_nh_asian", "race_nh_other",
        "race_hispanic_pct", "race_nh_white_pct", "race_nh_black_pct",
        "race_nh_asian_pct", "race_nh_other_pct",
        # Age groups (B01001) — raw counts for regional aggregation + pct shares
        "pop_age_total",
        "age_0_19", "age_20_34", "age_35_49", "age_50_64", "age_65plus",
        "age_0_19_pct", "age_20_34_pct", "age_35_49_pct",
        "age_50_64_pct", "age_65plus_pct",
    ]

    df = df[output_cols].sort_values("county_name").reset_index(drop=True)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "acs_snapshot.csv"
    df.to_csv(out_path, index=False)
    print(f"  Saved {len(df)} counties → {out_path}")
    return df


if __name__ == "__main__":
    fetch_acs()
