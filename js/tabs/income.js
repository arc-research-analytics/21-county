// js/tabs/income.js
// Income tab: KPI cards + income bar chart + poverty heat-map table + income distribution.

import * as Data from '../data.js';
import { getSelected, COUNTIES_21, CORE_11 } from '../filter.js';

// ── Module-level chart instances ─────────────────────────────────────────
let incomeChart = null;
let distChart   = null;

// ── HH income brackets for regional median interpolation ─────────────────
// Top bracket is open-ended; $250K used as conventional upper bound.
const BRACKETS = [
  { col: 'hhinc_lt10k',     lo: 0,       hi: 10_000  },
  { col: 'hhinc_10k_15k',   lo: 10_000,  hi: 15_000  },
  { col: 'hhinc_15k_20k',   lo: 15_000,  hi: 20_000  },
  { col: 'hhinc_20k_25k',   lo: 20_000,  hi: 25_000  },
  { col: 'hhinc_25k_30k',   lo: 25_000,  hi: 30_000  },
  { col: 'hhinc_30k_35k',   lo: 30_000,  hi: 35_000  },
  { col: 'hhinc_35k_40k',   lo: 35_000,  hi: 40_000  },
  { col: 'hhinc_40k_45k',   lo: 40_000,  hi: 45_000  },
  { col: 'hhinc_45k_50k',   lo: 45_000,  hi: 50_000  },
  { col: 'hhinc_50k_60k',   lo: 50_000,  hi: 60_000  },
  { col: 'hhinc_60k_75k',   lo: 60_000,  hi: 75_000  },
  { col: 'hhinc_75k_100k',  lo: 75_000,  hi: 100_000 },
  { col: 'hhinc_100k_125k', lo: 100_000, hi: 125_000 },
  { col: 'hhinc_125k_150k', lo: 125_000, hi: 150_000 },
  { col: 'hhinc_150k_200k', lo: 150_000, hi: 200_000 },
  { col: 'hhinc_200k_plus', lo: 200_000, hi: 250_000 },
];

// Short x-axis labels for the distribution column chart (one per BRACKETS entry)
const BRACKET_LABELS = [
  '<$10K', '$10K', '$15K', '$20K', '$25K', '$30K', '$35K', '$40K',
  '$45K',  '$50K', '$60K', '$75K', '$100K', '$125K', '$150K', '$200K+',
];

const C_BLUE = '#1270B3';

// ── Poverty heat-map color scale (OrRd-style, 0–25% range) ────────────────
// 3-stop: light cream → warm orange → dark brownish-red
const POV_STOPS = [
  { t: 0,   rgb: [255, 247, 236] }, // #FFF7EC — very light
  { t: 0.5, rgb: [252, 141,  89] }, // #FC8D59 — warm orange
  { t: 1,   rgb: [127,   0,   0] }, // #7F0000 — dark red
];

function povHeatColor(rate) {
  const t = Math.min(Math.max(rate, 0) / 25, 1);
  let lo = POV_STOPS[0], hi = POV_STOPS[POV_STOPS.length - 1];
  for (let i = 0; i < POV_STOPS.length - 1; i++) {
    if (t <= POV_STOPS[i + 1].t) { lo = POV_STOPS[i]; hi = POV_STOPS[i + 1]; break; }
  }
  const s = lo.t === hi.t ? 0 : (t - lo.t) / (hi.t - lo.t);
  const r = Math.round(lo.rgb[0] + s * (hi.rgb[0] - lo.rgb[0]));
  const g = Math.round(lo.rgb[1] + s * (hi.rgb[1] - lo.rgb[1]));
  const b = Math.round(lo.rgb[2] + s * (hi.rgb[2] - lo.rgb[2]));
  return { bg: `rgb(${r},${g},${b})`, dark: (0.299 * r + 0.587 * g + 0.114 * b) < 140 };
}

// ── Helpers ───────────────────────────────────────────────────────────────
const sumCol = (rows, col) =>
  rows.reduce((s, r) => s + (Number(r[col]) || 0), 0);

