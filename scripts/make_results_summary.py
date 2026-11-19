import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OURS = "Ours (multi-task LMP)"
PAPER_FRENCH = 0.74
NICE = {"TF-IDF(char)": "TF-IDF char", "BERTScore(XLM-R)": "BERTScore", "SBERT-Multi": "SBERT-Multi",
        "chrF": "chrF", "BLEU": "BLEU", "LaBSE": "LaBSE"}
EDIT_NAMES = {"drop_condition": "Condition dropped", "negation_flip": "Negation flipped",
              "hallucination": "Fact added (hallucination)", "omission": "Omission",
              "entity_swap": "Parties swapped", "obligation_flip": "Obligation flipped (shall -> may)",
              "change_scope": "Scope changed", "change_number": "Number or date changed",
              "drop_exception": "Exception dropped"}


def num(x):
    return float(str(x).split("±")[0].strip())


def nice(name):
    return NICE.get(name, name)


def build(res_dir):
    cfg = json.load(open(os.path.join(res_dir, "config.json")))
    e1 = pd.read_csv(os.path.join(res_dir, "exp1_main.csv"))
    e2 = pd.read_csv(os.path.join(res_dir, "exp2_languages.csv"))
    e3 = pd.read_csv(os.path.join(res_dir, "exp3a_domain.csv"))
    e4 = pd.read_csv(os.path.join(res_dir, "exp4_sanity.csv"))
    e5 = pd.read_csv(os.path.join(res_dir, "exp5a_robustness_drop.csv"))
    p5d = os.path.join(res_dir, "exp5d_legal_edit_ablation.csv")
    e5d = pd.read_csv(p5d) if os.path.exists(p5d) else None

    ours1 = e1[e1.system == OURS].iloc[0]
    base1 = e1[e1.system != OURS].copy()
    base1["p"] = base1.pearson.map(num)
    best1 = base1.sort_values("p", ascending=False).iloc[0]
    ens = e3[(e3.system == OURS) & e3.setting.str.startswith("in-domain")]
    ens_p = float(ens.pearson.iloc[0]) if len(ens) else None
    seeds = cfg.get("seeds", [])

    joint = e2[e2.setting.str.startswith("joint")]

    def lang(l):
        d = joint[joint.test_lang == l]
        o = d[d.system == OURS]
        b = d[d.system != OURS].sort_values("pearson", ascending=False)
        return (float(o.pearson.iloc[0]) if len(o) else None,
                (float(b.pearson.iloc[0]), nice(b.system.iloc[0])) if len(b) else (None, ""))

    fr, en, hi = lang("fr"), lang("en"), lang("hi")

    s_ours = e4[e4.system.str.contains(r"\+ DA", regex=True)].iloc[0]
    s_noda = e4[e4.system.str.contains("no DA")].iloc[0]
    s_base = e4[~e4.system.str.startswith("Ours")].sort_values("unrelated_<=1%", ascending=False)

    e5i = e5.set_index("variant")
    avg = e5i.loc["[average drop]"]
    base_cols = [c for c in e5.columns if c not in ("variant", OURS)]
    best_avg_col = max(base_cols, key=lambda c: avg[c])

    headline = [
        {"measure": f"Pearson with human scores ({len(seeds)} seeds)",
         "ours": f"{num(ours1.pearson):.2f} ± {float(str(ours1.pearson).split('±')[1]):.2f}" if "±" in str(ours1.pearson)
         else f"{num(ours1.pearson):.2f}",
         "ours_note": f"{ens_p:.2f} with the {len(seeds)} seed models averaged" if ens_p and len(seeds) > 1 else "",
         "baseline": f"{best1.p:.2f}", "baseline_name": nice(best1.system)},
        {"measure": "French alone", "ours": f"{fr[0]:.2f}", "ours_note": f"the paper's French-only model: {PAPER_FRENCH:.2f}",
         "baseline": f"{fr[1][0]:.2f}", "baseline_name": fr[1][1]},
        {"measure": "English / Hindi", "ours": f"{en[0]:.2f} / {hi[0]:.2f}", "ours_note": "",
         "baseline": f"{en[1][0]:.2f} / {hi[1][0]:.2f}", "baseline_name": ""},
        {"measure": "Unrelated legal sentences scored correctly low", "ours": f"{s_ours['unrelated_<=1%']:.0f}%",
         "ours_note": "", "baseline": f"{s_base['unrelated_<=1%'].iloc[0]:.0f}%", "baseline_name": nice(s_base.system.iloc[0])},
        {"measure": "Average score drop after one legal edit", "ours": f"{avg[OURS]:.2f}", "ours_note": "",
         "baseline": f"{avg[best_avg_col]:.2f}", "baseline_name": nice(best_avg_col)},
    ]

    exp1 = []
    for _, r in e1.iterrows():
        exp1.append({"system": "Ours (multi-task LMP)" if r.system == OURS else nice(r.system), "ours": r.system == OURS,
                     "pearson": str(r.pearson), "ci": str(r.pearson_95CI).replace(" (ensemble)", " (averaged)"),
                     "spearman": str(r.spearman), "rmse": str(r.rmse), "mae": str(r.mae), "over": str(r["over_%"]),
                     "f1": str(r.decision_macroF1)})
    exp1.sort(key=lambda r: (not r["ours"], -num(r["pearson"])))

    langs = []
    names = {"fr": "French", "en": "English", "hi": "Hindi"}
    for l in ("fr", "en", "hi"):
        o, (bp, bn) = lang(l)
        langs.append({"language": names[l], "setting": "joint training (fr + en + hi)", "ours": round(o, 3),
                      "baseline": round(bp, 3), "baseline_name": bn})
    for _, r in e2[e2.setting.str.startswith("zero-shot")].iterrows():
        src, tgt = r.setting.replace("zero-shot ", "").split("->")
        langs.append({"language": names.get(tgt, tgt), "setting": f"zero-shot, trained on {names.get(src, src)} only",
                      "ours": round(float(r.pearson), 3), "baseline": None, "baseline_name": ""})

    domain = [{"setting": r.setting, "system": nice(r.system) if r.system != OURS else "Ours",
               "pearson": round(float(r.pearson), 3), "over": round(float(r["over_%"]), 1), "n": int(r.n)}
              for _, r in e3.iterrows()]

    sanity = [{"system": ("Ours + augmentation" if "+ DA" in r.system else "Ours, no augmentation")
               if r.system.startswith("Ours") else nice(r.system),
               "ours": r.system.startswith("Ours"), "identical": float(r["identical_>=99%"]),
               "unrelated": float(r["unrelated_<=1%"]), "unrelated_mean": float(r.unrelated_mean)}
              for _, r in e4.iterrows()]
    sanity.sort(key=lambda r: (not r["ours"], -r["unrelated"]))

    edits = []
    for v, r in e5i.drop(index="[average drop]").iterrows():
        bc = max(base_cols, key=lambda c: r[c])
        edits.append({"edit": EDIT_NAMES.get(v, v), "ours": float(r[OURS]), "baseline": float(r[bc]),
                      "baseline_name": nice(bc)})
    edits.sort(key=lambda r: -r["ours"])

    ablation = None
    if e5d is not None:
        ablation = [{"system": r.system, "pearson": float(r.pearson), "rmse": float(r.rmse), "over": float(r["over_%"]),
                     "avg_drop": float(r.avg_edit_drop), "number_drop": float(r.drop_change_number),
                     "negation_drop": float(r.drop_negation_flip)} for _, r in e5d.iterrows()]

    meta = {"model": cfg.get("model_name"), "seeds": seeds, "n_test": int(ours1.n),
            "data": "FrJUDGE (297 French pairs, 5 law-student annotators) + NLLB-200 English/Hindi translations",
            "labels_note": "English and Hindi gold scores are the French human labels projected through translation."}
    return {"meta": meta, "headline": headline, "exp1": exp1, "languages": langs, "domain": domain,
            "sanity": sanity, "edits": edits, "ablation": ablation}


