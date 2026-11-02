"""CPU test of the FrJUDGE path (official split + projected translations) with a tiny local model.

    python tests/frjudge_test.py /path/to/JUDGEBERT/datastore
A fake translator is used (no downloads); on Colab the real NLLB-200 model is used.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smoke_test import build_tiny_model
from lmp.config import Config
from lmp.experiments import Runner
from lmp.frjudge import frjudge_dataset, make_verification_sheet


def fake_translator(texts, src, tgt):
    return [f"[{tgt}] {t}" for t in texts]


if __name__ == "__main__":
    datastore = sys.argv[1]
    tmp = tempfile.mkdtemp()
    model_dir = os.path.join(tmp, "tiny")
    build_tiny_model(model_dir)
    df = frjudge_dataset("frjudge_xling", datastore=datastore, cache_dir=tmp, translator=fake_translator)
    print(df.groupby(["lang", "split"]).size().unstack())
    sheet = make_verification_sheet(df, os.path.join(tmp, "verify.csv"), n_per_lang=90)
    print(sheet[["lang", "projected_lmp"]].groupby("lang").describe().round(2))
    cfg = Config(model_name=model_dir, bertscore_model=model_dir, bertscore_layer=2, epochs=2, seeds=[42],
                 max_len=128, output_dir=os.path.join(tmp, "out"), sbert_models=[])
    r = Runner(cfg, df=df, data_name="FrJUDGE + NLLB EN/HI (projected)")
    r.run_all()
    print(open(os.path.join(cfg.output_dir, "results.md")).read()[:300])
    print("FRJUDGE TEST PASSED")
