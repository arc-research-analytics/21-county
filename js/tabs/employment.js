// js/tabs/employment.js
// Employment tab: KPI cards + 2 Highcharts (trend line, industry mix stacked bar).

import * as Data from '../data.js';
import { getSelected, COUNTIES_21, CORE_11 } from '../filter.js';

// ── Module-level chart instances ──────────────────────────────────────────
let trendChart    = null;
let industryChart = null;

// ── Supersector definitions — key matches CSV column name ─────────────────
// Order controls stacking order (bottom → top in bar chart).
const SUPERSECTORS = [
  { key: 'Trade, transportation and utilities', label: 'Trade & Transport',       color: '#1270B3' },
  { key: 'Professional and business services',  label: 'Professional & Business', color: '#1AAFA6' },
  { key: 'Education and health services',       label: 'Education & Health',      color: '#42ADD3' },
  { key: 'Leisure and hospitality',             label: 'Leisure & Hospitality',   color: '#EE575D' },
  { key: 'Manufacturing',                       label: 'Manufacturing',            color: '#636EA0' },
  { key: 'Construction',                        label: 'Construction',             color: '#678539' },
  { key: 'Public administration',               label: 'Public Admin',             color: '#98AE3E' },
  { key: 'Financial activities',                label: 'Financial',                color: '#FDB713' },
  { key: 'Other services',                      label: 'Other Services',           color: '#C47B5A' },
  { key: 'Information',                         label: 'Information',              color: '#5B9BD5' },
  { key: 'Natural resources and mining',        label: 'Natural Resources',        color: '#A0A0A0' },
];

const TREND_LINE_COLORS = ['#1270B3', '#1AAFA6', '#42ADD3', '#EE575D', '#636EA0', '#678539'];

// ── Helpers ───────────────────────────────────────────────────────────────
const sumCol = (rows, col) =>
  rows.reduce((s, r) => s + (Number(r[col]) || 0), 0);

function isPresetRegionalSelection(selected) {
  if (selected.length === COUNTIES_21.length) return true;
  if (selected.length !== CORE_11.size) return false;
  return selected.every(n => CORE_11.has(n));
}

function fmtEmp(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}

function fmtPct(pct) {
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}

// ── Public API ────────────────────────────────────────────────────────────

export function init() {
  if (trendChart)    { trendChart.destroy();    trendChart    = null; }
  if (industryChart) { industryChart.destroy(); industryChart = null; }

  trendChart    = Highcharts.chart('chart-emp-trend',    buildTrendOptions());
  industryChart = Highcharts.chart('chart-emp-industry', buildIndustryOptions());

  render(getSelected());
}

