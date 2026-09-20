# Theme Preference Rule: White / Light Theme Default

1. **Default Theme Requirement**:
   - The default, first-visit, and unauthenticated theme for both the customer-facing landing page (`landing/`) and the developer operations console (`omnivoice/static/`) MUST ALWAYS BE **Light / White Theme**.
   - All future pages, components, dashboards, modals, and marketing assets must render in Light / White theme by default.

2. **Color System & Aesthetics**:
   - Light Theme Palette:
     - Background / Paper: `#FFFFFF` or `#F8FAFC`
     - Foreground / Body Text: `#0F172A` (high-contrast slate-900, meeting WCAG AAA)
     - Cards / Surfaces: `#FFFFFF` with `#E2E8F0` borders and subtle soft drop-shadows
     - Primary Accent: `#059669` (rich emerald) with `#047857` hover
     - Muted Text: `#475569` (slate-600)
   - Zero Eye Strain: Avoid unstyled glare; maintain crisp typography, balanced whitespace, and subtle slate borders.

3. **Dual-Theme Support**:
   - Dark mode must remain fully supported as an opt-in toggle for users who prefer it.
   - Dark mode preference must be stored in `localStorage` under key `"omni-theme"`.
   - When no preference is saved in `localStorage`, the system MUST default to `"light"`.
