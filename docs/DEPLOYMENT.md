# OmniVoice — Persistent Cloud Backend Deployment Guide

**Document Version:** 1.0  
**Task Reference:** OV-027  
**Status:** Operational Deployment Standard  

---

## 1. Deployment Architecture

OmniVoice runs as a **single-service, single-worker asynchronous voice backend** serving management APIs, the Operations Console, Server-Sent Events (SSE), and bidirectional carrier WebSocket streams directly over HTTP/1.1 and WSS on port 8000.

```
┌─────────────────────────────────────────────────────────────┐
│                   PSTN TELEPHONY CARRIERS                   │
│                       [Exotel] [Twilio]                     │
└──────────────────────────────┬──────────────────────────────┘
                               │ WSS (8kHz Linear PCM / u-law)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│            PERSISTENT CLOUD HOST (Railway / Fly.io)         │
│                                                             │
│   FastAPI + Uvicorn (Port 8000 -> HTTPS / WSS 443)          │
│   ├── Operations Console (Static assets at /)               │
│   ├── Operations Telemetry (SSE at /api/tenants/{id}/events)│
│   ├── Carrier Media Streams (/ws/exotel/{id}/{secret})      │
│   └── System Health & Readiness (/healthz, /readyz)         │
│                                                             │
│   In-Memory Runtime State:                                  │
│   ├── Active Call Sessions (services.active)                │
│   └── Silero VAD v4 (models/silero_vad.onnx)                │
│                                                             │
│   Persistent Volume Mount:                                  │
│   └── /app/data (SQLite database at /app/data/omnivoice.db) │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Invariants
1. **Single Worker**: Process concurrency is strictly limited to 1 worker (`workers=1`). Active call sessions, rolling history, and SQLite concurrency rely on single-process memory.
2. **No Separate Media Proxy**: The primary FastAPI application directly handles carrier WebSockets (`/ws/exotel/...` and `/ws/twilio`). No secondary gateway process is required in cloud environments.
3. **Persistent Volume Requirement**: SQLite WAL mode requires a durable, POSIX-compliant SSD block volume attached at `/app/data`.

---

## 2. Recommended Cloud Providers

| Provider | Recommended Region | Persistence | WebSocket / SSE | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Railway** *(Primary)* | Singapore (`asia-southeast1`) | Railway Volume (SSD) attached to `/app/data` | First-class, unbuffered | Simplest automated Dockerfile deployment, auto-TLS domain. |
| **Fly.io** *(Alternative)* | Mumbai, India (`bom`) | Fly Volume (`fly vol create`) | Native Fly Proxy | Sub-20ms network latency to Exotel Mumbai/BLR clusters. |
| **Custom Linux VPS** | Bangalore (`blr1`) | Host directory mount (`./data:/app/data`) | Native via Caddy / Nginx | Full control over Docker Compose and systemd. |

---

## 3. Environment Variables & Secret Contract

Configure the following environment variables in the cloud deployment platform (never commit secrets to version control):

```env
# System Configuration
OMNI_ADMIN_TOKEN=<generated_high_entropy_secret_48_chars>
OMNI_DATABASE=/app/data/omnivoice.db
OMNI_PUBLIC_BASE_URL=https://<assigned-cloud-domain>
OMNI_ENABLE_OUTBOUND=false

# Provider Credentials
OMNI_SARVAM_API_KEY=<secret_sarvam_api_key>
OMNI_GROQ_API_KEY=<secret_groq_api_key>
OMNI_EXOTEL_ACCOUNT_SID=<exotel_sid>
OMNI_EXOTEL_API_KEY=<exotel_key>
OMNI_EXOTEL_API_TOKEN=<exotel_token>

