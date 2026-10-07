import asyncio
import contextlib
import json
import logging
import time
from uuid import uuid4

from .audio import PCMFrameBuffer, Upsample8k
from .dialogue import (
    build_system_prompt,
    classify_turn_telemetry,
    missing_fact_reply,
    unsupported_action_reply,
)
from .duplex import CancelReason, FlexDuo, is_control_halt, normalize
from .providers import GnaniSTT, GnaniTTS, SarvamSTT, SarvamTTS, select_speech_provider
from .speech import SpeechSegmenter, normalize_speech


class CallEnded(Exception):
    pass


class CallSession:
    def __init__(self, call_id, tenant, transport, services):
        self.id, self.tenant, self.transport, self.services = call_id, tenant, transport, services
        self.config = tenant["config"]
        self.fsm = FlexDuo(self.config["backchannels"])
        self.stt = select_speech_provider(
            services.settings.stt_provider,
            "STT",
            sarvam_factory=lambda: SarvamSTT(services.settings),
            gnani_factory=lambda: GnaniSTT(
                services.settings,
                http=getattr(services, "http", None),
                language=self.config.get("language", "en-IN"),
                vad=services.vad.session() if getattr(services, "vad", None) else None,
            ),
        )
        self.tts = select_speech_provider(
            services.settings.tts_provider,
            "TTS",
            sarvam_factory=lambda: SarvamTTS(services.settings, self.config["language"]),
            gnani_factory=lambda: GnaniTTS(services.settings, self.config.get("language", "en-IN")),
        )
        self.vad = services.vad.session()
        self.upsample = Upsample8k()
        self.audio_queue = asyncio.Queue(maxsize=100)
        self.vad_queue = asyncio.Queue(maxsize=100)
        self.response = None
        self.slow = None
        self.history = []
        self.metrics = {"turns": [], "barge_in": [], "cache_hits": 0, "errors": 0}
        self.marks = {}
        self.last_prediction = 0.0
        self.last_voice = None
        self.read_results = {}
        self.generation_id = 0
        self.active_generation_id = None
        self.cancellation_reasons = {}
        self.pending_text = ""
        self.pending_final_time = 0.0

    async def run(self):
        try:
            async def open_voice():
                await self.tts.open()
                # Greeting must not wait for STT or retrieval initialization.
                self.response = asyncio.create_task(self.greet())

            async with asyncio.TaskGroup() as startup:
                startup.create_task(self.stt.open())
                startup.create_task(open_voice())
                startup.create_task(self.services.knowledge.refresh(self.tenant["id"]))
            async with asyncio.timeout(self.services.settings.max_call_seconds):
                async with asyncio.TaskGroup() as group:
                    group.create_task(self.receive())
                    group.create_task(self.send_stt())
                    group.create_task(self.detect_voice())
                    group.create_task(self.transcripts())
        except BaseExceptionGroup as group:
            _, unexpected = group.split((CallEnded,))
            if unexpected:
                self.metrics["errors"] += 1
        except (CallEnded, TimeoutError):
            pass
        except Exception:
            self.metrics["errors"] += 1
        finally:
            logging.getLogger("omnivoice.media").warning(
                "Call ended id=%s metrics=%s", self.id, json.dumps(self.metrics)
            )
            for task in (self.response, self.slow):
                if task:
                    task.cancel()
            await asyncio.gather(*(t for t in (self.response, self.slow) if t), return_exceptions=True)
            await self.services.actions.cancel(self.id)
            await asyncio.gather(self.stt.close(), self.tts.close(), return_exceptions=True)

    async def receive(self):
        from starlette.websockets import WebSocketDisconnect

        try:
            while True:
                message = await self.transport.ws.receive_json()
                event = message.get("event")
                if event == "media":
                    pcm = self.upsample.process(self.transport.decode(message))
                    # Never silently drop caller speech; overload terminates the call.
                    self.audio_queue.put_nowait(pcm)
                    self.vad_queue.put_nowait(pcm)
                elif event == "mark":
                    name = message.get("mark", {}).get("name")
                    if name in self.marks:
                        action_id = self.marks.pop(name)
                        if not self.marks:
                            self.fsm.played()
                        if action_id:
                            await self.services.actions.arm(action_id, self.id)
                elif event == "stop":
                    self.metrics["end_reason"] = "carrier_stop"
                    raise CallEnded()
        except WebSocketDisconnect as error:
            self.metrics["end_reason"] = "carrier_disconnect"
            self.metrics["close_code"] = error.code
            raise CallEnded() from None

    async def greet(self):
        metric = {"started": time.perf_counter()}
        try:
            await self.say(self.config["greeting"], metric=metric)
            self.history.append({"role": "assistant", "content": self.config["greeting"]})
        except asyncio.CancelledError:
            raise
        except Exception:
            self.metrics["errors"] += 1
            with contextlib.suppress(Exception):
                await self.transport.ws.close(code=1011)
        finally:
            self.metrics["greeting_audio_sent"] = "final_transcript_to_first_audio_sent_ms" in metric
            self.metrics["greeting_first_audio_ms"] = metric.get("final_transcript_to_first_audio_sent_ms")

    async def send_stt(self):
        while True:
            await self.stt.send(await self.audio_queue.get())

    async def detect_voice(self):
        while True:
            pcm = await self.vad_queue.get()
            probabilities = await asyncio.to_thread(self.vad.process, pcm)
            for probability in probabilities:
                self.fsm.voice(probability)
                if probability >= 0.6:
                    self.last_voice = time.perf_counter()

    async def interrupt(self):
        decided = time.perf_counter()
        if self.response:
            self.cancellation_reasons[self.generation_id] = CancelReason.PLAYBACK_INTERRUPT
            self.response.cancel()
        self.marks.clear()  # clear acknowledgements must never arm a cancelled write.
        await self.transport.clear()
        clear_sent = time.perf_counter()
        await asyncio.gather(self.tts.cancel(), self.services.actions.cancel(self.id))
        if self.response:
            await asyncio.gather(self.response, return_exceptions=True)
        self.fsm.played()
        self.metrics["barge_in"].append({"decision_to_clear_sent_ms": (clear_sent - decided) * 1000})

    async def _cancel_pending_generation(self, reason: CancelReason):
        if self.response and not self.response.done():
            self.cancellation_reasons[self.generation_id] = reason
            task = self.response
            self.response = None
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await asyncio.gather(self.tts.cancel(), self.services.actions.cancel(self.id))

    async def transcripts(self):
        async for transcript in self.stt.events():
            text = transcript.text.strip()
            if not text:
                continue
            was_playing = self.fsm.playing
            if self.fsm.transcript(text):
                await self.interrupt()
            elif was_playing and normalize(text) in self.fsm.backchannels:
                continue
            now = time.monotonic()
            if now - self.last_prediction >= 1.5 and (not self.slow or self.slow.done()):
                self.last_prediction = now
                self.slow = asyncio.create_task(self.speculate(text))
            if not transcript.final:
                continue
            final_received = time.perf_counter()
            voice_at_final = self.last_voice
            self.last_voice = None
            endpoint_delay = (
                max(0.0, (final_received - voice_at_final) * 1000)
                if voice_at_final is not None and voice_at_final <= final_received else None
            )

            interval_s = self.config.get(
                "continuation_interval_ms",
                getattr(getattr(self.services, "settings", None), "continuation_interval_ms", 750),
            ) / 1000.0

            response_active = self.response is not None and not self.response.done()

            # Generation-stage turn formulation: active response but audio not yet playing
            if response_active and not self.fsm.playing:
                if is_control_halt(text):
                    await self._cancel_pending_generation(CancelReason.CONTROL_HALT)
                    self.pending_text = ""
                    self.pending_final_time = 0.0
                    continue

                if self.pending_final_time > 0 and (now - self.pending_final_time) <= interval_s:
                    await self._cancel_pending_generation(CancelReason.SUPERSEDED)
                    self.pending_text = f"{self.pending_text} {text}".strip()
                    self.pending_final_time = now
                    self.generation_id += 1
                    self.response = asyncio.create_task(
                        self.respond(self.pending_text, final_received, self.generation_id,
                                     voice_at_final, endpoint_delay)
                    )
                    continue

                await self._cancel_pending_generation(CancelReason.SUPERSEDED)
                self.pending_text = text
                self.pending_final_time = now
                self.generation_id += 1
                self.response = asyncio.create_task(
                    self.respond(text, final_received, self.generation_id,
                                 voice_at_final, endpoint_delay)
                )
                continue

            # Playback or idle state
            if response_active:
                await self.interrupt()

            self.pending_text = text
            self.pending_final_time = now
            self.generation_id += 1
            self.response = asyncio.create_task(
                self.respond(text, final_received, self.generation_id,
                             voice_at_final, endpoint_delay)
            )

    async def speculate(self, partial):
        try:
            tools = await self.services.actions.tools(self.tenant["id"])
            topics, reads = await self.services.llm.predict(
                [*self.history, {"role": "user", "content": partial}], tools
            )

            async def read(item):
                try:
                    value = await self.services.actions.read(
                        self.tenant["id"], item["name"], item["arguments"]
                    )
                    key = json.dumps([item["name"], item["arguments"]], sort_keys=True)
                    self.read_results[key] = (time.monotonic(), value)
                    # Read cache is call-scoped, short-lived, and bounded.
                    if len(self.read_results) > 16:
                        self.read_results.pop(next(iter(self.read_results)))
                except Exception:
                    pass

            await asyncio.gather(
                self.services.knowledge.warm(self.tenant["id"], topics),
                *(read(r) for r in reads if isinstance(r, dict)),
            )
        except Exception:
            # Speculation failure cannot prevent the foreground call from continuing.
            self.metrics["speculation_errors"] = self.metrics.get("speculation_errors", 0) + 1

    async def say(self, text, action_id=None, metric=None):
        async def one():
            yield text

        await self.say_stream(one(), action_id=action_id, metric=metric)

    async def say_stream(self, segments, action_id=None, metric=None):
        """One utterance owns one TTS stream, PCM tail, carrier epoch and mark."""
        epoch = self.transport.epoch
        owner_generation = self.active_generation_id

        def owned():
            return epoch == self.transport.epoch and owner_generation == self.active_generation_id

        frames = PCMFrameBuffer(self.transport.frame_size)
        tts_started = None
        first_pcm_at = None

        async def prepared():
            nonlocal tts_started
            async for raw in segments:
                if not owned():
                    return
                spoken = normalize_speech(raw)
                if metric is not None:
                    metric["speech_normalization_changed"] = (
                        metric.get("speech_normalization_changed", False) or spoken != raw.strip()
                    )
                if not spoken:
                    continue
                if tts_started is None:
                    tts_started = time.perf_counter()
                if metric is not None:
                    metric["response_segment_count"] = metric.get("response_segment_count", 0) + 1
                    metric["tts_segment_count"] = metric.get("tts_segment_count", 0) + 1
                    metric.setdefault("first_segment_chars", len(spoken))
                    metric["total_speech_chars"] = metric.get("total_speech_chars", 0) + len(spoken)
                yield spoken

        # Prime the first segment before opening the provider receiver. This
        # avoids a no-text flush if the model emits formatting only.
        iterator = prepared()
        first = await anext(iterator, None)
        if first is None or not owned():
            return
        # A pending TTS response is still generation until carrier audio leaves.
        # This keeps ADR-001 supersession separate from a true playback barge-in.

        async def text_stream():
            yield first
            async for item in iterator:
                yield item

        async def audio_stream():
            if hasattr(self.tts, "stream_text"):
                async for pcm in self.tts.stream_text(text_stream()):
                    yield pcm
            else:  # Minimal test doubles implement only the original speak method.
                async for item in text_stream():
                    async for pcm in self.tts.speak(item):
                        yield pcm

        playback_started = False

        def first_sent():
            nonlocal playback_started
            if not playback_started:
                self.fsm.speaking()
                playback_started = True
            if metric is not None and "final_transcript_to_first_audio_sent_ms" not in metric:
                sent_at = time.perf_counter()
                metric["final_transcript_to_first_audio_sent_ms"] = (sent_at - metric["started"]) * 1000
                if first_pcm_at is not None:
                    metric["carrier_framing_delay_ms"] = (sent_at - first_pcm_at) * 1000
                if metric.get("last_voice") is not None:
                    metric["last_vad_speech_to_first_audio_sent_ms"] = (
                        sent_at - metric["last_voice"]
                    ) * 1000

        try:
            async for pcm in audio_stream():
                if not owned():
                    return
                if not pcm:
                    continue
                if first_pcm_at is None:
                    first_pcm_at = time.perf_counter()
                if metric is not None and "first_tts_ttfa_ms" not in metric:
                    metric["first_tts_ttfa_ms"] = (first_pcm_at - tts_started) * 1000
                for frame in frames.push(pcm):
                    if not await self.transport.send_frame(frame, epoch, first_sent, owned):
                        return
                    if metric is not None:
                        metric["outbound_audio_bytes"] = metric.get("outbound_audio_bytes", 0) + len(
                            frame
                        )
            if not owned():
                return
            tail, padding = frames.finish()
            if tail:
                if not await self.transport.send_frame(tail, epoch, first_sent, owned):
                    return
                if metric is not None:
                    metric["outbound_audio_bytes"] = metric.get("outbound_audio_bytes", 0) + len(tail)
                    metric["padded_tail_bytes"] = metric.get("padded_tail_bytes", 0) + padding
        finally:
            frames.clear()  # Interrupted generations never donate PCM to a new turn.
        if not owned():
            return
        mark = uuid4().hex
        self.marks[mark] = action_id
        if not await self.transport.mark(mark, epoch, owned):
            self.marks.pop(mark, None)

    async def respond(self, text, started, gen_id=0, voice_at_final=None, endpoint_delay=None):
        self.active_generation_id = gen_id
        metric = {
            "started": started,
            "last_voice": voice_at_final,
            "user_transcript": text,
            "agent_response": "",
        }
        if endpoint_delay is not None:
            metric["stt_endpoint_delay_ms"] = endpoint_delay
        history_pushed = False
        try:
            confirmed = await self.services.actions.confirm(
                self.tenant["id"], self.id, text, True, self.config["confirmation_phrases"]
            )
            if confirmed:
                metric["path"] = "confirmation"
                message = (
                    "The action completed successfully."
                    if confirmed["status"] == "committed"
                    else "I could not verify the outcome. Please ask the team to check before trying again."
                )
                metric["agent_response"] = message
                metric.update(
                    knowledge_status="grounded",
                    limitation_used=False,
                    clarification_requested=False,
                )
                await self.say(message, metric=metric)
                return
            await self.services.actions.cancel(self.id)
            self.history.append({"role": "user", "content": text})
            history_pushed = True
            self.history = self.history[-20:]
            answer, cache_type, elapsed = await self.services.knowledge.fast_answer(self.tenant["id"], text)
            metric.update(cache=cache_type, retrieval_ms=elapsed)
            if answer:
                metric["path"] = "fast_cache"
                self.metrics["cache_hits"] += 1
                metric["agent_response"] = answer
                metric.update(
                    knowledge_status="grounded",
                    limitation_used=False,
                    clarification_requested=False,
                )
                await self.say(answer, metric=metric)
                self.history.append({"role": "assistant", "content": answer})
                self.history = self.history[-20:]
                return
            retrieval_started = time.perf_counter()
            context = await self.services.knowledge.retrieve(self.tenant["id"], text)
            metric["rag_retrieval_ms"] = (time.perf_counter() - retrieval_started) * 1000
            metric["path"] = "foreground_rag"
            tools = await self.services.actions.tools(self.tenant["id"]) or []
            corpus = getattr(getattr(self.services, "knowledge", None), "corpora", {}).get(self.tenant["id"])
            corpus_topics = (
                [r["title"] for r in corpus.rows]
                if corpus and hasattr(corpus, "rows") and corpus.rows
                else [r["title"] for r in context]
            )
            unavailable_action = unsupported_action_reply(
                text, tools, corpus_topics, self.history, self.config["language"]
            ) or missing_fact_reply(
                text, context, tools, corpus_topics, self.history, self.config["language"]
            )
            if unavailable_action:
                metric["agent_response"] = unavailable_action
                metric.update(
                    knowledge_status="missing",
                    limitation_used=True,
                    clarification_requested=False,
                )
                await self.say(unavailable_action, metric=metric)
                self.history.append({"role": "assistant", "content": unavailable_action})
                self.history = self.history[-20:]
                return
            system = build_system_prompt(
                config=self.config,
                context=context,
                tools=tools,
                corpus_topics=corpus_topics,
                history=self.history,
                caller_text=text,
            )
            messages = [{"role": "system", "content": system}, *self.history]
            await self.generate(messages, tools, metric)
            telemetry = classify_turn_telemetry(
                agent_response=metric.get("agent_response", ""),
                context=context,
                fast_answered=False,
                tool_calls=metric.get("tool_called", False),
            )
            metric.update(telemetry)
        except asyncio.CancelledError:
            reason = self.cancellation_reasons.get(gen_id, CancelReason.PLAYBACK_INTERRUPT)
            if reason == CancelReason.PLAYBACK_INTERRUPT:
                metric["interrupted"] = True
            elif history_pushed and self.history and self.history[-1].get("content") == text:
                self.history.pop()
            raise
        except Exception:
            self.metrics["errors"] += 1
            metric["error"] = "response_failed"
            with contextlib.suppress(Exception):
                await self.transport.clear()
                await self.tts.cancel()
                await self.transport.ws.close(code=1011)
            # Do not substitute fake speech or an ungrounded provider fallback.
        finally:
            reason = self.cancellation_reasons.pop(gen_id, None)
            if reason not in {CancelReason.SUPERSEDED, CancelReason.CONTROL_HALT}:
                metric.pop("started", None)
                metric.pop("last_voice", None)
                self.metrics["turns"].append(metric)
                self.metrics["turns"] = self.metrics["turns"][-500:]
                # Console event is a bounded tenant-scoped projection, never audio or tool secrets.
                if events := getattr(self.services, "events", None):
                    try:
                        events.publish(
                            self.tenant["id"],
                            "call.turn",
                            {
                                "id": self.id,
                                "state": self.fsm.state,
                                "turn_count": len(self.metrics["turns"]),
                                "recent_transcript": metric.get("user_transcript", "")[:500],
                                "recent_response": metric.get("agent_response", "")[:500],
                                "first_audio_ms": metric.get("final_transcript_to_first_audio_sent_ms"),
                                "interrupted": bool(metric.get("interrupted")),
                            },
                        )
                    except Exception as error:
                        logging.getLogger("omnivoice.session").warning(
                            "Failed to publish call.turn event: %s", error
                        )
            if self.active_generation_id == gen_id:
                self.active_generation_id = None

    async def generate(self, messages, tools, metric):
        queue = asyncio.Queue(maxsize=8)
        tool_calls = {}
        full_text = []
        prefix = metric.get("agent_response", "").strip()
        first_usable_at = None

        async def produce():
            nonlocal first_usable_at
            llm_started = time.perf_counter()
            segmenter = SpeechSegmenter()
            async for delta in self.services.llm.stream(messages, tools):
                content = delta.get("content") or ""
                if content and "llm_first_token_ms" not in metric:
                    token_at = time.perf_counter()
                    metric["llm_first_token_ms"] = (token_at - metric["started"]) * 1000
                    metric["llm_ttft_ms"] = (token_at - llm_started) * 1000
                if content.strip() and first_usable_at is None:
                    first_usable_at = time.perf_counter()
                full_text.append(content)
                accumulated = "".join(full_text)
                metric["agent_response"] = f"{prefix} {accumulated}".strip() if prefix else accumulated
                for call in delta.get("tool_calls", []):
                    entry = tool_calls.setdefault(call["index"], {"name": "", "arguments": ""})
                    entry["name"] += call.get("function", {}).get("name", "")
                    entry["arguments"] += call.get("function", {}).get("arguments", "")
                for segment in segmenter.feed(content):
                    if first_usable_at is not None and "speech_buffer_delay_ms" not in metric:
                        metric["speech_buffer_delay_ms"] = (time.perf_counter() - first_usable_at) * 1000
                    await queue.put(segment)
            remaining = segmenter.finish()
            if remaining:
                if first_usable_at is not None and "speech_buffer_delay_ms" not in metric:
                    metric["speech_buffer_delay_ms"] = (time.perf_counter() - first_usable_at) * 1000
                await queue.put(remaining)
            await queue.put(None)

        async def consume(producer_task):
            saw_end = False

            async def segments():
                nonlocal saw_end
                while True:
                    segment = await queue.get()
                    if segment is None:
                        saw_end = True
                        return
                    yield segment

            await self.say_stream(segments(), metric=metric)
            if not saw_end:
                # Carrier epoch invalidation or provider early completion must
                # not strand an LLM producer blocked on the bounded queue.
                producer_task.cancel()

        try:
            async with asyncio.TaskGroup() as group:
                producer_task = group.create_task(produce())
                group.create_task(consume(producer_task))
        finally:
            if full_text:
                accumulated = "".join(full_text)
                metric["agent_response"] = f"{prefix} {accumulated}".strip() if prefix else accumulated

        if len(tool_calls) > 1:
            raise ValueError("Only one action may be proposed per turn")
        if tool_calls:
            metric["tool_called"] = True
        for call in tool_calls.values():
            arguments = json.loads(call["arguments"])
            tool = await self.services.actions.get_tool(self.tenant["id"], call["name"])
            if tool["kind"] == "write":
                staged = await self.services.actions.stage(
                    self.tenant["id"], self.id, call["name"], arguments
                )
                prompt = (
                    staged["summary"] + ' To confirm, say: "' + self.config["confirmation_phrases"][0] + '".'
                )
                current = metric.get("agent_response", "").strip()
                metric["agent_response"] = f"{current} {prompt}".strip() if current else prompt
                await self.say(prompt, action_id=staged["id"], metric=metric)
            else:
                key = json.dumps([call["name"], arguments], sort_keys=True)
                cached = self.read_results.get(key)
                result = (
                    cached[1]
                    if cached and time.monotonic() - cached[0] < 3
                    else await self.services.actions.read(self.tenant["id"], call["name"], arguments)
                )
                await self.generate(
                    [
                        *messages,
                        {
                            "role": "user",
                            "content": "Use this read-only tool result as data to answer, without making another tool call: "
                            + json.dumps(result),
                        },
                    ],
                    [],
                    metric,
                )
        if full_text:
            self.history.append({"role": "assistant", "content": "".join(full_text)})
            self.history = self.history[-20:]
