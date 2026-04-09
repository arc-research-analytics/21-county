// js/charts/theme.js
// Global Highcharts theme. Call applyTheme(isDark) whenever the color scheme changes.
// Existing charts are NOT automatically updated by Highcharts.setOptions() — callers
// must trigger a redraw on individual charts after switching themes.

const PALETTE_LIGHT = [
  '#1270B3', // ARC Agency Blue
  '#1AAFA6', // ARC Teal
  '#42ADD3', // ARC Sky Blue
  '#EE575D', // ARC Coral
  '#636EA0', // ARC Violet
  '#678539', // ARC Olive
  '#98AE3E', // ARC Yellow-green
  '#FDB713', // ARC Gold
];

const PALETTE_DARK = [
  '#7ab8e4', // Agency Blue (lightened for dark bg)
  '#42ADD3', // ARC Sky Blue
  '#1AAFA6', // ARC Teal
  '#EE575D', // ARC Coral
  '#636EA0', // ARC Violet
  '#98AE3E', // ARC Yellow-green
  '#678539', // ARC Olive
  '#FDB713', // ARC Gold
];

export function applyTheme(isDark = false) {
  if (!window.Highcharts) return;

  const text1    = isDark ? '#dff4ff' : '#071e27';
  const text2    = isDark ? '#c3c6d0' : '#43474f';
  const gridLine = isDark ? 'rgba(195,198,208,0.12)' : 'rgba(195,198,208,0.45)';
  const chartBg  = isDark ? '#0d2535'  : '#ffffff';
  const tipBg    = isDark ? 'rgba(18,45,62,0.95)' : 'rgba(219,241,254,0.95)';

  window.Highcharts.setOptions({
    colors: isDark ? PALETTE_DARK : PALETTE_LIGHT,

    chart: {
      backgroundColor: chartBg,
      style: { fontFamily: "'DINPro', sans-serif" },
      animation: { duration: 300 },
    },

    title: {
      text: '',
      style: {
        fontFamily: "'DINPro', sans-serif",
        fontWeight: '600',
        fontSize: '13px',
        color: text1,
      },
    },

    subtitle: { style: { fontSize: '11px', color: text2 } },

    xAxis: {
      gridLineColor: gridLine,
      lineColor: gridLine,
      tickColor: 'transparent',
      labels: {
        style: { color: text2, fontFamily: "'DINPro', sans-serif", fontSize: '11px' },
      },
    },

    yAxis: {
      gridLineColor: gridLine,
      labels: {
        style: { color: text2, fontFamily: "'DINPro', sans-serif", fontSize: '11px' },
      },
      title: { style: { color: text2, fontSize: '11px' } },
    },

    legend: {
      itemStyle: {
        color: text2,
        fontFamily: "'DINPro', sans-serif",
        fontWeight: '400',
        fontSize: '12px',
      },
      itemHoverStyle: { color: text1 },
    },

    tooltip: {
      backgroundColor: tipBg,
      borderWidth: 0,
      borderRadius: 8,
      style: {
        color: text1,
        fontFamily: "'DINPro', sans-serif",
        fontSize: '12px',
      },
      shadow: { offsetX: 0, offsetY: 4, opacity: 0.05, width: 20 },
    },

    plotOptions: {
      series: { animation: { duration: 350 } },
    },

    credits: { enabled: false },
  });
}