# Engine Models & Settings
OMNI_GROQ_MODEL=llama-3.1-8b-instant
OMNI_STT_MODEL=saaras:v3-realtime
OMNI_TTS_MODEL=bulbul:v3
OMNI_TTS_SPEAKER=shubh
OMNI_SILERO_MODEL=models/silero_vad.onnx
OMNI_SEMANTIC_ENABLED=false
```

---

## 4. Deployment Instructions

### Option A: Railway (Zero-CLI / Web UI or CLI)

1. **Create Project**: Link the GitHub repository in the Railway dashboard.
2. **Attach Persistent Volume**:
   - In service settings $\rightarrow$ **Volumes** $\rightarrow$ **Add Volume**.
   - Mount path: `/app/data`.
   - Size: `1 GB` (expandable).
3. **Configure Environment Variables**:
   - Add all variables listed in Section 3 under **Variables**.
4. **Deploy Service**:
   - Railway builds the container using [Dockerfile](file:///C:/Projects/OMNIVOICE-OV027/Dockerfile).
   - Silero VAD weights are automatically baked during build (`python -m omnivoice.cli models`).
5. **Set Public Domain**:
   - In service settings $\rightarrow$ **Networking** $\rightarrow$ **Generate Domain** (e.g. `https://omnivoice-production.up.railway.app`).
   - Update `OMNI_PUBLIC_BASE_URL` to match this generated domain.

### Option B: Docker / Compose (Self-Hosted VPS)

1. Clone repository to server.
2. Initialize environment and download models:
   ```bash
   cp .env.example .env
   # Edit .env with production credentials
   docker compose build
   docker compose up -d
   ```
3. Expose port 8000 via Caddy or Nginx with WebSocket upgrade and TLS certificate.

---

## 5. Health & Readiness Verification

Once deployed, verify the endpoints remotely:

```bash
# 1. Process Liveness Check (Must return HTTP 200)
curl -i https://<assigned-cloud-domain>/healthz

# Expected Response:
# HTTP/1.1 200 OK
# {"status":"ok","version":"0.1.0"}

# 2. Voice Engine Readiness Check (Must return HTTP 200)
curl -i https://<assigned-cloud-domain>/readyz

# Expected Response:
# HTTP/1.1 200 OK
# {"ready":true}
```

*Note on Semantic Retrieval:* If `OMNI_SEMANTIC_ENABLED=false`, `/readyz` will return `{"ready": true}` using the exact FAQ + lexical fallback engine.

---

## 6. Exotel Telephony Cutover

Do **not** alter Exotel telephony configuration until `/healthz` and `/readyz` return HTTP 200.

### Cutover Procedure
1. Navigate to the Operations Console at `https://<assigned-cloud-domain>/`.
2. Authenticate using `OMNI_ADMIN_TOKEN`.
3. In **Phone Numbers** / **Lines**, select the active Exotel carrier line and click **Connection Settings**.
4. Copy the permanent WebSocket Stream URL:
   ```
   wss://<assigned-cloud-domain>/ws/exotel/<line_id>/<stream_secret>
   ```
5. Log into the **Exotel Dashboard** $\rightarrow$ **App Bazaar** / **Flow Builder**.
6. Open the active Voicebot Flow $\rightarrow$ Select the **Voicebot Applet**.
7. Paste the copied WSS URL into the **Stream URL** field.
8. Click **Save** and **Publish** the flow.

---

## 7. Live PSTN Smoke Test

Conduct a single controlled mobile telephone call to the virtual number (`+914954269065`):

1. **Connection**: Carrier bridges PSTN call to `wss://<assigned-cloud-domain>/ws/exotel/...`.
2. **Greeting**: Initial tenant greeting plays audibly and clearly.
3. **Dialogue**: Speak a conversational query; verify speech detection, Sarvam STT transcription, Groq LLM inference, and Sarvam TTS synthesis.
4. **Operations Console**: Verify live call appears in the Operations Console with active status, turn counter increments via SSE, and final turn metrics persist upon hangup.

---

## 8. Rollback Procedure

If the cloud deployment experiences connection drops or provider failures:

1. Open the Exotel Dashboard $\rightarrow$ Flow Builder.
2. Re-enter the previous known-good development tunnel WSS URL.
3. Click **Save** and **Publish**.
4. Telephony routing immediately reverts to the local development environment (< 60 seconds).

---

## 9. Known Operational Limitations

1. **In-Memory Session Volatility**: In-flight calls reside in process memory. Container restarts or redeployments will drop active calls.
2. **Single Replica Only**: Multiple container replicas must **not** be launched against the same SQLite database file.
3. **WebSocket Proxy Timeouts**: Ensure reverse proxy WebSocket read timeouts are configured to at least 120 seconds or sustain ping frames.
