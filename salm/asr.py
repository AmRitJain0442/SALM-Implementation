"""Stage 1: turn audio into text, locally.

Uses sherpa-onnx (ONNX Runtime, CPU) so the same code runs on the Windows dev
machine and the Apple Silicon target. The model is NVIDIA's parakeet-tdt-0.6b-v2
exported to ONNX -- an offline model rather than a streaming one, because
Silero VAD cuts speech at natural pauses and an offline model decodes each
segment more accurately than any streaming model could.

Contextual biasing is supported but OFF by default: measured against this model
it produced no jargon-recall gain and materially worse WER at every setting.
See docs/superpowers/specs for the numbers. Jargon is repaired downstream in
salm/correct.py instead.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import sherpa_onnx

SAMPLE_RATE = 16000


class Transcriber:
    def __init__(
        self,
        model_dir: str | Path,
        num_threads: int = 4,
        hotwords: list[str] | None = None,
        hotwords_score: float = 0.0,
        hotwords_path: str | Path = "eval/tmp/hotwords.txt",
    ):
        model_dir = Path(model_dir)
        # Beam search measurably beats greedy on jargon ("Kubernetes" vs
        # "CubaNets" on the same clip) for a few ms more per segment.
        extra: dict = {"decoding_method": "modified_beam_search"}

        if hotwords and hotwords_score > 0:
            # modeling_unit is pinned to "cjkchar" deliberately: passing "bpe"
            # without a bpe.vocab (which this model does not ship) segfaults
            # the process inside the native library rather than raising.
            path = Path(hotwords_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(hotwords) + "\n", encoding="utf-8")
            extra = dict(
                hotwords_file=str(path),
                hotwords_score=hotwords_score,
                modeling_unit="cjkchar",
                decoding_method="modified_beam_search",
            )

        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(model_dir / "encoder.int8.onnx"),
            decoder=str(model_dir / "decoder.int8.onnx"),
            joiner=str(model_dir / "joiner.int8.onnx"),
            tokens=str(model_dir / "tokens.txt"),
            model_type="nemo_transducer",
            num_threads=num_threads,
            **extra,
        )

    def transcribe(self, samples: np.ndarray) -> str:
        stream = self._recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        self._recognizer.decode_stream(stream)
        return stream.result.text


class SpeechSegmenter:
    """Splits a continuous audio stream into utterances at natural pauses.

    Segmenting on silence is what keeps latency bounded while still handing the
    recogniser a whole utterance: the model sees full context, and the listener
    sees text one sentence behind rather than one word behind.
    """

    def __init__(
        self,
        vad_model: str | Path,
        min_silence_duration: float = 0.4,
        max_speech_duration: float = 12.0,
        threshold: float = 0.5,
    ):
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(vad_model)
        config.silero_vad.threshold = threshold
        config.silero_vad.min_silence_duration = min_silence_duration
        config.silero_vad.max_speech_duration = max_speech_duration
        config.sample_rate = SAMPLE_RATE
        self._window = config.silero_vad.window_size
        self._vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)
        self._pending = np.zeros(0, dtype=np.float32)

    def push(self, chunk: np.ndarray) -> list[np.ndarray]:
        """Feed audio; return any utterances that completed."""
        self._pending = np.concatenate([self._pending, chunk.astype(np.float32)])
        while len(self._pending) >= self._window:
            self._vad.accept_waveform(self._pending[: self._window])
            self._pending = self._pending[self._window :]
        return self._drain()

    def flush(self) -> list[np.ndarray]:
        """End of stream: emit whatever speech is still buffered."""
        self._vad.flush()
        return self._drain()

    def _drain(self) -> list[np.ndarray]:
        segments = []
        while not self._vad.empty():
            segments.append(np.array(self._vad.front.samples, dtype=np.float32))
            self._vad.pop()
        return segments

    @property
    def speech_detected(self) -> bool:
        return self._vad.is_speech_detected()


# Short acknowledgements the model invents when handed near-silence. The VAD
# filters most non-speech, but brief noise still slips through and would
# otherwise litter the transcript with "Okay." lines.
_FILLERS = {
    "", ".", "okay", "ok", "mm-hmm", "mmhmm", "mm", "hmm", "uh", "um", "ah",
    "yeah", "yep", "you", "thank you", "thanks", "bye", "so", "the", "oh",
}


def is_filler(text: str) -> bool:
    """True if the text carries no meaning worth putting in a transcript."""
    cleaned = text.strip().strip(".,!?-").strip().lower()
    return cleaned in _FILLERS
