// js/data.js
// Fetches all pipeline CSV outputs once on startup and caches them in memory.
// Depends on window.Papa (Papa Parse, loaded as a traditional <script> in index.html).

const _cache = new Map();

const CSV_FILES = [
  'population', 'employment', 'housing', 'education',
  'health', 'income', 'forecast', 'forecast_sectors',
  'wages', 'wages_by_industry', 'gdp', 'permits',
];

// Resolve the data path relative to THIS module file (frontend/js/data.js),
// not the page URL. Two levels up lands at the project root, then data/output/.
// This works correctly regardless of which directory the HTTP server is started from.
const BASE = new URL('../data/output/', import.meta.url).href;

/** Fetch + parse one CSV. Resolves to an array of row objects. */
function parseCsv(url) {
  return new Promise((resolve) => {
    window.Papa.parse(url, {
      download:      true,
      header:        true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: ({ data }) => resolve(data),
      error: (err) => {
        console.warn(`[data.js] Could not load ${url}:`, err.message);
        resolve([]); // Degrade gracefully — missing file returns empty array
      },
    });
  });
}

/**
 * Load all CSV files and vintages.json in parallel.
 * Dispatches 'dataReady' on window when complete.
 */
export async function loadAll() {
  const csvResults = await Promise.all(
    CSV_FILES.map(name => parseCsv(`${BASE}${name}.csv`).then(data => [name, data]))
  );

  for (const [name, data] of csvResults) {
    _cache.set(name, data);
  }

  try {
    const res = await fetch(`${BASE}vintages.json`);
    _cache.set('vintages', await res.json());
  } catch {
    _cache.set('vintages', {});
  }

  window.dispatchEvent(new CustomEvent('dataReady'));
}

/** Return cached rows for a dataset (empty array if not loaded). */
export function get(name) {
  return _cache.get(name) ?? [];
}

/** Return the vintages metadata object. */
export function getVintages() {
  return _cache.get('vintages') ?? {};
}
