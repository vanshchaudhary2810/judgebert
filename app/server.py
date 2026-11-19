"""Backend: FastAPI server for the Legal Meaning Preservation checker.

Run from the repository root:
    python -m uvicorn app.server:app --port 8000
then open http://localhost:8000

Environment variables:
    LMP_MODEL_DIR   folder of the trained model (default: models/lmp_model)
    LMP_IG_STEPS    Integrated-Gradients steps for word attributions (default 16; lower = faster)
"""
import io
import json
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

import pandas as pd
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lmp.baselines import bleu, chrf
from lmp.config import DECISIONS, ERROR_TYPES, Config, score_to_decision
from lmp.explain import ERROR_DESCRIPTIONS, explain_pair
from lmp.train import load_model, predict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.environ.get("LMP_MODEL_DIR", os.path.join(ROOT, "models", "lmp_model"))
RESULTS_DIR = os.path.join(ROOT, "results")
IG_STEPS = int(os.environ.get("LMP_IG_STEPS", "16"))
MAX_CHARS = 3000
MAX_BATCH_ROWS = 500

STATE = {"model": None, "tokenizer": None, "cfg": None, "device": None, "error": None, "load_seconds": None}
LOCK = threading.Lock()          # one inference at a time (keeps memory flat on a laptop)

ERROR_LABELS = {
    "omission": "Omission", "hallucination": "Added fact", "contradiction": "Contradiction",
    "obligation_permission": "Obligation / permission", "condition": "Condition",
    "exception": "Exception", "scope": "Scope", "number_date": "Number / date", "entity": "Parties",
}

EXAMPLES = [
    {"title": "Faithful simplification", "lang": "en", "kind": "good",
     "original": "The Insured shall notify the Insurer in writing of any loss within 30 days of its occurrence, failing which the claim shall not be admissible.",
     "simplified": "The insured must tell the insurer in writing about any loss within 30 days. Otherwise, the claim will not be accepted."},
    {"title": "shall → may", "lang": "en", "kind": "bad",
     "original": "The Insured shall notify the Insurer in writing of any loss within 30 days of its occurrence, failing which the claim shall not be admissible.",
     "simplified": "The insured may tell the insurer in writing about any loss within 30 days. Otherwise, the claim will not be accepted."},
    {"title": "Exception dropped", "lang": "en", "kind": "bad",
     "original": "The Insurer shall not be liable for any loss or damage caused by flood, unless the Flood Extension has been purchased and the additional premium paid.",
     "simplified": "The insurer will not pay for flood damage."},
    {"title": "Parties swapped", "lang": "en", "kind": "bad",
     "original": "The security deposit shall be refunded by the Landlord within 30 days of the Tenant vacating the premises.",
     "simplified": "The tenant must return the security deposit within 30 days after the landlord leaves."},
    {"title": "Negation lost", "lang": "en", "kind": "bad",
     "original": "The Tenant shall not sublet any part of the premises without the prior written consent of the Landlord.",
     "simplified": "The tenant can sublet any part of the premises without the landlord's written permission."},
    {"title": "Hindi: faithful", "lang": "hi", "kind": "good",
     "original": "किरायेदार प्रत्येक कैलेंडर माह की 5 तारीख को या उससे पूर्व रु. 25,000 का मासिक किराया अदा करेगा।",
     "simplified": "किरायेदार को हर महीने की 5 तारीख तक रु. 25,000 मासिक किराया देना होगा।"},
    {"title": "Hindi: date changed", "lang": "hi", "kind": "bad",
     "original": "किरायेदार प्रत्येक कैलेंडर माह की 5 तारीख को या उससे पूर्व रु. 25,000 का मासिक किराया अदा करेगा।",
     "simplified": "किरायेदार को हर महीने की 10 तारीख तक रु. 25,000 मासिक किराया देना होगा।"},
    {"title": "Hindi: must → may", "lang": "hi", "kind": "bad",
     "original": "बीमाधारक किसी भी हानि के घटित होने के 30 दिनों के भीतर बीमाकर्ता को लिखित रूप में सूचित करेगा।",
     "simplified": "बीमाधारक 30 दिनों के अंदर बीमाकर्ता को लिखकर नुकसान की जानकारी दे सकता है।"},
]


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load():
    if not os.path.exists(os.path.join(MODEL_DIR, "lmp_model.pt")):
        STATE["error"] = (f"No trained model found in {MODEL_DIR}. Download the 'lmp_model' folder from "
                          f"Google Drive (MyDrive/judgebert_final/lmp_model) into models/lmp_model.")
        print("WARNING:", STATE["error"])
        return
    t0 = time.time()
    dev = pick_device()
    cfg = Config(device=dev)
    try:
        model, tok = load_model(MODEL_DIR, cfg)
    except Exception as e:                       # e.g. an unsupported op on Apple GPU -> fall back to CPU
        if dev != "cpu":
            dev, cfg = "cpu", Config(device="cpu")
            model, tok = load_model(MODEL_DIR, cfg)
        else:
            STATE["error"] = f"Could not load the model: {e}"
            raise
    STATE.update(model=model, tokenizer=tok, cfg=cfg, device=dev, error=None, load_seconds=round(time.time() - t0, 1))
    print(f"Model loaded from {MODEL_DIR} on {dev} in {STATE['load_seconds']} s")


