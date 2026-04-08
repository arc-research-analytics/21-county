"""
fetch_oasis.py — Automated browser scraper for GA DPH OASIS health data.

Queries three OASIS pages:
  Hospital Discharge Rates  — qryMorbidity.aspx  (7 diagnostic categories)
  Low Birthweight           — qryBirth.aspx       (all mothers ages)
  Teen Pregnancy Rate       — qryPregnancy.aspx   (ages 15-17 and 18-19)

Each metric is scraped twice:
  Pass 1 — all 21 ARC counties  → per-county rows + 21-county aggregate summary
  Pass 2 — 11 core counties     → 11-county aggregate summary

Output: data/processed/health_indicators.csv
  county_name, year,
  low_birthweight_pct, teen_preg_rate,
  discharge_cancer, discharge_cardiovascular, discharge_endocrine,
  discharge_external, discharge_infectious, discharge_mental, discharge_respiratory

  county_name is one of: individual county name | "21-County Region" | "11-County Core"

Install dependency (one-time):
  conda run -n research pip install playwright
  conda run -n research playwright install chromium
"""

import asyncio
import re
import sys
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

sys.path.insert(0, str(Path(__file__).parent))
from config import COUNTIES, CORE_11_COUNTIES, DATA_PROCESSED

MORBIDITY_URL = "https://oasis.state.ga.us/oasis/webquery/qryMorbidity.aspx"
BIRTH_URL     = "https://oasis.state.ga.us/oasis/webquery/qryBirth.aspx"
PREGNANCY_URL = "https://oasis.state.ga.us/oasis/webquery/qryPregnancy.aspx"

# Regex patterns to match #drpCauseParent option text → output column name.
# Flexible matching avoids brittleness from OASIS label wording (e.g. slashes vs commas).
DISCHARGE_CATEGORIES = [
    (r"cancer|neoplasm",            "discharge_cancer"),
    (r"cardiovascular|circulatory", "discharge_cardiovascular"),
    (r"endocrine|nutritional",      "discharge_endocrine"),
    (r"external",                   "discharge_external"),
    (r"infectious|parasitic",       "discharge_infectious"),
    (r"mental|behavioral",          "discharge_mental"),
    (r"respiratory",                "discharge_respiratory"),
]

ARC_COUNTY_NAMES = set(COUNTIES.keys())


# ── Helpers ────────────────────────────────────────────────────────────────────

def _match_county(raw: str) -> str | None:
    """Strip 'County' suffix and return the matching ARC county name, or None."""
    clean = re.sub(r"\s*county\s*$", "", raw.strip(), flags=re.IGNORECASE).strip()
    if clean in ARC_COUNTY_NAMES:
        return clean
    for name in ARC_COUNTY_NAMES:
        if name.lower() == clean.lower():
            return name
    return None


async def _get_latest_year(page: Page) -> str:
    """Return the most recent year available in #lstTime."""
    options = await page.locator("#lstTime option").all()
    years = [
        (await opt.get_attribute("value") or "").strip()
        for opt in options
    ]
    numeric = [y for y in years if y.isdigit()]
    if not numeric:
        raise RuntimeError("No numeric years found in #lstTime")
    return max(numeric, key=int)


async def _select_counties(page: Page, county_names: set) -> None:
    """Select the given county names in #lstGeographies."""
    options = await page.locator("#lstGeographies option").all()
    values_to_select = []
    for opt in options:
        text = await opt.inner_text()
        normalized = _match_county(text)
        if normalized and normalized in county_names:
            val = await opt.get_attribute("value")
            if val:
                values_to_select.append(val)

    if not values_to_select:
        raise RuntimeError(
            f"No matching counties found in #lstGeographies for {county_names}. "
            "Geography type postback may not have completed."
        )

    await page.select_option("#lstGeographies", value=values_to_select)
    print(f"      Selected {len(values_to_select)} counties")


