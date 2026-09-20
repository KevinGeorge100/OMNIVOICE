"""Silero ONNX recurrent state is isolated per call. Inference runs off-loop."""

import numpy as np
import onnxruntime as ort


class SileroFactory:
    def __init__(self, path):
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.model = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])

    def session(self):
        return SileroSession(self.model)


class SileroSession:
    def __init__(self, model):
        self.model = model
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)
        self.buffer = bytearray()

    def process(self, pcm16k: bytes) -> list[float]:
        self.buffer.extend(pcm16k)
        probabilities = []
        while len(self.buffer) >= 1024:
            frame = bytes(self.buffer[:1024])
            del self.buffer[:1024]
            x = np.frombuffer(frame, dtype="<i2").astype(np.float32).reshape(1, -1) / 32768
            combined = np.concatenate((self.context, x), axis=1)
            output, self.state = self.model.run(
                None, {"input": combined, "state": self.state, "sr": np.array(16000, dtype=np.int64)}
            )
            self.context = x[:, -64:]
            probabilities.append(float(output.squeeze()))
        return probabilities
