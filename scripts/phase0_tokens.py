import wave, numpy as np, sherpa_onnx
M = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
def read(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768.0
r = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=f"{M}/encoder.int8.onnx", decoder=f"{M}/decoder.int8.onnx",
    joiner=f"{M}/joiner.int8.onnx", tokens=f"{M}/tokens.txt",
    model_type="nemo_transducer", num_threads=4, decoding_method="modified_beam_search")
for w in ["kuber","ebitda"]:
    s = r.create_stream(); s.accept_waveform(16000, read(f"eval/audio/{w}.wav")); r.decode_stream(s)
    print(f"{w}: {s.result.tokens}")