async def _select_cause_parent(page: Page, pattern: str) -> str:
    """
    Select the first #drpCauseParent option whose text matches the regex pattern.
    Returns the matched option label for logging.
    """
    options = await page.locator("#drpCauseParent option").all()
    for opt in options:
        text = (await opt.inner_text()).strip()
        if re.search(pattern, text, re.IGNORECASE):
            value = await opt.get_attribute("value")
            await page.select_option("#drpCauseParent", value=value)
            return text
    raise RuntimeError(f"No #drpCauseParent option matched pattern: {pattern!r}")


async def _parse_results(page: Page) -> pd.DataFrame:
    """
    Parse individual county rows from the OASIS results table.

    DOM structure (confirmed from DevTools):
      div#queryResults > table#Table2 > tbody > tr.detailedRows
        td.oasisOutputRowItemHeader          ← county name (may contain <a> tag)
        td.oasisOutputAlternatingRowItem     ← rate value

    Skips "County Summary" and other non-county rows.
    Returns DataFrame: county_name (str), value (float).
    """
    try:
        await page.wait_for_selector("div#queryResults table#Table2", timeout=45_000)
    except PWTimeout:
        raise RuntimeError("Timed out waiting for div#queryResults table#Table2")

    rows = await page.locator("div#queryResults table#Table2 tr.detailedRows").all()
    if not rows:
        raise RuntimeError("No tr.detailedRows found in results table")

    records = []
    for row in rows:
        name_cell  = row.locator("td.oasisOutputRowItemHeader")
        value_cell = row.locator(
            "td.oasisOutputAlternatingRowItem, td.oasisOutputRowItem"
        ).first

        raw_name  = (await name_cell.inner_text()).strip()
        raw_value = (await value_cell.inner_text()).strip()

        county = _match_county(raw_name)
        if county is None:
            continue  # skip "County Summary" and other aggregate rows

        try:
            value = float(raw_value.replace(",", ""))
        except ValueError:
            continue  # skip suppressed cells marked with "*"

        records.append({"county_name": county, "value": value})

    if not records:
        raise RuntimeError("Parsed zero county rows from results table")

    return pd.DataFrame(records)


async def _parse_summary(page: Page) -> float | None:
    """
    Extract the aggregate value from the "County Summary" row in the results table.
    Returns None if the row is absent or suppressed.
    """
    rows = await page.locator("div#queryResults table#Table2 tr.detailedRows").all()
    for row in rows:
        name_cell = row.locator("td.oasisOutputRowItemHeader")
        raw_name  = (await name_cell.inner_text()).strip()
        if "summary" in raw_name.lower():
            value_cell = row.locator(
                "td.oasisOutputAlternatingRowItem, td.oasisOutputRowItem"
            ).first
            raw_value = (await value_cell.inner_text()).strip()
            try:
                return float(raw_value.replace(",", ""))
            except ValueError:
                return None
    return None


# ── Per-category discharge scraper ────────────────────────────────────────────

async def _scrape_one_category(
    page: Page, pattern: str, year: str, county_names: set
) -> tuple[pd.DataFrame, float | None]:
    """
    Query one discharge category for the given county set.
    Returns (county_df, summary_value).
    county_df has columns: county_name, value.
    summary_value is the OASIS "County Summary" aggregate rate (or None).
    """
    await page.goto(MORBIDITY_URL, wait_until="networkidle")

    await page.select_option("#drpMeasure", label="Discharge Rate")
    await page.wait_for_load_state("networkidle")
    await page.select_option("#lstTime", value=year)
    await page.select_option("#lstAge", label="All Ages")

    await page.select_option("#drpGeoType", label="Counties")
    await page.wait_for_load_state("networkidle")
    await _select_counties(page, county_names)

    await page.select_option("#drpCauseCat", label="OASIS Detailed Causes")
    await page.wait_for_load_state("networkidle")
    matched_label = await _select_cause_parent(page, pattern)
    print(f"    → {matched_label} ...")
    await page.wait_for_load_state("networkidle")
    await page.select_option("#lstCauseChild", index=0)

    await page.select_option("#lstRace",      label="All Races")
    await page.select_option("#lstSex",       label="All Sexes")
    await page.select_option("#lstPayor",     label="All Payors")
    await page.select_option("#lstEthnicity", label="All Ethnicities")

    await page.click("#imgSubmit")
    await page.wait_for_load_state("networkidle")

    # Only parse per-county rows when querying all 21 (skip for 11-county pass)
    if county_names == ARC_COUNTY_NAMES:
        df = await _parse_results(page)
    else:
        df = pd.DataFrame(columns=["county_name", "value"])

    summary = await _parse_summary(page)
    return df, summary


