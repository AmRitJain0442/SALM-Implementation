import numpy as np
import pytest
from salm.audio import ArrayAudioSource


def test_replays_all_samples_in_blocks():
    samples = np.arange(1500, dtype=np.float32)

    chunks = list(ArrayAudioSource(samples, block=512).chunks())

    assert len(chunks) == 3
    assert np.array_equal(np.concatenate(chunks), samples)


def test_reads_a_wav_file():
    source = ArrayAudioSource.from_wav("eval/audio/kuber.wav")

    total = sum(len(c) for c in source.chunks())

    assert total > 16000


def test_rejects_a_wav_with_the_wrong_sample_rate(tmp_path):
    import wave
    path = tmp_path / "bad.wav"
    with wave.open(str(path), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 100)

    with pytest.raises(ValueError, match="44100"):
        ArrayAudioSource.from_wav(path)
