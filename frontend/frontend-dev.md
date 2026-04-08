# ARC 21-County Dashboard — Frontend Development Plan

## 1. Project Goals & Design Philosophy

This frontend replaces the ARC Tableau dashboard with a modern, executive-grade web application. The audience is senior leadership and decision-makers, so the UI prioritizes at-a-glance insight (2–3 headline KPIs per section) over raw data density. The design follows the **"Analytical Lens"** editorial system established in `Google-Stich-mockup/DESIGN.md`: deep authoritative navy, no 1px borders, tonal surface layering, Inter + Public Sans typography, and glassmorphism for interactive overlays.

---

## 2. File & Folder Structure

```
frontend/
  index.html                  # Single HTML entry point
  css/
    theme.css                 # CSS custom properties: color tokens + dark mode overrides
  js/
    main.js                   # App init, tab router, dark mode toggle
    data.js                   # CSV fetch + Papa Parse helpers; caches parsed data
    filter.js                 # County multi-select state; publishes change events
    charts/
      population.js
      employment.js
      economy.js
      housing.js
      education.js
      health.js
      income.js
      forecast.js
    tabs/
      population.js           # KPI render + chart orchestration for each tab
      employment.js
      economy.js
      housing.js
      education.js
      health.js
      income.js
      forecast.js
  old_tool/                   # Reference screenshots (not served)
  Google-Stich-mockup/        # Reference mockup (not served)
```

No build step. All JS files use native ES modules (`type="module"`). Dependencies loaded from CDN.

---

## 3. Technology Stack

| Purpose | Library | Delivery |
|---|---|---|
| UI components | **Web Awesome** (wa-*) | CDN |
| Utility CSS | **Tailwind CSS v3** | CDN with custom config |
| Charts | **Highcharts** (+ Highcharts More for advanced types) | CDN |
| CSV parsing | **Papa Parse** | CDN |
| Fonts | Inter + Public Sans | Google Fonts |

**Why no build step?** The output CSVs are fetched at runtime via relative paths. A simple HTTP server (`python -m http.server` from the project root) is the only requirement. File-protocol (`file://`) will not work due to browser CORS restrictions on `fetch()`.

### CSV relative paths (from `frontend/index.html`)
```
../data/output/population.csv
../data/output/employment.csv
../data/output/economy.csv      ← wages.csv + gdp.csv merged client-side
../data/output/housing.csv
../data/output/education.csv
../data/output/health.csv
../data/output/income.csv
../data/output/forecast.csv
../data/output/wages.csv
../data/output/wages_by_industry.csv
../data/output/gdp.csv
../data/output/vintages.json
```

---

## 4. Design System Summary

*(Full spec lives in `Google-Stich-mockup/DESIGN.md`. This section is the implementation contract.)*

### Color Tokens (CSS Custom Properties in `theme.css`)

```css
/* Light mode (default) */
:root {
  --color-primary:           #002c53;
  --color-primary-container: #1a426e;
  --color-secondary:         #006b5f;
  --color-tertiary:          #852300;
  --color-on-tertiary-container: #ff8e6b;

  --surface:                 #f3faff;
  --surface-bright:          #f3faff;
  --surface-container-lowest: #ffffff;
  --surface-container-low:   #e6f6ff;
  --surface-container:       #dbf1fe;
  --surface-container-high:  #d5ecf8;
  --surface-container-highest: #cfe6f2;

  --on-surface:              #071e27;
  --on-surface-variant:      #43474f;
  --outline-variant:         #c3c6d0;
}

/* Dark mode override — applied via [data-theme="dark"] on <html> */
[data-theme="dark"] {
  --color-primary:           #a5c9fd;
  --color-primary-container: #214874;
  --color-secondary:         #70d8c8;

  --surface:                 #071e27;
  --surface-container-lowest: #0d2535;
  --surface-container-low:   #122d3e;
  --surface-container:       #183447;
  --surface-container-high:  #1e3b50;
  --surface-container-highest: #24435a;

  --on-surface:              #dff4ff;
  --on-surface-variant:      #c3c6d0;
  --outline-variant:         rgba(195, 198, 208, 0.15);
}
```

### Typography
- Headlines / display numbers → **Inter** (700–900 weight)
- Chart titles → Inter 600 `1rem`
- Data labels, county names, table text → **Public Sans** 400–500
- Hero KPI number → Inter 900, `3.5rem` (display-lg)
- KPI label → Public Sans 500, `0.875rem`

### The No-Line Rule
Section boundaries are defined by background-color shifts between surface tiers — never `border: 1px solid`. The sole exception is a "ghost border" at `outline-variant` + 15% opacity for accessibility focus rings.