# ── Low birthweight scraper ───────────────────────────────────────────────────

async def _scrape_low_birthweight(
    page: Page, year: str, county_names: set
) -> tuple[pd.DataFrame, float | None]:
    """
    Query qryBirth.aspx for Percent Low Birthweight, all mothers ages.
    Returns (county_df, summary_value).
    """
    print("    → Low Birthweight (all ages) ...")

    await page.goto(BIRTH_URL, wait_until="networkidle")

    await page.select_option("#drpMeasure", value="Percent Low Birthweight <2,500 grams")
    await page.wait_for_load_state("networkidle")
    await page.select_option("#lstTime", value=year)

    await page.select_option("#drpAgeType", label="Mothers Age Groups")
    await page.wait_for_load_state("networkidle")
    await page.select_option("#lstAge", label="All Mothers Ages")

    await page.select_option("#drpGeoType", label="Counties")
    await page.wait_for_load_state("networkidle")
    await _select_counties(page, county_names)

    await page.select_option("#lstRace",           label="All Races")
    await page.select_option("#lstEthnicity",      label="All Ethnicities")
    await page.select_option("#lstPayor",          label="All Payors")
    await page.select_option("#lstEducationLevel", label="All Education Levels")
    await page.select_option("#lstSES",            label="All SES Vulnerability")

    await page.click("#imgSubmit")
    await page.wait_for_load_state("networkidle")

    if county_names == ARC_COUNTY_NAMES:
        df = await _parse_results(page)
        df = df.rename(columns={"value": "low_birthweight_pct"})
    else:
        df = pd.DataFrame(columns=["county_name", "low_birthweight_pct"])

    summary = await _parse_summary(page)
    return df, summary


# ── Teen pregnancy scraper ────────────────────────────────────────────────────

async def _scrape_teen_pregnancy(
    page: Page, year: str, county_names: set
) -> tuple[pd.DataFrame, float | None]:
    """
    Query qryPregnancy.aspx for Pregnancy Rate, mothers aged 15-17 and 18-19.
    Returns (county_df, summary_value).
    """
    print("    → Teen Pregnancy Rate (15-19) ...")

    await page.goto(PREGNANCY_URL, wait_until="networkidle")

    await page.select_option("#drpMeasure", label="Pregnancy Rate")
    await page.wait_for_load_state("networkidle")
    await page.select_option("#lstTime", value=year)

    await page.select_option("#drpAgeType", label="Mothers Age Groups")
    await page.wait_for_load_state("networkidle")
    await page.select_option("#lstAge", label=["15-17", "18-19"])

    await page.select_option("#drpGeoType", label="Counties")
    await page.wait_for_load_state("networkidle")
    await _select_counties(page, county_names)

    await page.select_option("#lstRace",      label="All Races")
    await page.select_option("#lstEthnicity", label="All Ethnicities")

    await page.click("#imgSubmit")
    await page.wait_for_load_state("networkidle")

    if county_names == ARC_COUNTY_NAMES:
        df = await _parse_results(page)
        df = df.rename(columns={"value": "teen_preg_rate"})
    else:
        df = pd.DataFrame(columns=["county_name", "teen_preg_rate"])

    summary = await _parse_summary(page)
    return df, summary


# ── Main async entry point ─────────────────────────────────────────────────────

