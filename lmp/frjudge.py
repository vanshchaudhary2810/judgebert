"""FrJUDGE (Beauchemin et al., EMNLP 2025): the only human-annotated legal-meaning-preservation dataset.

297 French insurance clause / GPT-4 simplification pairs, each rated 1-10 by 5 law students, with
free-text justifications. License: CC-BY-NC-SA 4.0 (academic, non-commercial use with attribution).

We use it in three ways:
  1. replication of JUDGEBERT with a multilingual encoder on the official train/dev/test split;
  2. source-language training data for cross-lingual transfer to English and Hindi;
  3. "translate-and-project": NLLB-200 translations to English + Hindi that inherit the French human
     label (pair-level). These projected labels are noisy by design; a subset is re-scored by our own
     annotators, which yields our human-annotated English/Hindi set AND measures how well legal
     meaning judgments survive translation.
"""
import os
import subprocess
from typing import List, Optional

import numpy as np
import pandas as pd

REPO = "https://github.com/GRAAL-Research/JUDGEBERT.git"
NLLB_CODES = {"fr": "fra_Latn", "en": "eng_Latn", "hi": "hin_Deva"}


def download_frjudge(dest: str = "external/JUDGEBERT") -> str:
    """Shallow-clone the authors' repository (data lives in datastore/). Returns the datastore path."""
    if not os.path.isdir(dest):
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--depth", "1", REPO, dest], check=True)
    return os.path.join(dest, "datastore")


def load_frjudge(datastore: str) -> pd.DataFrame:
    """One row per pair with the official split, 5 annotator scores, mean LMP and justifications."""
    rel = pd.read_json(os.path.join(datastore, "released", "FrJUDGE.jsonl"), lines=True)
    rel["k"] = rel.groupby(["original", "simplification"]).cumcount() + 1
    scores = rel.pivot_table(index=["original", "simplification"], columns="k", values="legal_meaning")
    scores.columns = [f"annotator_{c}" for c in scores.columns]
    just = rel.groupby(["original", "simplification"])["justifications"].apply(
        lambda s: " | ".join(x for x in s.astype(str) if len(x.strip()) > 3 and x.strip().lower() != "n/a"))
    df = scores.join(just).reset_index()
    df["lmp"] = df[[c for c in df.columns if c.startswith("annotator_")]].mean(axis=1)

    split_of = {}
    for split in ("train", "dev", "test"):
        s = pd.read_json(os.path.join(datastore, "training", f"{split}_FrJUDGE.jsonl"), lines=True)
        for o, p in zip(s["original"], s["simplification"]):
            split_of[(o, p)] = "val" if split == "dev" else split
    df["split"] = [split_of.get((o, p), "train") for o, p in zip(df["original"], df["simplification"])]

    df = df.rename(columns={"simplification": "simplified"})
    df["concept_id"] = [f"FR{i:03d}" for i in range(len(df))]     # translations share this id -> same split
    df["source_id"] = df["concept_id"] + "-fr"
    df["pair_id"] = df["source_id"]
    df["lang"], df["domain"], df["context"] = "fr", "insurance", ""
    df["errors"] = np.nan              # FrJUDGE has no error-type labels -> masked in the loss
    df["perturbation"], df["is_sanity"], df["label_source"] = "human", False, "human"
    return df


def nllb_translate(texts: List[str], src: str, tgt: str, model_name: str = "facebook/nllb-200-distilled-600M",
                   batch_size: int = 16, max_new_tokens: int = 256) -> List[str]:
    """Translate with NLLB-200 (Colab T4: ~1-2 min per 600 sentences)."""
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_name, src_lang=NLLB_CODES[src])
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(dev).eval()
    if dev == "cuda":
        model = model.half()
    bos = tok.convert_tokens_to_ids(NLLB_CODES[tgt])
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            enc = tok(texts[i:i + batch_size], return_tensors="pt", padding=True, truncation=True,
                      max_length=400).to(dev)
            gen = model.generate(**enc, forced_bos_token_id=bos, max_new_tokens=max_new_tokens, num_beams=4)
            out += tok.batch_decode(gen, skip_special_tokens=True)
    del model
    if dev == "cuda":
        torch.cuda.empty_cache()
    return out


