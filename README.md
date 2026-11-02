# Explainable Multilingual Legal Meaning Preservation

CSET 346 (NLP) project - an extension of **JUDGEBERT: Assessing Legal Meaning Preservation Between Sentences**
(Beauchemin et al., EMNLP 2025) from French insurance text to **English + Hindi**, two legal domains
(**insurance, tenancy**), with **explainable** outputs.

For each original-simplified pair the system produces:

| Output | How |
|---|---|
| **LMP score 1-10** | multilingual cross-encoder (XLM-R / MuRIL) with a bounded regression head |
| **Decision** | Preserved (>=6.5) / Partially Preserved / Not Preserved (<=2) - the paper's 7-10 / 2-6 / 1 brackets |
| **Legal error types** | multi-label head: omission, hallucination, contradiction, obligation_permission, condition, exception, scope, number_date, entity |
| **Explanation** | error-type head + rule-based legal diff (modality, negation, exceptions, numbers, parties) + Integrated-Gradients word attributions |

## Quick start (Google Colab)

1. Open `JUDGEBERT_LMP_Colab.ipynb` in Colab -> `Runtime -> Change runtime type -> T4 GPU`.
2. `Runtime -> Run all`. Default: `DATASET = "frjudge_xling"` (FrJUDGE + English/Hindi translations), `FAST_MODE = True`.
3. When the team annotation is done, set `HUMAN_CSV` to the annotated file and `FAST_MODE = False` (3 seeds, mean ± std).

The notebook is self-contained (it writes the `lmp/` package with `%%writefile`), so it needs no upload.

Locally: `pip install -r requirements.txt && python run_experiments.py [--human_csv data/x.csv] [--fast]`.
CPU smoke test without downloads: `python tests/smoke_test.py`.

## The five required experiments

| Brief | Code | What it reports |
|---|---|---|
| Exp 1 baseline vs. JUDGEBERT-style model | `Runner.exp1_baselines_vs_model` | Pearson, Spearman, RMSE, MAE, over-estimation %, decision acc/F1, bootstrap 95% CI. Baselines: TF-IDF char, chrF, BLEU, BERTScore (XLM-R), SBERT-Multi, LaBSE |
| Exp 2 English vs. Indian language | `exp2_languages` | per-language results + zero-shot en->hi and hi->en transfer |
| Exp 3 new domain / context | `exp3_domain_and_context` | insurance->tenancy and tenancy->insurance (true out-of-domain); sentence-only vs. context input |
| Exp 4 sanity checks | `exp4_sanity` | identical (expect 10) and unrelated same-domain legal pairs (expect 1), with vs. without data augmentation |
| Exp 5 error analysis (>=15 cases) | `exp5_robustness_and_errors` | score drop for 9 single legal edits per system, error-type P/R/F1 (model vs. rules), 20 explained cases (`exp5c_qualitative_cases.md`) |

All tables are written to `outputs/` as CSV plus `outputs/results.md`, with figures `fig_scatter.png` and `fig_robustness.png`.

## How this extends the paper (research gaps)

1. **Language generalisation** - English + Hindi with a parallel seed corpus; cross-lingual transfer.
2. **Domain generalisation / OOD split** - the paper never tested out-of-domain; we train on one domain and test on the other.
3. **Context** - the paper rated isolated sentences; we compare against context-augmented input.
4. **Explainability** - JUDGEBERT outputs one number; we add decision + error types + evidence + attributions.
5. **Robustness to small legal edits** - a controlled suite (shall->may, dropped "unless", changed amount, party swap, ...).
   Methodological fixes: grouped splits (no clause leakage), asymmetric loss (over-estimation penalised, cf. paper Table 6),
   bootstrap CIs, error labels per pair.

## Data

| Set | Size | Labels | Role |
|---|---|---|---|
| **FrJUDGE** (Beauchemin et al. 2025, CC-BY-NC-SA 4.0) | 297 French insurance pairs, official 186/21/90 split | human: 5 law students per pair (+ written justifications) | replication; source language for transfer |
| **FrJUDGE-EN / FrJUDGE-HI** | 297 + 297 pairs, NLLB-200 translations | French human label *projected* | cross-lingual training (translate-train) |
| **Ours: human EN/HI** (to annotate) | 180 test-split translations re-scored + 120 new tenancy pairs | human: 3 team annotators | evaluation in English/Hindi, new legal domain, projected-vs-human agreement |
| **Silver perturbations** | 396 + sanity pairs, 24 en/hi clause concepts | rule-generated | augmentation, error-type supervision, robustness suite |

* `lmp/frjudge.py` downloads FrJUDGE from the authors' GitHub, translates it (`nllb_translate`) and writes the
  annotation sheet of the 90 test pairs per language (`make_verification_sheet`).
* New tenancy clauses: collect ~30 clauses per language from the Model Tenancy Act 2021 (MoHUA) and the Tamil Nadu
  Regulation of Rights and Responsibilities of Landlords and Tenants Act 2017, simplify them with two open LLMs
  (`lmp/generate.py`), and add them to the annotation sheet.
* Annotation follows `ANNOTATION_GUIDE.md`; `lmp.data.load_annotated_csv` aggregates scores and prints Krippendorff's alpha.
* The silver data (`lmp/seed_data.py`, `lmp/perturb.py`) is rule-labelled: never report it as human results.

## Repository layout

```
lmp/
  config.py       hyper-parameters, error types, decision thresholds
  seed_data.py    parallel en-hi legal clauses (insurance, tenancy)
  perturb.py      legal perturbations, silver data, sanity pairs, robustness suite
  legal_diff.py   rule-based legal change detector (en + hi)
  data.py         CSV loading, annotator aggregation + Krippendorff alpha, grouped split, augmentation
  model.py        multi-task cross-encoder (score / decision / error types)
  train.py        training loop (asymmetric MSE + CE + class-balanced BCE, AMP, early stopping)
  metrics.py      Pearson, Spearman, RMSE, MAE, over-estimation, F1, sanity, bootstrap
  baselines.py    TF-IDF, chrF, BLEU, BERTScore, SBERT, LaBSE
  explain.py      Integrated Gradients + explanations
  experiments.py  Experiments 1-5 and the report
  generate.py     LLM simplification + annotation sheet
  frjudge.py      FrJUDGE loader, NLLB-200 translation, verification sheet
  demo.py         Gradio demo for the presentation
JUDGEBERT_LMP_Colab.ipynb   self-contained Colab notebook (built by scripts/build_notebook.py)
ANNOTATION_GUIDE.md         annotation procedure (bracket -> deduct -> error types)
data/                       seed sources + annotation template
tests/smoke_test.py         end-to-end CPU test with a tiny local model
tests/frjudge_test.py       FrJUDGE + translation path test (fake translator)
```

## Reference

Beauchemin, D., Albert-Rochette, M., Khoury, R., & Déziel, P.-L. (2025). JUDGEBERT: Assessing Legal Meaning
Preservation Between Sentences. *EMNLP 2025*, 92-118. Code: https://github.com/GRAAL-Research/JUDGEBERT
