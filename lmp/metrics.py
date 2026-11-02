"""Evaluation metrics: correlation, error, over-estimation, decisions, error types, sanity, bootstrap CIs."""
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

from .config import DECISIONS, Config, score_to_decision


def _safe_corr(fn, y, p):
    if len(y) < 3 or np.std(y) < 1e-9 or np.std(p) < 1e-9:
        return float("nan")
    return float(fn(y, p)[0])


def regression_metrics(y, p, cfg: Config, tol: float = 0.5) -> Dict[str, float]:
    y, p = np.asarray(y, float), np.asarray(p, float)
    yd = [score_to_decision(v, cfg) for v in y]
    pd_ = [score_to_decision(v, cfg) for v in p]
    return {
        "pearson": _safe_corr(pearsonr, y, p),
        "spearman": _safe_corr(spearmanr, y, p),
        "rmse": float(np.sqrt(np.mean((p - y) ** 2))),
        "mae": float(np.mean(np.abs(p - y))),
        # % of predictions that over-estimate preservation by more than `tol` Likert levels
        # (the dangerous direction; JUDGEBERT paper Table 6)
        "over_%": float(100 * np.mean(p > y + tol)),
        "decision_acc": float(accuracy_score(yd, pd_)),
        "decision_macroF1": float(f1_score(yd, pd_, labels=DECISIONS, average="macro", zero_division=0)),
        "n": int(len(y)),
    }


def bootstrap_ci(y, p, cfg: Config, metric="pearson", n_boot: int = 1000, seed: int = 0):
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y, float), np.asarray(p, float)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        v = regression_metrics(y[idx], p[idx], cfg)[metric]
        if not np.isnan(v):
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def error_type_metrics(gold: pd.Series, prob: pd.DataFrame, error_types: List[str], thr: float = 0.5) -> pd.DataFrame:
    """Per-type and micro/macro P/R/F1. `gold` = ';'-separated strings, `prob` = columns p_<type>."""
    mask = gold.notna()
    Y = np.array([[int(e in str(g).split(";")) for e in error_types] for g in gold[mask]])
    P = (prob.loc[mask, [f"p_{e}" for e in error_types]].to_numpy() >= thr).astype(int)
    rows = []
    for j, e in enumerate(error_types):
        pr, rc, f1, _ = precision_recall_fscore_support(Y[:, j], P[:, j], average="binary", zero_division=0)
        rows.append({"error_type": e, "precision": pr, "recall": rc, "f1": f1, "support": int(Y[:, j].sum())})
    for avg in ("micro", "macro"):
        pr, rc, f1, _ = precision_recall_fscore_support(Y, P, average=avg, zero_division=0)
        rows.append({"error_type": f"[{avg}]", "precision": pr, "recall": rc, "f1": f1, "support": int(Y.sum())})
    return pd.DataFrame(rows)


def sanity_metrics(scores: np.ndarray, kinds: np.ndarray) -> Dict[str, float]:
    """JUDGEBERT sanity checks on the 1-10 scale normalised to [0, 1]:
    identical pairs should score >= 0.99, unrelated pairs <= 0.01 (1% float margin, as in the paper)."""
    s = (np.asarray(scores, float) - 1.0) / 9.0
    kinds = np.asarray(kinds)
    ident, unrel = s[kinds == "identical"], s[kinds == "unrelated"]
    return {
        "identical_>=99%": float(100 * np.mean(ident >= 0.99)) if len(ident) else float("nan"),
        "unrelated_<=1%": float(100 * np.mean(unrel <= 0.01)) if len(unrel) else float("nan"),
        "identical_mean": float(1 + 9 * ident.mean()) if len(ident) else float("nan"),
        "unrelated_mean": float(1 + 9 * unrel.mean()) if len(unrel) else float("nan"),
    }


def summarize_seeds(per_seed: List[Dict[str, float]]) -> Dict[str, str]:
    """mean ± std over seeds, formatted for tables."""
    df = pd.DataFrame(per_seed)
    out = {}
    for c in df.columns:
        if c == "n":
            out[c] = int(df[c].iloc[0])
            continue
        m, s = df[c].mean(), df[c].std(ddof=0)
        out[c] = f"{m:.3f} ± {s:.3f}" if len(df) > 1 else f"{m:.3f}"
    return out
