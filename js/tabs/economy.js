// js/tabs/economy.js
// Economy tab: KPI cards (GDP level, GDP real growth since 2001)
//            + avg pay trend line + avg pay by sector bar.

import * as Data from '../data.js';
import { getSelected, COUNTIES_21, CORE_11 } from '../filter.js';

// ── Module-level chart instances ──────────────────────────────────────────
let payTrendChart = null;
let payChart      = null;

// ── Supersector definitions (keys match wages_by_industry.csv) ────────────
// Public sector is an aggregate of QCEW own_codes 1+2+3 (Federal/State/Local gov)
// produced by the QCEW fetcher; it sits alongside the 11 private supersectors.
const SUPERSECTORS = [
  { key: 'Trade, transportation and utilities', label: 'Trade & Transport',       color: '#1270B3' },
  { key: 'Professional and business services',  label: 'Professional & Business', color: '#1AAFA6' },
  { key: 'Education and health services',       label: 'Education & Health',      color: '#42ADD3' },
  { key: 'Leisure and hospitality',             label: 'Leisure & Hospitality',   color: '#EE575D' },
  { key: 'Manufacturing',                       label: 'Manufacturing',            color: '#636EA0' },
  { key: 'Construction',                        label: 'Construction',             color: '#678539' },
  { key: 'Public sector',                       label: 'Public Sector',            color: '#6A4C93' },
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

function fmtDollarsBig(n) {
  if (n >= 1_000_000_000_000) return `$${(n / 1_000_000_000_000).toFixed(2)}T`;
  if (n >= 1_000_000_000)     return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000)         return `$${(n / 1_000_000).toFixed(0)}M`;
  if (n >= 1_000)             return `$${(n / 1_000).toFixed(0)}K`;
  return `$${Math.round(n).toLocaleString()}`;
}

const fmtPay = n => `$${Math.round(n).toLocaleString()}`;
const fmtPct = p => `${p >= 0 ? '+' : ''}${p.toFixed(1)}%`;

function countySub(selected) {
  if (selected.length === 1) return `${selected[0]} County`;
  if (selected.length <= 3)  return selected.join(', ');
  if (selected.length === COUNTIES_21.length && isPresetRegionalSelection(selected)) return '21-county region';
  if (isPresetRegionalSelection(selected)) return '11-county core';
  return `${selected.length} counties`;
}

// ── Public API ────────────────────────────────────────────────────────────
export function init() {
  if (payTrendChart) { payTrendChart.destroy(); payTrendChart = null; }
  if (payChart)      { payChart.destroy();      payChart      = null; }

  payTrendChart = Highcharts.chart('chart-econ-paytrend', buildPayTrendOptions());
  payChart      = Highcharts.chart('chart-econ-pay',      buildPayOptions());

  render(getSelected());
}

