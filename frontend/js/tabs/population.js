// js/tabs/population.js
// Population tab: KPI cards + 3 Highcharts (trend line, race donut, age bar).

import * as Data   from '../data.js';
import { getSelected, COUNTIES_21, CORE_11 } from '../filter.js';

// ── Module-level chart instances ──────────────────────────────────────────
let trendChart = null;
let raceChart  = null;
let ageChart   = null;

// ── Color palette for this tab ────────────────────────────────────────────
// Hispanic, White(NH), Black(NH), Asian(NH), Other(NH)
const RACE_COLORS = ['#EE575D', '#1270B3', '#1AAFA6', '#42ADD3', '#636EA0'];
// Youngest → Oldest (reversed in render loop so darkest = oldest on chart)
const AGE_COLORS  = ['#636EA0', '#42ADD3', '#1AAFA6', '#1270B3', '#094070'];
// Population trend series colors (from assets/style-guide.md extended ARC palette)
const TREND_LINE_COLORS = ['#1270B3', '#1AAFA6', '#42ADD3', '#636EA0', '#EE575D', '#678539'];

// ── Helpers ───────────────────────────────────────────────────────────────
const sumCol = (rows, col) =>
  rows.reduce((s, r) => s + (Number(r[col]) || 0), 0);

function isPresetRegionalSelection(selected) {
  if (selected.length === COUNTIES_21.length) return true;
  if (selected.length !== CORE_11.size) return false;
  return selected.every(name => CORE_11.has(name));
}

function fmtPop(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}

function fmtPct(pct) {
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}

// ── Public API ────────────────────────────────────────────────────────────

/**
 * Create all three chart instances. Destroys any existing ones first so
 * theme changes (which call init() again) get fresh instances.
 */
export function init() {
  if (trendChart) { trendChart.destroy(); trendChart = null; }
  if (raceChart)  { raceChart.destroy();  raceChart  = null; }
  if (ageChart)   { ageChart.destroy();   ageChart   = null; }

  trendChart = Highcharts.chart('chart-pop-trend', buildTrendOptions());
  raceChart  = Highcharts.chart('chart-race',      buildRaceOptions());
  ageChart   = Highcharts.chart('chart-age',       buildAgeOptions());

  render(getSelected());
}

/**
 * Re-compute KPIs and push new data to all three charts.
 * Called on: initial load, filter change, theme change.
 */
