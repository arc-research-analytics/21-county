// js/filter.js
// Manages the county multi-select state. Dispatches a 'filterChange' CustomEvent
// on window whenever the selection changes so tab modules can re-render.

export const COUNTIES_21 = [
  'Barrow', 'Bartow', 'Carroll', 'Cherokee', 'Clayton', 'Cobb',
  'Coweta', 'Dawson', 'DeKalb', 'Douglas', 'Fayette', 'Forsyth',
  'Fulton', 'Gwinnett', 'Hall', 'Henry', 'Newton', 'Paulding',
  'Rockdale', 'Spalding', 'Walton',
];

export const CORE_11 = new Set([
  'Cherokee', 'Clayton', 'Cobb', 'DeKalb', 'Douglas',
  'Fayette', 'Forsyth', 'Fulton', 'Gwinnett', 'Henry', 'Rockdale',
]);

let _selected = new Set(COUNTIES_21); // Default: all 21

export const getSelected = () => _selected;
export const getAll      = () => COUNTIES_21;
export const isCore11    = (name) => CORE_11.has(name);

function dispatch() {
  window.dispatchEvent(
    new CustomEvent('filterChange', { detail: { selected: new Set(_selected) } })
  );
}

function syncSelectValue(select) {
  select.value = [..._selected];
}

function readSelectedFromElement(selectEl) {
  // Preferred: component API (if available)
  if (selectEl?.selectedOptions) {
    const selectedOptions = typeof selectEl.selectedOptions[Symbol.iterator] === 'function'
      ? [...selectEl.selectedOptions]
      : Array.from(selectEl.selectedOptions);
    const vals = selectedOptions
      .map(o => String(o?.value ?? '').trim())
      .filter(Boolean);
    if (vals.length) return vals;
  }

  // Fallback: inspect rendered options in light DOM
  const optionEls = [...selectEl.querySelectorAll('wa-option')];
  const selectedByProp = optionEls
    .filter(o => Boolean(o.selected))
    .map(o => String(o.value || '').trim())
    .filter(Boolean);
  if (selectedByProp.length) return selectedByProp;

  // Last fallback: selected attribute
  return optionEls
    .filter(o => o.hasAttribute('selected'))
    .map(o => String(o.value || '').trim())
    .filter(Boolean);
}

function normalizeSelected(rawValue, selectEl) {
  if (Array.isArray(rawValue)) {
    return rawValue.map(v => String(v).trim()).filter(Boolean);
  }

  if (rawValue && typeof rawValue[Symbol.iterator] === 'function' && typeof rawValue !== 'string') {
    const vals = [...rawValue]
      .map(v => (v && typeof v === 'object' && 'value' in v ? v.value : v))
      .map(v => String(v ?? '').trim())
      .filter(Boolean);
    if (vals.length) return vals;
  }

  if (typeof rawValue === 'string') {
    const normalized = rawValue
      .split(',')
      .map(v => v.trim())
      .filter(Boolean);
    if (normalized.length) return normalized;
  }

  // Fallback: read directly from component option state.
  const fromElement = readSelectedFromElement(selectEl);
  if (fromElement.length) return fromElement;

  // Final fallback: use current component value when it's a simple string.
  if (typeof selectEl?.value === 'string') {
    return selectEl.value
      .split(',')
      .map(v => v.trim())
      .filter(Boolean);
  }

  return [];
}

function updateButtonStates() {
  const btn11 = document.getElementById('btn-core11');
  const btn21 = document.getElementById('btn-21county');
  if (!btn11 || !btn21) return;

  const is11 = _selected.size === CORE_11.size && [..._selected].every(c => CORE_11.has(c));
  const is21 = _selected.size === COUNTIES_21.length;

  // Web Awesome button: variant="brand" (filled) vs "neutral" (ghost)
  btn21.variant = is21 ? 'brand' : 'neutral';
  btn11.variant = is11 ? 'brand' : 'neutral';
  btn21.outline = !is21;
  btn11.outline = !is11;
}

/**
 * Wire up the wa-select and preset buttons.
 * Call after loadAll() resolves so the DOM is ready and WA components are registered.
 */
export async function initFilter() {
  // Wait for Web Awesome's <wa-select> to be defined before setting its value
  await customElements.whenDefined('wa-select');

  const select = document.getElementById('county-select');
  const btn11  = document.getElementById('btn-core11');
  const btn21  = document.getElementById('btn-21county');

  // Set initial selection programmatically
  syncSelectValue(select);
  updateButtonStates();

  const handleSelectChange = () => {
    // Read select.value directly — the authoritative source in WA beta.5.
    // e.detail.value is often absent; we keep an empty selection when cleared.
    const raw = select.value;
    _selected = new Set(normalizeSelected(raw, select));
    updateButtonStates();
    dispatch();
  };

  // wa-change: fired when value settles after selection/deselection
  // wa-input:  fired on each incremental toggle inside the dropdown
  // wa-clear:  fired by the clear (×) button — value is [] at this point
  // change:    standard event alias some WA builds also dispatch
  select.addEventListener('wa-change', handleSelectChange);
  select.addEventListener('wa-input',  handleSelectChange);
  select.addEventListener('wa-clear',  handleSelectChange);
  select.addEventListener('change',    handleSelectChange);

  // 21-county preset
  btn21.addEventListener('click', () => {
    _selected = new Set(COUNTIES_21);
    syncSelectValue(select);
    updateButtonStates();
    dispatch();
  });

  // 11-county core preset
  btn11.addEventListener('click', () => {
    _selected = new Set(CORE_11);
    syncSelectValue(select);
    updateButtonStates();
    dispatch();
  });
}
