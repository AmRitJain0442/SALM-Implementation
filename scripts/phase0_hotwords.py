import wave, numpy as np, sherpa_onnx, os
M = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"

def read(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)/32768.0

def build(**kw):
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=f"{M}/encoder.int8.onnx", decoder=f"{M}/decoder.int8.onnx",
        joiner=f"{M}/joiner.int8.onnx", tokens=f"{M}/tokens.txt",
        model_type="nemo_transducer", num_threads=4,
        decoding_method="modified_beam_search", **kw)

# What tokens does the model actually emit for the ARR clip?
rec = build()
s = rec.create_stream(); s.accept_waveform(16000, read("eval/audio/arr.wav")); rec.decode_stream(s)
print("baseline text  :", repr(s.result.text))
print("baseline tokens:", s.result.tokens)

os.makedirs("eval/tmp", exist_ok=True)
for unit, vocab, hw in [
    ("bpe", "", "ARR"),
    ("cjkchar", "", "ARR"),
    ("bpe", f"{M}/bpe.vocab", "ARR"),
]:
    open("eval/tmp/hw.txt","w",encoding="utf-8").write(hw+"\n")
    try:
        r = build(hotwords_file="eval/tmp/hw.txt", hotwords_score=2.0,
                  modeling_unit=unit, bpe_vocab=vocab)
        st = r.create_stream(); st.accept_waveform(16000, read("eval/audio/arr.wav")); r.decode_stream(st)
        print(f"[OK]   unit={unit:8s} vocab={'yes' if vocab else 'no ':3s} -> {st.result.text!r}")
    except Exception as e:
        print(f"[FAIL] unit={unit:8s} vocab={'yes' if vocab else 'no ':3s} -> {type(e).__name__}: {str(e)[:110]}")
