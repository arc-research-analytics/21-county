"""
fetch_oasis.py — GA DPH OASIS health indicators via the DTT JSON API.

OASIS was redesigned 2026-04-30 from a Playwright-scraped ASP.NET WebForms site
into an SPA backed by clean JSON endpoints. This module hits those endpoints
directly with `requests` — no headless browser required.

Three topics, one POST each per cause/metric:
  Hospital Discharge   — /dtt/Discharge/GetData    (7 cause groups)
  Low Birthweight      — /dtt/Birth/GetData         (Percent Low Birthweight)
  Teen Pregnancy       — /dtt/Pregnancy/GetData     (Pregnancy Rate, ages 15-19)

Each POST submits the full county list and gets back per-county values plus a
"County Summary" aggregate row, so we make 9 calls for 21 counties and 9 calls
for the 11-county core (= 18 total).

Output: data/processed/health_indicators.csv
  county_name, year,
  low_birthweight_pct, teen_preg_rate,
  discharge_cancer, discharge_cardiovascular, discharge_endocrine,
  discharge_external, discharge_infectious, discharge_mental, discharge_respiratory

  county_name is one of: individual county name | "21-County Region" | "11-County Core"
"""

import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from config import COUNTIES, CORE_11_COUNTIES, DATA_PROCESSED

BASE = "https://oasis.state.ga.us"

DISCHARGE_URL = f"{BASE}/dtt/discharge"
BIRTH_URL     = f"{BASE}/dtt/birth"
PREGNANCY_URL = f"{BASE}/dtt/pregnancy"

# Discharge cause groups: column name → exact OASIS "cause parent" string.
# These are the 7 categories the prior Playwright scraper queried.
DISCHARGE_CATEGORIES = {
    "discharge_cancer":          "Cancers",
    "discharge_cardiovascular":  "Major Cardiovascular Diseases",
    "discharge_endocrine":       "Endocrine, Nutritional and Metabolic Diseases",
    "discharge_external":        "External Causes",
    "discharge_infectious":      "Infectious and Parasitic Diseases",
    "discharge_mental":          "Mental and Behavioral Disorders",
    "discharge_respiratory":     "Respiratory Diseases",
}

ARC_COUNTY_NAMES = sorted(COUNTIES.keys())

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0 Safari/537.36"
)


# ── Session / token helpers ────────────────────────────────────────────────────

def _open_session(page_url: str) -> tuple[requests.Session, str]:
    """GET a DTT page so its antiforgery cookie + token are bound to a session.
    Returns (session, anti_token). Both are required on every GetData POST."""
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    r = s.get(page_url, timeout=30)
    r.raise_for_status()
    m = re.search(r'data-anti="([^"]+)"', r.text)
    if not m:
        raise RuntimeError(f"Antiforgery token not found at {page_url} — "
                           "page structure may have changed again.")
    return s, m.group(1)


