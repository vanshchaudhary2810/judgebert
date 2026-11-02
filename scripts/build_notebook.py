"""Generate the self-contained Colab notebook from the package sources (keeps notebook == repo code)."""
import os

import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES = ["__init__.py", "config.py", "seed_data.py", "perturb.py", "legal_diff.py", "data.py", "model.py",
           "train.py", "metrics.py", "baselines.py", "explain.py", "experiments.py", "generate.py", "frjudge.py", "demo.py"]

nb = nbf.v4.new_notebook()
C, M = nbf.v4.new_code_cell, nbf.v4.new_markdown_cell
cells = []

cells.append(M("""# Explainable Multilingual Legal Meaning Preservation (JUDGEBERT extension)
**CSET 346 - NLP project.** A JUDGEBERT-style cross-encoder extended to **English + Hindi**, two legal domains
(**insurance**, **tenancy**), with **explainable** outputs and the five required experiments.

For each original-simplified pair the system outputs:
**LMP score (1-10)**, **decision** (Preserved / Partially / Not Preserved), **legal error types** and a **short explanation**.

| Research gap (JUDGEBERT paper) | Where it is addressed |
|---|---|
| French-only | English + Hindi, multilingual encoder, cross-lingual zero-shot (Exp. 2) |
| Single legal domain, no OOD test | insurance <-> tenancy transfer (Exp. 3a) |
| Sentence-level only | sentence-only vs. contextual input (Exp. 3b) |
| Score only, no explanation | multi-task heads + Integrated Gradients + rule evidence (Exp. 5) |
| Single simplification system, no fine-grained robustness test | controlled legal-edit suite (Exp. 5a), multi-LLM data generation (Sec. 3) |

**Before running:** `Runtime -> Change runtime type -> T4 GPU`, then `Runtime -> Run all`.

**Datasets** (choose in Section 4):

| `DATASET` | What it is | Labels |
|---|---|---|
| `"frjudge"` | FrJUDGE, the paper's 297 French insurance pairs, official split | human (5 law students) |
| `"frjudge_xling"` | FrJUDGE + NLLB-200 translations into English and Hindi (891 pairs) | French human labels *projected* through translation |
| `"silver"` | 24 parallel en/hi insurance + tenancy clauses x 9 legal perturbations | rule-generated (pipeline demo) |
| `HUMAN_CSV` | your team's annotated English/Hindi pairs (Section 5) | human (our annotators) |

The silver set is always added to *training* (it is the only data with legal error-type labels)."""))

cells.append(M("## 1. Setup"))
cells.append(C("""!pip -q install sentence-transformers sacrebleu krippendorff tabulate gradio
import torch, transformers
print("torch", torch.__version__, "| transformers", transformers.__version__)
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE - switch the runtime to T4 GPU")"""))

cells.append(M("""## 2. Project code
Each cell below writes one module of the `lmp` package (identical to the GitHub repo).
If you already pushed the repo, you can instead run `!git clone https://github.com/<you>/judgebert-lmp && %cd judgebert-lmp` and skip these cells."""))
cells.append(C("import os\nos.makedirs('lmp', exist_ok=True)\nos.makedirs('data', exist_ok=True)"))
for mod in MODULES:
    with open(os.path.join(ROOT, "lmp", mod), encoding="utf-8") as f:
        src = f.read()
    cells.append(C(f"%%writefile lmp/{mod}\n{src}"))

cells.append(M("## 3. Look at the data\nParallel English-Hindi seed clauses and the controlled legal perturbations used for silver data, augmentation and robustness tests."))
cells.append(C("""import pandas as pd
pd.set_option('display.max_colwidth', 160)
from lmp.seed_data import seed_rows
from lmp.perturb import build_silver_dataset, PERTURBATIONS

seeds = pd.DataFrame(seed_rows())
seeds[['source_id','concept_id','lang','domain','context','original']].to_csv('data/sources_seed.csv', index=False, encoding='utf-8-sig')
silver = build_silver_dataset()
print(len(seeds), "clauses |", len(silver), "silver pairs")
display(silver.groupby(['lang','domain']).size().unstack())
display(silver.sample(6, random_state=1)[['lang','perturbation','simplified','lmp','errors']])"""))
cells.append(C("""# Try the perturbations on any sentence
s, lang, dom = "The tenant must pay the monthly rent of Rs. 25,000 by the 5th of every month.", "en", "tenancy"
for name, (fn, etype, sev) in PERTURBATIONS.items():
    print(f"{name:16s} -> {fn(s, lang, dom)}")"""))