### Elevation / Shadows
- Cards: no box-shadow; use `surface-container-lowest` against `surface` background for perceived lift.
- Floating elements (dropdowns, modals): `box-shadow: 0 12px 40px rgba(7,30,39,0.06)`.

### Highcharts Theming
A shared Highcharts theme object is defined once in `js/charts/theme.js` and applied globally via `Highcharts.setOptions()`. Key overrides:
- `chart.backgroundColor`: `var(--surface-container-lowest)`
- `chart.style.fontFamily`: `'Public Sans', sans-serif`
- `title.style`: Inter 600
- `colors` array: `['#3c608e', '#006b5f', '#852300', '#70d8c8', '#ffb59f', '#a5c9fd', '#ff8e6b', '#8df5e4']`
- `xAxis/yAxis.gridLineColor`: `var(--outline-variant)` at 40% opacity
- `tooltip.backgroundColor`: `rgba(219,241,254,0.85)` + `backdropFilter: blur(16px)` (glassmorphism)
- `legend.itemStyle`: Public Sans, `var(--on-surface-variant)`
- Dark mode: toggled by swapping `backgroundColor` and label colors via `Highcharts.setOptions()` on theme change.

---

## 5. Layout Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  SIDEBAR (fixed, 220px wide)                                    │
│  ┌──────────────────┐  bg: surface-container-low               │
│  │  ARC logo        │                                           │
│  │  ─────────────   │                                           │
│  │  • Population    │  ← active: primary-fixed-dim vertical    │
│  │    Employment    │    pill indicator on left edge            │
│  │    Economy       │                                           │
│  │    Housing       │                                           │
│  │    Education     │                                           │
│  │    Health        │                                           │
│  │    Income        │                                           │
│  │    Forecast      │                                           │
│  │    About         │                                           │
│  │  ─────────────   │                                           │
│  │  🌙 Dark mode    │                                           │
│  └──────────────────┘                                           │
│                                                                 │
│  MAIN CONTENT (flex-1)   bg: surface                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  TOP BAR  (sticky, 64px)   bg: surface / glassmorphism  │   │
│  │  Tab title     [County filter ▼]  [11-Core] [21-Total]  │   │
│  │                                     Vintage: ACS 2024   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  KPI HERO ROW  (2 cards, asymmetric)                    │   │
│  │  bg: surface-container-lowest   rounded-xl              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CHART GRID  (varies per tab — see §7)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Sidebar Navigation
- Implemented with `<wa-menu>` + `<wa-menu-item>` web components.
- Active state: 3px left-edge vertical pill in `primary-fixed-dim` color; item bg `surface-container`.
- Tab switching is JS-driven (no page reload); only the active `<section>` is visible.

### Top Bar County Filter
- `<wa-select multiple placeholder="Select counties…">` with all 21 county options as `<wa-option>`.
- Two `<wa-button>` pills beside it: **"11-County Core"** and **"21-County Total"**.
  - Clicking either clears selection and applies the preset.
  - Active preset button uses `variant="brand"` (filled); the other uses `variant="neutral"` (ghost).
- Filter state lives in `filter.js`; any change dispatches a `filterChange` custom event that all tab modules listen to for re-render.
- **Default on load**: 21-County Total.

### Vintage Badge
Small `<wa-badge>` in the top bar showing e.g. `ACS 2025 · Pop 2023 · Emp 2025`. Populated from `vintages.json`.

---

## 6. Dark Mode

- Toggle: `<wa-icon-button>` in the sidebar footer (moon / sun icon).
- Implementation: toggle `data-theme="dark"` on `<html>`. CSS custom properties cascade automatically.
- Highcharts: on toggle, call `Highcharts.setOptions(darkThemeOverrides)` and re-render all charts.
- Persistence: `localStorage.setItem('theme', 'dark' | 'light')` — restored on page load.
- Web Awesome auto-respects `prefers-color-scheme`; we override with explicit `data-theme`.

---

## 7. Tab Specifications

Each tab section follows the same anatomy:
1. **KPI Hero Row** — 2 `<wa-card>` elements side by side (asymmetric widths welcome)
2. **Chart Grid** — 1–3 Highcharts instances in a CSS grid

### 7.1 Population
**Data:** `population.csv` — keyed on `county_name` + `year`

| KPI | Metric | Source column |
|---|---|---|
| Hero | Total regional population (latest year) | sum `population` |
| Trend | % change since 2010 (weighted avg / computed) | derived from `pct_chg_2010_now` |

**Charts:**
- **Population Trend** (Highcharts line, full-width): one series per selected county, x = year 2000–latest. Optionally a bold "regional total" series.
- **Race Profile** (Highcharts donut): summed raw counts for `race_hispanic`, `race_nh_white`, `race_nh_black`, `race_nh_asian`, `race_nh_other` across selected counties. Labels as percentages.
- **Age Profile** (Highcharts horizontal stacked bar): five age bands (`age_0_19` through `age_65plus`) as % columns per selected county. Or aggregated into a single regional bar if >3 counties selected.

