"""Central configuration for the Explainable Multilingual LMP project."""
from dataclasses import dataclass, field
from typing import List, Optional

# Legal error types (multi-label). Matches the course brief: omission, hallucination,
# contradiction, obligation/permission, conditions, exceptions, scope, dates/numbers, entities.
ERROR_TYPES: List[str] = [
    "omission",
    "hallucination",
    "contradiction",
    "obligation_permission",
    "condition",
    "exception",
    "scope",
    "number_date",
    "entity",
]

DECISIONS: List[str] = ["Not Preserved", "Partially Preserved", "Preserved"]


@dataclass
class Config:
    # ---- model ----
    # Good multilingual choices that cover English + Hindi:
    #   "xlm-roberta-base"            (default, robust)
    #   "google/muril-base-cased"     (trained on 17 Indian languages + English)
    #   "ai4bharat/IndicBERTv2-MLM-only"
    #   "xlm-roberta-large"           (best quality, needs A100 / small batch)
    model_name: str = "xlm-roberta-base"
    max_len: int = 256
    dropout: float = 0.1

    # ---- training ----
    epochs: int = 12
    batch_size: int = 16
    lr: float = 2e-5
    head_lr: float = 1e-3
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    patience: int = 4
    min_epochs: int = 3          # no checkpoint selection / early stopping before this epoch
    seeds: List[int] = field(default_factory=lambda: [42, 43, 44])
    fp16: bool = True

    # ---- loss ----
    # Over-estimating legal meaning preservation is the dangerous direction
    # (it approves bad simplifications), so it is penalised more heavily.
    over_penalty: float = 2.0
    w_decision: float = 0.5
    w_errors: float = 0.5

    # ---- data ----
    use_context: bool = False
    data_augmentation: bool = True   # add identical (=10) and unrelated (=1) pairs to training
    test_size: float = 0.2
    val_size: float = 0.1

    # ---- decision thresholds on the 1-10 LMP scale (paper: 7-10 accurate, 2-6 imprecise, 1 off-track) ----
    preserved_min: float = 6.5
    not_preserved_max: float = 2.0

    # ---- baselines ----
    bertscore_model: str = "xlm-roberta-base"
    bertscore_layer: int = 9
    sbert_models: List[str] = field(default_factory=lambda: [
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "sentence-transformers/LaBSE",
    ])
    run_neural_baselines: bool = True

    output_dir: str = "outputs"
    device: Optional[str] = None


def score_to_decision(score: float, cfg: Config) -> str:
    if score >= cfg.preserved_min:
        return DECISIONS[2]
    if score <= cfg.not_preserved_max:
        return DECISIONS[0]
    return DECISIONS[1]


def score_to_decision_id(score: float, cfg: Config) -> int:
    return DECISIONS.index(score_to_decision(score, cfg))