function isPresetRegionalSelection(selected) {
  if (selected.length === COUNTIES_21.length) return true;
  if (selected.length !== CORE_11.size) return false;
  return selected.every(n => CORE_11.has(n));
}

/**
 * Interpolate median income from bracket counts summed across selected rows.
 * Uses linear interpolation within the median bracket.
 */
function interpolateMedian(rows) {
  const counts   = BRACKETS.map(b => sumCol(rows, b.col));
  const total    = counts.reduce((s, c) => s + c, 0);
  if (total === 0) return null;

  const halfway  = total / 2;
  let cumulative = 0;
  for (let i = 0; i < BRACKETS.length; i++) {
    const prev = cumulative;
    cumulative += counts[i];
    if (cumulative >= halfway && counts[i] > 0) {
      const { lo, hi } = BRACKETS[i];
      return lo + ((halfway - prev) / counts[i]) * (hi - lo);
    }
  }
  return null;
}

function fmtIncome(n) {
  if (n == null) return '—';
  return '$' + Math.round(n).toLocaleString();
}

function fmtIncomeK(n) {
  if (n == null) return '';
  return n >= 1000 ? `$${Math.round(n / 1000)}K` : `$${Math.round(n)}`;
}

function fmtPct(pct) {
  if (pct == null) return '—';
  return `${pct.toFixed(1)}%`;
}

// ── Public API ────────────────────────────────────────────────────────────

export function init() {
  _lastLayoutMode = null; // force layout reapply on re-init
  if (incomeChart) { incomeChart.destroy(); incomeChart = null; }
  if (distChart)   { distChart.destroy();   distChart   = null; }

  incomeChart = Highcharts.chart('chart-income-county', buildIncomeOptions());
  distChart   = Highcharts.chart('chart-income-dist',   buildDistOptions());

  const povEl = document.getElementById('chart-poverty-county');
  if (povEl) povEl.innerHTML = '';

  render(getSelected());
}

