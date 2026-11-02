"""Loading human-annotated data, aggregating annotators, splitting and augmentation."""
import re
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from .config import Config
from .perturb import build_sanity_pairs, build_silver_dataset

REQUIRED = ["lang", "domain", "original", "simplified"]


def krippendorff_alpha(df: pd.DataFrame, cols) -> float:
    """Interval Krippendorff's alpha over annotator columns (NaN = not annotated)."""
    try:
        import krippendorff
        data = df[cols].T.to_numpy(dtype=float)
        return float(krippendorff.alpha(reliability_data=data, level_of_measurement="interval"))
    except Exception as e:  # pragma: no cover
        print("krippendorff not available:", e)
        return float("nan")


def load_annotated_csv(path: str) -> pd.DataFrame:
    """Load the human-annotated dataset (see annotation_template.csv).

    Columns: pair_id, source_id, lang, domain, context, original, simplified,
             annotator_1 ... annotator_k (1-10), errors (optional, ';'-separated), notes
    The gold LMP is the mean of the annotator columns (as in the JUDGEBERT paper).
    """
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing columns: {missing}")
    ann = [c for c in df.columns if re.match(r"annotator_\d+", c)]
    if "lmp" not in df.columns:
        if not ann:
            raise ValueError("Need either an 'lmp' column or annotator_1..k columns.")
        df["lmp"] = df[ann].mean(axis=1)
    if ann:
        print(f"Annotators: {len(ann)} | Krippendorff's alpha (interval): {krippendorff_alpha(df, ann):.3f}")
        df["lmp_std"] = df[ann].std(axis=1)
    df = df.dropna(subset=["lmp"]).copy()
    if "pair_id" not in df.columns:
        df["pair_id"] = [f"H{i:04d}" for i in range(len(df))]
    if "source_id" not in df.columns:
        df["source_id"] = df.groupby(["lang", "original"]).ngroup().map(lambda i: f"SRC{i:04d}")
    if "concept_id" not in df.columns:
        df["concept_id"] = df["source_id"]
    if "context" not in df.columns:
        df["context"] = ""
    if "errors" not in df.columns:
        df["errors"] = np.nan          # NaN = error labels unknown -> masked in the loss
    df["context"] = df["context"].fillna("")
    df["perturbation"] = df.get("perturbation", "human")
    df["is_sanity"] = False
    df["label_source"] = "human"
    return df


def prepare_data(cfg: Config, human_csv: Optional[str] = None, silver_seed: int = 13) -> pd.DataFrame:
    """Main dataset: human CSV if given, otherwise the silver seed dataset."""
    if human_csv:
        df = load_annotated_csv(human_csv)
        print(f"Loaded {len(df)} human-annotated pairs.")
    else:
        df = build_silver_dataset(seed=silver_seed)
        print(f"No human CSV given -> using {len(df)} SILVER pairs (pipeline demo only, not paper results).")
    return df.reset_index(drop=True)


def split_data(df: pd.DataFrame, cfg: Config, seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Grouped split: all variants of one clause (and its translation) stay in the same split.

    The JUDGEBERT paper split instances randomly; grouping avoids leakage where a perturbed
    copy of a test clause appears in training.
    """
    groups = df["concept_id"] if "concept_id" in df else df["source_id"]
    gss = GroupShuffleSplit(n_splits=1, test_size=cfg.test_size, random_state=seed)
    tr_idx, te_idx = next(gss.split(df, groups=groups))
    train_val, test = df.iloc[tr_idx], df.iloc[te_idx]
    g2 = train_val["concept_id"] if "concept_id" in train_val else train_val["source_id"]
    gss2 = GroupShuffleSplit(n_splits=1, test_size=cfg.val_size / (1 - cfg.test_size), random_state=seed)
    tr2, va2 = next(gss2.split(train_val, groups=g2))
    return (train_val.iloc[tr2].reset_index(drop=True),
            train_val.iloc[va2].reset_index(drop=True),
            test.reset_index(drop=True))


def augment(train: pd.DataFrame, cfg: Config, extra_silver: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Add identical (10) / unrelated (1) sanity pairs built ONLY from training clauses (JUDGEBERT-DA)."""
    parts = [train]
    if cfg.data_augmentation:
        parts.append(build_sanity_pairs(train, seed=11))
    if extra_silver is not None and len(extra_silver):
        parts.append(extra_silver)
    return pd.concat(parts, ignore_index=True)


def errors_to_multihot(value, error_types) -> Tuple[np.ndarray, float]:
    """Returns (multi-hot vector, mask). mask=0 when error labels are unknown (NaN)."""
    vec = np.zeros(len(error_types), dtype=np.float32)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return vec, 0.0
    for e in str(value).split(";"):
        e = e.strip()
        if e in error_types:
            vec[error_types.index(e)] = 1.0
    return vec, 1.0
