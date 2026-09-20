"""Real-time, full-duplex corpus WAV replay over the authenticated PCM gateway."""

import argparse
import asyncio
import base64
import json
import os
import time
import wave
from pathlib import Path

import numpy as np
import websockets


async def replay(args):
    url = os.environ.get("OMNI_REPLAY_URL", "")
    if not url.startswith(("ws://127.0.0.1", "ws://localhost", "wss://")):
        raise ValueError("Set OMNI_REPLAY_URL to the authenticated carrier/gateway URL")
    with wave.open(str(args.wav), "rb") as wav:
        if wav.getframerate() != 8000 or wav.getsampwidth() != 2:
            raise ValueError("Replay requires 8kHz PCM16 WAV")
        channels = wav.getnchannels()
        if not 0 <= args.channel < channels:
            raise ValueError("Invalid channel selection")
        pcm = (
            np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
            .reshape(-1, channels)[:, args.channel]
            .tobytes()
        )
    trace, playback = [], bytearray()
    started = time.perf_counter()
    mark_tasks = set()
    playback_until = started
    epoch = 0
    async with websockets.connect(url, max_size=2**20) as ws:
        await ws.send(
            json.dumps(
                {
                    "event": "start",
                    "stream_sid": "corpus-replay",
                    "start": {
                        "stream_sid": "corpus-replay",
                        "media_format": {"encoding": "raw/slin", "sample_rate": 8000},
                    },
                }
            )
        )

        async def acknowledge(name, deadline, generation):
            await asyncio.sleep(max(0, deadline - time.perf_counter()))
            if generation == epoch:
                await ws.send(json.dumps({"event": "mark", "mark": {"name": name}}))

        async def receive():
            nonlocal playback_until, epoch
            async for raw in ws:
                message = json.loads(raw)
                now = time.perf_counter()
                trace.append({"event": message["event"], "elapsed_ms": (now - started) * 1000})
                if message["event"] == "media":
                    audio = base64.b64decode(message["media"]["payload"])
                    playback.extend(audio)
                    playback_until = max(playback_until, now) + len(audio) / 16000
                elif message["event"] == "clear":
                    epoch += 1
                    playback_until = now
                elif message["event"] == "mark":
                    task = asyncio.create_task(acknowledge(message["mark"]["name"], playback_until, epoch))
                    mark_tasks.add(task)
                    task.add_done_callback(mark_tasks.discard)

        receiver = asyncio.create_task(receive())
        try:
            for offset in range(0, len(pcm), 320):
                await asyncio.sleep(max(0, started + offset / 16000 - time.perf_counter()))
                await ws.send(
                    json.dumps(
                        {
                            "event": "media",
                            "media": {"payload": base64.b64encode(pcm[offset : offset + 320]).decode()},
                        }
                    )
                )
            await asyncio.sleep(args.tail_seconds)
            await ws.send('{"event":"stop"}')
        finally:
            receiver.cancel()
            for task in mark_tasks:
                task.cancel()
            await asyncio.gather(receiver, *mark_tasks, return_exceptions=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "input": args.wav.name,
                "channel": args.channel,
                "trace": trace,
                "note": "Local gateway transport trace; no PSTN latency or WER claim.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    with wave.open(str(args.output.with_suffix(".wav")), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(playback)
    print("Replay trace and generated audio written. Private URL omitted.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=Path)
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--tail-seconds", type=float, default=10)
    parser.add_argument("--output", type=Path, default=Path("artifacts/replay.json"))
    args = parser.parse_args()
    # Do not expose the authentication-bearing WebSocket URL in exception output.
    try:
        asyncio.run(replay(args))
    except Exception as error:
        raise SystemExit(
            "Replay failed: " + type(error).__name__ + ". Check local configuration and provider logs."
        ) from None


if __name__ == "__main__":
    main()
