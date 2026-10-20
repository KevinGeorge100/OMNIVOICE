# Console V2 design system

The Operations Console is an operator workspace for live telephone sessions. It presents observed state, recorded evidence, and existing controls without decorative claims or simulated operational data. This design applies to the plain HTML, CSS, and JavaScript console in `omnivoice/static/`; it does not change any backend contract.

## Principles

1. Put current state and the next operational action first. Read-only configuration must look read-only.
2. Distinguish configured capability from verified provider health. Local timing never implies caller mouth-to-ear latency.
3. Keep conversation readable; move timing and identifiers into separate call-inspector tabs.
4. Use compact tables for records, restrained panels for distinct tasks, and empty states that say what will populate them.
5. Show semantic status with text. Color reinforces meaning but is never the only signal.

## Tokens

The semantic variables live in `omnivoice/static/style.css`. Dark mode is the default; light mode maps the same roles to lighter values. The saved `omni-theme` preference is respected.

| Role | Dark | Light | Use |
|---|---|---|---|
| Canvas `--paper` | `#0b0d10` | `#f5f6f8` | Main background |
| Navigation `--navigation` | `#0f1115` | `#fbfcfd` | Persistent sidebar |
| Surface `--surface` | `#14171c` | `#ffffff` | Panels and tables |
| Raised `--surface-raised` | `#191d23` | `#f7f8fa` | Headers and quiet control fills |
| Border `--border-subtle` | `#272c34` | `#dce1e8` | Structural dividers |
| Primary text `--ink` | `#f2f4f7` | `#1c2735` | Titles and values |
| Secondary text `--ink-secondary` | `#a7afba` | `#485467` | Explanations and labels |
| Muted text `--ink-muted` | `#8792a1` | `#596779` | Metadata |
| Accent `--accent` | `#7da2ff` | `#275cce` | Navigation, focus, and deliberate actions |

Success, warning, and danger use dedicated `--success`, `--warning`, and `--danger` roles with matching subtle backgrounds. Green is reserved for healthy or committed outcomes; amber denotes setup/pending; red denotes failure or destructive actions. Provider names and descriptive metrics do not inherit a health color.

## Type, spacing, and geometry

- System sans stack (Inter when installed, Segoe UI/system fallback) avoids a remote font dependency. Bundled JetBrains Mono is used for IDs, timings, and compact metadata.
- Page titles use 21–24 px semibold; section titles 13 px; body/table text 11–13 px; major metrics 23–29 px. Numeric figures use tabular digits.
- The spacing rhythm is 4, 8, 12, 16, 20, and 28 px. Dividers, not nested cards, separate related data.
- Panels use 8 px radii; controls use 5 px. Shadows are limited to dialogs and transient feedback.
- Motion is limited to 150–160 ms state changes. `prefers-reduced-motion` removes transitions and animation.

## Shell and navigation

The desktop shell has a 232 px sidebar, a 55 px context bar, and a content canvas capped at 1540 px. The sidebar groups Configure, Operate, and Insights/System routes while preserving every existing `data-page` route. The current route has both `aria-current="page"` and a visible accent edge. The workspace selector remains available at narrow widths.

The top bar contains the page context, a navigation-only command palette (`Ctrl+K` / `Cmd+K`), theme toggle, actual server readiness state, and the existing connect/disconnect action. The palette does not query a new backend endpoint. The locked state centers the existing token workflow and keeps the authenticated shell visually and semantically hidden until a token is present.

## Component patterns

- **Status:** text plus semantic border/fill. `Configured` is not presented as provider uptime. `Live` is derived from active-session data; action states use persisted values (`staged`, `armed`, `committed`, `cancelled`).
- **Tables:** one shared scroll container with sticky headers, thin row dividers, hover indication, readable numeric columns, and existing server-backed search, filters, and pagination. Narrow screens scroll the table horizontally instead of turning rows into cards.
- **Panels:** only for distinct operations such as runtime status, recent calls, setup, agent configuration, and analytics. Empty states provide a cause or next step without illustration.
- **Call inspection:** Conversation is the default tab. Metrics, Actions, and Technical use existing persisted call/turn/action fields. Missing timing is omitted or shown as unavailable; no invented trace stage appears.
- **Live calls:** compact session panels use only event-stream fields; the focused inspector groups current metadata, last recorded exchange, and available server timing.
- **Actions:** a filterable audit table and detail lifecycle reflect persisted states. The interface never arms or commits a write.
- **Forms and overlays:** existing modal forms, field names, and handlers remain. Dialogs use a clear heading, inline error, visible focus, and a Close label for read-only inspection. Exotel stream credentials are masked on screen; a deliberate copy action preserves carrier setup access.
- **Charts:** simple horizontal bars show recorded daily call volume, carrier mix, and outcome counts with explicit count labels and zero-based lengths. No research fixture number is presented as live analytics.

## Responsive and accessibility rules

At 1100 px, metric strips form two columns and the overview modules stack. At 800 px, the sidebar becomes a horizontal route rail while the workspace selector stays accessible; the content and settings collapse to one column. At 600 px, the context bar simplifies and operational tables retain horizontal scroll. QA checks 1920, 1440, 1024, 768, and 390 px viewports for document overflow.

The shell uses semantic buttons, table headers, labeled fields, visible `:focus-visible` rings, text status, accessible dialog labels, and reduced-motion support. Command navigation supports Up/Down/Enter/Escape. The browser workflow exercises auth, tenant selection, navigation, forms, call detail tabs, action inspection, light/dark themes, and narrow viewport behavior.
