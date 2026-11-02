"""CPU smoke test: builds a tiny random BERT locally (no downloads) and runs all 5 experiments.

    python tests/smoke_test.py

Numbers produced here are meaningless (random tiny model, 2 epochs); the test only checks that
every stage of the pipeline runs end to end.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, processors, trainers
from transformers import BertConfig, BertModel, PreTrainedTokenizerFast

from lmp.config import Config
from lmp.experiments import Runner
from lmp.perturb import build_silver_dataset


def build_tiny_model(path):
    texts = []
    df = build_silver_dataset()
    texts += df["original"].tolist() + df["simplified"].tolist() + df["context"].tolist()
    tok = Tokenizer(models.WordPiece(unk_token="[UNK]"))
    tok.normalizer = normalizers.NFC()
    tok.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
    tok.train_from_iterator(texts, trainers.WordPieceTrainer(
        vocab_size=2000, special_tokens=["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]))
    tok.post_processor = processors.TemplateProcessing(
        single="[CLS] $A [SEP]", pair="[CLS] $A [SEP] $B:1 [SEP]:1",
        special_tokens=[("[CLS]", tok.token_to_id("[CLS]")), ("[SEP]", tok.token_to_id("[SEP]"))])
    fast = PreTrainedTokenizerFast(tokenizer_object=tok, unk_token="[UNK]", pad_token="[PAD]",
                                   cls_token="[CLS]", sep_token="[SEP]", mask_token="[MASK]")
    fast.save_pretrained(path)
    conf = BertConfig(vocab_size=fast.vocab_size, hidden_size=64, num_hidden_layers=2, num_attention_heads=2,
                      intermediate_size=128, max_position_embeddings=256)
    BertModel(conf).save_pretrained(path)


if __name__ == "__main__":
    tmp = tempfile.mkdtemp()
    model_dir = os.path.join(tmp, "tiny-bert")
    build_tiny_model(model_dir)
    cfg = Config(model_name=model_dir, bertscore_model=model_dir, bertscore_layer=2, epochs=2, batch_size=16,
                 seeds=[42, 43], max_len=128, patience=2, lr=5e-4, output_dir=os.path.join(tmp, "outputs"),
                 sbert_models=["not-available/sbert"])
    runner = Runner(cfg)
    runner.run_all()
    print("\nOutputs:", sorted(os.listdir(cfg.output_dir)))
    print("SMOKE TEST PASSED")