export function render(selectedCounties) {
  const rows     = Data.get('income');
  const selected = [...selectedCounties];

  if (!incomeChart) return;

  document.getElementById('kpi-1-label').textContent = 'Regional Median Income';
  document.getElementById('kpi-2-label').textContent = 'Poverty Rate';

  // ── Vintage / scope subtitles ─────────────────────────────────────────────
  const acsYear   = Data.getVintages().acs_vintage;
  const acsPrefix = acsYear ? `ACS ${acsYear} estimate` : 'Latest ACS estimate';
  const scopeTag  = selected.length === 0 ? ''
    : selected.length <= 3               ? ` · ${selected.join(', ')}`
    : selected.length === COUNTIES_21.length && isPresetRegionalSelection(selected)
                                         ? ' · 21-county region'
    : isPresetRegionalSelection(selected) ? ' · 11-county core'
    :                                       ` · ${selected.length} counties`;

  document.getElementById('income-chart-sub').textContent = acsPrefix + scopeTag;

  // ── Layout: hide comparison panels when only one county is selected ──────
  applyIncomeLayout(selected.length);

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!selected.length) {
    document.getElementById('kpi-1-value').textContent = '—';
    document.getElementById('kpi-1-sub').textContent   = 'No counties selected';
    document.getElementById('kpi-2-value').textContent = '—';
    document.getElementById('kpi-2-value').className   = 'kpi-value';
    document.getElementById('kpi-2-sub').textContent   = '';

    incomeChart.xAxis[0].setCategories([], false);
    incomeChart.series[0].setData([], false);
    incomeChart.yAxis[0].update({ plotLines: [] }, false);
    incomeChart.redraw();
    renderPovertyTable([], acsPrefix, scopeTag);
    document.getElementById('income-dist-sub').textContent = acsPrefix;
    distChart.series[0].setData([], false);
    distChart.yAxis[0].update({ plotLines: [] }, false);
    distChart.redraw();
    return;
  }

  if (!rows.length) return;

  const selectedRows = rows.filter(r => selected.includes(r.county_name));

  // ── KPI 1: Regional median income ────────────────────────────────────────
  // Single county → use the published ACS median directly (more accurate).
  // Multi-county  → interpolate from summed bracket counts.
  const regionalMedian = selected.length === 1
    ? (selectedRows[0]?.median_hh_income ?? null)
    : interpolateMedian(selectedRows);

  const countySub = selected.length === 1 ? `${selected[0]} County`
    : selected.length <= 3                ? selected.join(', ')
    : selected.length === COUNTIES_21.length && isPresetRegionalSelection(selected)
                                          ? '21-county region'
    : isPresetRegionalSelection(selected) ? '11-county core'
    :                                       `${selected.length} counties`;

  document.getElementById('kpi-1-value').textContent = fmtIncome(regionalMedian);
  document.getElementById('kpi-1-sub').textContent   =
    `${acsYear ?? 'Latest'} estimate · ${countySub}`;

  // ── KPI 2: Regional poverty rate ──────────────────────────────────────────
  const totalBelow    = sumCol(selectedRows, 'poverty_below');
  const totalUniverse = sumCol(selectedRows, 'poverty_universe');
  const povertyRate   = totalUniverse > 0 ? (totalBelow / totalUniverse) * 100 : null;

  document.getElementById('kpi-2-value').textContent = fmtPct(povertyRate);
  document.getElementById('kpi-2-value').className   = 'kpi-value';
  document.getElementById('kpi-2-sub').textContent   =
    `${acsYear ?? 'Latest'} estimate · weighted aggregate`;

  // ── Income by county bar chart ────────────────────────────────────────────
  // Sort ascending → Highcharts renders bottom-to-top, so highest income ends at top.
  const incSorted = [...selectedRows]
    .filter(r => r.median_hh_income != null)
    .sort((a, b) => a.median_hh_income - b.median_hh_income);

  incomeChart.xAxis[0].setCategories(incSorted.map(r => r.county_name), false);
  incomeChart.series[0].setData(incSorted.map(r => r.median_hh_income), false);
  incomeChart.yAxis[0].update({
    plotLines: regionalMedian ? [{
      id:        'regional-median',
      value:     regionalMedian,
      color:     '#636EA0',
      dashStyle: 'ShortDash',
      width:     1.5,
      label: {
        text:  `Median: ${fmtIncome(regionalMedian)}`,
        rotation: 0,
        align:    'right',
        x:        -6,
        style: {
          color:      '#636EA0',
          fontSize:   '11px',
          fontFamily: "'DINPro', sans-serif",
          fontWeight: '600',
        },
      },
      zIndex: 5,
    }] : [],
  }, false);
  incomeChart.redraw();

  // ── Poverty rate heat-map table ───────────────────────────────────────────
  renderPovertyTable(selectedRows, acsPrefix, scopeTag);

  // ── Income bracket distribution column chart ──────────────────────────────
  // Sum bracket counts across all selected counties, normalize to %.
  const bracketCounts = BRACKETS.map(b => sumCol(selectedRows, b.col));
  const bracketTotal  = bracketCounts.reduce((s, c) => s + c, 0);
  const bracketPcts   = bracketTotal > 0
    ? bracketCounts.map(c => (c / bracketTotal) * 100)
    : bracketCounts.map(() => 0);

  document.getElementById('income-dist-sub').textContent = acsPrefix + scopeTag;
  distChart.series[0].setData(bracketPcts, false);

  // Overlay a plotLine at the regional median — finds which bracket it falls in.
  let medianPlotLine = [];
  if (regionalMedian != null) {
    // x position = index of the bracket containing the median (0-based category axis)
    const medIdx = BRACKETS.findIndex(b => regionalMedian < b.hi);
    const idx    = medIdx >= 0 ? medIdx : BRACKETS.length - 1;
    medianPlotLine = [{
      id:        'dist-median',
      value:     idx,
      color:     '#636EA0',
      dashStyle: 'ShortDash',
      width:     1.5,
      label: {
        text:     `Median: ${fmtIncome(regionalMedian)}`,
        rotation: 0,
        align:    'right',
        x:        -6,
        y:        14,
        style: {
          color:      '#636EA0',
          fontSize:   '10px',
          fontFamily: "'DINPro', sans-serif",
          fontWeight: '600',
        },
      },
      zIndex: 5,
    }];
  }
  distChart.xAxis[0].update({ plotLines: medianPlotLine }, false);
  distChart.redraw();
}

