# Console V2 design system

The OmniVoice Operations Console is a workspace for supervising live telephone agents and reviewing persisted call evidence. Its presentation is calm, precise, and operational. This document describes the final frontend in `omnivoice/static/`; it does not define a new backend contract or imply that an operator can take over, transfer, or terminate a call.

## Information hierarchy

The overview leads with recorded workspace performance, then current call activity, recent sessions, and readiness. P95 response latency is the time from final transcript to first outbound audio sent by the server; it excludes carrier transit and acoustic playback. Active calls appear from the existing authenticated event stream, and the empty state clearly says when none are in progress. Runtime details and additional metrics remain available behind disclosure.

The desktop navigation places Operations before Configure. Enterprise selection stays at the top, destinations scroll independently, and voice-system status remains at the bottom. At tablet and phone widths, a labeled menu opens the same routes and closes after selection. The top bar carries page context, search-pages command palette, theme toggle, console connection state, and disconnect. Console connection status is distinct from voice-engine readiness.

Call history uses a table on larger screens and cards on phones. Both use the existing filters, pagination, and call inspector. Inspectors show the session summary first, conversation turns on a readable timeline, and separate Metrics, Actions, and Technical tabs. The inspector is a side panel on laptops and a full-screen panel on phones. The search-pages palette remains centered within the viewport.

## Visual system

The default theme uses an off-white canvas, white surfaces, a pale sage navigation rail, dark navy text, and restrained teal emphasis. Dark mode maps the same semantic roles to deep blue-green surfaces and light text. Status color always accompanies text. The primary action is distinct from read-only values. The semantic tokens are defined in `omnivoice/static/console-theme.css` over the structural base in `style.css`; the default preference is light and is stored under `omni-theme-v3` to avoid carrying an obsolete theme choice into this refinement.

Self-hosted Geist Sans and Geist Mono are bundled in `omnivoice/static/fonts/` with the SIL Open Font License. The variable font files came from [Vercel's Geist v1.8.1 release](https://github.com/vercel/geist-font/releases/tag/v1.8.1). System fallbacks cover glyphs outside those fonts. Body text begins at 15 px, operational labels remain readable, and IDs and timings use monospaced digits. Spacing follows 8, 12, 16, 24, and 32 px intervals. Motion is limited to control-level state transitions; whole-page navigation is immediate. Reduced-motion preferences suppress remaining transitions where applicable.

## Component and safety rules

- **Live calls:** Read-only session rows use authenticated events. Disconnected and reconnecting states remain visible; no simulated calls are shown.
- **Knowledge, numbers, actions, and settings:** Existing API calls, fields, authentication, and tenant scope remain intact. Carrier registration is labeled as local configuration, not proof of a successful PSTN call.
- **Action lifecycle:** Staged, confirmed, and committed states reflect persisted records. The interface never bypasses the backend confirmation gate.
- **Status and analytics:** Charts use persisted tenant calls and explicit counts. Provider configuration is not presented as provider uptime, and server timing is not called mouth-to-ear latency.
- **Accessibility:** Semantic buttons, labeled fields, text statuses, visible focus rings, table headers, accessible dialogs, and keyboard-operable call-inspector tabs are required. The command palette supports Up/Down/Enter/Escape; inspector tabs support Left/Right/Home/End.

## Verification

The isolated browser workflow covers locked/auth state, enterprise creation and selection, knowledge and phone-number operations, every console route, call and action inspection, theme switching, keyboard tabs, mobile navigation and call cards, JavaScript errors, and zero document overflow at 1920, 1440, 1024, 768, and 390 px. Light and dark screenshots are inspected at laptop, tablet, and phone widths. The screenshots are local QA artifacts, not research measurements.
