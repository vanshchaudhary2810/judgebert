"""Explainable multi-task cross-encoder for Legal Meaning Preservation (LMP).

Like JUDGEBERT, the original and simplified texts are concatenated with a separator and
fed to one transformer. Unlike JUDGEBERT (single regression head, French-only CamemBERT),
this model is multilingual and has three heads on a shared encoder:
    score head    -> LMP in [1, 10]
    decision head -> Not / Partially / Preserved
    error head    -> multi-label legal error types (omission, obligation_permission, ...)
"""
import torch
import torch.nn as nn
from transformers import AutoModel

from .config import DECISIONS, ERROR_TYPES


class LMPModel(nn.Module):
    def __init__(self, model_name: str, dropout: float = 0.1, n_errors: int = len(ERROR_TYPES)):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        h = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.score_head = nn.Sequential(nn.Linear(h, h // 2), nn.GELU(), nn.Dropout(dropout), nn.Linear(h // 2, 1))
        self.decision_head = nn.Linear(h, len(DECISIONS))
        self.error_head = nn.Linear(h, n_errors)

    def pool(self, hidden, mask):
        mask = mask.unsqueeze(-1).to(hidden.dtype)
        return (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-6)

    def forward(self, input_ids=None, attention_mask=None, token_type_ids=None, inputs_embeds=None):
        kwargs = {"attention_mask": attention_mask}
        if inputs_embeds is not None:
            kwargs["inputs_embeds"] = inputs_embeds
        else:
            kwargs["input_ids"] = input_ids
        if token_type_ids is not None and getattr(self.encoder.config, "type_vocab_size", 1) > 1:
            kwargs["token_type_ids"] = token_type_ids
        hidden = self.encoder(**kwargs).last_hidden_state
        pooled = self.dropout(self.pool(hidden, attention_mask))
        raw = self.score_head(pooled).squeeze(-1)
        score = 1.0 + 9.0 * torch.sigmoid(raw)       # bounded to the 1-10 Likert range
        return {"score": score, "decision_logits": self.decision_head(pooled),
                "error_logits": self.error_head(pooled)}