**Layout:** Line chart full-width top; donut + age bar side by side below.

---

### 7.2 Employment
**Data:** `employment.csv` — keyed on `county_name` + `year`

| KPI | Metric | Source column |
|---|---|---|
| Hero | Total regional employment (latest year) | sum `employment` |
| Trend | % change since 2010 | derived from `pct_chg_2010_now` |

**Charts:**
- **Employment Trend** (line, full-width): regional total + individual county series.
- **Industry Mix** (Highcharts stacked horizontal bar): 11 supersector `_pct` columns for each selected county, latest year. Counties as categories on y-axis.

**Layout:** Line chart full-width top; stacked bar full-width below.

---

### 7.3 Economy *(new tab)*
**Data:** `gdp.csv` + `wages.csv` + `wages_by_industry.csv`

| KPI | Metric | Source |
|---|---|---|
| Hero | Regional GDP — latest year, in billions | sum `gdp_thousands` / 1,000,000 |
| Trend | Avg annual wage — latest year | sum `total_annual_wages` / sum `annual_avg_emplvl` from `wages.csv` |

**Charts:**
- **GDP Trend** (Highcharts line, full-width): real GDP in billions (chained 2017 $) for selected counties, 2001–latest.
- **Wages Trend** (Highcharts line): regional average annual pay over time.
- **Wages by Industry** (Highcharts column): `avg_annual_pay` by `supersector`, latest year available.

**Layout:** GDP + Wages trend lines side by side (50/50); industry wage bar full-width below.

---

### 7.4 Housing
**Data:** `housing.csv` + `permits.csv`

| KPI | Metric | Source column |
|---|---|---|
| Hero | Regional median home value (interpolated from bracket counts) | `homeval_*` brackets → client-side median interpolation |
| Trend | Vacancy rate | weighted avg `vacancy_rate` |

*Note: For counties where `homeval_total` is null (ACS 1-yr suppressed), omit from regional median calculation rather than substituting zero.*

**Charts:**
- **Residential Permits** (Highcharts area/column combo): `sf_permits` + `mf_total_permits` stacked, by year, summed across selected counties (from `permits.csv`).
- **Median Home Value by County** (Highcharts horizontal bar): single latest-year snapshot, sorted descending.
- **Tenure Split** (Highcharts donut): `owner_pct` vs `renter_pct`, summed from raw `owner_occupied` + `renter_occupied` counts.

**Layout:** Permits chart full-width top; bar + donut side by side below.

---

### 7.5 Education
**Data:** `education.csv`

| KPI | Metric | Source column |
|---|---|---|
| Hero | Regional avg HS graduation rate (latest GOSA year) | avg `grad_rate_pct` weighted by `cohort_total` |
| Trend | % of adults with bachelor's or higher | sum(`edu_bachelors_only` + `edu_grad_professional`) / sum(`edu_total`) |

**Charts:**
- **Educational Attainment** (Highcharts stacked horizontal bar): 5 attainment levels as % per selected county, sorted by `edu_bachelors_only_pct + edu_grad_professional_pct` descending.
- **Graduation Rate by District** (Highcharts horizontal bar): `grad_rate_pct` per `district_name`, for selected counties, sorted descending. Color-coded: ≥90% secondary (teal), 80–89% neutral, <80% tertiary (coral).

**Layout:** Attainment chart left (60%), grad rate chart right (40%).

---

### 7.6 Health
**Data:** `health.csv`

| KPI | Metric | Source column |
|---|---|---|
| Hero | % population without health insurance | weighted avg `uninsured_pct` by `pop_total` |
| *(single KPI — DPH data may be partial)* | | |

*If DPH columns are populated (non-null `low_birthweight_pct`), surface a second KPI: regional avg low birth weight rate.*

**Charts:**
- **Uninsured Rate by County** (Highcharts bar): `uninsured_pct` × 100, sorted ascending (lower = better), for selected counties.
- **Low Birth Weight vs. Teen Pregnancy** (Highcharts scatter): x = `teen_preg_rate`, y = `low_birthweight_pct`, one point per county. Labeled with county name. Only rendered if DPH data present; otherwise a "data pending" message card.
- **Hospital Discharge Rates** (Highcharts horizontal bar): 6 discharge categories per 100K for the selected regional aggregate (summed counts / summed population × 100,000). Only rendered if DPH data present.

**Layout:** Uninsured bar full-width top; scatter + discharge bar side by side below (conditionally).

---

### 7.7 Income
**Data:** `income.csv`