def to_markdown(s):
    m = s["meta"]
    L = ["# Results - Explainable Multilingual Legal Meaning Preservation", "",
         f"Model `{m['model']}`, {len(m['seeds'])} seeds {m['seeds']}, {m['n_test']} test pairs "
         f"(90 each in French, English, Hindi). Data: {m['data']}. {m['labels_note']}", "",
         "All numbers are generated from the CSV files in [`results/`](results/) by `scripts/make_results_summary.py`.", "",
         "## Final results", "",
         "| Measure | Our model | Best baseline |", "| --- | --- | --- |"]
    for h in s["headline"]:
        ours = f"**{h['ours']}**" + (f" ({h['ours_note']})" if h["ours_note"] else "")
        base = h["baseline"] + (f" ({h['baseline_name']})" if h["baseline_name"] else "")
        L.append(f"| {h['measure']} | {ours} | {base} |")

    L += ["", "## 1. Generic similarity metrics vs. our model (Experiment 1)", "",
          "| System | Pearson | 95% CI | Spearman | RMSE | MAE | % over-estimated | Decision macro-F1 |",
          "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in s["exp1"]:
        b = (lambda x: f"**{x}**") if r["ours"] else (lambda x: x)
        L.append(f"| {b(r['system'])} | {b(r['pearson'])} | {r['ci']} | {r['spearman']} | {r['rmse']} | {r['mae']} | "
                 f"{r['over']} | {r['f1']} |")
    L += ["", "Ours = mean ± std over the seeds. \"% over-estimated\" = predictions more than 0.5 points above the human score.",
          "", "![Predicted vs. human scores](results/fig_scatter.png)", "",
          "BERTScore gives almost every simplification 9-10; our model follows the human scores.", "",
          "## 2. Languages and zero-shot transfer (Experiment 2)", "",
          "| Test language | Setting | Ours: Pearson | Best baseline: Pearson |", "| --- | --- | --- | --- |"]
    for r in s["languages"]:
        base = f"{r['baseline']:.3f} ({r['baseline_name']})" if r["baseline"] is not None else "-"
        L.append(f"| {r['language']} | {r['setting']} | **{r['ours']:.3f}** | {base} |")
    L += ["", f"The paper's French-only JUDGEBERT reaches {PAPER_FRENCH} on French.", "",
          "## 3. New legal domain (Experiment 3)", "",
          "| Setting | System | Pearson | % over-estimated | Pairs |", "| --- | --- | --- | --- | --- |"]
    for r in s["domain"]:
        L.append(f"| {r['setting']} | {r['system']} | {r['pearson']:.3f} | {r['over']:.1f} | {r['n']} |")
    L += ["", "The tenancy probe uses rule-labelled pairs.", "",
          "## 4. Sanity checks (Experiment 4)", "",
          "| System | Identical pairs scored ~10 | Unrelated legal pairs scored ~1 | Mean score, unrelated (expect 1) |",
          "| --- | --- | --- | --- |"]
    for r in s["sanity"]:
        b = (lambda x: f"**{x}**") if r["ours"] else (lambda x: x)
        L.append(f"| {b(r['system'])} | {r['identical']:.1f}% | {r['unrelated']:.1f}% | {r['unrelated_mean']:.2f} |")
    L += ["", "## 5. Sensitivity to a single legal edit (Experiment 5a)", "",
          "| Legal edit | Ours: score drop | Best baseline: drop |", "| --- | --- | --- |"]
    for r in s["edits"]:
        L.append(f"| {r['edit']} | **{r['ours']:.2f}** | {r['baseline']:.2f} ({r['baseline_name']}) |")
    L += ["", "Higher = the metric reacts more to the legal change.", "",
          "![Score drop after one legal edit](results/fig_robustness.png)", ""]
    if s["ablation"]:
        L += ["## 6. Improvement attempt: legal-edit augmentation (Experiment 5d, negative result)", "",
              "| System (seed 42) | Pearson | RMSE | % over-estimated | Avg. edit drop | Number edit drop | Negation drop |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        for r in s["ablation"]:
            L.append(f"| {r['system']} | {r['pearson']:.3f} | {r['rmse']:.2f} | {r['over']:.1f} | {r['avg_drop']:.2f} | "
                     f"{r['number_drop']:.2f} | {r['negation_drop']:.2f} |")
        L += ["", "Training on rule-made edits of real pairs lowered agreement with humans, so the final model does not use it.", ""]
    L += ["## 7. Case study", "", "20 explained cases with the law students' own justifications: "
          "[`results/exp5c_qualitative_cases.md`](results/exp5c_qualitative_cases.md).", "",
          "## Reproduce", "", "Open `JUDGEBERT_LMP_Colab.ipynb` in Colab (T4 GPU) and run all cells; it regenerates every file "
          "in `results/`. Then run `python scripts/make_results_summary.py`.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    res = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results")
    s = build(res)
    with open(os.path.join(res, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    with open(os.path.join(ROOT, "RESULTS.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(s))
    print("wrote", os.path.join(res, "summary.json"), "and", os.path.join(ROOT, "RESULTS.md"))