async def _run() -> pd.DataFrame:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(MORBIDITY_URL, wait_until="networkidle")
        year = await _get_latest_year(page)
        print(f"  Latest year available: {year}")

        base   = pd.DataFrame({"county_name": sorted(ARC_COUNTY_NAMES)})
        result = base.copy()
        summaries_21: dict[str, float | None] = {}
        summaries_11: dict[str, float | None] = {}

        # ── Pass 1: all 21 counties ───────────────────────────────────────────
        print("\n  Pass 1 — all 21 counties (per-county data + 21-county summary)")

        for pattern, col_name in DISCHARGE_CATEGORIES:
            try:
                df, s21 = await _scrape_one_category(page, pattern, year, ARC_COUNTY_NAMES)
                df = df.rename(columns={"value": col_name})
                result = result.merge(df, on="county_name", how="left")
                summaries_21[col_name] = s21
            except Exception as exc:
                print(f"      WARNING: '{col_name}' failed — {exc}")
                result[col_name] = None
                summaries_21[col_name] = None

        try:
            lbw, s21 = await _scrape_low_birthweight(page, year, ARC_COUNTY_NAMES)
            result = result.merge(lbw, on="county_name", how="left")
            summaries_21["low_birthweight_pct"] = s21
        except Exception as exc:
            print(f"      WARNING: 'low_birthweight_pct' failed — {exc}")
            result["low_birthweight_pct"] = None
            summaries_21["low_birthweight_pct"] = None

        try:
            teen, s21 = await _scrape_teen_pregnancy(page, year, ARC_COUNTY_NAMES)
            result = result.merge(teen, on="county_name", how="left")
            summaries_21["teen_preg_rate"] = s21
        except Exception as exc:
            print(f"      WARNING: 'teen_preg_rate' failed — {exc}")
            result["teen_preg_rate"] = None
            summaries_21["teen_preg_rate"] = None

        # ── Pass 2: 11 core counties (summaries only) ─────────────────────────
        print("\n  Pass 2 — 11-county core (aggregate summary only)")

        for pattern, col_name in DISCHARGE_CATEGORIES:
            try:
                _, s11 = await _scrape_one_category(page, pattern, year, CORE_11_COUNTIES)
                summaries_11[col_name] = s11
            except Exception as exc:
                print(f"      WARNING: '{col_name}' (11-county) failed — {exc}")
                summaries_11[col_name] = None

        try:
            _, s11 = await _scrape_low_birthweight(page, year, CORE_11_COUNTIES)
            summaries_11["low_birthweight_pct"] = s11
        except Exception as exc:
            print(f"      WARNING: 'low_birthweight_pct' (11-county) failed — {exc}")
            summaries_11["low_birthweight_pct"] = None

        try:
            _, s11 = await _scrape_teen_pregnancy(page, year, CORE_11_COUNTIES)
            summaries_11["teen_preg_rate"] = s11
        except Exception as exc:
            print(f"      WARNING: 'teen_preg_rate' (11-county) failed — {exc}")
            summaries_11["teen_preg_rate"] = None

        await browser.close()

    # ── Append aggregate rows ─────────────────────────────────────────────────
    result["year"] = int(year)
    agg_rows = pd.DataFrame([
        {"county_name": "21-County Region", "year": int(year), **summaries_21},
        {"county_name": "11-County Core",   "year": int(year), **summaries_11},
    ])
    return pd.concat([result, agg_rows], ignore_index=True)


# ── Public entry point (called by run_pipeline.py) ────────────────────────────

def fetch_oasis():
    print("Scraping GA DPH OASIS health data (Playwright)...")

    df = asyncio.run(_run())

    col_order = [
        "county_name", "year",
        "low_birthweight_pct", "teen_preg_rate",
        "discharge_cancer", "discharge_cardiovascular", "discharge_endocrine",
        "discharge_external", "discharge_infectious", "discharge_mental",
        "discharge_respiratory",
    ]
    df = df[[c for c in col_order if c in df.columns]]

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "health_indicators.csv"
    df.to_csv(out_path, index=False)
    print(f"\n  Saved {len(df)} rows → {out_path}")
    return df


if __name__ == "__main__":
    fetch_oasis()
