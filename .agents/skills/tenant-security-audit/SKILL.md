---
name: tenant-security-audit
description: >-
  Audits multi-tenant isolation, RAG vector segregation, carrier authentication, SSRF boundaries, secret leakage, and two-phase action gating when modifying FastAPI routes, store operations, RAG/FAISS, tenant lines, webhooks, actions/tools, or document ingestion.
---

# Tenant Security & Multi-Tenant Audit Skill

Authoritative security invariants, isolation boundaries, SSRF mitigations, and execution safeguards for OmniVoice enterprise multi-tenant architecture.

Derived from `omnivoice/store.py`, `omnivoice/rag.py`, `omnivoice/actions.py`, `omnivoice/app.py`, and `docs/DEFINITION_OF_DONE.md`.

---

## 1. Multi-Tenant Data Isolation

### 1.1 Store & Database Operations (`omnivoice/store.py`)
* **Tenant Scoping Guarantee**:
  - Every tenant-owned resource (calls, carrier lines, knowledge entries, write actions, registered tools) must be partitioned by `tenant_id`.
  - Storage methods must enforce tenant boundaries on all queries, mutations, and deletions. (Note: Enforce tenant boundaries via access-layer methods or scoped query parameters; do not mandate a single rigid SQL syntax as long as the isolation invariant is provably maintained).
  - Cross-tenant data access, modification, or deletion must be strictly impossible.
* **Foreign Key Constraints**: SQLite schema must maintain `PRAGMA foreign_keys = ON;` with cascade behavior where defined.

### 1.2 RAG & Vector Index Isolation (`omnivoice/rag.py`)
* **Zero Cross-Tenant Leakage**: Knowledge belonging to Tenant A must **never** be retrievable by or exposed to Tenant B.
* **In-Memory Partitioning**: FAISS indices (`IndexFlatIP`), embeddings, and document chunk matrices must be instantiated and queried strictly per-tenant.
* **Exact FAQ Match Scoping**: FAQ fast-path caches must match only against the calling session's tenant knowledge repository.

---

## 2. Authentication & Carrier Security

### 2.1 API & Administrative Authentication
* **Admin Boundaries**: Routes managing tenant provisioning, global engine metrics, or platform configuration require administrative authentication via `Settings.admin_token` (Bearer token).
* **Tenant Boundaries**: Tenant-scoped routes require valid tenant authentication or authorization dependencies verifying access rights to the target `tenant_id`.

### 2.2 Carrier Ingress Verification
* **Twilio Telephony**:
  - Webhooks validate `X-Twilio-Signature` HMAC-SHA1 using the line's auth token where configured.
  - WebSocket media connections validate call SID and tenant line association.
* **Exotel Telephony**:
  - Exotel media stream applets connect to `/ws/exotel/{line_id}/{token}`.
  - Verification validates `{token}` against the line's configured `stream_secret` in the database.
  - *Architectural Notice*: Exotel media streaming applets currently do NOT support custom WebSocket handshake authorization headers; authentication must rely on mechanisms supported by the carrier. Do NOT invent unsupported custom headers.

---

## 3. Server-Side Request Forgery (SSRF) Prevention

### 3.1 External Action Endpoints (`omnivoice/actions.py`)
* **Mandatory Preflight Validation**: All user-configured external tool endpoints must be validated via `validate_public_url` prior to registration and execution.
* **Network Restrictions**:
  - Protocol: Enforce HTTPS only (`https://`).
  - Port: Default HTTPS port 443 only.
  - IP Address Bans: Block loopback (`127.0.0.0/8`, `::1`), private RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16`, `fe80::/10`), cloud metadata endpoints (`169.254.169.254`), and broadcast/multicast ranges.
  - Hostname Resolution: Resolve DNS hostnames and verify resolved IP addresses against the forbidden CIDR ranges to block DNS rebinding.

---

## 4. Secrets & Credentials Hygiene

* **Zero Secret Leakage**:
  - No plain API keys, tokens, or stream secrets may appear in:
    - Log files, stdout, or stderr.
    - Exception tracebacks or HTTP error responses.
    - URL query parameters where preventable.
    - Frontend browser responses or client-side JavaScript console.
    - Git commits, pull requests, or diffs.
    - Test fixtures committed to repository.
    - Screenshots or walkthrough artifacts.
* **Environment Configuration**: Secrets must be loaded exclusively via `pydantic-settings` from environment variables (`.env` or process environment), with `.env` permanently excluded from version control via `.gitignore`.

---

## 5. Enterprise Action Gating (Two-Phase Commit)

### 5.1 Confirmation Lifecycle (`omnivoice/actions.py`)
Any tool with side effects (write actions such as bookings, cancellations, payments, database updates) must strictly adhere to the four-stage lifecycle:
1. `STAGED`: Tool arguments and payload are validated, pending caller confirmation.
2. `ARMED`: Carrier audio playback plays confirmation prompt; playback mark confirms the prompt was heard.
3. `CONFIRMED`: Caller speaks an explicit phrase matching the tenant's configured confirmation phrase (exact match required).
4. `COMMITTED`: External HTTP POST is executed, and result is returned to the call session.

> [!CRITICAL]
> No side-effect action may bypass the armed/confirmed state machine. Unconfirmed, aborted, or interrupted turns must transition to `CANCELLED` or `EXPIRED`.

---

## 6. Audit Checklist

Before accepting changes to routes, storage, actions, or knowledge:
- [ ] Every database operation includes strict `tenant_id` scoping.
- [ ] FAISS vector index queries cannot retrieve chunks from another tenant.
- [ ] Admin endpoints reject requests with missing or invalid Bearer tokens.
- [ ] External HTTP requests validate target URLs against SSRF CIDR filters.
- [ ] Two-phase action confirmation is preserved for all side-effecting operations.
- [ ] No tokens, keys, or secrets are printed to logs or returned in error payloads.
