import sys, wave, numpy as np, sherpa_onnx, os
M = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
unit, hw = sys.argv[1], sys.argv[2]
def read(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)/32768.0
os.makedirs("eval/tmp", exist_ok=True)
open("eval/tmp/hw.txt","w",encoding="utf-8").write(hw+"\n")
r = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=f"{M}/encoder.int8.onnx", decoder=f"{M}/decoder.int8.onnx",
    joiner=f"{M}/joiner.int8.onnx", tokens=f"{M}/tokens.txt",
    model_type="nemo_transducer", num_threads=4,
    decoding_method="modified_beam_search",
    hotwords_file="eval/tmp/hw.txt", hotwords_score=float(os.environ.get("HWS","3.0")), modeling_unit=unit)
st = r.create_stream(); st.accept_waveform(16000, read("eval/audio/arr.wav")); r.decode_stream(st)
print(f"RESULT unit={unit!r} hw={hw!r} -> {st.result.text!r}")
