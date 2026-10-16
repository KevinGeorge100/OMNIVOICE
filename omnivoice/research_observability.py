"""Opt-in, payload-free Langfuse research observations.

The live exporter only sees an allowlisted projection of completed call metrics.
It never receives a CallSession, tenant object, transcript, audio, or tool payload.
"""

import asyncio
import logging
import math
from contextlib import contextmanager, nullcontext
from urllib.parse import urlsplit

LOG = logging.getLogger("omnivoice.research")
TURN_LIMIT = 20
QUEUE_LIMIT = 64
TURN_NUMBERS = (
    "stt_endpoint_delay_ms", "retrieval_ms", "rag_retrieval_ms", "llm_ttft_ms",
    "first_tts_ttfa_ms", "carrier_framing_delay_ms",
    "final_transcript_to_first_audio_sent_ms", "last_vad_speech_to_first_audio_sent_ms",
    "response_segment_count", "tts_segment_count",
)
TOOL_NUMBERS = (
    "invocations", "succeeded", "failed", "confirmation_required", "committed",
    "failed_commits", "unknown_outcome", "cache_hits", "cancelled",
    "duration_ms_total", "invalid_tool_requests", "action_end_to_end_ms_total",
)
PATHS = {"fast_cache", "foreground_rag", "confirmation"}
TOOL_ERRORS = {"invalid_arguments", "unauthorized_tool", "tool_error", "timeout"}
RESEARCH_SPAN_NAMES = {
    "omnivoice.completed_call_metrics", "recorded_turn_metrics",
    "omnivoice.scripted_sales_case", "scripted_tool_invocation", "scripted_action_confirmation",
}


def _research_span_only(span):
    """Do not export unrelated OpenTelemetry spans from the shared process."""
    return span.name in RESEARCH_SPAN_NAMES


def _number(value):
    if type(value) not in (int, float) or value < 0:
        return None
    try:
        finite = math.isfinite(value)
    except OverflowError:
        return None
    if not finite:
        return None
    return value


def live_projection(metrics: dict, provider: str, status: str) -> dict:
    """Allowlist only measured numbers and fixed categories; no recursive copy."""
    metrics = metrics if isinstance(metrics, dict) else {}
    turns = metrics.get("turns", [])
    turns = turns if isinstance(turns, list) else []
    safe_turns = []
    for turn in turns[-TURN_LIMIT:]:
        if not isinstance(turn, dict):
            continue
        item = {key: number for key in TURN_NUMBERS if (number := _number(turn.get(key))) is not None}
        if isinstance(turn.get("path"), str) and turn["path"] in PATHS:
            item["path"] = turn["path"]
        item["interrupted"] = turn.get("interrupted") is True
        safe_turns.append(item)
    summary = metrics.get("tool_summary", {})
    summary = summary if isinstance(summary, dict) else {}
    return {
        "source": "completed_live_call",
        "carrier": provider if isinstance(provider, str) and provider in {"exotel", "twilio"} else "other",
        "status": status if isinstance(status, str) and status in {"completed", "failed", "interrupted"} else "other",
        "turns_recorded": len(turns),
        "turns_exported": len(safe_turns),
        "turns_truncated": len(turns) > TURN_LIMIT,
        "turns": safe_turns,
        "errors": _number(metrics.get("errors", 0)),
        "cache_hits": _number(metrics.get("cache_hits", 0)),
        "barge_in_count": len(metrics.get("barge_in", [])) if isinstance(metrics.get("barge_in", []), list) else 0,
        "tool_summary": {
            key: number for key in TOOL_NUMBERS if (number := _number(summary.get(key))) is not None
        },
    }