// ── Layout toggle: single vs. multi-county ───────────────────────────────
// Single county: comparison charts (bar + poverty table) are meaningless with
// one data point, so hide them and let the distribution chart fill the space.

let _lastLayoutMode = null; // 'single' | 'multi' | 'empty'

function applyIncomeLayout(countyCount) {
  const mode = countyCount <= 1 ? 'single' : 'multi';
  if (mode === _lastLayoutMode) return; // nothing to do
  _lastLayoutMode = mode;

  const grid     = document.getElementById('income-grid');
  const barCard  = document.getElementById('income-bar-card');
  const povCard  = document.getElementById('income-poverty-card');

  if (mode === 'single') {
    // Distribution chart fills the full right column which becomes full-width
    grid.style.gridTemplateColumns = '1fr';
    barCard.style.display  = 'none';
    povCard.style.display  = 'none';
    setTimeout(() => distChart?.reflow(), 0);
  } else {
    grid.style.gridTemplateColumns = '3fr 2fr';
    barCard.style.display  = '';
    povCard.style.display  = '';
    setTimeout(() => { incomeChart?.reflow(); distChart?.reflow(); }, 0);
  }
}

// ── Poverty heat-map table ────────────────────────────────────────────────

function renderPovertyTable(rows, acsPrefix, scopeTag) {
  const container = document.getElementById('chart-poverty-county');
  if (!container) return;

  document.getElementById('poverty-chart-sub').textContent = acsPrefix + (scopeTag ?? '');

  if (!rows.length) {
    container.innerHTML =
      `<p style="padding:1rem;font-size:13px;color:var(--on-surface-variant);font-family:'DINPro',sans-serif">No counties selected</p>`;
    return;
  }

  const sorted = [...rows]
    .filter(r => r.poverty_rate_pct != null)
    .sort((a, b) => b.poverty_rate_pct - a.poverty_rate_pct);

  // ── Outer wrapper fills the flex-1 container ──────────────────────────────
  const wrapper = document.createElement('div');
  wrapper.style.cssText = 'height:100%;display:flex;flex-direction:column;padding-top:10px;';

  // ── Column header ─────────────────────────────────────────────────────────
  const header = document.createElement('div');
  header.style.cssText = [
    'display:flex',
    'justify-content:space-between',
    'align-items:center',
    'padding:0 10px 8px 8px',
    "font-size:11px;font-family:'DINPro',sans-serif",
    'font-weight:500',
    'color:var(--on-surface-variant)',
    'text-transform:uppercase',
    'letter-spacing:0.05em',
    'border-bottom:1.5px solid var(--outline-variant)',
    'flex-shrink:0',
  ].join(';');
  header.innerHTML = '<span>County</span><span>Poverty Rate</span>';
  wrapper.appendChild(header);

  // ── Rows container: flex column, distributes height evenly (no scroll) ────
  const rowsContainer = document.createElement('div');
  rowsContainer.style.cssText = [
    'flex:1',
    'min-height:0',
    'display:flex',
    'flex-direction:column',
    'gap:2px',
    'padding-top:6px',
    'overflow-y:auto',
  ].join(';');

  sorted.forEach(r => {
    const { bg, dark } = povHeatColor(r.poverty_rate_pct);
    const fg = dark ? '#ffffff' : '#2a1000';

    const row = document.createElement('div');
    row.dataset.county = r.county_name;
    row.style.cssText = [
      'flex:1',
      'min-height:14px',
      `background:${bg}`,
      'border-radius:3px',
      'display:flex',
      'justify-content:space-between',
      'align-items:center',
      'padding:0 10px 0 8px',
      'cursor:default',
      'transition:filter 80ms',
    ].join(';');

    const nameEl = document.createElement('span');
    nameEl.style.cssText = `font-size:12px;font-family:'DINPro',sans-serif;color:${fg};`;
    nameEl.textContent = r.county_name;

    const rateEl = document.createElement('span');
    rateEl.style.cssText = `font-size:12px;font-family:'DINPro',sans-serif;font-weight:600;color:${fg};`;
    rateEl.textContent = `${r.poverty_rate_pct.toFixed(1)}%`;

    row.appendChild(nameEl);
    row.appendChild(rateEl);

    // ── Cross-highlight: hovering a table row highlights the income bar ───
    row.addEventListener('mouseenter', () => {
      row.style.filter = 'brightness(0.85)';
      if (incomeChart) {
        const pt = incomeChart.series[0]?.points?.find(p => p.category === r.county_name);
        if (pt) {
          pt.setState('hover');
          incomeChart.tooltip.refresh(pt);
        }
      }
    });
    row.addEventListener('mouseleave', () => {
      row.style.filter = '';
      if (incomeChart) {
        const pt = incomeChart.series[0]?.points?.find(p => p.category === r.county_name);
        if (pt) pt.setState('');
        incomeChart.tooltip.hide();
      }
    });

    rowsContainer.appendChild(row);
  });

  wrapper.appendChild(rowsContainer);
  container.innerHTML = '';
  container.appendChild(wrapper);
}

