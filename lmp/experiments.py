import copy
import gc
import json
import os
from dataclasses import asdict, replace
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import torch

from .baselines import run_baselines
from .config import DECISIONS, ERROR_TYPES, Config, score_to_decision
from .data import augment, prepare_data, split_data
from .explain import explain_pair
from .legal_diff import legal_diff
from .metrics import (bootstrap_ci, error_type_metrics, regression_metrics, sanity_metrics,
                      summarize_seeds)
from .perturb import build_sanity_pairs, build_silver_dataset, perturbation_suite, real_pair_edits
from .train import predict, save_model, train_model

OURS = "Ours (multi-task LMP)"


def _md(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False, floatfmt=".3f")
    except Exception:
        return df.to_string(index=False)


def _free(model):
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


class Runner:
    def __init__(self, cfg: Config, human_csv: Optional[str] = None, ablation_seeds: Optional[List[int]] = None,
                 split_seed: int = 42, df: Optional[pd.DataFrame] = None, data_name: str = ""):
        self.cfg = cfg
        self.human = human_csv is not None or df is not None
        self.ablation_seeds = ablation_seeds or cfg.seeds[:1]
        os.makedirs(cfg.output_dir, exist_ok=True)
        self.df = df.reset_index(drop=True) if df is not None else prepare_data(cfg, human_csv)
        self.data_name = data_name or ("human CSV" if human_csv else ("custom" if df is not None else "SILVER"))
        self.train, self.val, self.test = split_data(self.df, cfg, seed=split_seed)
        self.extra_silver = None
        if self.human:
            silver = build_silver_dataset()
            held_out = set(self.val["original"]) | set(self.test["original"])
            self.extra_silver = silver[~silver["original"].isin(held_out)].reset_index(drop=True)
            print(f"+ {len(self.extra_silver)} silver pairs used as extra training data")
        self.report: List[str] = []
        self.model = self.tokenizer = None
        print(f"train {len(self.train)} | val {len(self.val)} | test {len(self.test)} pairs "
              f"(grouped by clause / official split, no leakage)")
        print("languages:", self.df["lang"].value_counts().to_dict())
        self.df.to_csv(os.path.join(cfg.output_dir, "dataset_used.csv"), index=False)

    def fit_predict(self, train: pd.DataFrame, val: pd.DataFrame, eval_sets: Dict[str, pd.DataFrame],
                    cfg: Optional[Config] = None, seeds: Optional[List[int]] = None, keep_model=False,
                    augment_train=True, tag=""):
        cfg = cfg or self.cfg
        seeds = seeds or cfg.seeds
        tr = augment(train, cfg, self.extra_silver) if augment_train else train
        if cfg.legal_edit_aug:
            edits = real_pair_edits(train)
            print(f"[{tag}] + {len(edits)} legal-edit pairs built from real training pairs")
            tr = pd.concat([tr, edits], ignore_index=True)
        per_seed = {k: [] for k in eval_sets}
        for i, seed in enumerate(seeds):
            print(f"[{tag}] training seed {seed} on {len(tr)} pairs ...")
            model, tok, hist = train_model(tr, val, cfg, seed=seed)
            hist.to_csv(os.path.join(cfg.output_dir, f"history_{tag}_seed{seed}.csv"), index=False)
            for name, d in eval_sets.items():
                per_seed[name].append(predict(model, tok, d, cfg))
            if keep_model and i == 0:
                self.model, self.tokenizer = model, tok
            else:
                _free(model)
        out = {}
        for name, preds in per_seed.items():
            mean = sum(p.drop(columns=["pred_decision"]) for p in preds) / len(preds)
            mean["pred_decision"] = [score_to_decision(s, cfg) for s in mean["pred_score"]]
            mean.attrs["per_seed_scores"] = [p["pred_score"].to_numpy() for p in preds]
            out[name] = mean
        return out

    def _seed_table(self, gold, pred_frame, cfg=None):
        cfg = cfg or self.cfg
        return summarize_seeds([regression_metrics(gold, s, cfg) for s in pred_frame.attrs["per_seed_scores"]])

    def _log(self, title, df, note=""):
        text = f"\n## {title}\n\n{note}\n\n{_md(df)}\n"
        print(text)
        self.report.append(text)

    def exp1_baselines_vs_model(self):
        cfg = self.cfg
        test = self.test.copy()
        self.sanity_test = build_sanity_pairs(test, seed=5)
        base = test[test["lmp"] >= 7] if self.human else test[test["perturbation"] == "faithful"]
        self.robust = perturbation_suite(base).reset_index(drop=True)

        preds = self.fit_predict(self.train, self.val,
                                 {"test": test, "sanity": self.sanity_test, "robust": self.robust},
                                 keep_model=True, tag="main")
        self.pred_test, self.pred_sanity, self.pred_robust = preds["test"], preds["sanity"], preds["robust"]
        save_model(self.model, self.tokenizer, os.path.join(cfg.output_dir, "lmp_model"))

        allpairs = pd.concat([test.assign(_set="test"), self.sanity_test.assign(_set="sanity"),
                              self.robust.assign(_set="robust")], ignore_index=True)
        b = run_baselines(allpairs, cfg)
        self.base_test = b[allpairs._set == "test"].set_index(test.index)
        self.base_sanity = b[allpairs._set == "sanity"].set_index(self.sanity_test.index)
        self.base_robust = b[allpairs._set == "robust"].set_index(self.robust.index)
        self.baseline_names = list(b.columns)

        y = test["lmp"].to_numpy()
        rows = []
        for name in self.baseline_names:
            m = regression_metrics(y, self.base_test[name], cfg)
            lo, hi = bootstrap_ci(y, self.base_test[name], cfg)
            rows.append({"system": name, **{k: round(v, 3) if isinstance(v, float) else v for k, v in m.items()},
                         "pearson_95CI": f"[{lo:.2f}, {hi:.2f}]"})
        ours = self._seed_table(y, self.pred_test)
        lo, hi = bootstrap_ci(y, self.pred_test["pred_score"], cfg)
        rows.append({"system": OURS, **ours, "pearson_95CI": f"[{lo:.2f}, {hi:.2f}] (ensemble)"})
        table = pd.DataFrame(rows)
        table.to_csv(os.path.join(cfg.output_dir, "exp1_main.csv"), index=False)
        self._log("Experiment 1 - Generic similarity vs. LMP model (test set)", table,
                  "Scores on the 1-10 LMP scale. over_% = predictions that over-estimate preservation by "
                  ">0.5 levels (dangerous direction). Ours = mean ± std over seeds.")
        self._plot_scatter(y)
        return table

    def exp2_languages(self):
        cfg, test = self.cfg, self.test
        rows = []
        for lang in sorted(test["lang"].unique()):
            m = (test["lang"] == lang).to_numpy()
            y = test.loc[m, "lmp"].to_numpy()
            for name in self.baseline_names:
                rows.append({"setting": "joint (all languages)", "test_lang": lang, "system": name,
                             **regression_metrics(y, self.base_test.loc[m, name], cfg)})
            rows.append({"setting": "joint (all languages)", "test_lang": lang, "system": OURS,
                         **regression_metrics(y, self.pred_test.loc[m, "pred_score"], cfg)})
        langs = sorted(self.df["lang"].unique())
        if len(langs) >= 2:
            for src, tgt in [(s, t) for s in langs for t in langs if s != t and t != "fr"]:
                tr = self.train[self.train["lang"] == src]
                va = self.val[self.val["lang"] == src]
                te = test[test["lang"] == tgt]
                if len(tr) == 0 or len(te) == 0:
                    continue
                old = self.extra_silver
                if old is not None:
                    self.extra_silver = old[old["lang"] == src]
                p = self.fit_predict(tr, va if len(va) else self.val, {"t": te}, seeds=self.ablation_seeds,
                                     tag=f"xling_{src}2{tgt}")["t"]
                self.extra_silver = old
                rows.append({"setting": f"zero-shot {src}->{tgt}", "test_lang": tgt, "system": OURS,
                             **regression_metrics(te["lmp"], p["pred_score"], cfg)})
        table = pd.DataFrame(rows).round(3)
        table.to_csv(os.path.join(cfg.output_dir, "exp2_languages.csv"), index=False)
        self._log("Experiment 2 - English vs. Hindi (and cross-lingual transfer)",
                  table[["setting", "test_lang", "system", "pearson", "spearman", "rmse", "mae", "over_%", "n"]])
        return table

    def exp3_domain_and_context(self):
        cfg = self.cfg
        rows = []
        domains = sorted(self.df["domain"].unique())
        for d in domains:
            m = (self.test["domain"] == d).to_numpy()
            rows.append({"setting": "in-domain (joint training)", "test_domain": d, "system": OURS,
                         **regression_metrics(self.test.loc[m, "lmp"], self.pred_test.loc[m, "pred_score"], cfg)})
            best_b = max(self.baseline_names, key=lambda n: np.nan_to_num(
                regression_metrics(self.test["lmp"], self.base_test[n], cfg)["pearson"], nan=-1))
            rows.append({"setting": "in-domain", "test_domain": d, "system": best_b,
                         **regression_metrics(self.test.loc[m, "lmp"], self.base_test.loc[m, best_b], cfg)})
        if len(domains) == 1 and self.extra_silver is not None:
            other = self.extra_silver[self.extra_silver["domain"] != domains[0]]
            if len(other):
                old = self.extra_silver
                self.extra_silver = old[old["domain"] == domains[0]]
                p = self.fit_predict(self.train, self.val, {"t": other}, seeds=self.ablation_seeds,
                                     tag="domain_probe")["t"]
                self.extra_silver = old
                rows.append({"setting": f"out-of-domain {domains[0]}->{other['domain'].iloc[0]} (silver probe)",
                             "test_domain": other["domain"].iloc[0], "system": OURS,
                             **regression_metrics(other["lmp"], p["pred_score"], cfg)})
        if len(domains) >= 2:
            for src in domains:
                for tgt in domains:
                    if src == tgt:
                        continue
                    tr = self.train[self.train["domain"] == src]
                    va = self.val[self.val["domain"] == src]
                    te = self.df[(self.df["domain"] == tgt) & ~self.df["concept_id"].isin(tr["concept_id"])]
                    old = self.extra_silver
                    if old is not None:
                        self.extra_silver = old[old["domain"] == src]
                    p = self.fit_predict(tr, va if len(va) else self.val, {"t": te}, seeds=self.ablation_seeds,
                                         tag=f"domain_{src}2{tgt}")["t"]
                    self.extra_silver = old
                    rows.append({"setting": f"out-of-domain {src}->{tgt}", "test_domain": tgt, "system": OURS,
                                 **regression_metrics(te["lmp"], p["pred_score"], cfg)})
        dom_table = pd.DataFrame(rows).round(3)
        dom_table.to_csv(os.path.join(cfg.output_dir, "exp3a_domain.csv"), index=False)
        self._log("Experiment 3a - Legal-domain generalisation",
                  dom_table[["setting", "test_domain", "system", "pearson", "rmse", "mae", "over_%", "n"]])

        if not self.df["context"].fillna("").astype(str).str.strip().any():
            self._log("Experiment 3b - Sentence-only vs. contextual input", pd.DataFrame(),
                      "Skipped: this dataset has no context column (FrJUDGE pairs are isolated sentences).")
            return dom_table, None
        ctx_cfg = replace(cfg, use_context=True)
        p_ctx = self.fit_predict(self.train, self.val, {"t": self.test}, cfg=ctx_cfg, seeds=self.ablation_seeds,
                                 tag="context")["t"]
        y = self.test["lmp"]
        sent_only = summarize_seeds([regression_metrics(y, s, cfg)
                                     for s in self.pred_test.attrs["per_seed_scores"][:len(self.ablation_seeds)]])
        ctx_table = pd.DataFrame([{"input": "sentence-only (original || simplified)", **sent_only},
                                  {"input": "contextual (context || original || simplified)",
                                   **self._seed_table(y, p_ctx, ctx_cfg)}])
        ctx_table.to_csv(os.path.join(cfg.output_dir, "exp3b_context.csv"), index=False)
        note = ("NOTE: with silver labels the context cannot change the gold score, so this only checks the "
                "pipeline. With human data, annotate a subset both with and without context.") if not self.human else ""
        self._log("Experiment 3b - Sentence-only vs. contextual input", ctx_table, note)
        return dom_table, ctx_table

    def exp4_sanity(self):
        cfg = self.cfg
        kinds = self.sanity_test["perturbation"].to_numpy()
        rows = [{"system": n, **sanity_metrics(self.base_sanity[n], kinds)} for n in self.baseline_names]
        rows.append({"system": OURS + " + DA", **sanity_metrics(self.pred_sanity["pred_score"], kinds)})
        no_da = replace(cfg, data_augmentation=False)
        p = self.fit_predict(self.train, self.val, {"s": self.sanity_test}, cfg=no_da,
                             seeds=self.ablation_seeds, tag="noDA")["s"]
        rows.append({"system": OURS + " (no DA)", **sanity_metrics(p["pred_score"], kinds)})
        table = pd.DataFrame(rows).round(2)
        table.to_csv(os.path.join(cfg.output_dir, "exp4_sanity.csv"), index=False)
        self._log("Experiment 4 - Sanity checks (held-out clauses)", table,
                  "identical_>=99%: share of identical pairs scored >= 99% of the scale (higher is better). "
                  "unrelated_<=1%: share of unrelated same-domain legal pairs scored <= 1% (higher is better).")
        return table

    def exp5_robustness_and_errors(self, n_cases: int = 20):
        cfg = self.cfg
        r = self.robust.copy()
        r[OURS] = self.pred_robust["pred_score"].to_numpy()
        for n in self.baseline_names:
            r[n] = self.base_robust[n].to_numpy()
        systems = self.baseline_names + [OURS]
        mean = r.groupby("variant")[systems].mean()
        drop = (mean.loc["faithful"] - mean).drop(index="faithful")
        drop.loc["[average drop]"] = drop.mean()
        drop_table = drop.reset_index().round(2)
        drop_table.to_csv(os.path.join(cfg.output_dir, "exp5a_robustness_drop.csv"), index=False)
        self._log("Experiment 5a - Score drop caused by one legal edit (higher = more sensitive = better)",
                  drop_table, "Each row: mean(score of faithful simplification) - mean(score after the edit).")
        self._plot_robustness(drop.drop(index="[average drop]"))

        t = self.test.copy()
        if t["errors"].notna().any():
            model_m = error_type_metrics(t["errors"], self.pred_test, ERROR_TYPES)
            rule_prob = pd.DataFrame(
                [{f"p_{e}": float(e in legal_diff(o, s, l)["error_types"]) for e in ERROR_TYPES}
                 for o, s, l in zip(t["original"], t["simplified"], t["lang"])], index=t.index)
            rule_m = error_type_metrics(t["errors"], rule_prob, ERROR_TYPES)
            et = model_m.merge(rule_m, on=["error_type", "support"], suffixes=("_model", "_rules")).round(3)
            et.to_csv(os.path.join(cfg.output_dir, "exp5b_error_types.csv"), index=False)
            self._log("Experiment 5b - Legal error-type classification (P/R/F1)", et)

        cases = self._select_cases(n_cases)
        out = []
        for _, c in cases.iterrows():
            ex = explain_pair(self.model, self.tokenizer, c["original"], c["simplified"], c["lang"], cfg,
                              domain=c["domain"], context=c.get("context", ""))
            out.append({
                "pair_id": c["pair_id"], "lang": c["lang"], "domain": c["domain"],
                "gold_errors": c.get("errors", ""), "original": c["original"], "simplified": c["simplified"],
                "gold_lmp": round(float(c["lmp"]), 2), "model_lmp": ex["lmp_score"], "model_decision": ex["decision"],
                "model_error_types": ";".join(ex["error_types"]),
                "BERTScore": round(float(self.base_test.loc[c.name, "BERTScore(XLM-R)"]), 2)
                if "BERTScore(XLM-R)" in self.base_test else None,
                "chrF": round(float(self.base_test.loc[c.name, "chrF"]), 2),
                "explanation": ex["explanation"],
                "human_justification": c.get("justifications", "") if isinstance(c.get("justifications", ""), str) else "",
            })
        qual = pd.DataFrame(out)
        qual.to_csv(os.path.join(cfg.output_dir, "exp5c_qualitative_cases.csv"), index=False)
        with open(os.path.join(cfg.output_dir, "exp5c_qualitative_cases.md"), "w", encoding="utf-8") as f:
            for i, q in qual.iterrows():
                f.write(f"### Case {i + 1} ({q['lang']}, {q['domain']}, gold errors: {q['gold_errors'] or 'none'})\n"
                        f"- **Original:** {q['original']}\n- **Simplified:** {q['simplified']}\n"
                        f"- **Gold LMP:** {q['gold_lmp']} | **Model:** {q['model_lmp']} ({q['model_decision']}) "
                        f"| **chrF:** {q['chrF']} | **BERTScore:** {q['BERTScore']}\n"
                        f"- **Explanation:** {q['explanation']}\n"
                        + (f"- **Annotators' justification:** {q['human_justification']}\n" if q['human_justification'] else "")
                        + "\n")
        self._log(f"Experiment 5c - Qualitative error analysis ({len(qual)} cases, full text in exp5c_qualitative_cases.md)",
                  qual[["pair_id", "lang", "gold_errors", "gold_lmp", "model_lmp", "chrF", "model_error_types"]])
        return drop_table, qual

    def _select_cases(self, n):
        t = self.test.copy()
        t["abs_err"] = (self.pred_test["pred_score"] - t["lmp"]).abs()
        t = t.sort_values("abs_err", ascending=False)
        picked, seen = [], set()

        def take(idx):
            c = t.loc[idx, "concept_id"] if "concept_id" in t else idx
            if idx not in picked and c not in seen:
                picked.append(idx)
                seen.add(c)

        if t["errors"].notna().any():
            for e in ERROR_TYPES:
                for idx in t[t["errors"].fillna("").str.contains(e)].index[:1]:
                    take(idx)
        bins = pd.cut(t["lmp"], bins=[0, 3, 5, 7, 10.01], labels=False)
        quota = max(1, (n - len(picked)) // 4)
        for b in range(4):
            for idx in t[bins == b].index:
                if sum(bins.loc[picked] == b) >= quota:
                    break
                take(idx)
        for idx in t.index:
            if len(picked) >= n:
                break
            take(idx)
        return t.loc[picked[:n]]

    def exp5d_legal_edit_ablation(self):
        cfg = self.cfg
        seeds = self.ablation_seeds
        aug_cfg = replace(cfg, legal_edit_aug=True)
        p = self.fit_predict(self.train, self.val, {"test": self.test, "robust": self.robust}, cfg=aug_cfg,
                             seeds=seeds, tag="legal_edit_aug")
        k = len(seeds)
        main_test = np.mean(self.pred_test.attrs["per_seed_scores"][:k], axis=0)
        main_rob = np.mean(self.pred_robust.attrs["per_seed_scores"][:k], axis=0)

        def drops(scores):
            r = self.robust.assign(_s=scores)
            m = r.groupby("variant")["_s"].mean()
            d = (m.loc["faithful"] - m).drop(index="faithful")
            return d

        rows = []
        for name, t_scores, r_scores in [("Ours (main)", main_test, main_rob),
                                         ("Ours + legal-edit augmentation", p["test"]["pred_score"].to_numpy(),
                                          p["robust"]["pred_score"].to_numpy())]:
            m = regression_metrics(self.test["lmp"], t_scores, cfg)
            d = drops(r_scores) if len(self.robust) else pd.Series(dtype=float)
            row = {"system": name, "pearson": m["pearson"], "rmse": m["rmse"], "over_%": m["over_%"],
                   "avg_edit_drop": float(d.mean()) if len(d) else float("nan")}
            for v in ("change_number", "negation_flip", "obligation_flip", "entity_swap", "drop_exception"):
                row[f"drop_{v}"] = float(d.get(v, float("nan")))
            rows.append(row)
        table = pd.DataFrame(rows).round(3)
        table.to_csv(os.path.join(cfg.output_dir, "exp5d_legal_edit_ablation.csv"), index=False)
        self._log(f"Experiment 5d - Improvement: legal-edit augmentation (seeds {seeds}, same split)", table,
                  "Test-set agreement with humans (pearson, rmse) and sensitivity to single legal edits (drops, "
                  "higher = better). Edits are built only from training pairs.")
        self.ablation_table = table
        return table

    def _plot_scatter(self, y):
        try:
            import matplotlib.pyplot as plt
            best = max(self.baseline_names, key=lambda n: np.nan_to_num(
                regression_metrics(y, self.base_test[n], self.cfg)["pearson"], nan=-1))
            fig, ax = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
            for a, (name, p) in zip(ax, [(best, self.base_test[best]), (OURS, self.pred_test["pred_score"])]):
                a.scatter(y, p, s=18, alpha=0.7)
                a.plot([1, 10], [1, 10], "k--", lw=1)
                a.set_title(name)
                a.set_xlabel("gold LMP")
                a.set_xlim(0.5, 10.5)
                a.set_ylim(0.5, 10.5)
            ax[0].set_ylabel("predicted LMP")
            fig.tight_layout()
            fig.savefig(os.path.join(self.cfg.output_dir, "fig_scatter.png"), dpi=150)
            plt.close(fig)
        except Exception as e:
            print("plot skipped:", e)

    def _plot_robustness(self, drop: pd.DataFrame):
        try:
            import matplotlib.pyplot as plt
            ax = drop.plot.bar(figsize=(11, 4.5), width=0.8)
            ax.set_ylabel("score drop (1-10 scale)")
            ax.set_title("Sensitivity to single legal edits")
            ax.axhline(0, color="k", lw=0.8)
            plt.xticks(rotation=30, ha="right")
            plt.tight_layout()
            plt.savefig(os.path.join(self.cfg.output_dir, "fig_robustness.png"), dpi=150)
            plt.close()
        except Exception as e:
            print("plot skipped:", e)

    def write_report(self):
        head = ("# Results - Explainable Multilingual Legal Meaning Preservation\n\n"
                f"Data: {self.data_name if self.human else 'SILVER (rule-generated, pipeline demo only)'} | "
                f"model: `{self.cfg.model_name}` | seeds: {self.cfg.seeds}\n")
        path = os.path.join(self.cfg.output_dir, "results.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(head + "".join(self.report))
        with open(os.path.join(self.cfg.output_dir, "config.json"), "w") as f:
            json.dump(asdict(self.cfg), f, indent=2)
        print("Report written to", path)

    def run_all(self):
        self.exp1_baselines_vs_model()
        self.exp2_languages()
        self.exp3_domain_and_context()
        self.exp4_sanity()
        self.exp5_robustness_and_errors()
        self.exp5d_legal_edit_ablation()
        self.write_report()
