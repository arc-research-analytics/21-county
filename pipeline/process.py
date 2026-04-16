"""
Combine all processed intermediate files into the 7 final output CSVs
consumed by the frontend dashboard.

Reads from: data/processed/
Writes to:  data/output/

Output files (one per dashboard tab):
  population.csv    — time series + 2023 race/age profile
  employment.csv    — time series + industry breakdown
  housing.csv       — ACS snapshot + building permits
  education.csv     — ACS attainment + GOSA graduation rates
  health.csv        — ACS uninsured + GA DPH indicators
  income.csv        — ACS median income + poverty
  forecast.csv      — S17 2020 vs 2050 totals + sector breakdown
"""

import json
import pandas as pd
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import COUNTIES, STATE_FIPS, DATA_PROCESSED, DATA_OUTPUT, CORE_11_COUNTIES, ACS_YEAR

FIPS_TO_NAME = {STATE_FIPS + v: k for k, v in COUNTIES.items()}
NAME_TO_FIPS = {v: k for k, v in FIPS_TO_NAME.items()}


def _add_region_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Add an 'in_core_11' boolean column so the frontend can aggregate either way."""
    if "county_name" in df.columns:
        df["in_core_11"] = df["county_name"].isin(CORE_11_COUNTIES)
    return df


def _load(filename: str) -> pd.DataFrame:
    path = DATA_PROCESSED / filename
    if not path.exists():
        print(f"  WARNING: {filename} not found — skipping.")
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"county_fips": str})
    return df


def build_population():
    print("  Building population.csv...")
    ts  = _load("population_timeseries.csv")
    acs = _load("acs_snapshot.csv")  # race/age profile lives here (B03002 + B01001)

    if ts.empty:
        return

    # Add pct change columns
    ts = ts.sort_values(["county_fips", "year"])
    pop_2000 = ts[ts["year"] == 2000].set_index("county_fips")["population"].rename("pop_2000")
    pop_2010 = ts[ts["year"] == 2010].set_index("county_fips")["population"].rename("pop_2010")

    ts = ts.merge(pop_2000.reset_index(), on="county_fips", how="left")
    ts = ts.merge(pop_2010.reset_index(), on="county_fips", how="left")
    ts["pct_chg_2000_2010"] = ((ts["pop_2010"] - ts["pop_2000"]) / ts["pop_2000"] * 100).round(1)
    ts["pct_chg_2010_now"]  = ((ts["population"] - ts["pop_2010"]) / ts["pop_2010"] * 100).round(1)

    # Merge race/age profile from ACS snapshot
    profile_cols = [c for c in acs.columns if c.startswith(("race_", "age_"))]
    if profile_cols and not acs.empty:
        out = ts.merge(acs[["county_fips"] + profile_cols], on="county_fips", how="left")
    else:
        out = ts

    out = _add_region_flag(out)
    out.to_csv(DATA_OUTPUT / "population.csv", index=False)
    print(f"    {len(out)} rows")


def build_employment():
    print("  Building employment.csv...")
    ts  = _load("employment_timeseries.csv")
    ind = _load("employment_by_industry.csv")

    if ts.empty:
        return

    # Anchor year for percent-change calculation (matches dashboard label)
    ts = ts.sort_values(["county_fips", "year"])
    emp_2010 = (
        ts[ts["year"] == 2010]
        .set_index("county_fips")["employment"]
        .rename("emp_2010")
    )
    ts = ts.merge(emp_2010.reset_index(), on="county_fips", how="left")
    ts["pct_chg_2010_now"] = (
        (ts["employment"] - ts["emp_2010"]) / ts["emp_2010"] * 100
    ).round(1)

    if not ind.empty:
        out = ts.merge(ind, on=["county_fips", "county_name", "year"], how="left")
    else:
        out = ts

    out = _add_region_flag(out)
    out.to_csv(DATA_OUTPUT / "employment.csv", index=False)
    print(f"    {len(out)} rows")


def build_housing():
    print("  Building housing.csv...")
    acs     = _load("acs_snapshot.csv")
    permits = _load("building_permits.csv")

    if acs.empty:
        return

    # ACS snapshot already has all housing fields
    housing_cols = [
        "county_fips", "county_name", "acs_vintage",
        "median_home_value",
        "total_units", "occupied_units", "vacant_units", "vacancy_rate",
        "owner_occupied", "renter_occupied", "owner_pct", "renter_pct",
        "hh_total", "hh_married_family", "hh_other_family", "hh_nonfamily",
        "hh_married_pct", "hh_single_pct", "hh_nonfamily_pct",
        # Home value distribution brackets (B25075) — sum across owner-occupied units then interpolate regional median
        "homeval_total",
        "homeval_lt10k", "homeval_10k_15k", "homeval_15k_20k", "homeval_20k_25k",
        "homeval_25k_30k", "homeval_30k_35k", "homeval_35k_40k", "homeval_40k_45k",
        "homeval_45k_50k", "homeval_50k_60k", "homeval_60k_70k", "homeval_70k_80k",
        "homeval_80k_90k", "homeval_90k_100k",
        "homeval_100k_125k", "homeval_125k_150k", "homeval_150k_175k", "homeval_175k_200k",
        "homeval_200k_250k", "homeval_250k_300k", "homeval_300k_400k", "homeval_400k_500k",
        "homeval_500k_750k", "homeval_750k_1m", "homeval_1m_1500k", "homeval_1500k_plus",
    ]
    out = acs[[c for c in housing_cols if c in acs.columns]].copy()

    # Merge latest year of permits into the housing snapshot for context
    if not permits.empty:
        latest_year = permits["year"].max()
        latest_permits = permits[permits["year"] == latest_year].copy()
        latest_permits["county_fips"] = latest_permits["county_name"].map(NAME_TO_FIPS).astype(str)
        out["county_fips"] = out["county_fips"].astype(str)
        out = out.merge(
            latest_permits[["county_fips", "year", "sf_permits", "mf_total_permits", "total_permits"]],
            on="county_fips", how="left"
        )
        out = out.rename(columns={"year": "permits_vintage"})

    out = _add_region_flag(out)
    out.to_csv(DATA_OUTPUT / "housing.csv", index=False)
    print(f"    {len(out)} rows")


def build_education():
    print("  Building education.csv...")
    acs  = _load("acs_snapshot.csv")
    gosa = _load("graduation_rates.csv")

    if acs.empty:
        return

    edu_cols = [
        "county_fips", "county_name", "acs_vintage",
        "edu_total",
        "edu_less_than_hs", "edu_hs_equiv", "edu_some_col_assoc",
        "edu_bachelors_only", "edu_grad_professional",
    ]
    out = acs[[c for c in edu_cols if c in acs.columns]].copy()

    # Compute pct shares of total attainment population (25+)
    for group in ["less_than_hs", "hs_equiv", "some_col_assoc", "bachelors_only", "grad_professional"]:
        col = f"edu_{group}"
        if col in out.columns:
            out[f"{col}_pct"] = (out[col] / out["edu_total"] * 100).round(1)

    if not gosa.empty:
        # Graduation rates join on county_name (multiple districts per county OK)
        out = out.merge(gosa, on="county_name", how="left")

    out = _add_region_flag(out)
    out.to_csv(DATA_OUTPUT / "education.csv", index=False)
    print(f"    {len(out)} rows")


def build_health():
    print("  Building health.csv...")
    acs = _load("acs_snapshot.csv")
    dph = _load("health_indicators.csv")

    if acs.empty:
        return

    health_cols = [
        "county_fips", "county_name", "acs_vintage",
        "pop_total", "uninsured_count", "uninsured_pct",
    ]
    out = acs[[c for c in health_cols if c in acs.columns]].copy()

    if not dph.empty:
        dph["county_fips"] = dph["county_name"].map(NAME_TO_FIPS)
        out = out.merge(
            dph.drop(columns=["county_fips"], errors="ignore"),
            on="county_name", how="left"
        )

    out = _add_region_flag(out)
    out.to_csv(DATA_OUTPUT / "health.csv", index=False)
    print(f"    {len(out)} rows")


def build_income():
    print("  Building income.csv...")
    acs = _load("acs_snapshot.csv")

    if acs.empty:
        return

    income_cols = [
        "county_fips", "county_name", "acs_vintage",
        "median_hh_income",
        "poverty_universe", "poverty_below", "poverty_rate",
        # B19001 income distribution — used to interpolate 11/21-county regional medians
        "hhinc_total",
        "hhinc_lt10k", "hhinc_10k_15k", "hhinc_15k_20k", "hhinc_20k_25k",
        "hhinc_25k_30k", "hhinc_30k_35k", "hhinc_35k_40k", "hhinc_40k_45k",
        "hhinc_45k_50k", "hhinc_50k_60k", "hhinc_60k_75k", "hhinc_75k_100k",
        "hhinc_100k_125k", "hhinc_125k_150k", "hhinc_150k_200k", "hhinc_200k_plus",
    ]
    out = acs[[c for c in income_cols if c in acs.columns]].copy()
    out["poverty_rate_pct"] = (out["poverty_rate"] * 100).round(1)

    out = _add_region_flag(out)
    out.to_csv(DATA_OUTPUT / "income.csv", index=False)
    print(f"    {len(out)} rows")


def build_forecast():
    print("  Building forecast.csv...")
    totals  = _load("forecast_totals.csv")
    sectors = _load("forecast_by_sector.csv")

    if totals.empty:
        return

    totals["county_fips"] = totals["county_name"].map(NAME_TO_FIPS)

    # Pivot sector data wide: one column per supersector per decade
    if not sectors.empty:
        sector_wide = sectors.pivot_table(
            index=["county_name", "year"],
            columns="supersector",
            values="employment",
            aggfunc="sum"
        ).reset_index()
        sector_wide.columns = [
            f"emp_{c.lower().replace(' ', '_').replace(',', '')}_{y}" if c != "county_name" and c != "year"
            else c
            for c, y in zip(sector_wide.columns, [""] * len(sector_wide.columns))
        ]
        # Simpler: save sector breakdowns as a separate long-format file
        sectors.to_csv(DATA_OUTPUT / "forecast_sectors.csv", index=False)

    totals = _add_region_flag(totals)
    totals.to_csv(DATA_OUTPUT / "forecast.csv", index=False)
    print(f"    {len(totals)} rows (totals) + {len(sectors)} rows (sectors)")


def build_wages():
    print("  Building wages.csv...")
    ts  = _load("qcew_wages.csv")
    ind = _load("qcew_wages_by_industry.csv")

    if ts.empty:
        return

    out = _add_region_flag(ts)
    out.to_csv(DATA_OUTPUT / "wages.csv", index=False)
    print(f"    {len(out)} rows (totals)")

    if not ind.empty:
        ind = _add_region_flag(ind)
        ind.to_csv(DATA_OUTPUT / "wages_by_industry.csv", index=False)
        print(f"    {len(ind)} rows (by industry)")


def build_gdp():
    print("  Building gdp.csv...")
    gdp = _load("bea_gdp.csv")

    if gdp.empty:
        return

    out = _add_region_flag(gdp)
    out.to_csv(DATA_OUTPUT / "gdp.csv", index=False)
    print(f"    {len(out)} rows")


def build_permits():
    print("  Building permits.csv...")
    permits = _load("building_permits.csv")

    if permits.empty:
        return

    out = _add_region_flag(permits)
    out.to_csv(DATA_OUTPUT / "permits.csv", index=False)
    print(f"    {len(out)} rows ({int(out['year'].min())}–{int(out['year'].max())})")


def _generate_vintages() -> dict:
    """
    Build a vintage metadata dict from the intermediate processed files.
    Written to data/output/vintages.json so the frontend can label each chart
    with the correct data-as-of year without hardcoding anything.
    """
    meta: dict = {"generated": str(date.today())}

    # ACS snapshot vintage year — read the year fetch_acs actually used.
    # fetch_acs._discover_acs_year() may fall back one year if the target vintage
    # isn't published yet (e.g. ACS 2025 isn't available until September 2026).
    acs_year_file = DATA_PROCESSED / "acs_year.txt"
    meta["acs_vintage"] = (
        int(acs_year_file.read_text().strip()) if acs_year_file.exists() else ACS_YEAR
    )

    # Time series latest years
    for key, filename, col in [
        ("population_latest_year",  "population_timeseries.csv",  "year"),
        ("employment_latest_year",  "employment_timeseries.csv",  "year"),
        ("wages_latest_year",       "qcew_wages.csv",             "year"),
        ("gdp_latest_year",         "bea_gdp.csv",                "year"),
        ("permits_latest_year",     "building_permits.csv",       "year"),
    ]:
        df = _load(filename)
        if not df.empty and col in df.columns:
            meta[key] = int(df[col].max())

    # Employment: how many QWI quarters fed the latest-year average
    emp_q_file = DATA_PROCESSED / "employment_quarters.json"
    if emp_q_file.exists():
        emp_q = json.loads(emp_q_file.read_text())
        meta["employment_latest_quarter"] = emp_q["max_quarter"]

    # GOSA graduation rates school year
    gosa = _load("graduation_rates.csv")
    if not gosa.empty:
        yr_col = next((c for c in gosa.columns if "year" in c.lower()), None)
        if yr_col:
            meta["gosa_latest_year"] = str(gosa[yr_col].max())

    return meta


def process_all():
    print("Processing all data into output CSVs...")
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)

    build_population()
    build_employment()
    build_housing()
    build_education()
    build_health()
    build_income()
    build_forecast()
    build_wages()
    build_gdp()
    build_permits()

    # Vintage metadata — written last so all processed files are available
    vintages = _generate_vintages()
    vintages_path = DATA_OUTPUT / "vintages.json"
    with open(vintages_path, "w") as f:
        json.dump(vintages, f, indent=2)
    print(f"\n  vintages.json: {vintages}")

    print("\nDone. Output files:")
    for f in sorted(DATA_OUTPUT.glob("*.csv")):
        rows = sum(1 for _ in open(f)) - 1
        print(f"  {f.name:<30} {rows} rows")


if __name__ == "__main__":
    process_all()
