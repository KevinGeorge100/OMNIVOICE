# Vobiz Voice API carrier adapter

Status: **synthetic validation only; no Vobiz PSTN call has been made**. This adapter is built on stable main. The KooKoo worktree is separate and is not a runtime carrier in this branch.

## Protocol basis (checked 23 October 2026)

- [Vobiz `<Stream>` reference](https://www.vobiz.ai/docs/xml/stream) defines the `Response`/`Stream` XML, `bidirectional`, `keepCallAlive`, `audioTrack`, inbound `contentType`, and WSS URL as element text.
- [Stream events](https://www.vobiz.ai/docs/xml/stream/stream-events) defines inbound `start`, `media`, `playedStream`, `clearedAudio` and outbound `playAudio`, `checkpoint`, `clearAudio`, `stop`. It explicitly says **no inbound `stop` JSON is guaranteed**; the WebSocket close is the normal end signal. The adapter also accepts a `stop` event defensively if one arrives.
- [Checkpoint](https://www.vobiz.ai/docs/xml/stream/checkpoint-event) says `playedStream` carries `event` and `name` only and only arrives after uninterrupted queued playback. [Clear audio](https://www.vobiz.ai/docs/xml/stream/clear-audio) says new playback should wait for `clearedAudio`.
- [Callbacks](https://www.vobiz.ai/docs/concepts/callbacks) document form-encoded POST and `CallUUID`, `From`, `To`, `Direction`/`Event`; [callback validation](https://www.vobiz.ai/docs/concepts/validating-callbacks) documents optional V2/V3 HMAC-SHA256 URL-and-nonce signatures. Signature headers are not guaranteed unless callback credentials are configured. OmniVoice always requires the per-line secret in both the Answer URL and WSS path, and validates V2/V3 when present and the Vobiz Auth Token is configured. A missing signature is **not** proof of carrier origin.
- [Applications](https://www.vobiz.ai/docs/applications) and [create application](https://www.vobiz.ai/docs/applications/create-application) describe application Answer URL, POST method, and attaching an owned number. [Outbound call API](https://www.vobiz.ai/docs/call/make-call) specifies `POST /api/v1/Account/{auth_id}/Call/` with `X-Auth-ID`, `X-Auth-Token` and a JSON body. Generic API support is documented; **trial-account outbound permission and verified-recipient restrictions remain unverified**.

## Architecture and media contract

```
Vobiz PSTN → protected Answer webhook → <Stream> → authenticated WSS
             → μ-law 8 kHz decode → canonical PCM16 mono 8 kHz
             → existing CallSession / Silero / Gnani or Sarvam / Groq / RAG / tools
             → existing ActionEngine → existing TTS PCM16 8 kHz
             → μ-law encode → playAudio → Vobiz PSTN
```

The adapter requests **inbound** `audio/x-mulaw;rate=8000` and checks `start.mediaFormat.encoding=audio/x-mulaw`, `sampleRate=8000`, and the inbound track. Each `media.payload` is base64-decoded and G.711 μ-law-decoded with the existing codec. Outbound 320-byte PCM frames become 160-byte μ-law frames (20 ms), base64-encoded as `playAudio.media.payload`, with `contentType=audio/x-mulaw`, `sampleRate=8000`, and the active `streamId`. No WAV/MP3 headers are sent. Codec metadata is directional: the XML `contentType` does **not** configure outbound audio.

The existing session, VAD, STT, dialogue, RAG, tools, action engine, TTS, persistence, per-tenant capacity, and telemetry are reused. No database migration is needed: `lines.provider` and `calls.provider` are text columns. The local OmniVoice call UUID remains the primary call ID; SHA-256 hashes of Vobiz's `start.callId` and `start.streamId` are retained in call metrics for correlation without exposing raw provider identifiers in the console. The WSS line ID binds the session to exactly one tenant.

## Routes and Answer XML

- `POST /webhooks/vobiz/{line_id}/{stream_secret}`: form-encoded Answer URL; validates the line/provider and secret with constant-time comparison, checks an HTTPS public origin, optionally validates V2/V3 signature when supplied, and returns `application/xml`. It never records caller numbers or the body.
- `WS /ws/vobiz/{line_id}/{stream_secret}`: validates the line/provider and secret **before accepting**, then validates `start` metadata before allocating the call. No separate Vobiz-supplied bearer header is assumed.

The generated XML has this shape; all URL text is XML-escaped and the actual secret is never printed here:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response><Stream bidirectional="true" keepCallAlive="true" audioTrack="inbound" contentType="audio/x-mulaw;rate=8000">wss://PUBLIC_HOST/ws/vobiz/LINE_ID/STREAM_SECRET</Stream></Response>
```

`keepCallAlive=true` runs the stream exclusively. We do not configure a status callback or a hangup URL because the WebSocket close is sufficient for live session cleanup and there is no separate status handler in this adapter. Vobiz's own docs distinguish an HTTP `StopStream` callback from the WebSocket close. Carrier-provided status events therefore are **not** a substitute for a real PSTN validation.

## Configuration and line registration

Required for inbound: `OMNI_PUBLIC_BASE_URL=https://PUBLIC_HOST`, a running publicly reachable HTTPS/WSS endpoint, a tenant and registered `provider=vobiz` line, and working OmniVoice speech/LLM providers. `OMNI_VOBIZ_AUTH_ID` and `OMNI_VOBIZ_AUTH_TOKEN` are needed for outbound calls; the token is also used to verify a V2/V3 signature **if** Vobiz sends one. Credentials are `SecretStr` values and belong only in a private `.env`/process environment. `OMNI_ENABLE_OUTBOUND=false` remains the default.

In the console, choose **Phone numbers → Connect a phone number → Vobiz**, enter the existing trial number in E.164 format, then open **Connection details → Copy protected URL**. The button copies the full Primary Answer URL to the Windows/browser clipboard without displaying the secret. The authenticated tenant `GET /api/tenants/{tenant_id}/lines/{line_id}/connection` API is an alternative for operators using an API client. Keep request paths out of reverse-proxy access logs; both carrier routes contain a routing secret. Do not paste the URL in tickets or screenshots.

## Vobiz Console setup after a public endpoint exists

1. Verify `OMNI_PUBLIC_BASE_URL` is the actual HTTPS public origin and its WSS upgrade reaches this FastAPI process. `http://127.0.0.1:8000` cannot receive Vobiz calls.
2. Register the existing trial number as a Vobiz line in the correct OmniVoice tenant. Copy the protected Answer URL from its Connection details.
3. In **Voice Applications**, create an application with **Application name: `OmniVoice`**; **Primary Answer URL: the copied protected URL**; **Method: POST**. Leave **Hangup URL** and **Fallback URL** blank. Keep **Default endpoint app: OFF** and **Public URI: OFF** unless an operator has a separate documented need.
4. Save, then link the already assigned trial number to the `OmniVoice` application. Do not buy another number or alter other applications.
5. Make one manually authorized inbound test call. Check greeting, caller turn, response, barge-in, call history and capacity release. Check the Vobiz dashboard's own call log for its `CallUUID`; compare with locally retained hashes if correlation is needed. Do not infer latency or reliability from one call.

The protected URL has the **shape** `https://PUBLIC_HOST/webhooks/vobiz/LINE_ID/STREAM_SECRET`. Never paste a real secret into documentation. The console clipboard control is the safe way to obtain the exact URL.

## Outbound trial option

The existing tenant-scoped `POST /api/tenants/{tenant_id}/dial` path supports a Vobiz line using the officially documented JSON call API. It is disabled until `OMNI_ENABLE_OUTBOUND=true`, and each request must supply a destination E.164 number and `consent_confirmed=true`. The console's **Place an outbound call** button is an explicit, user-initiated action; no scheduled or automatic call is created by this adapter. Calls may use trial balance or incur charges. Ask Vobiz to confirm trial recipient permissions before using this path; no live call was attempted during development. If the REST submission times out, check Vobiz call logs before retrying because the outcome may be uncertain.

## Playback, interruption and action safety

`checkpoint` follows each spoken response. A matching WebSocket `playedStream.name` marks playback complete; only a matching outstanding mark can arm an existing staged write. An interrupt clears the pending marks before sending `clearAudio`, so a delayed or duplicate acknowledgement cannot arm a cancelled action. The adapter waits for the matching `clearedAudio.streamId` before sending replacement audio. If the acknowledgement does not arrive promptly, playback fails closed instead of racing a stale clear. No `playedStream` timeout is treated as confirmation. Explicit caller verbal confirmation is still required for a staged write to commit through ActionEngine.

## Local validation and limits

Run `.venv/Scripts/python.exe -m pytest tests/test_vobiz.py -q` for the **SYNTHETIC / NON-PSTN** route-and-media rehearsal. The test drives the real Answer route and WSS route with Vobiz-shaped `start`, `media`, `playedStream`, `clearedAudio`, and a defensive `stop`; the AI session is mocked so it makes no provider request or phone call. It checks codec framing, capacity release, persistence, tenant isolation, wrong format, provider failure and acknowledgement safety. This proves adapter behavior locally, **not** carrier connectivity, handset playback, trial entitlement, or mouth-to-ear latency.

Vobiz trial constraints, production carrier behavior, real PSTN barge-in timing, callback signature coverage, and public WSS reachability remain to be verified in a controlled live call. `maxRetries` defaults to zero; this adapter does not claim reliable reconnection after a mid-call carrier drop.

## Carrier differences

| Carrier | Inbound format | Outbound command | Playback completion | Clear command | Deployment state |
| --- | --- | --- | --- | --- | --- |
| Exotel | PCM16/8 kHz | `media` | `mark` | `clear` | Existing integration unchanged |
| Vobiz | μ-law/8 kHz, base64 | `playAudio` with declared codec/rate | `checkpoint` → `playedStream` | `clearAudio` → `clearedAudio` | Adapter locally validated; PSTN pending |
| KooKoo/Ozonetel | Separate parked worktree | Separate provider contract | Separate provider contract | Separate provider contract | Not merged or modified here |

Source of truth for any carrier behavior is its own current protocol; the three envelopes are not interchangeable.
