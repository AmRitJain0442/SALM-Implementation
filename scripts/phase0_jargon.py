import wave, numpy as np, sherpa_onnx, os
M = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
rank = {}
for line in open(f"{M}/tokens.txt", encoding="utf-8"):
    p = line.rstrip("\n").split(" ")
    if len(p) >= 2: rank[p[0]] = int(p[1])

def bpe(word):
    sym = ["▁"+word[0]] + list(word[1:])
    if sym[0] not in rank: sym = ["▁"] + list(word)
    while True:
        best, bi = None, -1
        for i in range(len(sym)-1):
            r = rank.get(sym[i]+sym[i+1])
            if r is not None and (best is None or r < best): best, bi = r, i
        if bi < 0: break
        sym[bi:bi+2] = [sym[bi]+sym[bi+1]]
    return " ".join(sym)

def spell(w): return " ".join(["▁"+w[0]] + list(w[1:]))
def read(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768.0

HW = [bpe("Quantex"), bpe("Halberd"), spell("CRIMS"), bpe("Nimbus"),
      bpe("Vectrabridge"), bpe("Skylark"), bpe("Orbex")]
os.makedirs("eval/tmp", exist_ok=True)

def run(score, wav):
    kw = {}
    if score:
        open("eval/tmp/hw.txt","w",encoding="utf-8").write("\n".join(HW)+"\n")
        kw = dict(hotwords_file="eval/tmp/hw.txt", hotwords_score=score, modeling_unit="cjkchar")
    r = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=f"{M}/encoder.int8.onnx", decoder=f"{M}/decoder.int8.onnx",
        joiner=f"{M}/joiner.int8.onnx", tokens=f"{M}/tokens.txt",
        model_type="nemo_transducer", num_threads=4,
        decoding_method="modified_beam_search", **kw)
    s = r.create_stream(); s.accept_waveform(16000, read(wav)); r.decode_stream(s)
    return s.result.text

print("hotwords:", HW, "\n")
TRUTH = {"j1":"the Quantex pipeline feeds Halberd every morning",
         "j2":"CRIMS flagged three exceptions in the Nimbus tier",
         "j3":"we migrated Vectrabridge onto the Skylark platform",
         "j4":"Orbex reconciliation runs before the CRIMS batch"}
for w in ["j1","j2","j3","j4"]:
    print(f"{w}  truth: {TRUTH[w]}")
    print(f"    off      : {run(0, f'eval/audio/{w}.wav')!r}")
    for sc in [3.0, 4.0, 5.0]:
        print(f"    score={sc:<4}: {run(sc, f'eval/audio/{w}.wav')!r}")
    print()
