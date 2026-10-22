# Final demo freeze readiness — repository-side audit

This is an engineering readiness assessment, not a new research measurement or a claim that a physical PSTN call was made. See the [runbook](FINAL_DEMO_RUNBOOK.md) and [canonical evidence index](research/FINAL_EVIDENCE_INDEX.md).

| Severity | Finding | Disposition |
| --- | --- | --- |
| Critical | No newly verified critical defect in the reviewed local paths. | Continue controlled validation; this is not a formal penetration test. |
| High | Call-end logging previously serialized the full metrics object, which can contain transcripts and responses. Nearby event exceptions and carrier disconnect reasons could also carry untrusted text. | Fixed on this branch: fixed numeric summary and exception categories only; focused privacy regression test. Operational SQLite/SSE records retain their existing access controls. |
| High | Container startup ignored a platform-assigned `PORT`. | Fixed on this branch with an explicit-port override test. Railway remains undeployed. |
| High | KooKoo/Ozonetel WebSocket contract and normal playback receipt have no account-specific PSTN confirmation. | Adapter remains parked on `codex/kookoo-carrier-adapter`. No KooKoo booking commit can be claimed; user/provider validation is required. |
| High | The separate console checkout has uncommitted changes to retained OV-031 timing evidence. | Left untouched. Do not merge that artifact as a new benchmark without provenance review. The console's isolated browser workflow passed. |
| Medium | Repeatable final demo data and public fallback required manual, error-prone setup. | Added marked synthetic fixture, reset/dry-run, read-only preflight, and tested temporary tunnel launcher. Reset refuses a tenant with a carrier line or active call. |
| Medium | Deployment guide contained a machine-local Dockerfile URI and a hardcoded historic phone number. | Replaced with repository-relative instructions and number selected from the console. |
| Low | Cloudflare Quick Tunnel URL is temporary and may take time to propagate. | Local and public `/healthz` and `/readyz` returned HTTP 200 in a controlled smoke; not a stability or uptime claim. |
| Defer | Railway payment/platform readiness, Exotel credits, KooKoo KYC/DID/protocol confirmation. | External administrative dependencies; no subscription, KYC, dashboard or carrier account was changed here. |

## Freeze classification

- **Ready now:** deterministic local rehearsal, isolated synthetic knowledge/lead/slots, safe reset/preflight, server and browser checks, and reviewed deployment configuration.
- **Waiting on external provider:** a current physical sales-agent PSTN call, KooKoo account-specific stream verification, Exotel credits, and Railway service creation.
- **Optional after demo:** external CRM/calendar connectors, PostgreSQL/Redis migration, distributed capacity and production retention policy.
- **Do not change before review:** retained research artifacts and the parked carrier/console branches without independent validation; keep exact metric definitions and historical-versus-current evidence labels.
