# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

All Python commands must use the `research` conda environment:
```bash
conda run -n research python pipeline/run_pipeline.py
```

A `.env` file in the project root holds API keys loaded automatically by `config.py` via `python-dotenv`:
- `CENSUS_API_KEY` — Census Bureau (ACS, PEP, QWI, CBP)
- `BEA_API_KEY` — Bureau of Economic Analysis (GDP by county)

## Running the Pipeline

```bash
# Full run (default vintage: 2024)
conda run -n research python pipeline/run_pipeline.py

# Specific data vintage
conda run -n research python pipeline/run_pipeline.py --vintage 2024

# Re-run specific stages only (skips everything else)
conda run -n research python pipeline/run_pipeline.py --only acs process

# Skip a stage (e.g. while GA DPH files are not yet downloaded)
conda run -n research python pipeline/run_pipeline.py --skip ga_dph

# Run a single fetcher directly
conda run -n research python pipeline/fetch_acs.py
```

## Architecture

The pipeline is a linear ETL: **fetch → process → output**.

```
pipeline/
  config.py              # All shared constants — edit here first
  run_pipeline.py        # Orchestrator: --vintage, --only, --skip flags
  fetch_*.py             # One fetcher per data source
  process.py             # Combines processed files into 7 output CSVs

data/
  raw/                   # Cached downloads and manual files (git-ignored)
    ga_dph/              # Manual OASIS downloads (see README.md inside)
  processed/             # Intermediate CSVs (one per fetcher)
  output/                # Final CSVs consumed by the frontend
```

### Data vintage

`config.py` reads `ARC_VINTAGE` from the environment (default `2024`). Setting `--vintage` in `run_pipeline.py` writes this env var before any modules load, so all stages see the same value. Three constants derive from it: `ACS_YEAR`, `PEP_END_YEAR`, `QWI_END_YEAR`.

### Fetcher summary

| Stage | Source | Notes |
|---|---|---|
| `population` | Census PEP API | 3 vintages stitched: intercensal 2000–09, PEP 2010–19, PEP `charv` 2020+. Auto-retries prior vintage on 404. |
| `acs` | Census ACS API | 1-year estimates with automatic 5-year fallback for counties under ~65K (currently Dawson). ~120 variables chunked into 45-var API calls. |
| `employment` | Census QWI `/sa` endpoint | END_YEAR = `current_year - 1` (independent of ARC_VINTAGE). Time range uses literal `+` in URL string (not `params=`) to avoid `%2B` encoding. NAICS codes `31-33`, `44-45`, `48-49` are hyphenated. Auto-retries `END_YEAR-1` on 204. |
| `hud_permits` | Census BPS monthly TXT files | Fetches all years 2000–latest complete calendar year. Monthly TXT files cached in `data/raw/bps/` (~300 files; ~instant after first run). |
| `gosa` | `download.gosa.ga.gov` | Scrapes open directory listing for `Graduation_Rate_*.csv`; tries `current_year-1` then `current_year-2`. Caches locally. |
| `forecast` | `atlantaregional.org` | Tries S18 URLs first, falls back to S17. Sheet names and decade columns detected dynamically. Caches locally. |
| `qcew` | BLS QCEW annual singlefile ZIPs | 10-year rolling window ending at the **latest available year** (auto-discovered via HEAD request, independent of ARC_VINTAGE). Files from `data.bls.gov` (not `www.bls.gov` — CDN blocks scripts). ZIPs cached in `data/raw/qcew/`. agglvl_code 70 = county total; agglvl_code 73 + own_code 5 = private sector wages by supersector. |
| `bea_gdp` | BEA Regional API (CAGDP9) | Real GDP by county, all years in one call. Requires `BEA_API_KEY` in `.env`. Returns 2001–present. |
| `ga_dph` | Manual download | No API. Files go in `data/raw/ga_dph/`. Pipeline continues with empty health indicators if absent. |
| `process` | `data/processed/` | Combines all intermediates into 10 output CSVs + `vintages.json`. Adds `in_core_11` boolean flag to every file. Snapshot CSVs (housing, income, education, health) carry `acs_vintage`; `housing.csv` also carries `permits_vintage` for the latest permit year merged in. |

### Region definitions

- **21-county region**: all keys in `COUNTIES` dict in `config.py`
- **11-county core**: `CORE_11_COUNTIES` set in `config.py` — Cherokee, Clayton, Cobb, DeKalb, Douglas, Fayette, Forsyth, Fulton, Gwinnett, Henry, Rockdale
- Every output CSV carries an `in_core_11` column so the frontend can aggregate either way without hardcoding county lists

### Regional median household income

`income.csv` includes raw B19001 bracket counts (`hhinc_lt10k` … `hhinc_200k_plus`). The frontend computes regional medians by summing bracket counts across the desired counties then interpolating. The top bracket (`hhinc_200k_plus`) is open-ended; use $250,000 as the conventional upper bound.

### Output files

Seven CSVs in `data/output/`, one per dashboard tab:

| File | Key columns |
|---|---|
| `population.csv` | `year`, `population`, `pct_chg_2000_2010`, `pct_chg_2010_now`, `race_*` raw counts + `race_*_pct`, `age_*` raw counts + `age_*_pct` |
| `employment.csv` | `year`, `employment`, `pct_chg_2010_now`, 11 supersector columns + `_pct` variants |
| `housing.csv` | `median_home_value`, `vacancy_rate`, `owner_pct`, `renter_pct`, `hh_*_pct`, permit counts, `homeval_*` bracket counts (B25075, 27 brackets; sum across counties then interpolate regional median; top bracket $1.5M+, use $2M as upper bound) |
| `education.csv` | `edu_*_pct` attainment groups, `district_name`, `grad_rate_pct` |
| `health.csv` | `uninsured_pct` (ACS); DPH columns populated only after manual download |
| `income.csv` | `median_hh_income`, `poverty_rate_pct`, `hhinc_*` bracket counts |
| `forecast.csv` | `pop_2020`, `pop_2050`, `emp_2020`, `emp_2050`, `*_net_increase`, `*_pct_increase` |
| `forecast_sectors.csv` | Long format: `county_name`, `year`, `supersector`, `employment` |
| `wages.csv` | `year`, `total_annual_wages`, `annual_avg_emplvl`, `avg_annual_pay`, `annual_avg_estabs` — QCEW 10-year series, all industries total; regional avg = `sum(total_annual_wages) / sum(annual_avg_emplvl)` |
| `wages_by_industry.csv` | Long format: `year`, `supersector`, `total_annual_wages`, `annual_avg_emplvl`, `avg_annual_pay` — private sector wages by industry |
| `gdp.csv` | `year`, `gdp_thousands` — BEA real GDP (chained 2017 dollars), 2001–present |
| `permits.csv` | Long format: `county_name`, `year`, `sf_permits`, `mf_total_permits`, `total_permits` — annual totals 2000–present |
| `vintages.json` | Metadata: `generated`, `acs_vintage`, `population_latest_year`, `employment_latest_year`, `wages_latest_year`, `gdp_latest_year`, `permits_latest_year`, `gosa_latest_year` |

### GA DPH (manual)

Download three files from https://oasis.state.ga.us, save to `data/raw/ga_dph/` using the naming convention in that folder's `README.md`. The fetcher handles flexible column naming via regex and will partially populate `health.csv` from whichever files are present.
