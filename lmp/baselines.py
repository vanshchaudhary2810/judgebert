"""Generic semantic-similarity baselines, all mapped to the 1-10 LMP scale (decimal scaling, as in the paper).

Lexical : TF-IDF char n-gram cosine, chrF, BLEU
Neural  : BERTScore-F1 (multilingual XLM-R, own implementation), SBERT multilingual, LaBSE
"""
from typing import Dict

import numpy as np
import pandas as pd
import torch


def _to_scale(sim) -> np.ndarray:
    return 1.0 + 9.0 * np.clip(np.asarray(sim, dtype=float), 0.0, 1.0)


def tfidf_char(df: pd.DataFrame) -> np.ndarray:
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)
    vec.fit(pd.concat([df["original"], df["simplified"]]).astype(str))
    A, B = vec.transform(df["original"].astype(str)), vec.transform(df["simplified"].astype(str))
    sims = np.asarray(A.multiply(B).sum(1)).ravel()   # rows are L2-normalised -> dot = cosine
    return _to_scale(sims)


def chrf(df: pd.DataFrame) -> np.ndarray:
    from sacrebleu.metrics import CHRF
    m = CHRF()
    return _to_scale([m.sentence_score(s, [o]).score / 100 for o, s in zip(df["original"], df["simplified"])])


def bleu(df: pd.DataFrame) -> np.ndarray:
    from sacrebleu.metrics import BLEU
    m = BLEU(tokenize="intl", effective_order=True)
    return _to_scale([m.sentence_score(s, [o]).score / 100 for o, s in zip(df["original"], df["simplified"])])


@torch.no_grad()
def bertscore_f1(df: pd.DataFrame, model_name="xlm-roberta-base", layer=9, batch_size=32) -> np.ndarray:
    """BERTScore F1 (Zhang et al., 2019) without IDF, greedy cosine matching of contextual embeddings."""
    from transformers import AutoModel, AutoTokenizer
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name, output_hidden_states=True).to(dev).eval()

    def embed(texts):
        enc = tok(list(texts), padding=True, truncation=True, max_length=256, return_tensors="pt",
                  return_special_tokens_mask=True)
        special = enc.pop("special_tokens_mask").bool()
        enc = {k: v.to(dev) for k, v in enc.items()}
        hs = model(**enc).hidden_states[layer]
        hs = torch.nn.functional.normalize(hs, dim=-1)
        mask = enc["attention_mask"].bool() & ~special.to(dev)
        return hs, mask

    out = []
    o, s = df["original"].astype(str).tolist(), df["simplified"].astype(str).tolist()
    for i in range(0, len(o), batch_size):
        ho, mo = embed(o[i:i + batch_size])
        hs, ms = embed(s[i:i + batch_size])
        sim = torch.bmm(hs, ho.transpose(1, 2))                      # [B, Ls, Lo]
        sim = sim.masked_fill(~mo.unsqueeze(1), -2).masked_fill(~ms.unsqueeze(2), -2)
        prec = (sim.max(2).values * ms).sum(1) / ms.sum(1).clamp(min=1)       # simplified -> original
        rec = (sim.max(1).values * mo).sum(1) / mo.sum(1).clamp(min=1)        # original -> simplified
        f1 = 2 * prec * rec / (prec + rec).clamp(min=1e-8)
        out.append(f1.cpu().numpy())
    del model
    return _to_scale(np.concatenate(out))


@torch.no_grad()
def sbert_cosine(df: pd.DataFrame, model_name: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    m = SentenceTransformer(model_name, device=dev)
    a = m.encode(df["original"].astype(str).tolist(), normalize_embeddings=True, batch_size=64)
    b = m.encode(df["simplified"].astype(str).tolist(), normalize_embeddings=True, batch_size=64)
    del m
    return _to_scale((a * b).sum(1))


def run_baselines(df: pd.DataFrame, cfg, neural: bool = None) -> pd.DataFrame:
    """Return a DataFrame (same index as df) with one 1-10 score column per baseline."""
    neural = cfg.run_neural_baselines if neural is None else neural
    res: Dict[str, np.ndarray] = {}
    res["TF-IDF(char)"] = tfidf_char(df)
    res["chrF"] = chrf(df)
    res["BLEU"] = bleu(df)
    if neural:
        try:
            res["BERTScore(XLM-R)"] = bertscore_f1(df, cfg.bertscore_model, cfg.bertscore_layer)
        except Exception as e:
            print("BERTScore skipped:", e)
        for name in cfg.sbert_models:
            short = "LaBSE" if "LaBSE" in name else "SBERT-Multi"
            try:
                res[short] = sbert_cosine(df, name)
            except Exception as e:
                print(f"{short} skipped:", e)
    return pd.DataFrame(res, index=df.index)
