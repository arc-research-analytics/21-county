// js/main.js
// App entry point: data loading, tab routing, dark mode, filter wiring.

import { loadAll, getVintages } from './data.js';
import { initFilter, getSelected } from './filter.js';
import { applyTheme } from './charts/theme.js';
import * as PopTab from './tabs/population.js';
import * as MapMod from './map.js';

// ── Tab registry ──────────────────────────────────────────────────────────
const TAB_TITLES = {
  population: 'Population',
  employment: 'Employment',
  economy:    'Economy',
  housing:    'Housing',
  education:  'Education',
  health:     'Health',
  income:     'Income',
  forecast:   '2050 Forecast',
  about:      'About',
};

// Map tab id → module. Add new modules here in later phases.
const TAB_MODULES = {
  population: PopTab,
};

// Tracks which tabs have already been initialized (charts created)
const _initialized = new Set();
let _activeTab = 'population';
let _isDark    = false;

// ── Dark mode ─────────────────────────────────────────────────────────────
function initDarkMode() {
  const stored = localStorage.getItem('arc-theme');
  _isDark = stored === 'dark'
    || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches);
  applyThemeAndUpdate(_isDark, false); // false = skip chart redraw on initial load

  document.getElementById('dark-mode-toggle').addEventListener('click', () => {
    _isDark = !_isDark;
    localStorage.setItem('arc-theme', _isDark ? 'dark' : 'light');
    applyThemeAndUpdate(_isDark, true);
  });
}

function applyThemeAndUpdate(dark, redrawCharts) {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  document.getElementById('dark-mode-icon').setAttribute('name', dark ? 'sun' : 'moon');
  applyTheme(dark);
  MapMod.setTheme(dark);

  if (redrawCharts) {
    // Re-init all initialized tabs so charts pick up the new Highcharts.setOptions() palette
    for (const id of _initialized) {
      TAB_MODULES[id]?.init();
    }
  }
}

// ── Navigation ────────────────────────────────────────────────────────────
function initNav() {
  document.querySelectorAll('.nav-item[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

function switchTab(tabId) {
  if (tabId === _activeTab && _initialized.has(tabId)) return;

  // Update nav active state
  document.querySelectorAll('.nav-item[data-tab]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabId);
  });

  // Show/hide panels
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById(`panel-${tabId}`)?.classList.remove('hidden');

  // Update top-bar title
  document.getElementById('tab-title').textContent = TAB_TITLES[tabId] ?? tabId;

  _activeTab = tabId;

  // Init or re-render the tab module
  const mod = TAB_MODULES[tabId];
  if (mod) {
    if (!_initialized.has(tabId)) {
      mod.init();
      _initialized.add(tabId);
    } else {
      mod.render(getSelected());
    }
  }
}

// ── Vintage badge ─────────────────────────────────────────────────────────
function renderVintageBadge() {
  const v = getVintages();
  const parts = [];
  if (v.acs_vintage)            parts.push(`ACS ${v.acs_vintage}`);
  if (v.population_latest_year) parts.push(`Pop ${v.population_latest_year}`);
  if (v.employment_latest_year) parts.push(`Emp ${v.employment_latest_year}`);
  document.getElementById('vintage-badge').textContent =
    parts.length ? parts.join(' · ') : 'Data loaded';
}

// ── Bootstrap ─────────────────────────────────────────────────────────────
async function main() {
  // Apply dark mode first (before any paint)
  initDarkMode();
  initNav();

  // Show loading state in vintage badge
  document.getElementById('vintage-badge').textContent = 'Loading data…';

  // Fetch all CSVs
  await loadAll();

  renderVintageBadge();

  // Wire up the county filter (awaits WA custom element registration internally)
  await initFilter();

  // Initialize the county selection map (async; renders when tiles load)
  MapMod.init(_isDark, getSelected());

  // Listen for filter changes → re-render active tab + map
  window.addEventListener('filterChange', (e) => {
    const mod = TAB_MODULES[_activeTab];
    if (mod && _initialized.has(_activeTab)) {
      mod.render(e.detail.selected);
    }
    MapMod.render(e.detail.selected);
  });

  // Boot the default tab
  switchTab('population');
}

main().catch(err => console.error('[main.js] Startup error:', err));
