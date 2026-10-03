"""Stateful 8 kHz G.711/PCM conversion; no removed stdlib audioop dependency."""

import numpy as np


def mulaw_decode(data: bytes) -> bytes:
    u = np.bitwise_not(np.frombuffer(data, dtype=np.uint8)).astype(np.int32)
    magnitude = (((u & 15) << 3) + 132) << ((u >> 4) & 7)
    pcm = np.where(u & 128, 132 - magnitude, magnitude - 132)
    return pcm.astype("<i2").tobytes()


def mulaw_encode(data: bytes) -> bytes:
    samples = np.frombuffer(data, dtype="<i2").astype(np.int32)
    sign = np.where(samples < 0, 128, 0)
    magnitude = np.minimum(np.abs(samples), 32635) + 132
    exponent = np.maximum(0, np.floor(np.log2(magnitude)).astype(np.int32) - 7)
    mantissa = (magnitude >> (exponent + 3)) & 15
    return np.bitwise_not(sign | (exponent << 4) | mantissa).astype(np.uint8).tobytes()


class Upsample8k:
    """Causal linear interpolation, carrying the preceding sample across packets."""

    def __init__(self):
        self.previous = 0

    def process(self, pcm: bytes) -> bytes:
        if len(pcm) % 2:
            raise ValueError("PCM must contain complete 16-bit samples")
        x = np.frombuffer(pcm, dtype="<i2").astype(np.int32)
        if not len(x):
            return b""
        previous = np.concatenate(([self.previous], x[:-1]))
        output = np.empty(len(x) * 2, dtype="<i2")
        output[0::2] = (previous + x) // 2
        output[1::2] = x
        self.previous = int(x[-1])
        return output.tobytes()


class PCMFrameBuffer:
    """Carry raw PCM across synthesis chunks; pad once at utterance end."""

    def __init__(self, frame_size: int):
        if frame_size <= 0 or frame_size % 2:
            raise ValueError("PCM frame size must contain complete samples")
        self.frame_size = frame_size
        self.pending = bytearray()

    def push(self, pcm: bytes) -> list[bytes]:
        if len(pcm) % 2:
            raise ValueError("PCM must contain complete 16-bit samples")
        self.pending.extend(pcm)
        full = len(self.pending) // self.frame_size
        frames = [
            bytes(self.pending[offset : offset + self.frame_size])
            for offset in range(0, full * self.frame_size, self.frame_size)
        ]
        del self.pending[: full * self.frame_size]
        return frames

    def finish(self) -> tuple[bytes | None, int]:
        if not self.pending:
            return None, 0
        padding = self.frame_size - len(self.pending)
        frame = bytes(self.pending) + b"\0" * padding
        self.pending.clear()
        return frame, padding

    def clear(self) -> None:
        self.pending.clear()
