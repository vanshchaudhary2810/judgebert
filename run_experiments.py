"""Command-line entry point (same as the Colab notebook).

    python run_experiments.py                          # silver demo data
    python run_experiments.py --human_csv data/annotated.csv --model google/muril-base-cased
    python run_experiments.py --fast                   # 1 seed, fewer epochs
"""
import argparse

from lmp.config import Config
from lmp.experiments import Runner

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--human_csv", default=None)
    ap.add_argument("--model", default="xlm-roberta-base")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--no_neural_baselines", action="store_true")
    ap.add_argument("--out", default="outputs")
    a = ap.parse_args()
    cfg = Config(model_name=a.model, output_dir=a.out, run_neural_baselines=not a.no_neural_baselines)
    if a.fast:
        cfg.seeds, cfg.epochs = [42], 8
    Runner(cfg, human_csv=a.human_csv).run_all()