export function render(selectedCounties) {
  const gdpRows  = Data.get('gdp');
  const wageRows = Data.get('wages');
  const indRows  = Data.get('wages_by_industry');
  const selected = [...selectedCounties];

  if (!payTrendChart) return;

  document.getElementById('kpi-1-label').textContent = 'Regional GDP';
  document.getElementById('kpi-2-label').textContent = 'Real GDP Growth Since 2001';

  // ── Empty state ──────────────────────────────────────────────────────────
  if (!selected.length) {
    document.getElementById('kpi-1-value').textContent = '—';
    document.getElementById('kpi-1-sub').textContent   = 'No counties selected';
    document.getElementById('kpi-2-value').textContent = '—';
    document.getElementById('kpi-2-sub').textContent   = '';
    document.getElementById('kpi-2-value').className   = 'kpi-value';
    while (payTrendChart.series.length > 0) payTrendChart.series[0].remove(false);
    payTrendChart.redraw();
    payChart.xAxis[0].setCategories([], false);
    while (payChart.series.length > 0) payChart.series[0].remove(false);
    payChart.redraw();
    return;
  }

  if (!gdpRows.length || !wageRows.length) return;

  const sub = countySub(selected);

  // ── KPI 1: Regional GDP (latest year, level) ─────────────────────────────
  const gdpYears   = [...new Set(gdpRows.map(r => r.year))].sort((a, b) => a - b);
  const gdpLatest  = gdpYears[gdpYears.length - 1];
  const gdpStart   = gdpYears[0];
  const gdpLatestRows = gdpRows.filter(r => r.year === gdpLatest && selected.includes(r.county_name));
  const gdpStartRows  = gdpRows.filter(r => r.year === gdpStart  && selected.includes(r.county_name));
  const totalGdp  = sumCol(gdpLatestRows, 'gdp_thousands') * 1000;
  const startGdp  = sumCol(gdpStartRows,  'gdp_thousands') * 1000;
  const gdpGrowth = startGdp > 0 ? ((totalGdp - startGdp) / startGdp) * 100 : null;

  document.getElementById('kpi-1-value').textContent = fmtDollarsBig(totalGdp);
  document.getElementById('kpi-1-sub').textContent   = `${gdpLatest} · ${sub}`;

  // ── KPI 2: Real GDP growth since 2001 ────────────────────────────────────
  const kpi2El = document.getElementById('kpi-2-value');
  if (gdpGrowth !== null) {
    kpi2El.textContent = fmtPct(gdpGrowth);
    kpi2El.className   = `kpi-value ${gdpGrowth >= 0 ? 'positive' : 'negative'}`;
    document.getElementById('kpi-2-sub').textContent =
      `${fmtDollarsBig(startGdp)} in ${gdpStart} → ${fmtDollarsBig(totalGdp)} in ${gdpLatest}`;
  } else {
    kpi2El.textContent = '—';
    kpi2El.className   = 'kpi-value';
    document.getElementById('kpi-2-sub').textContent = '';
  }

  // ── Avg annual pay trend line (QCEW, 2015–latest) ────────────────────────
  // Regional aggregation: Σ total_annual_wages / Σ annual_avg_emplvl per year
  // (linear — correct regardless of county-count). County-level lines use the
  // per-county avg_annual_pay directly.
  const wageYears  = [...new Set(wageRows.map(r => r.year))].sort((a, b) => a - b);
  const wageLatest = wageYears[wageYears.length - 1];

  const trendSeries = [];
  if (selected.length <= 6) {
    selected.forEach((name, i) => {
      const lineColor = TREND_LINE_COLORS[i % TREND_LINE_COLORS.length];
      trendSeries.push({
        name,
        type:      'line',
        data:      wageYears.map(yr => {
          const r = wageRows.find(x => x.year === yr && x.county_name === name);
          return r && r.avg_annual_pay ? [yr, Number(r.avg_annual_pay)] : [yr, null];
        }),
        lineWidth: selected.length === 1 ? 2.5 : 2,
        color:     lineColor,
        marker:    { enabled: false },
        showInLegend: true,
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
    const regionalData = wageYears.map(yr => {
      const rows = wageRows.filter(r => r.year === yr && selected.includes(r.county_name));
      const w = sumCol(rows, 'total_annual_wages');
      const e = sumCol(rows, 'annual_avg_emplvl');
      return [yr, e > 0 ? w / e : null];
    });
    trendSeries.push({
      name:      isPresetRegionalSelection(selected) ? 'Regional Avg' : 'Selected avg',
      type:      'line',
      data:      regionalData,
      lineWidth: 3,
      color:     '#1270B3',
      marker:    { enabled: false },
      zIndex:    5,
    });
  }

  while (payTrendChart.series.length > 0) payTrendChart.series[0].remove(false);
  trendSeries.forEach(s => payTrendChart.addSeries(s, false));
  payTrendChart.redraw();

  // ── Avg pay by sector (horizontal bars, sorted desc) ─────────────────────
  const latestIndRows = indRows.filter(
    r => r.year === wageLatest && selected.includes(r.county_name)
  );

  const sectorData = SUPERSECTORS.map(sec => {
    const rows = latestIndRows.filter(r => r.supersector === sec.key);
    const w = sumCol(rows, 'total_annual_wages');
    const e = sumCol(rows, 'annual_avg_emplvl');
    return {
      label: sec.label,
      color: sec.color,
      pay:   e > 0 ? w / e : null,
      wages: w,
      emp:   e,
    };
  })
    .filter(d => d.pay !== null && d.pay > 0)
    .sort((a, b) => b.pay - a.pay);

  const categories = sectorData.map(d => d.label);
  const pointData  = sectorData.map(d => ({
    y:     d.pay,
    color: d.color,
    wages: d.wages,
    emp:   d.emp,
  }));

  payChart.xAxis[0].setCategories(categories, false);
  while (payChart.series.length > 0) payChart.series[0].remove(false);
  payChart.addSeries({
    name: 'Avg Annual Pay',
    data: pointData,
  }, false);
  payChart.redraw();

  document.getElementById('econ-pay-sub').textContent =
    `${wageLatest} · private supersectors + public-sector aggregate · ${sub}`;
}

// ── Chart option factories ────────────────────────────────────────────────

function buildPayTrendOptions() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const axisLine = isDark ? 'rgba(195,198,208,0.20)' : 'rgba(195,198,208,0.55)';

  return {
    chart: {
      type:   'line',
      margin: [16, 20, 46, 72],
    },
    title:    { text: '' },
    subtitle: { text: '' },
    xAxis: {
      title: { text: '' },
      tickInterval: 1,
      crosshair: {
        color:     isDark ? 'rgba(122, 184, 228, 0.9)' : 'rgba(9, 64, 112, 0.55)',
        dashStyle: 'Dot',
        width:     isDark ? 2 : 1,
      },
      labels: { formatter() { return this.value; } },
    },
    yAxis: {
      title:     { text: '' },
      min:       0,
      lineWidth: 1,
      lineColor: axisLine,
      labels: {
        formatter() {
          const v = this.value;
          if (v >= 1_000) return `$${Math.round(v / 1_000)}K`;
          return `$${v}`;
        },
      },
    },
    legend: { enabled: false },
    tooltip: {
      shared: true,
      shadow: false,
      formatter() {
        if (this.points?.length) {
          const points = this.points
            .filter(p => p.y !== null && p.y !== undefined)
            .sort((a, b) => b.y - a.y);
          const lines = points.map(p =>
            `<span style="color:${p.color}; font-weight:600">${p.series.name}</span>: <b>${fmtPay(p.y)}</b>`
          );
          return `<b>${this.x}</b><br/>${lines.join('<br/>')}`;
        }
        return `<b>${this.series.name}</b><br/>${this.x}: <b>${fmtPay(this.y)}</b>`;
      },
    },
    series: [],
  };
}

function buildPayOptions() {
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
      title:  { text: '' },
      min:    0,
      labels: {
        formatter() {
          const v = this.value;
          if (v >= 1_000) return `$${Math.round(v / 1_000)}K`;
          return `$${v}`;
        },
      },
    },
    plotOptions: {
      bar: {
        borderWidth: 0,
        colorByPoint: true,
        dataLabels: {
          enabled: true,
          formatter() { return fmtPay(this.y); },
          style: {
            fontFamily: "'DINPro', sans-serif",
            fontSize:   '11px',
            fontWeight: '600',
            textOutline: 'none',
          },
        },
      },
    },
    legend: { enabled: false },
    tooltip: {
      shadow: false,
      formatter() {
        const wages = fmtDollarsBig(this.point.wages);
        const jobs  = Math.round(this.point.emp).toLocaleString();
        return `<b>${this.x}</b><br/>` +
          `<span style="opacity:0.75">${wages} total wages · ${jobs} jobs</span>`;
      },
    },
    series: [],
  };
}