export function render(selectedCounties) {
  const rows     = Data.get('population');
  const selected = [...selectedCounties];

  if (!trendChart) return;

  // Update ACS vintage labels from pipeline metadata
  const acsYear = Data.getVintages().acs_vintage;
  const acsLabel = acsYear ? `ACS ${acsYear} estimate` : 'Latest ACS estimate';
  document.getElementById('race-vintage-label').textContent = acsLabel;
  document.getElementById('age-vintage-label').textContent  = acsLabel;

  if (!selected.length) {
    document.getElementById('kpi-pop-value').textContent = '—';
    document.getElementById('kpi-pop-sub').textContent   = 'No counties selected';
    const growthEl = document.getElementById('kpi-growth-value');
    growthEl.textContent = '—';
    growthEl.className   = 'kpi-value';
    document.getElementById('kpi-growth-sub').textContent = '';

    while (trendChart.series.length > 0) trendChart.series[0].remove(false);
    trendChart.redraw();
    raceChart.series[0].setData([], true, { duration: 200 });
    ageChart.xAxis[0].setCategories([], false);
    ageChart.series[0].setData([], true, { duration: 200 });
    return;
  }

  if (!rows.length) return;

  const years      = [...new Set(rows.map(r => r.year))].sort((a, b) => a - b);
  const latestYear = years[years.length - 1];

  const latestRows = rows.filter(r => r.year === latestYear && selected.includes(r.county_name));
  const rows2010   = rows.filter(r => r.year === 2010       && selected.includes(r.county_name));

  // ── KPI 1: Total population ──────────────────────────────────────────────
  const totalPop = sumCol(latestRows, 'population');
  const pop2010  = sumCol(rows2010,   'population');
  const growth   = pop2010 > 0 ? ((totalPop - pop2010) / pop2010) * 100 : null;

  document.getElementById('kpi-pop-value').textContent = fmtPop(totalPop);
  document.getElementById('kpi-pop-sub').textContent   =
    `${latestYear} estimate · ${selected.length} ${selected.length === 1 ? 'county' : 'counties'}`;

  // ── KPI 2: Growth since 2010 ─────────────────────────────────────────────
  const growthEl = document.getElementById('kpi-growth-value');
  if (growth !== null) {
    growthEl.textContent = fmtPct(growth);
    growthEl.className   = `kpi-value ${growth >= 0 ? 'positive' : 'negative'}`;
  } else {
    growthEl.textContent = '—';
    growthEl.className   = 'kpi-value';
  }
  document.getElementById('kpi-growth-sub').textContent =
    pop2010 > 0 ? `${fmtPop(pop2010)} in 2010 → ${fmtPop(totalPop)} in ${latestYear}` : '';

  // ── Trend line chart ──────────────────────────────────────────────────────
  // Regional total series (always shown)
  const regionalData = years.map(yr => {
    const s = rows
      .filter(r => r.year === yr && selected.includes(r.county_name))
      .reduce((acc, r) => acc + (r.population || 0), 0);
    return [yr, s];
  });

  const trendSeries = [];
  const totalSeriesName = selected.length === 1
    ? selected[0]
    : (isPresetRegionalSelection(selected) ? 'Regional Total' : 'Selected total');

  if (selected.length <= 6) {
    // Show only individual county lines (no combined total line).
    selected.forEach((name, i) => {
      trendSeries.push({
        name,
        type: 'line',
        data: years.map(yr => {
          const r = rows.find(x => x.year === yr && x.county_name === name);
          return r ? [yr, r.population] : [yr, null];
        }),
        lineWidth: selected.length === 1 ? 2.5 : 2,
        color: TREND_LINE_COLORS[i % TREND_LINE_COLORS.length],
        marker: { enabled: false },
        showInLegend: true,
        enableMouseTracking: true,
      });
    });
  } else {
    // Collapse to one combined line for dense selections.
    trendSeries.push({
      name:      totalSeriesName,
      type:      'line',
      data:      regionalData,
      lineWidth: 3,
      color:     '#1270B3',
      marker:    { enabled: false },
      zIndex:    5,
    });
  }

  // Clear existing series and replace
  while (trendChart.series.length > 0) trendChart.series[0].remove(false);
  trendSeries.forEach(s => trendChart.addSeries(s, false));
  trendChart.redraw();

  // ── Race / ethnicity donut ───────────────────────────────────────────────
  const raceData = [
    { name: 'Hispanic',              y: sumCol(latestRows, 'race_hispanic'),  color: RACE_COLORS[0] },
    { name: 'White Non-Hispanic',    y: sumCol(latestRows, 'race_nh_white'),  color: RACE_COLORS[1] },
    { name: 'Black Non-Hispanic',    y: sumCol(latestRows, 'race_nh_black'),  color: RACE_COLORS[2] },
    { name: 'Asian Non-Hispanic',    y: sumCol(latestRows, 'race_nh_asian'),  color: RACE_COLORS[3] },
    { name: 'Other Non-Hispanic',    y: sumCol(latestRows, 'race_nh_other'),  color: RACE_COLORS[4] },
  ];
  raceChart.series[0].setData(raceData, true, { duration: 300 });

  // ── Age profile bar ───────────────────────────────────────────────────────
  const ageBands = [
    { name: '65+',      col: 'age_65plus' },
    { name: '50–64',    col: 'age_50_64'  },
    { name: '35–49',    col: 'age_35_49'  },
    { name: '20–34',    col: 'age_20_34'  },
    { name: 'Under 20', col: 'age_0_19'   },
  ];
  const agePopTotal = ageBands.reduce((s, b) => s + sumCol(latestRows, b.col), 0);
  const ageData = ageBands.map((b, i) => ({
    name:  b.name,
    y:     agePopTotal > 0 ? +((sumCol(latestRows, b.col) / agePopTotal) * 100).toFixed(1) : 0,
    color: AGE_COLORS[AGE_COLORS.length - 1 - i], // reverse so darkest = youngest (top of axis)
  }));

  ageChart.xAxis[0].setCategories(ageBands.map(b => b.name), false);
  ageChart.series[0].setData(ageData, true, { duration: 300 });
}

