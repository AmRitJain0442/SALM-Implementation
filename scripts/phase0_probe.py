"""Throwaway probe: does hotword biasing work on Parakeet TDT in sherpa-onnx?"""
import wave, numpy as np, sherpa_onnx, time, sys

M = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"

def read(p):
    with wave.open(p) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return a.astype(np.float32) / 32768.0

def build(**kw):
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=f"{M}/encoder.int8.onnx", decoder=f"{M}/decoder.int8.onnx",
        joiner=f"{M}/joiner.int8.onnx", tokens=f"{M}/tokens.txt",
        model_type="nemo_transducer", num_threads=4, **kw)

def run(rec, path):
    s = rec.create_stream(); s.accept_waveform(16000, read(path))
    t = time.time(); rec.decode_stream(s)
    return s.result.text, time.time() - t

for method in ["greedy_search", "modified_beam_search"]:
    try:
        rec = build(decoding_method=method)
        txt, el = run(rec, "eval/audio/arr.wav")
        print(f"[OK]   {method:22s} ({el:.2f}s): {txt!r}")
    except Exception as e:
        print(f"[FAIL] {method:22s}: {type(e).__name__}: {str(e)[:160]}")
