# Design System Specification

## 1. Overview & Creative North Star
The core objective of this design system is to evolve regional data visualization from a static "report" into a dynamic, editorial experience. We are moving away from the rigid, grid-bound layouts of traditional dashboards toward a concept we call **"The Analytical Lens."**

This system treats data not as a series of isolated charts, but as a fluid narrative. By utilizing a **High-End Editorial** approach, we prioritize breathing room, intentional asymmetry, and depth. The "template" look is discarded in favor of overlapping surface layers and high-contrast typography scales that guide the eye naturally through complex regional insights. It is a system built on trust, authority, and interactive discovery.

---

## 2. Colors & Tonal Depth
Our palette is anchored in deep, authoritative blues and neutrals, punctuated by high-chroma accents that breathe life into data.

### The Palette
- **Primary Base:** `primary` (#002c53) — Reserved for high-level navigation and foundational branding.
- **Secondary (Data Teal):** `secondary` (#006b5f) — Used for growth metrics and positive trends.
- **Tertiary (Data Coral):** `tertiary_fixed_variant` (#852300) — Used for highlighting specific deltas or divergent data points.
- **Surface Foundations:** `surface` (#f3faff) to `surface_container_highest` (#cfe6f2).

### The "No-Line" Rule
To achieve a premium, modern feel, **1px solid borders are prohibited** for defining sections. Boundaries must be defined through:
1. **Background Shifts:** Place a `surface_container_low` section directly against a `surface` background.
2. **Tonal Transitions:** Use subtle shifts between `surface_container` tiers to create logical groupings.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. 
- Use `surface_container_lowest` (#ffffff) for the primary content cards to make them "pop" against the `surface` background.
- Nest smaller data modules inside these cards using `surface_container_low` (#e6f6ff) to create a sense of organized density without adding visual noise.

### The "Glass & Gradient" Rule
For interactive elements like floating filter panels or "View Details" overlays, employ **Glassmorphism**. Use semi-transparent variants of `surface_container` with a `backdrop-blur` (12px–20px). Main CTAs should utilize a subtle linear gradient from `primary` (#002c53) to `primary_container` (#1a426e) to add a "soul" and depth that flat hex codes cannot provide.

---

## 3. Typography
We utilize a dual-font strategy to balance technical precision with editorial elegance.

*   **Headlines & Display:** **Inter** is used for its geometric clarity. High contrast in scale (e.g., `display-lg` at 3.5rem vs `title-sm` at 1rem) creates a clear information hierarchy.
*   **Data Labels:** **Public Sans** is utilized for `label-md` and `label-sm`. Its slightly narrower apertures ensure that dense regional data points remain legible even at small sizes.

**Editorial Intent:** Use `display-md` for the "Hero" metric of a page (e.g., total population) to act as a visual anchor. Smaller `headline-sm` units should be used for chart titles, ensuring they don't compete with the data itself.

---

## 4. Elevation & Depth
Depth is a functional tool, not a decoration. We convey hierarchy through **Tonal Layering**.

### The Layering Principle
Rather than shadows, use the surface tiers. A `surface_container_highest` sidebar provides a natural physical boundary against a `surface_bright` main stage. 

### Ambient Shadows
When a card must float (such as a dropdown or an active modal):
- **Blur:** 24px to 40px.
- **Opacity:** 4% to 8%.
- **Color:** Use a tinted version of `on_surface` (#071e27) rather than pure black to ensure the shadow feels like a part of the environment.

### The "Ghost Border" Fallback
If accessibility requirements demand a border (e.g., high-contrast mode), use a **Ghost Border**. Apply `outline_variant` (#c3c6d0) at **15% opacity**. Never use 100% opaque lines; they create "visual cages" that restrict the flow of data.

---

## 5. Components

### Buttons
- **Primary:** Gradient fill (`primary` to `primary_container`), `on_primary` text, `md` (0.375rem) roundedness.
- **Secondary:** Surface-tonal. Use `secondary_container` with `on_secondary_container` text.
- **Ghost:** No background. Use `primary` text with a subtle `surface_variant` hover state.

### Cards & Data Modules
**Strict Rule:** No dividers. Use vertical white space from the spacing scale (e.g., 24px or 32px) to separate the header from the chart body. Cards use `surface_container_lowest` (#ffffff) with `xl` (0.75rem) roundedness for a soft, approachable feel.

### Navigation
The sidebar should feel integrated. Use `surface_container_low` for the background and `primary_fixed_dim` for the active state indicator—a vertical pill shape rather than a full-width block.

### Interactive Data Points (Chips)
Use `secondary_fixed` (#8df5e4) for active filters. These should have a "Glass" effect when hovered, increasing the backdrop-blur to signal interactivity.

---

## 6. Do's and Don'ts

### Do
- **DO** use asymmetry. Large charts should be balanced by smaller, focused metric "callouts" to create a dynamic rhythm.
- **DO** use the `on_tertiary_container` (#ff8e6b) coral sparingly to draw the eye to critical alerts or data anomalies.
- **DO** prioritize white space. If a dashboard feels "full," increase the padding rather than shrinking the font.

### Don't
- **DON'T** use 100% black text. Always use `on_surface` (#071e27) for better optical comfort.
- **DON'T** use the "box-in-a-box" layout style. If you need to group items, use a background color shift, not a border.
- **DON'T** use standard drop shadows. If an element doesn't feel "raised" enough with tonal shifting, use the Ambient Shadow specification.