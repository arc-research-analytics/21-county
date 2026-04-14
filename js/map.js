// js/map.js
// County-selection map using Mapbox GL JS.
// Basemap: CARTO raster tiles (no auth required — avoids token URL-restriction issues).
// Call init() once on startup; render(selected) updates highlighted counties.

const TOKEN       = 'pk.eyJ1Ijoid3dyaWdodDIxIiwiYSI6ImNtN2MwdjdtYjBqeTUycnBwbHI1cWJrZmIifQ.BztD8jx6SLKxOtjK1ae4kg';
const GEOJSON_URL = new URL('../ga-counties.geojson', import.meta.url).href;

let _map          = null;
let _geojson      = null;
let _isDark       = false;
let _ready        = false;
let _lastSelected = [];
let _pending      = null;

// ── EPSG:3857 → WGS84 ─────────────────────────────────────────────────────────
function _projectCoord([x, y]) {
  return [
    (x * 180) / 20037508.342789244,
    (2 * Math.atan(Math.exp(y / 6378137)) - Math.PI / 2) * (180 / Math.PI),
  ];
}

function _projectGeom(geom) {
  const ring = r => r.map(_projectCoord);
  if (geom.type === 'Polygon')
    return { ...geom, coordinates: geom.coordinates.map(ring) };
  if (geom.type === 'MultiPolygon')
    return { ...geom, coordinates: geom.coordinates.map(p => p.map(ring)) };
  return geom;
}

function _reproject(raw) {
  return {
    ...raw,
    features: raw.features.map(f => ({
      ...f,
      properties: {
        ...f.properties,
        county_name: f.properties.NAME.replace(/ County$/, '').trim(),
      },
      geometry: _projectGeom(f.geometry),
    })),
  };
}

// ── Bounding box of all features ───────────────────────────────────────────────
function _getBounds(geojson) {
  let minLng = Infinity, maxLng = -Infinity,
      minLat = Infinity, maxLat = -Infinity;
  for (const f of geojson.features) {
    // flat(3) turns nested coordinate arrays into a plain [lng,lat,lng,lat,...] sequence
    const flat = f.geometry.coordinates.flat(3);
    for (let i = 0; i < flat.length; i += 2) {
      minLng = Math.min(minLng, flat[i]);
      maxLng = Math.max(maxLng, flat[i]);
      minLat = Math.min(minLat, flat[i + 1]);
      maxLat = Math.max(maxLat, flat[i + 1]);
    }
  }
  return [[minLng, minLat], [maxLng, maxLat]];
}

// ── CARTO raster basemap style spec ───────────────────────────────────────────
// Using CARTO tiles avoids Mapbox-hosted tile requests that fail under
// token URL restrictions. CARTO tiles require no authentication.
function _styleSpec(isDark) {
  const variant = isDark ? 'dark_all' : 'light_all';
  return {
    version: 8,
    sources: {
      carto: {
        type: 'raster',
        tiles: [
          `https://a.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}@2x.png`,
          `https://b.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}@2x.png`,
          `https://c.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}@2x.png`,
        ],
        tileSize: 256,
        attribution: '© <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
      },
    },
    layers: [{ id: 'carto-base', type: 'raster', source: 'carto' }],
  };
}

// ── Paint expression builders ──────────────────────────────────────────────────
function _fillColor(isDark, sel) {
  return ['case',
    ['in', ['get', 'county_name'], ['literal', sel]],
    '#1270B3',
    isDark ? '#c0c0c0' : '#787878',
  ];
}

function _lineColor(isDark, sel) {
  return ['case',
    ['in', ['get', 'county_name'], ['literal', sel]],
    '#1270B3',
    isDark ? 'rgba(180,180,180,0.65)' : 'rgba(100,100,100,0.7)',
  ];
}

function _lineWidth(sel) {
  return ['case',
    ['in', ['get', 'county_name'], ['literal', sel]],
    2,
    0.5,
  ];
}

// ── Source + layer setup ───────────────────────────────────────────────────────
function _addLayers(sel) {
  _map.addSource('counties', { type: 'geojson', data: _geojson });
  _map.addLayer({
    id: 'counties-fill', type: 'fill', source: 'counties',
    paint: {
      'fill-color':   _fillColor(_isDark, sel),
      'fill-opacity': 0.35,
    },
  });
  _map.addLayer({
    id: 'counties-outline', type: 'line', source: 'counties',
    paint: {
      'line-color': _lineColor(_isDark, sel),
      'line-width': _lineWidth(sel),
    },
  });
}

// ── Public API ─────────────────────────────────────────────────────────────────

export async function init(isDark = false, initialSelected = []) {
  _isDark       = isDark;
  _lastSelected = [...initialSelected];

  mapboxgl.accessToken = TOKEN;

  const resp = await fetch(GEOJSON_URL);
  _geojson = _reproject(await resp.json());

  const bounds = _getBounds(_geojson);

  _map = new mapboxgl.Map({
    container:          'map-counties',
    style:              _styleSpec(isDark),
    bounds:             bounds,
    fitBoundsOptions:   { padding: 6 },
    interactive:        false,
    attributionControl: false,
  });

  _map.on('load', () => {
    const sel = _pending ?? _lastSelected;
    _addLayers(sel);
    _lastSelected = sel;
    _pending      = null;
    _ready        = true;
  });
}

export function render(selected) {
  const arr = [...selected];
  _lastSelected = arr;

  if (!_ready) { _pending = arr; return; }

  _map.setPaintProperty('counties-fill',    'fill-color',  _fillColor(_isDark, arr));
  _map.setPaintProperty('counties-outline', 'line-color',  _lineColor(_isDark, arr));
  _map.setPaintProperty('counties-outline', 'line-width',  _lineWidth(arr));
}

export function setTheme(isDark) {
  _isDark = isDark;
  if (!_map) return;

  if (!_ready) return; // map still loading — _isDark update above is enough;
                       // init()'s load handler will use the updated _isDark

  // Surgically swap just the CARTO raster source instead of calling setStyle(),
  // which nukes all layers and relies on style.load firing reliably (it doesn't
  // for custom style spec objects in Mapbox GL JS v3).
  const variant = isDark ? 'dark_all' : 'light_all';
  const tiles = ['a', 'b', 'c'].map(s =>
    `https://${s}.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}@2x.png`
  );

  _map.removeLayer('carto-base');
  _map.removeSource('carto');
  _map.addSource('carto', { type: 'raster', tiles, tileSize: 256 });
  // Insert basemap layer below the county fill so counties stay on top
  _map.addLayer({ id: 'carto-base', type: 'raster', source: 'carto' }, 'counties-fill');

  // Update county colors for the new theme
  _map.setPaintProperty('counties-fill',    'fill-color',  _fillColor(isDark, _lastSelected));
  _map.setPaintProperty('counties-outline', 'line-color',  _lineColor(isDark, _lastSelected));
}