cells.append(M("""## 4. Configuration
* `DATASET`: `"frjudge_xling"` (default), `"frjudge"` or `"silver"` - see the table at the top.
* `HUMAN_CSV`: path to your team's annotated file (overrides `DATASET`). Upload it with the folder icon on the left.
* `MODEL_NAME`: `xlm-roberta-base` (default), `google/muril-base-cased` (Indian languages), `xlm-roberta-large` (A100).
* `FAST_MODE`: 1 seed / 15 epochs (roughly 35-45 min on a T4 for `frjudge_xling`). Off = 3 seeds, mean ± std as in JUDGEBERT."""))
cells.append(C("""from lmp.config import Config

DATASET    = "frjudge_xling"   # "frjudge" | "frjudge_xling" | "silver"
HUMAN_CSV  = None              # e.g. "data/annotated_pairs.csv"
MODEL_NAME = "xlm-roberta-base"
FAST_MODE  = True

cfg = Config(model_name=MODEL_NAME, output_dir="outputs")
if FAST_MODE:
    cfg.seeds, cfg.epochs = [42], 15
cfg"""))

cells.append(M("""## 4b. Load FrJUDGE (+ translate to English and Hindi)
Clones the authors' repository (data licence CC-BY-NC-SA 4.0) and, for `frjudge_xling`, translates every
original and simplification with NLLB-200 (cached in `data/frjudge_en.csv` and `data/frjudge_hi.csv`; ~3-5 min, once)."""))
cells.append(C("""from lmp.frjudge import frjudge_dataset
from lmp.data import krippendorff_alpha

if HUMAN_CSV is None and DATASET != "silver":
    data_df = frjudge_dataset(DATASET)
    fr = data_df[data_df.lang == "fr"]
    ann = [c for c in fr.columns if c.startswith("annotator_")]
    print("FrJUDGE pairs:", len(fr), "| official split:", fr.split.value_counts().to_dict())
    print("Krippendorff alpha (interval) between the 5 annotators:", round(krippendorff_alpha(fr, ann), 3))
    print("Per-annotator mean LMP:", fr[ann].mean().round(2).to_dict())
    display(data_df.groupby(["lang", "split"]).size().unstack())
    if DATASET == "frjudge_xling":
        display(data_df[data_df.concept_id == "FR010"][["lang", "original", "simplified", "lmp"]])  # one pair in fr/en/hi
else:
    data_df = None"""))

cells.append(M("""## 5. (Optional) Build your own dataset with open LLMs
1. Put your real clauses in a CSV with columns `source_id, lang, domain, context, original`
   (start from `data/sources_seed.csv`; add clauses from real Indian insurance policy wordings and rent agreements).
2. Generate simplifications with two or more open LLMs (more realistic errors than one system).
3. Download the annotation sheet, rate it following `ANNOTATION_GUIDE.md` (e.g. in Google Sheets), upload, and set `HUMAN_CSV`."""))
cells.append(C("""RUN_GENERATION = False   # set True to generate (about 5-10 min for 100 clauses x 2 models on a T4)
if RUN_GENERATION:
    from lmp.generate import generate_pairs, make_annotation_sheet
    sources = pd.read_csv("data/sources_seed.csv")
    pairs = generate_pairs(sources, systems=["Qwen/Qwen2.5-1.5B-Instruct", "Qwen/Qwen2.5-3B-Instruct"])
    sheet = make_annotation_sheet(pairs, "data/to_annotate.csv", n_annotators=3)
    display(sheet.head())
    from google.colab import files; files.download("data/to_annotate.csv")"""))