export function render(selectedCounties) {
  const rows     = Data.get('employment');
  const selected = [...selectedCounties];

  if (!trendChart) return;

  document.getElementById('kpi-1-label').textContent = 'Total Employment';
  document.getElementById('kpi-2-label').textContent = 'Growth Since 2000';

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!selected.length) {
    document.getElementById('kpi-1-value').textContent = '—';
    document.getElementById('kpi-1-sub').textContent   = 'No counties selected';
    const growthEl = document.getElementById('kpi-2-value');
    growthEl.textContent = '—';
    growthEl.className   = 'kpi-value';
    document.getElementById('kpi-2-sub').textContent = '';

    while (trendChart.series.length > 0)    trendChart.series[0].remove(false);
    trendChart.redraw();
    industryChart.xAxis[0].setCategories([], false);
    while (industryChart.series.length > 0) industryChart.series[0].remove(false);
    industryChart.redraw();
    return;
  }

  if (!rows.length) return;

  const years      = [...new Set(rows.map(r => r.year))].sort((a, b) => a - b);
  const latestYear = years[years.length - 1];

  const latestRows = rows.filter(r => r.year === latestYear && selected.includes(r.county_name));
  const rows2000   = rows.filter(r => r.year === 2000        && selected.includes(r.county_name));

  // ── KPI 1: Total employment ───────────────────────────────────────────────
  const totalEmp = sumCol(latestRows, 'employment');
  const emp2000  = sumCol(rows2000,   'employment');
  const growth   = emp2000 > 0 ? ((totalEmp - emp2000) / emp2000) * 100 : null;

  const countySub = selected.length === 1 ? `${selected[0]} County`
    : selected.length <= 3                ? selected.join(', ')
    : selected.length === COUNTIES_21.length && isPresetRegionalSelection(selected)
                                          ? '21-county region'
    : isPresetRegionalSelection(selected) ? '11-county core'
    :                                       `${selected.length} counties`;

  document.getElementById('kpi-1-value').textContent = fmtEmp(totalEmp);
  document.getElementById('kpi-1-sub').textContent   = `${latestYear} estimate · ${countySub}`;

  // ── KPI 2: Growth since 2000 ──────────────────────────────────────────────
  const growthEl = document.getElementById('kpi-2-value');
  if (growth !== null) {
    growthEl.textContent = fmtPct(growth);
    growthEl.className   = `kpi-value ${growth >= 0 ? 'positive' : 'negative'}`;
  } else {
    growthEl.textContent = '—';
    growthEl.className   = 'kpi-value';
  }
  document.getElementById('kpi-2-sub').textContent =
    emp2000 > 0
      ? `${fmtEmp(emp2000)} in 2000 → ${fmtEmp(totalEmp)} in ${latestYear}`
      : '';

  // ── Trend line chart ──────────────────────────────────────────────────────
  const trendSeries = [];

  if (selected.length <= 6) {
    // Individual county lines
    selected.forEach((name, i) => {
      const lineColor = TREND_LINE_COLORS[i % TREND_LINE_COLORS.length];
      trendSeries.push({
        name,
        type:      'line',
        data:      years.map(yr => {
          const r = rows.find(x => x.year === yr && x.county_name === name);
          return r ? [yr, r.employment] : [yr, null];
        }),
        lineWidth: selected.length === 1 ? 2.5 : 2,
        color:     lineColor,
        marker:    { enabled: false },
        showInLegend: true,
        enableMouseTracking: true,
        dataLabels: {
          enabled:      selected.length > 1,
          allowOverlap: false,
          crop:         false,
          align:        'right',
          x:            -8,
          style: {
            color:       lineColor,
            fontFamily:  "'DINPro', sans-serif",
            fontSize:    '11px',
            fontWeight:  '600',
            textOutline: 'none',
          },
          formatter() {
            const data = this.series.options.data || [];
            for (let idx = data.length - 1; idx >= 0; idx -= 1) {
              const point = data[idx];
              const x = Array.isArray(point) ? point[0] : point?.x;
              const y = Array.isArray(point) ? point[1] : point?.y;
              if (y !== null && y !== undefined) {
                return this.x === x ? this.series.name : null;
              }
            }
            return null;
          },
        },
      });
    });
  } else {
    // Collapse to one combined total line for dense selections
    const regionalData = years.map(yr => {
      const s = rows
        .filter(r => r.year === yr && selected.includes(r.county_name))
        .reduce((acc, r) => acc + (r.employment || 0), 0);
      return [yr, s];
    });
    trendSeries.push({
      name:      isPresetRegionalSelection(selected) ? 'Regional Total' : 'Selected total',
      type:      'line',
      data:      regionalData,
      lineWidth: 3,
      color:     '#1270B3',
      marker:    { enabled: false },
      zIndex:    5,
    });
  }

  while (trendChart.series.length > 0) trendChart.series[0].remove(false);
  trendSeries.forEach(s => trendChart.addSeries(s, false));
  trendChart.redraw();

  // ── Industry mix stacked bar ──────────────────────────────────────────────
  // ≤11 counties → individual row per county.
  // >11 counties → collapse to one aggregate row (21-county view is unreadable
  //               as individual bars; a single regional profile is more useful).
  const INDIVIDUAL_THRESHOLD = 11;
  const showIndividual = selected.length <= INDIVIDUAL_THRESHOLD;

  const aggregateLabel = isPresetRegionalSelection(selected)
    ? (selected.length === COUNTIES_21.length ? '21-County Region' : '11-County Core')
    : `${selected.length} Selected Counties`;

  const categories = showIndividual ? [...selected] : [aggregateLabel];

  const industrySeries = SUPERSECTORS.map(sector => ({
    name:  sector.label,
    color: sector.color,
    data:  categories.map(cat => {
      const countyList = showIndividual ? [cat] : selected;
      const countyRows = latestRows.filter(r => countyList.includes(r.county_name));
      return sumCol(countyRows, sector.key);
    }),
  }));

  industryChart.xAxis[0].setCategories(categories, false);
  while (industryChart.series.length > 0) industryChart.series[0].remove(false);
  industrySeries.forEach(s => industryChart.addSeries(s, false));
  industryChart.redraw();

  const vintages = Data.getVintages();
  const yearLabel = vintages.employment_latest_year ?? 'Latest year';
  const empQ      = vintages.employment_latest_quarter;
  const partial   = empQ && empQ < 4 ? ` (Q1–Q${empQ} avg)` : '';
  const aggNote   = showIndividual ? '' : ' · regional aggregate';
  document.getElementById('emp-industry-sub').textContent =
    `${yearLabel}${partial} · share of total employment by sector${aggNote}`;
}

