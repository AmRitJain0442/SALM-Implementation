"""Audio sources feeding the pipeline.

Both sources expose the same `chunks()` iterator, so a recorded file can be
replayed through exactly the code path a live meeting uses. That is what lets
the evaluation harness measure the real system rather than an approximation
of it.
"""

from __future__ import annotations

import queue
import wave
from pathlib import Path
from typing import Iterator

import numpy as np

SAMPLE_RATE = 16000
BLOCK = 512


class Microphone:
    """Live capture from an input device."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, block: int = BLOCK, device=None):
        self._sample_rate = sample_rate
        self._block = block
        self._device = device
        self._queue: queue.Queue = queue.Queue()
        self._stream = None
        self._running = False

    def start(self) -> None:
        import sounddevice as sd

        def callback(indata, frames, time_info, status):
            # Copy: sounddevice reuses the buffer after the callback returns.
            self._queue.put(indata[:, 0].copy())

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            blocksize=self._block,
            channels=1,
            dtype="float32",
            device=self._device,
            callback=callback,
        )
        self._stream.start()
        self._running = True

    def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def chunks(self) -> Iterator[np.ndarray]:
        while self._running:
            try:
                yield self._queue.get(timeout=0.1)
            except queue.Empty:
                continue


class ArrayAudioSource:
    """Replays audio already in memory, for evaluation and tests."""

    def __init__(self, samples: np.ndarray, block: int = BLOCK):
        self._samples = samples.astype(np.float32)
        self._block = block

    @classmethod
    def from_wav(cls, path: str | Path, block: int = BLOCK) -> "ArrayAudioSource":
        with wave.open(str(path)) as handle:
            if handle.getframerate() != SAMPLE_RATE:
                raise ValueError(
                    f"{path} is {handle.getframerate()} Hz; expected {SAMPLE_RATE}"
                )
            raw = handle.readframes(handle.getnframes())
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        return cls(samples, block=block)

    def start(self) -> None:  # symmetry with Microphone
        pass

    def stop(self) -> None:
        pass

    def chunks(self) -> Iterator[np.ndarray]:
        for i in range(0, len(self._samples), self._block):
            yield self._samples[i : i + self._block]