cells.append(M("""### 5b. Annotation sheet of translated FrJUDGE pairs (our human-annotated English/Hindi set)
All 90 official-test pairs in English and in Hindi (180 pairs). Our annotators re-score them
(the French label is in the column `projected_lmp` - hide it in Google Sheets). This gives our human EN/HI labels
**and** measures whether legal-meaning judgments survive translation (projected vs. re-scored agreement)."""))
cells.append(C("""if data_df is not None and DATASET == "frjudge_xling":
    from lmp.frjudge import make_verification_sheet
    sheet = make_verification_sheet(data_df, "data/to_annotate_translated.csv", n_per_lang=90)
    display(sheet.head())
    # from google.colab import files; files.download("data/to_annotate_translated.csv")"""))

cells.append(M("## 6. Load data and split (official FrJUDGE split / grouped by clause - no leakage)"))
cells.append(C("""from lmp.experiments import Runner
if HUMAN_CSV:
    runner = Runner(cfg, human_csv=HUMAN_CSV, data_name="our human-annotated EN/HI pairs")
elif data_df is not None:
    runner = Runner(cfg, df=data_df, data_name={"frjudge": "FrJUDGE (human, French)",
                    "frjudge_xling": "FrJUDGE + NLLB English/Hindi (projected labels)"}[DATASET])
else:
    runner = Runner(cfg)"""))

cells.append(M("## 7. Experiment 1 - generic semantic similarity vs. LMP model\nTrains the multi-task model (score + decision + error types, asymmetric loss) and runs TF-IDF, chrF, BLEU, BERTScore, SBERT-Multi and LaBSE."))
cells.append(C("""exp1 = runner.exp1_baselines_vs_model()
from IPython.display import Image, display
display(exp1)
display(Image("outputs/fig_scatter.png"))"""))

cells.append(M("## 8. Experiment 2 - per-language results and cross-lingual zero-shot transfer (fr->en, fr->hi, en<->hi)"))
cells.append(C("exp2 = runner.exp2_languages()\ndisplay(exp2)"))

cells.append(M("## 9. Experiment 3 - new legal domain and contextual input"))
cells.append(C("exp3_domain, exp3_context = runner.exp3_domain_and_context()\ndisplay(exp3_domain)\nif exp3_context is not None: display(exp3_context)"))

cells.append(M("## 10. Experiment 4 - identical / unrelated sanity checks (with vs. without augmentation)"))
cells.append(C("exp4 = runner.exp4_sanity()\ndisplay(exp4)"))

cells.append(M("## 11. Experiment 5 - robustness to single legal edits, error types, qualitative analysis (>= 15 cases)"))
cells.append(C("""exp5_drop, exp5_cases = runner.exp5_robustness_and_errors(n_cases=20)
display(exp5_drop)
display(Image("outputs/fig_robustness.png"))
display(exp5_cases[['pair_id','lang','gold_lmp','model_lmp','chrF','explanation','human_justification']])"""))

cells.append(M("## 12. Full report"))
cells.append(C("""runner.write_report()
from IPython.display import Markdown
display(Markdown(open("outputs/results.md", encoding="utf-8").read()))"""))

cells.append(M("## 13. Use the system on any pair"))
cells.append(C("""from lmp.explain import explain_pair
out = explain_pair(runner.model, runner.tokenizer,
    original="The Insurer shall not be liable for any loss caused by flood, unless the Flood Extension has been purchased.",
    simplified="The insurer will not pay for flood damage.",
    lang="en", cfg=cfg)
print(out["explanation"])
{k: out[k] for k in ["lmp_score", "decision", "error_types", "rule_error_types"]}"""))
cells.append(C("""# Interactive demo for the presentation (public link valid for 72 h)
from lmp.demo import launch_demo
launch_demo(runner.model, runner.tokenizer, cfg)"""))

cells.append(M("## 14. Save results"))
cells.append(C("""!zip -qr outputs.zip outputs -x "outputs/lmp_model/*"
from google.colab import files
files.download("outputs.zip")
# To keep the trained model too:  from google.colab import drive; drive.mount('/content/drive'); !cp -r outputs /content/drive/MyDrive/lmp_outputs"""))

nb["cells"] = cells
nb["metadata"] = {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
                  "kernelspec": {"name": "python3", "display_name": "Python 3"},
                  "language_info": {"name": "python"}}
out = os.path.join(ROOT, "JUDGEBERT_LMP_Colab.ipynb")
nbf.write(nb, out)
print("wrote", out, "with", len(cells), "cells")
