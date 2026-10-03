import asyncio
import base64
import time

from .audio import mulaw_decode, mulaw_encode


class MediaTransport:
    def __init__(self, ws, provider, stream_id):
        self.ws, self.provider, self.stream_id = ws, provider, stream_id
        self.send_lock = asyncio.Lock()
        self.sequence = 0
        self.chunk = 0
        self.timestamp = 0
        self.epoch = 0
        self.next_send_at = 0.0

    @property
    def frame_size(self):
        return 3200 if self.provider == "exotel" else 320

    def decode(self, message):
        payload = base64.b64decode(message["media"]["payload"], validate=True)
        if len(payload) > 16000:
            raise ValueError("Media packet exceeds one second")
        pcm = mulaw_decode(payload) if self.provider == "twilio" else payload
        if len(pcm) % 2:
            raise ValueError("Incomplete PCM sample")
        return pcm

    def envelope(self, event):
        self.sequence += 1
        if self.provider == "exotel":
            return {"event": event, "stream_sid": self.stream_id}
        return {"event": event, "streamSid": self.stream_id}

    async def audio(self, pcm8k, epoch, on_first_sent=None):
        # Compatibility path for callers supplying complete utterances. The live
        # session uses PCMFrameBuffer and send_frame to preserve segment continuity.
        for offset in range(0, len(pcm8k), self.frame_size):
            frame = pcm8k[offset : offset + self.frame_size].ljust(self.frame_size, b"\0")
            if not await self.send_frame(frame, epoch, on_first_sent):
                return
            on_first_sent = None

    async def send_frame(self, frame, epoch, on_first_sent=None, owner_check=None):
        if len(frame) != self.frame_size:
            raise ValueError("Outbound carrier frame has incorrect size")
        # Pacing happens before each send so the final mark is not delayed by
        # an unnecessary post-frame sleep. Clear invalidates sleeping senders.
        delay = self.next_send_at - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        async with self.send_lock:
            if epoch != self.epoch or (owner_check is not None and not owner_check()):
                return False
            packet = self.envelope("media")
            self.chunk += 1
            packet["media"] = {
                "payload": base64.b64encode(
                    mulaw_encode(frame) if self.provider == "twilio" else frame
                ).decode()
            }
            self.timestamp += len(frame) // 16
            await asyncio.wait_for(self.ws.send_json(packet), 1)
            self.next_send_at = time.monotonic() + len(frame) / 16000
            if on_first_sent:
                on_first_sent()
            return True

    async def mark(self, name, epoch, owner_check=None):
        async with self.send_lock:
            if epoch != self.epoch or (owner_check is not None and not owner_check()):
                return False
            packet = self.envelope("mark")
            packet["mark"] = {"name": name}
            await asyncio.wait_for(self.ws.send_json(packet), 1)
            return True

    async def clear(self):
        self.epoch += 1
        async with self.send_lock:
            self.next_send_at = 0.0
            await asyncio.wait_for(self.ws.send_json(self.envelope("clear")), 1)