class ResearchObserver:
    def __init__(self, client=None, *, enabled=False, error=None):
        self.client = client
        self.enabled = enabled
        self.error = error
        self.queue = asyncio.Queue(maxsize=QUEUE_LIMIT)
        self.worker = None
        self.dropped = 0
        self.exported = 0
        self.failures = 0

    @classmethod
    def from_settings(cls, settings, *, client_override=None, explicit=False):
        if not (settings.research_observability_enabled or explicit):
            return cls()
        if client_override is not None:
            return cls(client_override, enabled=True)
        public = settings.langfuse_public_key.get_secret_value()
        secret = settings.langfuse_secret_key.get_secret_value()
        if not public or not secret:
            raise ValueError("Langfuse research export requires public and secret keys")
        base = urlsplit(settings.langfuse_base_url)
        if base.scheme != "https" or not base.hostname or base.username or base.password:
            raise ValueError("Langfuse research export requires a public HTTPS base URL")
        try:
            from langfuse import Langfuse
        except ImportError:
            raise RuntimeError("Install the research extra to enable Langfuse export") from None
        return cls(Langfuse(
            public_key=public, secret_key=secret, base_url=settings.langfuse_base_url,
            timeout=2, should_export_span=_research_span_only,
        ), enabled=True)

    def _sdk_failed(self, operation, error):
        self.failures += 1
        LOG.warning("research_export_failed operation=%s failure_type=%s", operation, type(error).__name__)

    def start_live(self):
        if self.client is not None and self.worker is None:
            self.worker = asyncio.create_task(self._drain(), name="research-observability")

    def submit_live(self, metrics: dict, provider: str, status: str):
        if self.worker is None:
            return
        projection = live_projection(metrics, provider, status)
        try:
            self.queue.put_nowait(projection)
        except asyncio.QueueFull:
            self.dropped += 1
            LOG.warning("research_export_dropped reason=queue_full limit=%d", QUEUE_LIMIT)

    async def _drain(self):
        while True:
            item = await self.queue.get()
            try:
                if item is None:
                    return
                await asyncio.to_thread(self._emit_live, item)
                self.exported += 1
            except Exception as error:
                self.failures += 1
                LOG.warning("research_export_failed failure_type=%s", type(error).__name__)
            finally:
                self.queue.task_done()

    def _emit_live(self, item):
        root = self.client.start_observation(
            as_type="span", name="omnivoice.completed_call_metrics",
            metadata={key: item[key] for key in (
                "source", "carrier", "status", "turns_recorded", "turns_exported", "turns_truncated"
            )},
        )
        try:
            root.update(output={
                "errors": item["errors"], "cache_hits": item["cache_hits"],
                "barge_in_count": item["barge_in_count"], "tool_summary": item["tool_summary"],
            })
            for turn in item["turns"]:
                child = root.start_observation(
                    as_type="span", name="recorded_turn_metrics", metadata=turn,
                )
                child.end()
        finally:
            root.end()

    @contextmanager
    def case(self, case_id: str, category: str):
        if self.client is None:
            with nullcontext(None) as span:
                yield span
            return
        try:
            manager = self.client.start_as_current_observation(
                as_type="agent", name="omnivoice.scripted_sales_case",
                metadata={"source": "offline_scripted", "case_id": case_id, "category": category},
            )
            span = manager.__enter__()
        except Exception as error:
            self._sdk_failed("case_start", error)
            yield None
            return
        try:
            yield span
        finally:
            try:
                manager.__exit__(None, None, None)
            except Exception as error:
                self._sdk_failed("case_end", error)

    @contextmanager
    def tool(self, name: str):
        if self.client is None:
            with nullcontext(None) as span:
                yield span
            return
        safe_name = name if name in {
            "lookup_lead", "check_demo_slots", "schedule_demo", "create_followup",
        } else "other_tool"
        try:
            span = self.client.start_observation(
                as_type="tool", name="scripted_tool_invocation", metadata={"tool": safe_name},
            )
        except Exception as error:
            self._sdk_failed("tool_start", error)
            yield None
            return
        try:
            yield span
        finally:
            try:
                span.end()
            except Exception as error:
                self._sdk_failed("tool_end", error)

    @contextmanager
    def action(self, name: str):
        if self.client is None:
            with nullcontext(None) as span:
                yield span
            return
        safe_name = name if name in {"schedule_demo", "create_followup"} else "other_action"
        try:
            span = self.client.start_observation(
                as_type="span", name="scripted_action_confirmation", metadata={"action": safe_name},
            )
        except Exception as error:
            self._sdk_failed("action_start", error)
            yield None
            return
        try:
            yield span
        finally:
            try:
                span.end()
            except Exception as error:
                self._sdk_failed("action_end", error)

    def finish_action(self, span, result):
        if span is not None:
            status = result.get("status") if isinstance(result, dict) else None
            try:
                span.update(output={
                    "status": status if status in {"committed", "failed", "unknown"} else "not_confirmed"
                })
            except Exception as error:
                self._sdk_failed("action_update", error)

    def finish_tool(self, span, result):
        if span is not None:
            code = result.error_code if result.error_code in TOOL_ERRORS else None
            try:
                span.update(output={
                    "success": result.success, "error_code": code,
                    "confirmation_required": result.confirmation_required,
                    "duration_ms": _number(result.duration_ms),
                })
            except Exception as error:
                self._sdk_failed("tool_update", error)

    def finish_case(self, span, record):
        if span is None:
            return
        complete = record["task_completed"] is True
        try:
            span.update(output={
                "task_completed": complete,
                "tool_invocations": record.get("tool_invocations") if complete else None,
                "unsafe_commits": record.get("unsafe_commits") if complete else None,
            })
            span.score_trace(name="scripted_task_completed", value=float(complete), data_type="NUMERIC")
            if complete:
                span.score_trace(
                    name="unsafe_commit_count", value=float(record["unsafe_commits"]), data_type="NUMERIC"
                )
        except Exception as error:
            self._sdk_failed("case_update", error)

    def snapshot(self):
        return {
            "enabled": self.enabled, "configured": self.client is not None,
            "queued": self.queue.qsize(), "exported": self.exported,
            "dropped": self.dropped, "failures": self.failures,
            "error": self.error,
        }

    async def close(self):
        if self.worker is not None:
            try:
                await asyncio.wait_for(self.queue.join(), timeout=2)
            except TimeoutError:
                self.dropped += self.queue.qsize()
            if not self.worker.done():
                self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
            self.worker = None
        if self.client is not None:
            try:
                await asyncio.wait_for(asyncio.to_thread(self.client.shutdown), timeout=2)
            except Exception as error:
                self.failures += 1
                LOG.warning("research_shutdown_failed failure_type=%s", type(error).__name__)
