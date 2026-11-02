"""Build YOUR dataset: generate simplifications of real legal clauses with open LLMs on Colab.

Mirrors the JUDGEBERT setup (zero-shot prompt of Kew et al. 2023, temperature 1.0, top-p 0.9) but
uses open models and *several* systems, so the test set is not limited to one model's error profile.
"""
from typing import List

import pandas as pd
import torch


# The paper's prompt (Appendix A), translated; the language instruction is in capitals as in the paper.
PROMPTS = {
    "en": "Rewrite the complex sentence with simple sentence(s). Keep the meaning the same, but make it simpler. "
          "ANSWER IN ENGLISH!\n\nComplex: {input}",
    "hi": "जटिल वाक्य को एक या अधिक सरल वाक्यों में दोबारा लिखें। अर्थ वही रखें, लेकिन इसे सरल बनाएं। "
          "केवल हिंदी में उत्तर दें!\n\nजटिल वाक्य: {input}",
}

# Small instruction models that fit a free Colab T4 and handle English + Hindi reasonably.
DEFAULT_SYSTEMS = ["Qwen/Qwen2.5-1.5B-Instruct", "Qwen/Qwen2.5-3B-Instruct"]


@torch.no_grad()
def simplify_with_llm(texts: List[str], langs: List[str], model_name: str, max_new_tokens: int = 160,
                      temperature: float = 1.0, top_p: float = 0.9, batch_size: int = 8) -> List[str]:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_name, padding_side="left")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_name, torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None)
    outs = []
    for i in range(0, len(texts), batch_size):
        prompts = [tok.apply_chat_template([{"role": "user", "content": PROMPTS[l].format(input=t)}],
                                           tokenize=False, add_generation_prompt=True)
                   for t, l in zip(texts[i:i + batch_size], langs[i:i + batch_size])]
        enc = tok(prompts, return_tensors="pt", padding=True).to(model.device)
        gen = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=True, temperature=temperature,
                             top_p=top_p, pad_token_id=tok.pad_token_id)
        for g in gen[:, enc["input_ids"].shape[1]:]:
            outs.append(tok.decode(g, skip_special_tokens=True).strip().split("\n\n")[0])
        print(f"  {model_name}: {min(i + batch_size, len(texts))}/{len(texts)}")
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return outs


def generate_pairs(sources: pd.DataFrame, systems: List[str] = None, seed: int = 0) -> pd.DataFrame:
    """sources: columns source_id, lang, domain, context, original -> one row per (clause, system)."""
    torch.manual_seed(seed)
    systems = systems or DEFAULT_SYSTEMS
    rows = []
    for sysname in systems:
        simp = simplify_with_llm(sources["original"].tolist(), sources["lang"].tolist(), sysname)
        part = sources.copy()
        part["simplified"] = simp
        part["system"] = sysname
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


def make_annotation_sheet(pairs: pd.DataFrame, path: str, n_annotators: int = 3, seed: int = 0) -> pd.DataFrame:
    """Shuffled sheet for annotators. The `system` column is kept for analysis but should be hidden
    from annotators (as in the paper) - e.g. hide it in Google Sheets."""
    sheet = pairs.sample(frac=1.0, random_state=seed).reset_index(drop=True).copy()
    sheet.insert(0, "pair_id", [f"H{i:04d}" for i in range(len(sheet))])
    if "concept_id" not in sheet:
        sheet["concept_id"] = sheet["source_id"]
    for k in range(1, n_annotators + 1):
        sheet[f"annotator_{k}"] = float("nan")
    sheet["errors"] = ""
    sheet["notes"] = ""
    sheet.to_csv(path, index=False, encoding="utf-8-sig")   # utf-8-sig so Excel shows Hindi correctly
    print(f"Wrote {len(sheet)} pairs to {path}")
    return sheet
