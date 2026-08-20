"""Integration tests: these load the real model and decode real audio."""
import wave
import numpy as np
import pytest

from salm.asr import Transcriber, SpeechSegmenter, is_filler

MODEL = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
VAD = "models/silero_vad.onnx"


def read_wav(path):
    with wave.open(path) as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


@pytest.fixture(scope="module")
def transcriber():
    return Transcriber(MODEL, num_threads=4)


def test_transcribes_speech_to_text(transcriber):
    text = transcriber.transcribe(read_wav("eval/audio/kuber.wav"))

    assert "kubernetes" in text.lower()


def test_the_model_hallucinates_filler_on_silence(transcriber):
    """Documents why the pipeline needs a filler guard, not just the VAD."""
    silence = np.zeros(16000, dtype=np.float32)

    # The model does not return empty -- it invents a short acknowledgement.
    assert is_filler(transcriber.transcribe(silence))


def test_segmenter_finds_the_speech_in_a_padded_clip():
    segmenter = SpeechSegmenter(VAD)
    padding = np.zeros(8000, dtype=np.float32)
    audio = np.concatenate([padding, read_wav("eval/audio/kuber.wav"), padding])

    segments = []
    for i in range(0, len(audio), 512):
        segments.extend(segmenter.push(audio[i:i + 512]))
    segments.extend(segmenter.flush())

    assert len(segments) >= 1
    assert sum(len(s) for s in segments) < len(audio)
