import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from xml.sax.saxutils import quoteattr

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader

from .actions import ActionEngine, validate_public_url, validate_tool
from .config import Settings
from .models import DialInput, FAQInput, LineInput, TenantInput, ToolInput
from .providers import Groq
from .rag import Embedder, Knowledge
from .session import CallSession
from .store import Store, token_hash
from .transport import MediaTransport
from .vad import SileroFactory


def create_app(settings=None):
    settings = settings or Settings()
    services = SimpleNamespace(settings=settings, active={}, vad=None, model_error=None)

    @asynccontextmanager
    async def lifespan(app):
        services.store = Store(settings.database)
        await services.store.open()
        services.http = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=30),
            follow_redirects=False,
            trust_env=False,
        )
        embedder = None
        if settings.semantic_enabled:
            try:
                embedder = await asyncio.to_thread(
                    Embedder, settings.embedding_model, settings.embedding_cache
                )
            except Exception:
                services.model_error = "Embedding model unavailable; run model setup and restart"
        if settings.silero_model.is_file():
            try:
                services.vad = await asyncio.to_thread(SileroFactory, settings.silero_model)
            except Exception:
                services.model_error = "Silero model failed to load"
        services.knowledge = Knowledge(
            services.store, embedder, settings.cache_threshold, settings.cache_ttl_seconds
        )
        services.actions = ActionEngine(services.store, services.http)
        services.llm = Groq(settings, services.http)
        try:
            yield
        finally:
            if services.actions.tasks:
                await asyncio.gather(*services.actions.tasks, return_exceptions=True)
            await services.http.aclose()
            await services.store.close()

    app = FastAPI(title="OmniVoice", version="0.1.0", lifespan=lifespan)
    app.state.services = services

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
            )
        return response

    async def identity(authorization: str = Header(default="")):
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "A bearer token is required")
        token = authorization[7:]
        admin = settings.admin_token.get_secret_value()
        if admin and secrets.compare_digest(token, admin):
            return "admin"
        row = await services.store.one("SELECT id FROM tenants WHERE token_hash=?", (token_hash(token),))
        if not row:
            raise HTTPException(401, "Invalid token")
        return row["id"]

    async def admin(who=Depends(identity)):
        if who != "admin":
            raise HTTPException(403, "Administrator access required")

    async def tenant_access(tenant_id: str, who=Depends(identity)):
        if who not in ("admin", tenant_id):
            raise HTTPException(404, "Tenant not found")
        tenant = await services.store.tenant(tenant_id)
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        return tenant

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    def readiness():
        missing = settings.missing_voice_settings()
        if services.vad is None and "SILERO_MODEL" not in missing:
            missing.append("SILERO_MODEL_INVALID")
        if not settings.admin_token.get_secret_value():
            missing.append("ADMIN_TOKEN")
        return {
            "voice_ready": not missing,
            "missing": missing,
            "semantic_cache": services.knowledge.embedder is not None,
            "retrieval_mode": "FAISS semantic + exact FAQ"
            if services.knowledge.embedder
            else "exact FAQ + lexical document retrieval",
            "model_error": services.model_error,
            "outbound_enabled": settings.enable_outbound,
            "active_calls": len(services.active),
            "max_calls": settings.max_calls,
            "providers": {
                "speech": "Sarvam",
                "reasoning": "Groq",
                "reasoning_model": settings.groq_model,
                "telephony": ["Exotel", "Twilio"],
            },
        }

    @app.get("/readyz")
    async def ready():
        state = readiness()
        return JSONResponse({"ready": state["voice_ready"]}, status_code=200 if state["voice_ready"] else 503)

    @app.get("/api/status", dependencies=[Depends(identity)])
    async def status():
        return readiness()

    @app.get("/api/tenants")
    async def tenants(who=Depends(identity)):
        if who == "admin":
            return await services.store.rows("SELECT id,name,created FROM tenants ORDER BY created DESC")
        return await services.store.rows("SELECT id,name,created FROM tenants WHERE id=?", (who,))

    @app.post("/api/tenants", status_code=201, dependencies=[Depends(admin)])
    async def create_tenant(body: TenantInput):
        if {s.casefold().strip() for s in body.backchannels} & {
            s.casefold().strip() for s in body.confirmation_phrases
        }:
            raise HTTPException(422, "Confirmation phrases must differ from backchannels")
        return await services.store.create_tenant(body.model_dump())

    @app.get("/api/tenants/{tenant_id}")
    async def tenant(tenant=Depends(tenant_access)):
        return tenant

    @app.get("/api/tenants/{tenant_id}/knowledge")
    async def knowledge(tenant=Depends(tenant_access)):
        return await services.store.rows(
            "SELECT id,kind,title,approved,created FROM knowledge WHERE tenant_id=? ORDER BY created DESC",
            (tenant["id"],),
        )

    @app.post("/api/tenants/{tenant_id}/faqs", status_code=201)
    async def faq(body: FAQInput, tenant=Depends(tenant_access)):
        item = await services.store.add_knowledge(
            tenant["id"], "faq", body.question, body.answer, body.approved
        )
        services.knowledge.invalidate(tenant["id"])
        await services.knowledge.refresh(tenant["id"])
        return {"id": item}

    @app.post("/api/tenants/{tenant_id}/documents", status_code=201)
    async def document(file: UploadFile = File(...), tenant=Depends(tenant_access)):
        raw = await file.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(413, "Documents are limited to 5 MiB")
        name = Path(file.filename or "document").name
        extension = Path(name).suffix.lower()

        def extract():
            if extension == ".pdf":
                pdf = PdfReader(io.BytesIO(raw))
                if len(pdf.pages) > 100:
                    raise ValueError("PDFs are limited to 100 pages")
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
            if extension in {".txt", ".md", ".json", ".sql"}:
                return raw.decode("utf-8-sig")
            raise ValueError("Use PDF, TXT, MD, JSON or SQL schema files")

        try:
            text = await asyncio.to_thread(extract)
        except Exception:
            raise HTTPException(
                422, "Could not extract document text; use a text PDF or UTF-8 text file"
            ) from None
        if not text.strip() or len(text) > 300000:
            raise HTTPException(422, "Document must contain 1–300,000 extracted characters")
        item = await services.store.add_knowledge(tenant["id"], "document", name, text)
        services.knowledge.invalidate(tenant["id"])
        await services.knowledge.refresh(tenant["id"])
        return {"id": item, "characters": len(text)}

    @app.delete("/api/tenants/{tenant_id}/knowledge/{item_id}")
    async def delete_knowledge(item_id: str, tenant=Depends(tenant_access)):
        if not await services.store.delete_knowledge(tenant["id"], item_id):
            raise HTTPException(404, "Knowledge item not found")
        services.knowledge.invalidate(tenant["id"])
        return {"deleted": True}

    @app.get("/api/tenants/{tenant_id}/lines")
    async def lines(tenant=Depends(tenant_access)):
        return await services.store.rows(
            "SELECT id,provider,number FROM lines WHERE tenant_id=?", (tenant["id"],)
        )

    @app.post("/api/tenants/{tenant_id}/lines", status_code=201)
    async def add_line(body: LineInput, tenant=Depends(tenant_access)):
        line_id, stream_secret = uuid4().hex, secrets.token_urlsafe(32)
        try:
            await services.store.execute(
                "INSERT INTO lines VALUES (?,?,?,?,?)",
                (line_id, tenant["id"], body.provider, body.number, stream_secret),
            )
        except Exception:
            raise HTTPException(409, "Phone number is already configured") from None
        return {
            "id": line_id,
            "note": "Configure your carrier with the protected URL from the connection endpoint",
        }

    @app.get("/api/tenants/{tenant_id}/lines/{line_id}/connection")
    async def connection(line_id: str, tenant=Depends(tenant_access)):
        line = await services.store.one(
            "SELECT * FROM lines WHERE id=? AND tenant_id=?", (line_id, tenant["id"])
        )
        if not line:
            raise HTTPException(404, "Line not found")
        base = settings.public_base_url.rstrip("/")
        if not base.startswith("https://"):
            raise HTTPException(409, "Set OMNI_PUBLIC_BASE_URL to your public HTTPS origin first")
        if line["provider"] == "twilio":
            return {"webhook_url": base + "/telephony/twilio/" + line_id}
        return {
            "stream_url": base.replace("https://", "wss://", 1)
            + "/ws/exotel/"
            + line_id
            + "/"
            + line["stream_secret"]
        }

    @app.get("/api/tenants/{tenant_id}/calls")
    async def calls(tenant=Depends(tenant_access)):
        rows = await services.store.rows(
            "SELECT * FROM calls WHERE tenant_id=? ORDER BY started DESC LIMIT 100", (tenant["id"],)
        )
        for row in rows:
            row["metrics"] = json.loads(row["metrics"])
            if row["id"] in services.active:
                row["metrics"] = services.active[row["id"]].metrics
                row["state"] = services.active[row["id"]].fsm.state
        return rows

    @app.get("/api/tenants/{tenant_id}/actions")
    async def actions(tenant=Depends(tenant_access)):
        return await services.store.rows(
            "SELECT id,call_id,tool,summary,status,created FROM actions WHERE tenant_id=? ORDER BY created DESC LIMIT 100",
            (tenant["id"],),
        )

    @app.get("/api/tenants/{tenant_id}/tools")
    async def tools(tenant=Depends(tenant_access)):
        return await services.actions.tools(tenant["id"])

    @app.post("/api/tenants/{tenant_id}/tools", dependencies=[Depends(admin)])
    async def add_tool(body: ToolInput, tenant=Depends(tenant_access)):
        config = body.model_dump()
        try:
            validate_tool(config)
            await validate_public_url(body.url)
        except Exception:
            raise HTTPException(
                422, "Invalid tool schema, public HTTPS endpoint, or confirmation template"
            ) from None
        await services.store.execute(
            "INSERT INTO tools VALUES (?,?,?) ON CONFLICT(tenant_id,name) DO UPDATE SET config=excluded.config",
            (tenant["id"], body.name, json.dumps(config)),
        )
        return {"registered": body.name}

    @app.post("/api/tenants/{tenant_id}/dial")
    async def dial(body: DialInput, tenant=Depends(tenant_access)):
        if not settings.enable_outbound or not body.consent_confirmed:
            raise HTTPException(409, "Outbound calling must be enabled and recipient consent confirmed")
        if not readiness()["voice_ready"]:
            raise HTTPException(409, "Voice providers are not ready")
        line = await services.store.one(
            "SELECT * FROM lines WHERE id=? AND tenant_id=?", (body.line_id, tenant["id"])
        )
        if not line:
            raise HTTPException(404, "Line not found")
        config = await connection(body.line_id, tenant)
        if line["provider"] == "exotel":
            if not all(
                (
                    settings.exotel_account_sid,
                    settings.exotel_api_key.get_secret_value(),
                    settings.exotel_api_token.get_secret_value(),
                )
            ):
                raise HTTPException(409, "Exotel credentials are missing")
            url = (
                f"https://api-stream.exotel.com/v1/Accounts/{settings.exotel_account_sid}/Calls/connect.json"
            )
            auth = (settings.exotel_api_key.get_secret_value(), settings.exotel_api_token.get_secret_value())
            data = {
                "From": body.to,
                "CallerId": line["number"],
                "StreamType": "bidirectional",
                "StreamUrl": config["stream_url"],
                "Record": "false",
            }
        else:
            if not settings.twilio_account_sid or not settings.twilio_auth_token.get_secret_value():
                raise HTTPException(409, "Twilio credentials are missing")
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Calls.json"
            auth = (settings.twilio_account_sid, settings.twilio_auth_token.get_secret_value())
            data = {"To": body.to, "From": line["number"], "Url": config["webhook_url"]}
        try:
            response = await services.http.post(url, auth=auth, data=data, timeout=15)
            response.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(
                502, "Carrier request failed or its outcome is uncertain; check carrier logs before retrying"
            ) from None
        return {"submitted": True}

    @app.post("/telephony/twilio/{line_id}")
    async def twiml(line_id: str, request: Request):
        line = await services.store.one("SELECT * FROM lines WHERE id=? AND provider='twilio'", (line_id,))
        secret = settings.twilio_auth_token.get_secret_value()
        if not line or not secret or not settings.public_base_url.startswith("https://"):
            raise HTTPException(403, "Invalid carrier request")
        form = await request.form()
        url = settings.public_base_url.rstrip("/") + request.url.path
        signed = url + "".join(
            key + value for key in sorted(form) for value in sorted(set(form.getlist(key)))
        )
        signature = base64.b64encode(
            hmac.new(secret.encode(), signed.encode(), hashlib.sha1).digest()
        ).decode()
        if not secrets.compare_digest(signature, request.headers.get("X-Twilio-Signature", "")):
            raise HTTPException(403, "Invalid carrier signature")
        stream = settings.public_base_url.replace("https://", "wss://", 1).rstrip("/") + "/ws/twilio"
        xml = (
            "<Response><Connect><Stream url="
            + quoteattr(stream)
            + '><Parameter name="line_id" value='
            + quoteattr(line_id)
            + '/><Parameter name="token" value='
            + quoteattr(line["stream_secret"])
            + "/></Stream></Connect></Response>"
        )
        return Response(xml, media_type="application/xml")

    async def serve_media(ws, provider, line_id=None, token=None):
        await ws.accept()
        call_id = None
        try:
            async with asyncio.timeout(5):
                message = await ws.receive_json()
                if message.get("event") == "connected":
                    message = await ws.receive_json()
            if message.get("event") != "start":
                await ws.close(1008)
                return
            start = message["start"]
            if provider == "twilio":
                params = start.get("customParameters", {})
                line_id, token = params.get("line_id"), params.get("token")
                fmt = start.get("mediaFormat", {})
                if (
                    fmt.get("sampleRate") != 8000
                    or fmt.get("encoding") != "audio/x-mulaw"
                    or fmt.get("channels") != 1
                ):
                    await ws.close(1003)
                    return
                stream_id = start["streamSid"]
            else:
                stream_id = start.get("stream_sid") or message.get("stream_sid")
                fmt = start.get("media_format", {})
                logging.getLogger("omnivoice.media").warning(
                    "Exotel start format: rate=%s encoding=%s",
                    str(fmt.get("sample_rate", "missing"))[:32],
                    str(fmt.get("encoding", "missing"))[:32],
                )
                if str(fmt.get("sample_rate", 8000)) != "8000" or fmt.get("encoding", "raw/slin") not in {
                    "base64",
                    "raw/slin",
                    "audio/x-l16",
                    "pcm",
                    "linear16",
                }:
                    await ws.close(1003)
                    return
            line = await services.store.one(
                "SELECT * FROM lines WHERE id=? AND provider=?", (line_id, provider)
            )
            if not line or not token or not secrets.compare_digest(token, line["stream_secret"]):
                await ws.close(1008)
                return
            if not readiness()["voice_ready"] or not stream_id or len(services.active) >= settings.max_calls:
                await ws.close(1013)
                return
            tenant = await services.store.tenant(line["tenant_id"])
            call_id = uuid4().hex
            session = CallSession(call_id, tenant, MediaTransport(ws, provider, stream_id), services)
            # No await between capacity check and admission in the single-worker runtime.
            if len(services.active) >= settings.max_calls:
                await ws.close(1013)
                return
            services.active[call_id] = session
            await services.store.execute(
                "INSERT INTO calls (id,tenant_id,provider,status,started) VALUES (?,?,?,?,?)",
                (call_id, tenant["id"], provider, "active", time.time()),
            )
            await session.run()
        except Exception as error:
            logging.getLogger("omnivoice.media").warning(
                "Media session ended: %s", type(error).__name__
            )
        finally:
            if call_id and call_id in services.active:
                session = services.active.pop(call_id)
                await services.store.execute(
                    "UPDATE calls SET status=?,ended=?,metrics=? WHERE id=?",
                    (
                        "failed" if session.metrics["errors"] else "completed",
                        time.time(),
                        json.dumps(session.metrics),
                        call_id,
                    ),
                )
            try:
                await ws.close()
            except Exception:
                pass

    @app.websocket("/ws/twilio")
    async def twilio(ws: WebSocket):
        await serve_media(ws, "twilio")

    @app.websocket("/ws/exotel/{line_id}/{token}")
    async def exotel(ws: WebSocket, line_id: str, token: str):
        await serve_media(ws, "exotel", line_id, token)

    @app.websocket("/ws/audio/{line_id}/{token}")
    async def audio(ws: WebSocket, line_id: str, token: str):
        # Alias for authenticated, Exotel-format PCM telephony gateways.
        await serve_media(ws, "exotel", line_id, token)

    @app.websocket("/ws/audio")
    async def generic_audio(ws: WebSocket):
        # Gateway clients can keep credentials in headers instead of the URL.
        authorization = ws.headers.get("authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else None
        await serve_media(ws, "exotel", ws.headers.get("x-omni-line"), token)

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    async def console():
        return FileResponse(static / "index.html")

    return app
