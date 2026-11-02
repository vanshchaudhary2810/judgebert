"""Explanations: Integrated-Gradients token attributions + rule-based legal evidence + error-type head."""
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch

from .config import ERROR_TYPES, Config
from .legal_diff import legal_diff
from .train import first_input, predict

ERROR_DESCRIPTIONS = {
    "omission": "an essential fact of the original is missing",
    "hallucination": "the simplification adds a fact that is not in the original",
    "contradiction": "the simplification states the opposite of the original (negation flipped)",
    "obligation_permission": "an obligation (shall/must) and a permission (may/can) were confused",
    "condition": "a condition (if / in the event of) was dropped or changed",
    "exception": "an exception or proviso (unless / provided that) was dropped or changed",
    "scope": "the scope changed (any/all/every/only/vehicle vs car ...)",
    "number_date": "an amount, time limit, percentage or date changed",
    "entity": "the legal parties/roles were changed or swapped",
}


def _merge_subwords(tokens: List[str], scores: np.ndarray) -> List[Tuple[str, float]]:
    words, cur, cur_s = [], "", 0.0
    for t, s in zip(tokens, scores):
        if t.startswith("▁") or t.startswith("Ġ") or (not t.startswith("##") and cur == ""):
            if cur:
                words.append((cur, cur_s))
            cur, cur_s = t.lstrip("▁Ġ"), float(s)
        elif t.startswith("##"):
            cur, cur_s = cur + t[2:], cur_s + float(s)
        else:
            if cur:
                words.append((cur, cur_s))
            cur, cur_s = t, float(s)
    if cur:
        words.append((cur, cur_s))
    return [(w, s) for w, s in words if w.strip()]


def integrated_gradients(model, tokenizer, original: str, simplified: str, cfg: Config,
                         context: str = "", steps: int = 32) -> Dict[str, List[Tuple[str, float]]]:
    """Attribution of the LMP score to each word (Sundararajan et al., 2017).

    Negative attribution = the word pushed the predicted preservation score DOWN.
    Baseline = all-<pad> embeddings (special tokens kept).
    """
    device = next(model.parameters()).device
    model.eval()
    a = first_input({"original": original, "context": context}, cfg)
    enc = tokenizer(a, simplified, truncation=True, max_length=cfg.max_len, return_tensors="pt").to(device)
    emb_layer = model.encoder.get_input_embeddings()
    ids = enc["input_ids"]
    x = emb_layer(ids).detach()
    special = torch.tensor(tokenizer.get_special_tokens_mask(ids[0].tolist(), already_has_special_tokens=True),
                           device=device).bool()
    base_ids = torch.where(special, ids[0], torch.full_like(ids[0], tokenizer.pad_token_id)).unsqueeze(0)
    x0 = emb_layer(base_ids).detach()

    alphas = torch.linspace(1.0 / steps, 1.0, steps, device=device).view(-1, 1, 1)
    grads_total = torch.zeros_like(x)
    chunk = 8
    for i in range(0, steps, chunk):
        al = alphas[i:i + chunk]
        xi = (x0 + al * (x - x0)).requires_grad_(True)
        mask = enc["attention_mask"].expand(xi.size(0), -1)
        tt = enc.get("token_type_ids")
        out = model(inputs_embeds=xi, attention_mask=mask,
                    token_type_ids=tt.expand(xi.size(0), -1) if tt is not None else None)
        g = torch.autograd.grad(out["score"].sum(), xi)[0]
        grads_total += g.sum(0, keepdim=True)
    attr = ((x - x0) * grads_total / steps).sum(-1)[0].detach().cpu().numpy()

    tokens = tokenizer.convert_ids_to_tokens(ids[0].tolist())
    # find the segment boundary: second run of tokens after the first separator(s)
    sep_positions = [i for i, t in enumerate(tokens) if t in (tokenizer.sep_token, tokenizer.eos_token)]
    first_sep = sep_positions[0] if sep_positions else len(tokens) // 2
    spec = special.cpu().numpy()
    seg_a = [(t, s) for i, (t, s) in enumerate(zip(tokens, attr)) if i < first_sep and not spec[i]]
    seg_b = [(t, s) for i, (t, s) in enumerate(zip(tokens, attr)) if i > first_sep and not spec[i]]
    return {
        "original": _merge_subwords([t for t, _ in seg_a], np.array([s for _, s in seg_a])),
        "simplified": _merge_subwords([t for t, _ in seg_b], np.array([s for _, s in seg_b])),
    }


def explain_pair(model, tokenizer, original: str, simplified: str, lang: str, cfg: Config,
                 domain: str = "", context: str = "", top_k: int = 5, err_thr: float = 0.5,
                 with_ig: bool = True) -> Dict:
    """Full system output for one pair: score, decision, error types, evidence and explanation."""
    row = pd.DataFrame([{"original": original, "simplified": simplified, "context": context,
                         "lang": lang, "domain": domain}])
    pred = predict(model, tokenizer, row, cfg).iloc[0]
    score = float(pred["pred_score"])
    probs = {e: float(pred[f"p_{e}"]) for e in ERROR_TYPES}
    model_errors = [e for e, p in sorted(probs.items(), key=lambda kv: -kv[1]) if p >= err_thr]
    rules = legal_diff(original, simplified, lang)

    ig = integrated_gradients(model, tokenizer, original, simplified, cfg, context) if with_ig else None
    neg_words = []
    if ig:
        neg_words = [w for w, s in sorted(ig["simplified"], key=lambda ws: ws[1])[:top_k] if s < 0]

    lines = [f"LMP score: {score:.1f}/10 -> {pred['pred_decision']}."]
    if model_errors:
        lines.append("Predicted legal error type(s): " + "; ".join(
            f"{e} (p={probs[e]:.2f}): {ERROR_DESCRIPTIONS[e]}" for e in model_errors) + ".")
    elif score < cfg.preserved_min:
        top = max(probs, key=probs.get)
        lines.append(f"No error type above threshold; most likely: {top} (p={probs[top]:.2f}).")
    if rules["findings"]:
        lines.append("Rule-based evidence: " + " ".join(rules["findings"]))
    if neg_words:
        lines.append("Words in the simplification that lowered the score most: " + ", ".join(f"'{w}'" for w in neg_words) + ".")
    return {
        "lmp_score": round(score, 2),
        "decision": pred["pred_decision"],
        "error_types": model_errors,
        "error_probs": {k: round(v, 3) for k, v in probs.items()},
        "rule_findings": rules["findings"],
        "rule_error_types": sorted(rules["error_types"]),
        "attributions": ig,
        "explanation": " ".join(lines),
    }