def fall_back_to_cpu():
    STATE["model"] = STATE["model"].to("cpu")
    STATE["cfg"] = Config(device="cpu")
    STATE["device"] = "cpu"
    print("Switched to CPU")


@asynccontextmanager
async def lifespan(app):
    load()
    yield


app = FastAPI(title="Legal Meaning Preservation API", version="1.0", lifespan=lifespan)


def detect_lang(*texts: str) -> str:
    t = " ".join(texts)
    if re.search(r"[ऀ-ॿ]", t):
        return "hi"
    low = f" {t.lower()} "
    fr_hits = len(re.findall(r"[éèêàçùûôœ]", low)) + sum(low.count(w) for w in (" le ", " la ", " les ", " des ", " est ", " du ", " l’", " l'"))
    return "fr" if fr_hits >= 3 else "en"


def require_model():
    if STATE["model"] is None:
        raise HTTPException(503, STATE["error"] or "Model is still loading.")


class PairIn(BaseModel):
    original: str = Field(..., min_length=1, max_length=MAX_CHARS)
    simplified: str = Field(..., min_length=1, max_length=MAX_CHARS)
    lang: Optional[str] = "auto"
    explain_words: bool = True


@app.get("/api/status")
def status():
    return {"model_loaded": STATE["model"] is not None, "device": STATE["device"], "model_dir": MODEL_DIR,
            "error": STATE["error"], "load_seconds": STATE["load_seconds"], "ig_steps": IG_STEPS,
            "results_available": os.path.exists(os.path.join(RESULTS_DIR, "summary.json"))}


@app.get("/api/examples")
def examples():
    return EXAMPLES


@app.post("/api/analyze")
def analyze(p: PairIn):
    require_model()
    orig, simp = p.original.strip(), p.simplified.strip()
    if not orig or not simp:
        raise HTTPException(422, "Both texts are required.")
    detected = detect_lang(orig, simp)
    lang = detected if (p.lang or "auto") == "auto" else p.lang
    if lang not in ("en", "hi", "fr"):
        raise HTTPException(422, "Language must be en, hi, fr or auto.")
    model, tok, cfg = STATE["model"], STATE["tokenizer"], STATE["cfg"]
    t0 = time.time()
    with LOCK:
        try:
            ex = explain_pair(model, tok, orig, simp, lang, cfg, with_ig=p.explain_words, ig_steps=IG_STEPS)
        except RuntimeError:
            if STATE["device"] == "cpu":
                raise
            fall_back_to_cpu()                    # an op unsupported on the Apple GPU: continue on CPU
            model, cfg = STATE["model"], STATE["cfg"]
            ex = explain_pair(model, tok, orig, simp, lang, cfg, with_ig=p.explain_words, ig_steps=IG_STEPS)
    elapsed = time.time() - t0
    pair = pd.DataFrame([{"original": orig, "simplified": simp}])
    n_tokens = len(tok(orig, simp, truncation=True, max_length=cfg.max_len)["input_ids"])
    probs = sorted(({"type": e, "label": ERROR_LABELS[e], "p": round(v, 3), "description": ERROR_DESCRIPTIONS[e]}
                    for e, v in ex["error_probs"].items()), key=lambda d: -d["p"])
    attr = ex["attributions"] or {"original": [], "simplified": []}
    return {
        "lmp_score": ex["lmp_score"], "decision": ex["decision"], "decisions": DECISIONS,
        "error_types": ex["error_types"], "error_probs": probs,
        "rule_findings": ex["rule_findings"], "rule_error_types": ex["rule_error_types"],
        "attributions": {k: [[w, round(float(s), 5)] for w, s in v] for k, v in attr.items()},
        "explanation": ex["explanation"],
        "generic_metrics": {"chrF": round(float(chrf(pair)[0]), 2), "BLEU": round(float(bleu(pair)[0]), 2)},
        "lang": lang, "lang_detected": detected, "tokens": n_tokens, "truncated": n_tokens >= cfg.max_len,
        "time_ms": int(elapsed * 1000), "device": STATE["device"],
        "rules_available": lang in ("en", "hi"),
    }


