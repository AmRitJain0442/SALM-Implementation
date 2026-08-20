import wave, numpy as np, sherpa_onnx, os
M = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
vocab = [l.split()[0] for l in open(f"{M}/tokens.txt",encoding="utf-8") if l.split()]
vset = set(vocab)

def tok(word):
    """Greedy longest-match BPE segmentation over tokens.txt."""
    s, out, first = word, [], True
    while s:
        for n in range(len(s), 0, -1):
            cand = ("▁" if first else "") + s[:n]
            if cand in vset:
                out.append(cand); s = s[n:]; first = False; break
        else:
            if first: first=False
            else: return None
    return " ".join(out) if out else None

def spell(word):   # acronym spelled letter-by-letter
    return " ".join(["▁"+word[0]] + list(word[1:]))

def read(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768.0

def run(hw, score, wav):
    kw = {}
    if hw:
        open("eval/tmp/hw.txt","w",encoding="utf-8").write("\n".join(hw)+"\n")
        kw = dict(hotwords_file="eval/tmp/hw.txt", hotwords_score=score, modeling_unit="cjkchar")
    r = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=f"{M}/encoder.int8.onnx", decoder=f"{M}/decoder.int8.onnx",
        joiner=f"{M}/joiner.int8.onnx", tokens=f"{M}/tokens.txt",
        model_type="nemo_transducer", num_threads=4,
        decoding_method="modified_beam_search", **kw)
    s = r.create_stream(); s.accept_waveform(16000, read(wav)); r.decode_stream(s)
    return s.result.text

os.makedirs("eval/tmp", exist_ok=True)
print("tokenizations: ARR=%r EBITDA=%r Kubernetes=%r" % (spell("ARR"), spell("EBITDA"), tok("Kubernetes")))
hw = [spell("ARR"), spell("EBITDA"), tok("Kubernetes")]
hw = [h for h in hw if h]
for wav in ["arr","ebitda","kuber"]:
    base = run(None, 0, f"eval/audio/{wav}.wav")
    print(f"\n{wav}:\n  off      : {base!r}")
    for sc in [4.0, 5.0, 6.0, 8.0]:
        print(f"  score={sc:<4}: {run(hw, sc, f'eval/audio/{wav}.wav')!r}")