def translate_frjudge(fr: pd.DataFrame, langs=("en", "hi"), cache_dir: str = "data",
                      translator=nllb_translate) -> pd.DataFrame:
    """Translate original + simplification of every FrJUDGE pair; the French human label is projected.

    Results are cached to data/frjudge_<lang>.csv so translation runs only once.
    """
    parts = []
    for lang in langs:
        path = os.path.join(cache_dir, f"frjudge_{lang}.csv")
        if os.path.exists(path):
            t = pd.read_csv(path)
        else:
            uniq_orig = list(dict.fromkeys(fr["original"]))
            print(f"Translating {len(uniq_orig)} originals + {len(fr)} simplifications fr->{lang} ...")
            o_map = dict(zip(uniq_orig, translator(uniq_orig, "fr", lang)))
            s_tr = translator(fr["simplified"].tolist(), "fr", lang)
            t = fr.copy()
            t["original_fr"], t["simplified_fr"] = t["original"], t["simplified"]
            t["original"] = t["original_fr"].map(o_map)
            t["simplified"] = s_tr
            t["lang"] = lang
            t["source_id"] = t["concept_id"] + f"-{lang}"
            t["pair_id"] = t["source_id"]
            t["label_source"] = "projected"     # label inherited from the French human judgments
            os.makedirs(cache_dir, exist_ok=True)
            t.to_csv(path, index=False, encoding="utf-8")
        t["errors"] = np.nan
        t["context"] = t["context"].fillna("") if "context" in t else ""
        parts.append(t)
    return pd.concat(parts, ignore_index=True)


def frjudge_dataset(mode: str = "frjudge_xling", datastore: Optional[str] = None, cache_dir: str = "data",
                    translator=nllb_translate) -> pd.DataFrame:
    """mode='frjudge' -> French only; 'frjudge_xling' -> French + projected English + Hindi."""
    datastore = datastore or download_frjudge()
    fr = load_frjudge(datastore)
    if mode == "frjudge":
        return fr
    tr = translate_frjudge(fr, cache_dir=cache_dir, translator=translator)
    keep = [c for c in fr.columns if c in tr.columns]
    return pd.concat([fr, tr[keep + [c for c in ("original_fr", "simplified_fr") if c in tr.columns]]],
                     ignore_index=True)


def make_verification_sheet(xling: pd.DataFrame, path: str, n_per_lang: int = 90, n_annotators: int = 3,
                            seed: int = 0) -> pd.DataFrame:
    """Annotation sheet of translated pairs for our team to re-score in English / Hindi.

    Takes the official TEST split first (90 pairs per language), so the human EN/HI scores are on pairs the
    model never trains on; tops up with val/train pairs if n_per_lang > 90. The projected (French) label is
    kept in `projected_lmp` - hide that column from annotators.
    """
    rows = []
    for lang in ("en", "hi"):
        d = xling[xling["lang"] == lang]
        order = {"test": 0, "val": 1, "train": 2}
        d = d.assign(_o=d["split"].map(order)).sample(frac=1, random_state=seed).sort_values("_o", kind="stable")
        rows.append(d.head(n_per_lang).drop(columns="_o"))
    sheet = pd.concat(rows).sample(frac=1, random_state=seed).reset_index(drop=True)
    sheet = sheet.rename(columns={"lmp": "projected_lmp"})
    cols = ["pair_id", "concept_id", "split", "lang", "domain", "context", "original", "simplified", "projected_lmp"]
    sheet = sheet[[c for c in cols if c in sheet.columns]].copy()
    for k in range(1, n_annotators + 1):
        sheet[f"annotator_{k}"] = np.nan
    sheet["errors"], sheet["translation_ok"], sheet["notes"] = "", "", ""
    sheet.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(sheet)} pairs ({n_per_lang} per language) to {path}: "
          f"{sheet['split'].value_counts().to_dict()}")
    return sheet