@app.post("/api/batch")
async def batch(file: UploadFile = File(...)):
    require_model()
    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    except Exception as e:
        raise HTTPException(422, f"Could not read the CSV: {e}")
    cols = {c.lower().strip(): c for c in df.columns}
    if "original" not in cols or "simplified" not in cols:
        raise HTTPException(422, "The CSV needs the columns 'original' and 'simplified' (and optionally 'lang').")
    df = df.rename(columns={cols["original"]: "original", cols["simplified"]: "simplified"})
    if "lang" in cols:
        df = df.rename(columns={cols["lang"]: "lang"})
    df = df.dropna(subset=["original", "simplified"]).head(MAX_BATCH_ROWS).reset_index(drop=True)
    if df.empty:
        raise HTTPException(422, "No rows with both 'original' and 'simplified' text.")
    df["original"], df["simplified"] = df["original"].astype(str), df["simplified"].astype(str)
    if "lang" not in df:
        df["lang"] = "auto"
    df["lang"] = [detect_lang(o, s) if str(l).strip().lower() in ("", "auto", "nan") else str(l).strip().lower()
                  for o, s, l in zip(df.original, df.simplified, df["lang"])]
    t0 = time.time()
    with LOCK:
        try:
            pred = predict(STATE["model"], STATE["tokenizer"], df, STATE["cfg"], batch_size=16)
        except RuntimeError:
            if STATE["device"] == "cpu":
                raise
            fall_back_to_cpu()
            pred = predict(STATE["model"], STATE["tokenizer"], df, STATE["cfg"], batch_size=16)
    cfg = STATE["cfg"]
    rows = []
    chrf_scores = chrf(df)
    for i, r in df.iterrows():
        errs = [ERROR_LABELS[e] for e in ERROR_TYPES if pred.loc[i, f"p_{e}"] >= 0.5]
        score = float(pred.loc[i, "pred_score"])
        rows.append({"original": r.original, "simplified": r.simplified, "lang": r["lang"],
                     "lmp_score": round(score, 2), "decision": score_to_decision(score, cfg),
                     "error_types": ", ".join(errs), "chrF": round(float(chrf_scores[i]), 2)})
    return {"rows": rows, "n": len(rows), "time_ms": int((time.time() - t0) * 1000),
            "truncated_to": MAX_BATCH_ROWS if len(df) == MAX_BATCH_ROWS else None}


@app.get("/api/results")
def results():
    path = os.path.join(RESULTS_DIR, "summary.json")
    if not os.path.exists(path):
        raise HTTPException(404, "results/summary.json not found. Run: python scripts/make_results_summary.py")
    with open(path, encoding="utf-8") as f:
        return JSONResponse(json.load(f))


if os.path.isdir(RESULTS_DIR):
    app.mount("/results", StaticFiles(directory=RESULTS_DIR), name="results")
app.mount("/", StaticFiles(directory=os.path.join(ROOT, "app", "static"), html=True), name="static")