| KPI | Metric | Source column |
|---|---|---|
| Hero | Regional median household income (interpolated from `hhinc_*` brackets) | `hhinc_lt10k` … `hhinc_200k_plus` → client-side interpolation; top bracket upper bound $250K |
| Trend | Regional poverty rate | sum(`poverty_below`) / sum(`poverty_universe`) × 100 |

**Charts:**
- **Median HH Income by County** (Highcharts horizontal bar): `median_hh_income` per county, sorted descending. Reference line at regional median.
- **Poverty Rate by County** (Highcharts horizontal bar): `poverty_rate_pct` per county, sorted ascending. Color: below 8% = secondary, 8–15% = neutral, >15% = tertiary (coral alert).

**Layout:** Two charts side by side (50/50).

---

### 7.8 2050 Forecast
**Data:** `forecast.csv` + `forecast_sectors.csv`

| KPI | Metric | Source column |
|---|---|---|
| Hero | Projected population net increase 2020–2050 | sum `pop_net_increase` |
| Trend | Projected employment net increase 2020–2050 | sum `emp_net_increase` |

**Charts:**
- **Population Growth by County** (Highcharts combo — column for net increase, line for % increase, dual y-axis): one bar per county showing `pop_net_increase`, overlaid line for `pop_pct_increase`.
- **Employment Growth by County** (same combo style): `emp_net_increase` + `emp_pct_increase`.
- **Sector Employment Forecast** (Highcharts grouped column): from `forecast_sectors.csv`, 2020 vs 2050 employment by `supersector` for selected counties combined.

**Layout:** Population combo chart (50%) + Employment combo chart (50%) top; sector comparison full-width below.

---

### 7.9 About
Static content panel (no charts). Contains:
- ARC logo + description of the dashboard
- Data source citations (matching the original About tab language)
- Link to the original Tableau tool for reference
- Vintage table: reads `vintages.json` and renders a clean table of data freshness dates.

---

## 8. Data Loading Strategy

**`data.js`** exports a single `loadAll()` function that fetches all CSVs in parallel on app init using `Promise.all()`. Papa Parse converts each to an array of row objects. Results are cached in a module-level `Map` so tab switches do not re-fetch.

```
loadAll()
  → fetch all CSVs in parallel
  → parse with Papa Parse (header: true, dynamicTyping: true)
  → store in cache: { population: [...], employment: [...], ... }
  → dispatch 'dataReady' event on window
```

**`filter.js`** listens to `wa-select`'s change event and the two preset buttons. On change, it:
1. Updates the active county set in module state.
2. Dispatches a `filterChange` CustomEvent on `window`.

Each tab module listens for `filterChange` and calls its own `render(countySet)` function, which:
1. Filters the cached rows to the active counties.
2. Recomputes aggregates.
3. Calls `chart.update(newData, true, true)` on the existing Highcharts instance (no full redraw).
4. Updates KPI card inner HTML.

---

## 9. KPI Card Component Pattern

KPI cards are plain HTML (not a Web Awesome component) to allow maximum typography control, but styled consistently:

```html
<div class="kpi-card">
  <p class="kpi-label">Total Population</p>
  <p class="kpi-value">5.2M</p>
  <p class="kpi-trend positive">+36.4% since 2010</p>
</div>
```

- `kpi-value`: Inter 900, `3rem`, `var(--on-surface)`
- `kpi-label`: Public Sans 500, `0.8rem` uppercase tracked, `var(--on-surface-variant)`
- `kpi-trend.positive`: `var(--color-secondary)` with a ▲ prefix
- `kpi-trend.negative`: `var(--color-tertiary)` (coral) with a ▼ prefix

---

## 10. Responsive Considerations

The primary audience is desktop (executive laptop / monitor). Mobile is secondary. Breakpoint strategy:
- ≥1280px: full layout as described (sidebar + main content).
- 768px–1279px: sidebar collapses to icon-only rail; county filter moves to a drawer.
- <768px: top tab bar replaces sidebar; filter in a bottom sheet. Charts stack vertically.

Use Tailwind's `lg:` prefix for breakpoints. Web Awesome's `<wa-drawer>` handles the mobile filter panel.

---

## 11. Serving / Dev Setup

```bash
# From the project root:
python -m http.server 8000
# Then open: http://localhost:8000/frontend/
```

Or use VS Code Live Server pointed at the project root. The frontend assumes it can resolve `../data/output/` relative to its own path.

---

## 12. Implementation Order

1. `theme.css` — color tokens, dark mode overrides
2. `index.html` skeleton — sidebar, top bar, tab panel shells, CDN links
3. `data.js` — CSV loading + caching
4. `filter.js` — county filter state + preset buttons
5. `main.js` — tab routing, dark mode toggle, `dataReady` listener
6. Highcharts base theme (`js/charts/theme.js`)
7. Tabs in priority order: **Population → Employment → Income → Housing → Economy → Education → Health → Forecast → About**
