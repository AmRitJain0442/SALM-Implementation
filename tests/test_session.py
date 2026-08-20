from salm.audio import ArrayAudioSource
from salm.glossary import Glossary, Term
from salm.pipeline import Pipeline
from salm.session import Session

MODEL = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
VAD = "models/silero_vad.onnx"


def test_transcribes_a_recording_end_to_end():
    glossary = Glossary([Term(canonical="Kubernetes", type="jargon")])
    seen = []

    session = Session(
        model_dir=MODEL,
        vad_model=VAD,
        pipeline=Pipeline(glossary),
        on_utterance=seen.append,
    )
    session.run(ArrayAudioSource.from_wav("eval/audio/kuber.wav"))

    assert len(seen) >= 1
    assert "kubernetes" in " ".join(u.text for u in seen).lower()


def test_expands_an_acronym_end_to_end():
    glossary = Glossary([
        Term(canonical="EBITDA",
             expansion="Earnings Before Interest, Taxes, Depreciation and Amortization",
             type="acronym"),
    ])
    seen = []

    session = Session(model_dir=MODEL, vad_model=VAD,
                      pipeline=Pipeline(glossary), on_utterance=seen.append)
    session.run(ArrayAudioSource.from_wav("eval/audio/ebitda.wav"))

    assert "Earnings Before Interest" in " ".join(u.text for u in seen)
