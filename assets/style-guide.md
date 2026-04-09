# ARC Eviction Tracker — Style Guide

This guide documents the visual design system used in the Metro Atlanta Eviction Tracker, published by the Atlanta Regional Commission (ARC). Use it as a reference when applying this design language to other ARC applications.

---

## Typography

### Fonts in Use

Two typefaces are actively used throughout the application. The font files live in `assets/fonts/` and can be copied directly to another project.

| Family | Files | Weights Available | Role |
|--------|-------|-------------------|------|
| **DINPro** | `DINPro.otf` (400), `DINPro-Bold.otf` (700), `DINPro-Medium.otf` (500), `DINPro-Italic.otf` (400 italic) | Regular, Medium, Bold, Italic | Primary UI font — used for almost all interface elements: header, labels, buttons, tooltips, legend, slider, drawer titles, and popup content |
| **MinionPro** | `MinionPro-Regular.otf` (400), `MinionPro-Semibold.otf` (600) | Regular, Semibold | Serif accent font — used for dialog titles, the About modal body text, and the mobile welcome dialog |

### Font Stack Fallbacks

```css
font-family: 'DINPro', Arial, sans-serif;      /* UI elements */
font-family: 'MinionPro', Georgia, serif;       /* Dialog/editorial content */
```

### @font-face Declarations

```css
@font-face {
    font-family: 'DINPro';
    src: url('assets/fonts/DINPro.otf') format('opentype');
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: 'DINPro';
    src: url('assets/fonts/DINPro-Medium.otf') format('opentype');
    font-weight: 500;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: 'DINPro';
    src: url('assets/fonts/DINPro-Bold.otf') format('opentype');
    font-weight: 700;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: 'DINPro';
    src: url('assets/fonts/DINPro-Italic.otf') format('opentype');
    font-weight: 400;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: 'MinionPro';
    src: url('assets/fonts/MinionPro-Regular.otf') format('opentype');
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: 'MinionPro';
    src: url('assets/fonts/MinionPro-Semibold.otf') format('opentype');
    font-weight: 600;
    font-style: normal;
    font-display: swap;
}
```

### Unused Font Files

Two additional font files are present in the repo but are not currently applied in the stylesheet. Do not rely on them being available in future versions:

- `NeutraText-Bold.otf` / `NeutraText-Demi.otf` — declared in an unused `@font-face` block; no `font-family: 'NeutraText'` appears in any style rule
- `DINPro-CondBoldItalic.otf` — declared as `'DINProCondBoldItalic'`; also unused

---

## Color Palette

### Core Application Colors