def _post_getdata(session: requests.Session, token: str,
                  endpoint: str, referer: str, payload: dict) -> dict:
    """POST a GetData request and return the parsed JSON. Retries transient errors."""
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "RequestVerificationToken": token,
        "Referer": referer,
        "Accept": "*/*",
    }
    last_err = None
    for attempt in range(3):
        try:
            r = session.post(endpoint, headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            last_err = e
            if attempt < 2:
                time.sleep(2.0 ** attempt)
                continue
    raise RuntimeError(f"GetData failed after 3 attempts: {last_err}")


def _values_by_county(resp: dict, counties: list[str]) -> tuple[dict[str, float], float | None]:
    """
    Parse a GetData response into (per-county dict, summary value).

    Response shape: {"rowHeaders": [["Fulton"], ..., ["County Summary"]], "values": [...]}
    The Birth endpoint duplicates `values` (length 2*len(rowHeaders)) — slice to fit.
    """
    headers = [h[0] if isinstance(h, list) else h for h in (resp.get("rowHeaders") or [])]
    values  = resp.get("values") or []
    n = len(headers)
    if len(values) >= n:
        values = values[:n]

    per_county: dict[str, float] = {}
    summary: float | None = None
    for name, val in zip(headers, values):
        if name == "County Summary":
            summary = val
        elif name in counties:
            per_county[name] = val
    return per_county, summary


# ── Per-topic queries ──────────────────────────────────────────────────────────

def _query_discharge(year: str, counties: list[str]) -> tuple[dict[str, dict[str, float]],
                                                              dict[str, float | None]]:
    """
    Returns (county_values, summary_values) where:
      county_values[col_name][county] = discharge rate
      summary_values[col_name] = 21- or 11-county summary
    """
    sess, token = _open_session(DISCHARGE_URL)
    county_vals: dict[str, dict[str, float]] = {}
    summary_vals: dict[str, float | None] = {}

    for col_name, cause_group in DISCHARGE_CATEGORIES.items():
        payload = {
            "GeoType": "Counties",
            "Geographies": counties,
            "Times": [year],
            "Measure": ["Hospital Discharge Rate"],
            "AgeType": "Detailed Age Groups",
            "Ages": ["All Detailed Ages"],
            "Race": ["All Races"],
            "Payor": ["All Payors"],
            "Ethnicity": ["All Ethnicities"],
            "Sex": ["All Sexes"],
            "CauseTypes": [cause_group],
            "CauseParentFirstItem": cause_group,
            "CauseSource": "OASIS Detailed Causes",
            "SES": ["All Social Vulnerability Indexes"],
            "stratifyCause": False,
            "stratifyAge": False,
            "stratifyPayor": False,
            "stratifySES": False,
        }
        resp = _post_getdata(sess, token, f"{BASE}/dtt/Discharge/GetData",
                             DISCHARGE_URL, payload)
        per, summary = _values_by_county(resp, counties)
        county_vals[col_name] = per
        summary_vals[col_name] = summary
        print(f"      ✓ {col_name:28s} ({len(per)} counties, summary={summary})")

    return county_vals, summary_vals


def _query_low_birthweight(year: str, counties: list[str]) -> tuple[dict[str, float], float | None]:
    sess, token = _open_session(BIRTH_URL)
    payload = {
        "GeoType": "Counties",
        "Geographies": counties,
        "Times": [year],
        "Measure": ["Percent Low Birthweight <2,500 grams"],
        "AgeType": "Mothers Age Groups",
        "Ages": ["All Mothers Reproductive"],
        "Race": ["All Races"],
        "Education": ["All Educations PPOR"],
        "Ethnicity": ["All Ethnicities"],
        "Sex": [],
        "Payor": ["All Payors"],
        "SES": ["All Social Vulnerability Indexes"],
        "stratifyPayor": False,
        "stratifyAge": False,
        "stratifyEducation": False,
        "stratifySES": False,
    }
    resp = _post_getdata(sess, token, f"{BASE}/dtt/Birth/GetData", BIRTH_URL, payload)
    per, summary = _values_by_county(resp, counties)
    print(f"      ✓ low_birthweight_pct          ({len(per)} counties, summary={summary})")
    return per, summary


def _query_teen_pregnancy(year: str, counties: list[str]) -> tuple[dict[str, float], float | None]:
    sess, token = _open_session(PREGNANCY_URL)
    payload = {
        "GeoType": "Counties",
        "Geographies": counties,
        "Times": [year],
        "Measure": ["Pregnancy Rate"],
        "AgeType": "Mothers Age Groups",
        "Ages": ["15 - 17", "18 - 19"],
        "Race": ["All Races"],
        "Education": [],
        "Ethnicity": ["All Ethnicities"],
        "Sex": [],
        "Payor": [],
        "SES": [],
        "stratifyAge": False,
    }
    resp = _post_getdata(sess, token, f"{BASE}/dtt/Pregnancy/GetData", PREGNANCY_URL, payload)
    per, summary = _values_by_county(resp, counties)
    print(f"      ✓ teen_preg_rate               ({len(per)} counties, summary={summary})")
    return per, summary


def _latest_year() -> str:
    """Pick the most recent year that all three topics publish, so every metric
    in a row is from the same vintage."""
    latest = []
    for fname in ("timeDischarge.json", "timeBirth.json", "timePregnancy.json"):
        r = requests.get(f"{BASE}/dtt/data/{fname}", timeout=20)
        r.raise_for_status()
        years = [int(x["value"]) for x in r.json() if x.get("value", "").isdigit()]
        if not years:
            raise RuntimeError(f"No numeric years in {fname}")
        latest.append(max(years))
    return str(min(latest))


# ── Public entry point ─────────────────────────────────────────────────────────

def fetch_oasis():
    print("Fetching GA DPH OASIS health data via DTT JSON API...")

    year = _latest_year()
    print(f"  Latest year available across all three topics: {year}")

    base = pd.DataFrame({"county_name": ARC_COUNTY_NAMES})
    result = base.copy()

    # ── Pass 1: all 21 counties (per-county values + 21-county summary) ──────
    print("\n  Pass 1 — all 21 counties")
    counties_21 = ARC_COUNTY_NAMES
    summaries_21: dict[str, float | None] = {}

    print("    Hospital Discharge:")
    discharge_per, discharge_sum = _query_discharge(year, counties_21)
    for col, per in discharge_per.items():
        result[col] = result["county_name"].map(per)
    summaries_21.update(discharge_sum)

    print("    Low Birthweight:")
    lbw_per, lbw_sum = _query_low_birthweight(year, counties_21)
    result["low_birthweight_pct"] = result["county_name"].map(lbw_per)
    summaries_21["low_birthweight_pct"] = lbw_sum

    print("    Teen Pregnancy:")
    teen_per, teen_sum = _query_teen_pregnancy(year, counties_21)
    result["teen_preg_rate"] = result["county_name"].map(teen_per)
    summaries_21["teen_preg_rate"] = teen_sum

    # ── Pass 2: 11 core counties (only the County Summary value) ────────────
    print("\n  Pass 2 — 11-county core (aggregate summary only)")
    counties_11 = sorted(CORE_11_COUNTIES)
    summaries_11: dict[str, float | None] = {}

    print("    Hospital Discharge:")
    _, discharge_sum11 = _query_discharge(year, counties_11)
    summaries_11.update(discharge_sum11)

    print("    Low Birthweight:")
    _, lbw_sum11 = _query_low_birthweight(year, counties_11)
    summaries_11["low_birthweight_pct"] = lbw_sum11

    print("    Teen Pregnancy:")
    _, teen_sum11 = _query_teen_pregnancy(year, counties_11)
    summaries_11["teen_preg_rate"] = teen_sum11

    # ── Append aggregate rows ───────────────────────────────────────────────
    result["year"] = int(year)
    agg = pd.DataFrame([
        {"county_name": "21-County Region", "year": int(year), **summaries_21},
        {"county_name": "11-County Core",   "year": int(year), **summaries_11},
    ])
    df = pd.concat([result, agg], ignore_index=True)

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
