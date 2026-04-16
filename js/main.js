// js/main.js
// App entry point: data loading, tab routing, dark mode, filter wiring.

import { loadAll, getVintages } from './data.js';
import { initFilter, getSelected } from './filter.js';
import { applyTheme } from './charts/theme.js';
import * as PopTab     from './tabs/population.js';
import * as EmpTab     from './tabs/employment.js';
import * as EconTab    from './tabs/economy.js';
import * as IncomeTab  from './tabs/income.js';
import * as MapMod     from './map.js';

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
  employment: EmpTab,
  economy:    EconTab,
  income:     IncomeTab,
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

  // Update top-bar title and vintage badge
  document.getElementById('tab-title').textContent = TAB_TITLES[tabId] ?? tabId;
  renderVintageBadge(tabId);

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

// ── Vintage badge — tab-specific so only relevant vintages are shown ───────
function renderVintageBadge(tabId = _activeTab) {
  const v     = getVintages();
  const acs   = v.acs_vintage;
  const pop   = v.population_latest_year;
  const emp   = v.employment_latest_year;
  const empQ  = v.employment_latest_quarter;
  const wages = v.wages_latest_year;
  const gdp   = v.gdp_latest_year;
  const prm   = v.permits_latest_year;
  const gosa  = v.gosa_latest_year;

  // QWI lags ~2 quarters; flag the latest year when fewer than 4 quarters
  // fed the average (e.g. "Emp 2025 (Q1–Q2)"). Bare "Emp 2025" means full year.
  const empLabel = emp && (empQ && empQ < 4 ? `Emp ${emp} (Q1–Q${empQ})` : `Emp ${emp}`);

  const BADGE = {
    population: [pop   && `Pop ${pop}`],
    employment: [empLabel],
    economy:    [gdp   && `GDP ${gdp}`,   wages && `Wages ${wages}`],
    housing:    [acs   && `ACS ${acs}`,   prm   && `Permits ${prm}`],
    education:  [acs   && `ACS ${acs}`,   gosa  && `GOSA ${gosa}`],
    health:     [acs   && `ACS ${acs}`],
    income:     [acs   && `ACS ${acs}`],
    forecast:   ['ARC 2050 Forecast'],
    about:      [],
  };

  const parts = (BADGE[tabId] ?? []).filter(Boolean);
  document.getElementById('vintage-badge').textContent =
    parts.length ? parts.join(' · ') : '';
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

  // Badge will be set correctly by switchTab('population') below;

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