// ── Chart option factories ────────────────────────────────────────────────

function buildTrendOptions() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const axisLine = isDark ? 'rgba(195,198,208,0.20)' : 'rgba(195,198,208,0.55)';

  return {
    chart: {
      type:   'line',
      margin: [16, 20, 46, 64],
    },
    title:    { text: '' },
    subtitle: { text: '' },
    xAxis: {
      title: { text: '' },
      tickInterval: 5,
      crosshair: {
        color:     isDark ? 'rgba(122, 184, 228, 0.9)' : 'rgba(9, 64, 112, 0.55)',
        dashStyle: 'Dot',
        width:     isDark ? 2 : 1,
      },
      labels: { formatter() { return this.value; } },
    },
    yAxis: {
      title: { text: '' },
      min: 0,
      lineWidth: 1,
      lineColor: axisLine,
      labels: {
        formatter() {
          const v = this.value;
          if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
          if (v >= 1_000)     return `${Math.round(v / 1_000)}K`;
          return v;
        },
      },
    },
    legend: { enabled: false },
    tooltip: {
      shared: true,
      shadow: false,
      formatter() {
        const fmtVal = v => Math.round(v).toLocaleString();
        // If this year is the partial latest year, note the quarter range.
        // Vintages are read per-render so the tooltip stays in sync with data.
        const vint      = Data.getVintages();
        const partialY  = (vint.employment_latest_quarter && vint.employment_latest_quarter < 4)
                          ? vint.employment_latest_year : null;
        const partialQ  = vint.employment_latest_quarter;
        const partialNote = this.x === partialY
          ? `<br/><span style="opacity:0.75; font-size:0.85em">Q1–Q${partialQ} avg · partial year</span>`
          : '';
        if (this.points?.length) {
          const points = this.points
            .filter(p => p.y !== null && p.y !== undefined)
            .sort((a, b) => b.y - a.y);
          const lines = points.map(p =>
            `<span style="color:${p.color}; font-weight:600">${p.series.name}</span>: <b>${fmtVal(p.y)}</b>`
          );
          if (points.length > 1) {
            const total = points.reduce((acc, p) => acc + p.y, 0);
            lines.push(
              `${isPresetRegionalSelection([...getSelected()]) ? 'Regional Total' : 'Selected total'}: <b>${fmtVal(total)}</b>`
            );
          }
          return `<b>${this.x}</b><br/>${lines.join('<br/>')}${partialNote}`;
        }
        return `<b>${this.series.name}</b><br/>${this.x}: <b>${Math.round(this.y).toLocaleString()}</b>${partialNote}`;
      },
    },
    series: [],
  };
}

function buildIndustryOptions() {
  return {
    chart: {
      type: 'bar',
    },
    title:    { text: '' },
    subtitle: { text: '' },
    xAxis: {
      categories: [],
      labels: {
        style: { fontSize: '12px', fontFamily: "'DINPro', sans-serif" },
      },
    },
    yAxis: {
      title:          { text: '' },
      labels:         { format: '{value}%' },
      reversedStacks: false,
    },
    plotOptions: {
      bar: {
        stacking:    'percent',
        borderWidth: 0,
        borderRadius: 0,
        dataLabels:  { enabled: false },
      },
    },
    legend: {
      layout:        'vertical',
      align:         'right',
      verticalAlign: 'middle',
      itemStyle: {
        fontFamily: "'DINPro', sans-serif",
        fontSize:   '11px',
        fontWeight: '400',
      },
      itemMarginBottom: 4,
      symbolRadius:     2,
    },
    tooltip: {
      shadow: false,
      formatter() {
        return `<b>${this.x}</b><br/>` +
          `<span style="color:${this.color}">${this.series.name}</span>: ` +
          `<b>${this.percentage.toFixed(1)}%</b> ` +
          `(${Math.round(this.y).toLocaleString()} jobs)`;
      },
    },
    series: [],
  };
}