// ── Chart option factories ────────────────────────────────────────────────

function buildIncomeOptions() {
  return {
    chart: { type: 'bar' },
    title:    { text: '' },
    subtitle: { text: '' },
    xAxis: {
      categories: [],
      labels: { style: { fontSize: '12px', fontFamily: "'DINPro', sans-serif" } },
    },
    yAxis: {
      title:      { text: '' },
      plotLines:  [],
      endOnTick:  false,
      maxPadding: 0.05,
      labels: {
        formatter() {
          return this.value >= 1000
            ? `$${Math.round(this.value / 1000)}K`
            : `$${this.value}`;
        },
      },
    },
    plotOptions: {
      bar: {
        borderWidth:  0,
        borderRadius: 2,
        color:        C_BLUE,
        // ── Cross-highlight: hovering a bar highlights the poverty table row ─
        point: {
          events: {
            mouseOver() {
              const row = document.querySelector(
                `#chart-poverty-county [data-county="${this.category}"]`
              );
              if (row) row.style.filter = 'brightness(0.85)';
            },
            mouseOut() {
              const row = document.querySelector(
                `#chart-poverty-county [data-county="${this.category}"]`
              );
              if (row) row.style.filter = '';
            },
          },
        },
        dataLabels: {
          enabled:  true,
          inside:   true,
          align:    'right',
          formatter() { return fmtIncomeK(this.y); },
          style: {
            fontFamily:  "'DINPro', sans-serif",
            fontSize:    '11px',
            fontWeight:  '500',
            textOutline: 'none',
            color:       '#ffffff',
          },
        },
      },
    },
    legend:  { enabled: false },
    tooltip: {
      followPointer: true,
      shadow: false,
      formatter() {
        return `<b>${this.x}</b><br/>Median HH Income: <b>${fmtIncome(this.y)}</b>`;
      },
    },
    series: [{ name: 'Median HH Income', data: [] }],
  };
}

function buildDistOptions() {
  return {
    chart: { type: 'column' },
    title:    { text: '' },
    subtitle: { text: '' },
    xAxis: {
      categories: BRACKET_LABELS,
      plotLines:  [],
      labels: {
        rotation: -45,
        align:    'right',
        style: { fontSize: '10px', fontFamily: "'DINPro', sans-serif" },
      },
    },
    yAxis: {
      title: { text: '' },
      labels: {
        formatter() { return `${this.value.toFixed(0)}%`; },
        style: { fontSize: '10px' },
      },
    },
    plotOptions: {
      column: {
        borderWidth:  0,
        borderRadius: 1,
        color:        C_BLUE,
        pointPadding: 0.05,
        groupPadding: 0,
        dataLabels:   { enabled: false },
      },
    },
    legend:  { enabled: false },
    tooltip: {
      followPointer: true,
      shadow: false,
      formatter() {
        return `<b>${this.x}</b><br/>Share of households: <b>${this.y.toFixed(1)}%</b>`;
      },
    },
    series: [{ name: 'Households', data: [] }],
  };
}