// ── Chart option factories ────────────────────────────────────────────────

function buildTrendOptions() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

  return {
    chart: {
      type: 'line',
      margin: [16, 20, 46, 64],
    },
    title:    { text: '' },
    subtitle: { text: '' },
    xAxis: {
      title: { text: '' },
      tickInterval: 5,
      crosshair: {
        color: isDark ? 'rgba(122, 184, 228, 0.9)' : 'rgba(9, 64, 112, 0.55)',
        dashStyle: 'Dot',
        width: isDark ? 2 : 1,
      },
      labels: {
        formatter() { return this.value; },
      },
    },
    yAxis: {
      title: { text: '' },
      labels: {
        formatter() {
          const v = this.value;
          if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
          if (v >= 1_000)     return `${Math.round(v / 1_000)}K`;
          return v;
        },
      },
    },
    legend: {
      enabled: false,
    },
    tooltip: {
      shared: true,
      shadow: false,
      formatter() {
        const fmtVal = (value) => Math.round(value).toLocaleString();

        if (this.points?.length) {
          const lines = this.points
            .filter(p => p.y !== null && p.y !== undefined)
            .map(p => `${p.series.name}: <b>${fmtVal(p.y)}</b>`);
          if (this.points.length > 1) {
            const total = this.points
              .filter(p => p.y !== null && p.y !== undefined)
              .reduce((acc, p) => acc + p.y, 0);
            lines.push(`Selected total: <b>${fmtVal(total)}</b>`);
          }
          return `<b>${this.x}</b><br/>${lines.join('<br/>')}`;
        }

        const v = this.y;
        return `<b>${this.series.name}</b><br/>${this.x}: <b>${fmtVal(v)}</b>`;
      },
    },
    series: [],
  };
}

function buildRaceOptions() {
  return {
    chart: {
      type:   'pie',
      margin: [8, 8, 16, 8],
    },
    title:    { text: '' },
    tooltip: {
      formatter() {
        return `<b>${this.percentage.toFixed(1)}%</b><br/>${Math.round(this.y).toLocaleString('en-US')} people`;
      },
    },
    plotOptions: {
      pie: {
        innerSize: '56%',
        borderWidth: 0,
        dataLabels: {
          enabled:  true,
          distance: 14,
          format:   '<b style="font-weight:500">{point.name}</b><br/>{point.percentage:.1f}%',
          style: {
            fontFamily: "'DINPro', sans-serif",
            fontSize:   '11px',
            fontWeight: '400',
            textOutline: 'none',
          },
        },
      },
    },
    series: [{ name: 'Population', data: [] }],
  };
}

function buildAgeOptions() {
  return {
    chart: {
      type:   'bar',
      margin: [8, 64, 28, 72],
    },
    title:    { text: '' },
    xAxis: {
      categories: [],
      labels: {
        style: { fontSize: '12px', fontFamily: "'DINPro', sans-serif" },
      },
    },
    yAxis: {
      title: { text: '' },
      labels: { format: '{value}%' },
      gridLineWidth: 1,
    },
    legend: { enabled: false },
    tooltip: {
      followPointer:  true,
      valueSuffix:    '%',
      valueDecimals:  1,
      formatter() {
        return `<b>${this.point.name}</b>: ${this.y.toFixed(1)}% of population`;
      },
    },
    plotOptions: {
      bar: {
        borderRadius: 3,
        borderWidth:  0,
        dataLabels: {
          enabled: true,
          format:  '{y:.1f}%',
          style: {
            fontFamily: "'DINPro', sans-serif",
            fontSize:   '11px',
            fontWeight: '500',
            textOutline: 'none',
          },
        },
      },
    },
    series: [{ name: 'Share of Population', data: [] }],
  };
}
