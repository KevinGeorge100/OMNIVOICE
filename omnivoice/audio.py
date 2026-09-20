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