| Swatch | Hex | Usage |
|--------|-----|-------|
| ![#58585A](https://placehold.co/16x16/58585A/58585A.png) **Charcoal Gray** | `#58585A` | Primary text color, header background, button resting state backgrounds, tooltip backgrounds, legend labels, slider labels. The dominant neutral throughout the UI. |
| ![#1270B3](https://placehold.co/16x16/1270B3/1270B3.png) **Agency Blue** | `#1270B3` | Hover state on primary buttons (County Trends, Map Options), brand color used in Web Awesome component overrides. Core ARC brand blue. |
| ![#ffffff](https://placehold.co/16x16/ffffff/ffffff.png) **White** | `#ffffff` | Header text, button text on hover, UI panel backgrounds (`--ui-panel-bg`). |
| ![#ffeb3b](https://placehold.co/16x16/ffeb3b/ffeb3b.png) **Highlight Yellow** | `#ffeb3b` | Tooltip location name label (high-contrast accent on dark tooltip background). |
| ![#e31a1c](https://placehold.co/16x16/e31a1c/e31a1c.png) **Alert Red** | `#e31a1c` | Popup close button hover color; also the upper-mid stop in the choropleth gradient. |

### Brand Color Scale (Agency Blue Ramp)

Used to override Web Awesome component brand tokens. The `--wa-color-brand-50` value (`#1270B3`) is the baseline.

| Token | Hex |
|-------|-----|
| `--wa-color-brand-95` | `#ddeef9` |
| `--wa-color-brand-90` | `#b8d9f2` |
| `--wa-color-brand-80` | `#7ab8e4` |
| `--wa-color-brand-70` | `#4897d0` |
| `--wa-color-brand-60` | `#1a85d0` |
| `--wa-color-brand-50` | `#1270B3` ← base |
| `--wa-color-brand-40` | `#0d5a8e` |
| `--wa-color-brand-30` | `#094070` |
| `--wa-color-brand-20` | `#062a4a` |
| `--wa-color-brand-10` | `#031525` |

### Extended ARC Brand Palette

These colors are part of the broader ARC organizational palette. Some are used in this application; all are available for use in other ARC applications.

| Swatch | Hex | RGB | Notes |
|--------|-----|-----|-------|
| ![#EE575D](https://placehold.co/16x16/EE575D/EE575D.png) | `#EE575D` | R238 G93 B93 | Coral red |
| ![#636EA0](https://placehold.co/16x16/636EA0/636EA0.png) | `#636EA0` | R99 G110 B160 | Muted violet |
| ![#1270B3](https://placehold.co/16x16/1270B3/1270B3.png) | `#1270B3` | R18 G112 B179 | Agency blue — **primary brand color, used in this app** |
| ![#42ADD3](https://placehold.co/16x16/42ADD3/42ADD3.png) | `#42ADD3` | R66 G173 B211 | Sky blue |
| ![#1AAFA6](https://placehold.co/16x16/1AAFA6/1AAFA6.png) | `#1AAFA6` | R26 G175 B166 | Teal |
| ![#678539](https://placehold.co/16x16/678539/678539.png) | `#678539` | R103 G133 B57 | Olive green |
| ![#98AE3E](https://placehold.co/16x16/98AE3E/98AE3E.png) | `#98AE3E` | R152 G174 B62 | Yellow-green |
| ![#FDB713](https://placehold.co/16x16/FDB713/FDB713.png) | `#FDB713` | — | Bright gold — **not used in this app**, reserved for future use |

### Choropleth Map Gradient (Legend)

The map uses a yellow-to-dark-red sequential gradient for the choropleth fill:

```css
background: linear-gradient(to top,
    #ffffcc 0%,   /* light yellow — lowest values */
    #fed976 25%,  /* yellow */
    #fd8d3c 50%,  /* orange */
    #e31a1c 75%,  /* red */
    #800026 100%  /* dark red — highest values */
);
```

---

## App Header

The fixed header spans the full width at the top of the viewport.

| Property | Value |
|----------|-------|
| Background color | `#58585A` |
| Text color | `#ffffff` |
| Opacity | `1.0` (fully opaque) |
| Height | **50px** (fixed, set explicitly in CSS via `height: 50px; box-sizing: border-box`) |
| Padding | `5px` top/bottom · `20px` left/right |
| Font | DINPro Bold, `29px` (desktop) · `21px` (mobile) |
| Position | `fixed`, `z-index: 2`, spans full viewport width |
| Layout | Flexbox — title text left-aligned, logo right-aligned |

### Logo in Header

The header contains the ARC logo (`assets/arc_logo-small.png`) right-aligned, wrapped in a link to `https://atlantaregional.org/`.

| Property | Value |
|----------|-------|
| File | `assets/arc_logo-small.png` |
| Height (desktop) | `30px` (width auto) |
| Height (mobile) | `16px` (width auto) |

---

## ARC Logo Watermark

A secondary, larger ARC logo appears as a watermark overlaid on the map in the lower-right area.

| Property | Value |
|----------|-------|
| File | `assets/arc_logo.png` |
| Height | `60px` (width auto) |
| Position | `bottom: 30px`, `right: 200px` (absolute) |
| Opacity | `0.8` |
| Drop shadow | `drop-shadow(0 2px 4px rgba(0,0,0,0.2))` |
| Mobile | Hidden (`display: none`) |

The logo links to the ARC website (`https://atlantaregional.org/`) and carries `alt="Atlanta Regional Commission"`.

---

## UI Panel Surfaces

Floating UI panels (legend, month display box, slider container, buttons) use a shared CSS variable for their background. This makes it easy to apply a global opacity or tint change:

```css
:root {
    --ui-panel-bg: rgba(255, 255, 255, 1); /* fully opaque white */
}
```

All panels share:
- `border-radius: 5px`
- `box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2)`
- No border (`border: none`)

---

## Interaction Colors

| State | Color |
|-------|-------|
| Button resting text | `#58585A` |
| Button resting background | `var(--ui-panel-bg)` (white) |
| Button hover background | `#1270B3` (agency blue) or `#58585A` (charcoal) |
| Button hover text | `#ffffff` |
| Close button hover background | `rgba(227, 26, 28, 0.1)` |
| Close button hover icon | `#e31a1c` |

---

## UI Component Library — Web Awesome

The app uses [Web Awesome](https://www.webawesome.com/) (built by the Font Awesome team) as its primary UI component library. All interactive widgets — buttons, drawers, dialogs, sliders, tooltips, radio groups, spinners, and icons — are Web Awesome custom elements (`<wa-*>`). Do not introduce a second component library; use Web Awesome components for any new UI elements.

### CDN Setup

```html
<link rel="stylesheet" href="https://early.webawesome.com/webawesome@3.0.0-beta.5/dist/styles/webawesome.css" />
<script type="module" src="https://early.webawesome.com/webawesome@3.0.0-beta.5/dist/webawesome.loader.js"></script>
```

Both tags are required. The stylesheet provides base component styles and the CSS custom property tokens (including `--wa-color-brand-*` used for theming). The loader script registers all `<wa-*>` custom elements.

### Loading Spinner (`<wa-spinner>`)

The app uses `<wa-spinner>` for all loading states. It inherits `currentColor` for its color and scales with `font-size`.

```html
<!-- Full-screen overlay spinner (app load) -->
<wa-spinner style="font-size: 4rem"></wa-spinner>

<!-- Inline spinner (chart loading states) -->
<wa-spinner style="font-size: 4rem"></wa-spinner>
```

| Usage | Location | Size |
|-------|----------|------|
| App load overlay | `#loadingOverlay` inside `.loading-content` | `font-size: 4rem` |
| Popup chart loading | `#chartLoadingIndicator` inside `.chart-loading` | `font-size: 4rem` |

The spinner color is inherited from the parent element's text color. In the full-screen overlay (dark background), the parent `.loading-content` has `color: white`, so the spinner renders white. No explicit color override is needed.

To prevent a flash of unstyled Web Awesome components before the loader script registers them, this CSS rule hides dialog and drawer elements until they are defined:

```css
wa-dialog:not(:defined),
wa-drawer:not(:defined) {
    display: none;
}
```

---

## Icons — Web Awesome (`<wa-icon>`)

Icons are a subset of the Web Awesome library. They are loaded from the same CDN as the rest of the library (see CDN Setup above) and rendered as inline SVGs via the `<wa-icon>` custom element.

### Usage Syntax

```html
<wa-icon name="icon-name"></wa-icon>               <!-- default (solid) variant -->
<wa-icon name="icon-name" variant="regular"></wa-icon>  <!-- outline/regular variant -->
<wa-icon name="icon-name" size="large"></wa-icon>       <!-- size override -->
```

### Icons Used in This App

| Icon name | Variant | Location |
|-----------|---------|----------|
| `arrow-down` | default (solid) | County Trends button |
| `arrow-right` | default (solid) | Map Options button |
| `info-circle` | default (solid) | About button in Options drawer footer |
| `download` | default (solid) | Download button in Options drawer footer |
| `exclamation-triangle` | default (solid) | Error state in month display and popup |
| `building` | solid + regular | Favicon (see below) |

Browse the full icon library at [webawesome.com/icons](https://www.webawesome.com/icons).

### Color Inheritance

Web Awesome icons render as inline SVGs using `currentColor`. This means **they inherit the text color of their parent element automatically** — no separate color needs to be set on the icon itself. If you change a button's text color on hover, the icon inside it will change with it.

```css
/* No special icon styling needed — the icon inherits color from the button */
#countyTrendsBtn::part(base):hover {
    background-color: #1270B3;
    color: #ffffff;  /* both button text AND wa-icon inside will turn white */
}
```

To override an icon's color explicitly:

```html
<wa-icon name="exclamation-triangle" style="color: #c62828;"></wa-icon>
```

### Dark Mode and Icon Variants — Manual, Not Automatic

**Web Awesome icons do not automatically switch between variants for light vs. dark mode.** The "Nox!" toggle seen in the Web Awesome icon browser is a preview tool on their website only — it is not built-in behavior of `<wa-icon>`.

What actually happens:
- `<wa-icon>` inherits `currentColor`, so if your CSS changes text colors via a `prefers-color-scheme` media query, the icon color will follow
- But the icon will **not** automatically swap from the `solid` variant (filled, better on light backgrounds) to the `regular` variant (outlined, better on dark backgrounds) — that requires manual JavaScript

This app handles the favicon adaptively in `js/favicon.js`, but regular in-page icons are not dark-mode adapted (the app does not implement a dark theme).

### Favicon — Adaptive Dark/Light Mode (Manual)

The browser tab favicon is a special case where dark/light adaptation is implemented. The technique in `js/favicon.js`:

1. **Fetch two SVG variants** of the `building` icon from Web Awesome's shadow DOM:
   - `solid` variant → dark-filled (`#1a1a2e`) for use on light browser tabs
   - `regular` variant → white outline (`#ffffff`) for use on dark browser tabs
2. **Serialize each to a `data:image/svg+xml` URL**, replacing `currentColor` with the explicit color
3. **Detect OS color scheme** using `window.matchMedia('(prefers-color-scheme: dark)')`
4. **Swap the favicon `href`** immediately on load and whenever the OS preference changes

```js
const mq = window.matchMedia('(prefers-color-scheme: dark)');
function update(isDark) {
    link.href = isDark ? darkModeFavicon : lightModeFavicon;
}
update(mq.matches);
mq.addEventListener('change', (e) => update(e.matches));
```

To adapt this pattern for another icon, change the `name` and `variant` arguments passed to `getIconSvg()`, and update the fill colors to suit your application's background colors.
