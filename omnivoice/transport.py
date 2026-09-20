import asyncio
import base64

from .audio import mulaw_decode, mulaw_encode


class MediaTransport:
    def __init__(self, ws, provider, stream_id):
        self.ws, self.provider, self.stream_id = ws, provider, stream_id
        self.send_lock = asyncio.Lock()
        self.sequence = 0
        self.chunk = 0
        self.timestamp = 0
        self.epoch = 0

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
        # Exotel documents a 3.2KB minimum, aligned to 320-byte PCM units.
        # Carrier clear messages still discard queued audio on interruption.
        frame_size = 3200 if self.provider == "exotel" else 320
        for offset in range(0, len(pcm8k), frame_size):
            frame = pcm8k[offset : offset + frame_size]
            if self.provider == "exotel" and len(frame) < frame_size:
                frame = frame.ljust(frame_size, b"\x00")
            async with self.send_lock:
                if epoch != self.epoch:
                    return
                packet = self.envelope("media")
                self.chunk += 1
                packet["media"] = {
                    "payload": base64.b64encode(
                        mulaw_encode(frame) if self.provider == "twilio" else frame
                    ).decode()
                }
                # Exotel outbound messages need only the payload. Optional numeric
                # metadata has inconsistent string/number schemas across gateways.
                self.timestamp += len(frame) // 16
                await asyncio.wait_for(self.ws.send_json(packet), 1)
                if on_first_sent:
                    on_first_sent()
                    on_first_sent = None
            # Bound downstream accumulation; receive/VAD/STT continue concurrently.
            await asyncio.sleep(len(frame) / 16000)

    async def mark(self, name, epoch):
        async with self.send_lock:
            if epoch != self.epoch:
                return
            packet = self.envelope("mark")
            packet["mark"] = {"name": name}
            await asyncio.wait_for(self.ws.send_json(packet), 1)

    async def clear(self):
        self.epoch += 1
        async with self.send_lock:
            await asyncio.wait_for(self.ws.send_json(self.envelope("clear")), 1)
