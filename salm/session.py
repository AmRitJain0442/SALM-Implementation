"""Drives one transcription session from an audio source to finished text.

Owns the loop but not the transport: the caller supplies the audio source and
receives utterances through a callback, so the same session powers the web
server, the CLI, and the evaluation harness.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

import numpy as np

from .asr import SpeechSegmenter, Transcriber
from .pipeline import Pipeline, Utterance


class AudioSource(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def chunks(self): ...


class Session:
    def __init__(
        self,
        model_dir: str | Path,
        vad_model: str | Path,
        pipeline: Pipeline,
        on_utterance: Callable[[Utterance], None] | None = None,
        num_threads: int = 4,
        hotwords: list[str] | None = None,
        hotwords_score: float = 0.0,
    ):
        self._transcriber = Transcriber(
            model_dir,
            num_threads=num_threads,
            hotwords=hotwords,
            hotwords_score=hotwords_score,
        )
        self._vad_model = vad_model
        self._pipeline = pipeline
        self._on_utterance = on_utterance or (lambda _: None)
        self._stopping = False
        self.utterances: list[Utterance] = []

    def stop(self) -> None:
        self._stopping = True

    def run(self, source: AudioSource) -> list[Utterance]:
        segmenter = SpeechSegmenter(self._vad_model)
        self._stopping = False
        self._pipeline.reset()
        self.utterances = []

        source.start()
        try:
            for chunk in source.chunks():
                if self._stopping:
                    break
                for segment in segmenter.push(chunk):
                    self._emit(segment)
            for segment in segmenter.flush():
                self._emit(segment)
        finally:
            source.stop()

        return self.utterances

    def _emit(self, segment: np.ndarray) -> None:
        utterance = self._pipeline.process(self._transcriber.transcribe(segment))
        if utterance is None:
            return
        self.utterances.append(utterance)
        self._on_utterance(utterance)
