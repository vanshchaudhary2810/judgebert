from dataclasses import dataclass, field
from typing import List, Optional

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
    model_name: str = "xlm-roberta-base"
    max_len: int = 256
    dropout: float = 0.1

    epochs: int = 20
    batch_size: int = 16
    lr: float = 3e-5
    head_lr: float = 1e-3
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    patience: int = 6
    min_epochs: int = 3
    select_metric: str = "pearson"
    seeds: List[int] = field(default_factory=lambda: [42, 43, 44])
    fp16: bool = True

    over_penalty: float = 2.0
    w_decision: float = 0.5
    w_errors: float = 0.5

    use_context: bool = False
    data_augmentation: bool = True
    legal_edit_aug: bool = False
    test_size: float = 0.2
    val_size: float = 0.1

    preserved_min: float = 6.5
    not_preserved_max: float = 2.0

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
