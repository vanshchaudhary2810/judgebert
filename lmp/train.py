"""Training / inference for the LMP cross-encoder (plain PyTorch loop, works on Colab GPU or CPU)."""
import copy
import math
import random
import time
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

from .config import DECISIONS, ERROR_TYPES, Config, score_to_decision_id
from .data import errors_to_multihot
from .model import LMPModel


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def get_device(cfg: Config) -> torch.device:
    if cfg.device:
        return torch.device(cfg.device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def first_input(row, cfg: Config) -> str:
    """Segment A = [context] + original. Segment B = simplified."""
    ctx = str(row.get("context", "") or "")
    if cfg.use_context and ctx.strip():
        return f"{ctx} || {row['original']}"
    return str(row["original"])


class PairDataset(Dataset):
    def __init__(self, df: pd.DataFrame, cfg: Config):
        self.rows = df.to_dict("records")
        self.cfg = cfg

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        err, mask = errors_to_multihot(r.get("errors", np.nan), ERROR_TYPES)
        lmp = float(r.get("lmp", np.nan)) if r.get("lmp") is not None else np.nan
        return {
            "a": first_input(r, self.cfg), "b": str(r["simplified"]),
            "lmp": lmp,
            "decision": score_to_decision_id(lmp, self.cfg) if not np.isnan(lmp) else -100,
            "errors": err, "err_mask": mask,
        }


def make_collate(tokenizer, cfg: Config):
    def collate(batch):
        enc = tokenizer([b["a"] for b in batch], [b["b"] for b in batch], truncation=True,
                        max_length=cfg.max_len, padding=True, return_tensors="pt")
        enc["lmp"] = torch.tensor([b["lmp"] for b in batch], dtype=torch.float)
        enc["decision"] = torch.tensor([b["decision"] for b in batch], dtype=torch.long)
        enc["errors"] = torch.tensor(np.stack([b["errors"] for b in batch]))
        enc["err_mask"] = torch.tensor([b["err_mask"] for b in batch], dtype=torch.float)
        return enc
    return collate


def multitask_loss(out, batch, cfg: Config, pos_weight=None) -> Tuple[torch.Tensor, Dict[str, float]]:
    pred, gold = out["score"].float(), batch["lmp"]
    diff = pred - gold
    # asymmetric MSE: over-estimation (approving a bad simplification) costs more
    w = torch.where(diff > 0, torch.full_like(diff, cfg.over_penalty), torch.ones_like(diff))
    l_score = (w * diff.pow(2)).mean() / cfg.over_penalty
    l_dec = F.cross_entropy(out["decision_logits"].float(), batch["decision"], ignore_index=-100)
    # pos_weight balances rare error types (each type occurs in only a small share of pairs)
    bce = F.binary_cross_entropy_with_logits(out["error_logits"].float(), batch["errors"], reduction="none",
                                             pos_weight=pos_weight).mean(1)
    l_err = (bce * batch["err_mask"]).sum() / batch["err_mask"].sum().clamp(min=1.0)
    total = l_score + cfg.w_decision * l_dec + cfg.w_errors * l_err
    return total, {"score": l_score.item(), "decision": l_dec.item(), "errors": l_err.item()}


@torch.no_grad()
def predict(model: LMPModel, tokenizer, df: pd.DataFrame, cfg: Config, batch_size: int = 64) -> pd.DataFrame:
    device = next(model.parameters()).device
    model.eval()
    tmp = df.copy()
    if "lmp" not in tmp:
        tmp["lmp"] = np.nan
    dl = DataLoader(PairDataset(tmp, cfg), batch_size=batch_size, shuffle=False,
                    collate_fn=make_collate(tokenizer, cfg))
    scores, dec, errs = [], [], []
    for batch in dl:
        inputs = {k: batch[k].to(device) for k in ("input_ids", "attention_mask", "token_type_ids") if k in batch}
        out = model(**inputs)
        scores.append(out["score"].float().cpu().numpy())
        dec.append(out["decision_logits"].float().softmax(-1).cpu().numpy())
        errs.append(torch.sigmoid(out["error_logits"].float()).cpu().numpy())
    scores, dec, errs = np.concatenate(scores), np.concatenate(dec), np.concatenate(errs)
    res = pd.DataFrame({"pred_score": scores, "pred_decision": [DECISIONS[i] for i in dec.argmax(1)]}, index=df.index)
    for j, e in enumerate(ERROR_TYPES):
        res[f"p_{e}"] = errs[:, j]
    return res


def _quick_eval(model, tokenizer, df, cfg) -> Dict[str, float]:
    p = predict(model, tokenizer, df, cfg)["pred_score"].to_numpy()
    y = df["lmp"].to_numpy(dtype=float)
    rmse = float(np.sqrt(np.mean((p - y) ** 2)))
    r = float(np.corrcoef(p, y)[0, 1]) if np.std(p) > 1e-8 and np.std(y) > 1e-8 else 0.0
    return {"rmse": rmse, "pearson": r}


def train_model(train_df: pd.DataFrame, val_df: pd.DataFrame, cfg: Config, seed: int = 42,
                verbose: bool = True):
    """Fine-tune the multi-task cross-encoder. Returns (model, tokenizer, history)."""
    set_seed(seed)
    device = get_device(cfg)
    tokenizer = AutoTokenizer.from_pretrained(cfg.model_name)
    model = LMPModel(cfg.model_name, cfg.dropout).to(device)

    dl = DataLoader(PairDataset(train_df, cfg), batch_size=cfg.batch_size, shuffle=True,
                    collate_fn=make_collate(tokenizer, cfg))
    enc_params = [p for n, p in model.named_parameters() if n.startswith("encoder.")]
    head_params = [p for n, p in model.named_parameters() if not n.startswith("encoder.")]
    opt = torch.optim.AdamW([{"params": enc_params, "lr": cfg.lr},
                             {"params": head_params, "lr": cfg.head_lr}], weight_decay=cfg.weight_decay)
    total = max(1, len(dl) * cfg.epochs)
    sched = get_linear_schedule_with_warmup(opt, int(cfg.warmup_ratio * total), total)
    use_amp = cfg.fp16 and device.type == "cuda"
    # class-balancing weights for the error-type head, estimated on rows with known error labels
    ev = [errors_to_multihot(v, ERROR_TYPES) for v in train_df.get("errors", pd.Series([np.nan] * len(train_df)))]
    known = np.array([v for v, m in ev if m > 0])
    if len(known):
        pos = known.sum(0)
        pos_weight = torch.tensor(np.clip((len(known) - pos) / np.maximum(pos, 1), 1.0, 5.0),
                                  dtype=torch.float, device=device)
    else:
        pos_weight = None
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best, best_state, bad, history = math.inf, None, 0, []
    for epoch in range(1, cfg.epochs + 1):
        model.train()
        t0, run = time.time(), []
        for batch in dl:
            batch = {k: v.to(device) for k, v in batch.items()}
            inputs = {k: batch[k] for k in ("input_ids", "attention_mask", "token_type_ids") if k in batch}
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
                out = model(**inputs)
            loss, parts = multitask_loss(out, batch, cfg, pos_weight)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            run.append(loss.item())
        val = _quick_eval(model, tokenizer, val_df, cfg) if len(val_df) else {"rmse": float(np.mean(run)), "pearson": 0}
        history.append({"epoch": epoch, "train_loss": float(np.mean(run)), **{f"val_{k}": v for k, v in val.items()}})
        if verbose:
            print(f"  epoch {epoch:2d} | train loss {np.mean(run):.3f} | val RMSE {val['rmse']:.3f} "
                  f"| val r {val['pearson']:.3f} | {time.time() - t0:.0f}s")
        if epoch < cfg.min_epochs:
            continue                      # let the randomly initialised heads settle first
        # lower is better: -Pearson (+ a small RMSE term to break ties), or plain RMSE
        crit = (-val["pearson"] + 0.02 * val["rmse"]) if cfg.select_metric == "pearson" else val["rmse"]
        if crit < best - 1e-4:
            best, bad = crit, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg.patience:
                if verbose:
                    print(f"  early stopping at epoch {epoch}")
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return model, tokenizer, pd.DataFrame(history)


def save_model(model: LMPModel, tokenizer, path: str):
    import json
    import os
    os.makedirs(path, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(path, "lmp_model.pt"))
    tokenizer.save_pretrained(path)
    model.encoder.config.save_pretrained(path)
    with open(os.path.join(path, "lmp_meta.json"), "w") as f:
        json.dump({"error_types": ERROR_TYPES, "decisions": DECISIONS}, f)


def load_model(path: str, cfg: Config):
    """Reload a saved model (encoder architecture is rebuilt from cfg.model_name)."""
    import os
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = LMPModel(cfg.model_name, cfg.dropout)
    model.load_state_dict(torch.load(os.path.join(path, "lmp_model.pt"), map_location="cpu"))
    return model.to(get_device(cfg)).eval(), tokenizer
