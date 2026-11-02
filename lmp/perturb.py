"""Controlled legal perturbations (English + Hindi) and silver-label generation.

Each perturbation takes a faithful simplification and introduces exactly one legally
meaningful change (obligation -> permission, dropped exception, changed number, ...).
They serve three purposes:
  1. silver training/augmentation data (`build_silver_dataset`)
  2. the robustness test suite for Experiment 5 (`perturbation_suite`)
  3. identical / unrelated sanity pairs for Experiment 4 (`build_sanity_pairs`)
"""
import random
import re
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .seed_data import seed_rows

# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------

def _earliest(text: str, rules: List[Tuple[str, str]], flags=0):
    """Apply the rule whose match starts earliest (longest match wins ties). Returns new text or None."""
    best = None
    for pat, rep in rules:
        m = re.search(pat, text, flags)
        if m and (best is None or (m.start(), -len(m.group(0))) < (best[0].start(), -len(best[0].group(0)))):
            best = (m, pat, rep)
    if best is None:
        return None
    m, pat, rep = best
    return text[: m.start()] + m.expand(rep) + text[m.end():]


def _tidy(text: str, lang: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.।])", r"\1", text)
    text = re.sub(r",\s*([.।])", r"\1", text)
    text = re.sub(r"([.।])\s*([.।])", r"\1", text)
    if lang == "en":
        # capitalise sentence starts
        text = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
        if not text.endswith((".", "!", "?")):
            text += "."
    else:
        if not text.endswith("।"):
            text += "।"
    return text


def _match_case(src: str, rep: str) -> str:
    return rep[:1].upper() + rep[1:] if src[:1].isupper() and rep else rep


def _split_sentences(text: str, lang: str) -> List[str]:
    if lang == "en":
        return [s for s in re.split(r"(?<!Rs\.)(?<=[.!?])\s+", text.strip()) if s]
    return [s.strip() + "।" for s in text.strip().split("।") if s.strip()]


# --------------------------------------------------------------------------------------
# perturbations: f(text, lang, domain, rng) -> Optional[str]
# --------------------------------------------------------------------------------------

def obligation_flip(text, lang, domain=None, rng=None):
    """must/shall <-> may/can  |  ना होगा <-> सकता है"""
    if lang == "en":
        rules = [
            (r"\bmust not\b", "may"), (r"\bshall not\b", "may"),
            (r"\bmust\b", "may"), (r"\bshall\b", "may"), (r"\bhas to\b", "may"),
            (r"\bmay\b", "must"), (r"\bcan\b", "must"),
        ]
    else:
        rules = [
            (r"(\S+?)ना होगा", r"\1 सकता है"), (r"(\S+?)नी होगी", r"\1 सकती है"),
            (r"(\S+?)ने होंगे", r"\1 सकता है"), (r"(\S+?)ना पड़ेगा", r"\1 सकता है"),
            (r"(\S+) सकता है", r"\1ना होगा"), (r"(\S+) सकती है", r"\1नी होगी"),
        ]
    out = _earliest(text, rules)
    return _tidy(out, lang) if out else None


def negation_flip(text, lang, domain=None, rng=None):
    """Remove the first negation, or insert one if there is none -> contradiction."""
    if lang == "en":
        if re.search(r"(?<!If )\bnot\b", text):
            out = re.sub(r"\s*(?<!If )\bnot\b", "", text, count=1)
        else:
            out = _earliest(text, [(r"\b(will|must|may|is|are|shall)\b", r"\1 not"), (r"\bcan\b", "cannot")])
    else:
        if "नहीं" in text:
            out = re.sub(r"नहीं\s*", "", text, count=1)
        else:
            out = _earliest(text, [
                (r"(\S+) (सकता|सकती) है", r"नहीं \1 \2"),
                (r" (होगा|होगी|होंगे|है|जाएगा|जाएगी)(?=[\s,।])", r" नहीं \1"),
            ])
    return _tidy(out, lang) if out and out != text else None


def drop_exception(text, lang, domain=None, rng=None):
    if lang == "en":
        rules = [
            (r",?\s*\bunless\b[^,.;]*", ""), (r",?\s*\bprovided( that)?\b[^,.;]*", ""),
            (r",?\s*\bexcept\b[^,.;]*", ""), (r"\s*\bwithout\b[^,.;]*", ""),
        ]
    else:
        rules = [
            (r",?\s*सिवाय इसके कि[^।]*", ""), (r",?\s*बशर्ते[^।]*", ""),
            (r",?\s*जब तक कि[^।]*", ""), (r"\S+ की (?:\S+ )?\S+ के बिना ", ""),
        ]
    out = _earliest(text, rules)
    return _tidy(out, lang) if out and out != text else None


def drop_condition(text, lang, domain=None, rng=None):
    if lang == "en":
        rules = [(r"\b(If|When) [^,]*,\s*", ""), (r"\s+\bif\b[^,.]*", "")]
    else:
        rules = [
            (r"(यदि|अगर) [^,]*, तो\s*", ""),
            (r"(?:(?<=^)|(?<=। ))(?:\S+ ){0,3}\S+ हों तो ", ""),
            (r"^[^,।]*? होने पर ", ""),
        ]
    out = _earliest(text, rules)
    return _tidy(out, lang) if out and out != text else None


_EN_NUM_WORDS = {"two": "four", "three": "six", "eleven": "six", "twelve": "six", "double": "half"}
_HI_NUM_WORDS = {"दो": "चार", "तीन": "छह", "ग्यारह": "छह", "बारह": "छह", "दोगुना": "आधा", "दोगुने": "आधे"}


def _indian_format(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def change_number(text, lang, domain=None, rng=None):
    def num_rep(m):
        raw = m.group(0)
        n = int(raw.replace(",", ""))
        new = n + 1 if 1900 <= n <= 2100 else n * 2
        return _indian_format(new) if "," in raw else str(new)

    cands = []
    m = re.search(r"\d[\d,]*\d|\d", text)
    if m:
        cands.append((m.start(), m, None))
    words = _EN_NUM_WORDS if lang == "en" else _HI_NUM_WORDS
    for w, rep in words.items():
        pat = rf"\b{w}\b" if lang == "en" else rf"(?<!\S){w}(?!\S)"
        mw = re.search(pat, text, re.I if lang == "en" else 0)
        if mw:
            cands.append((mw.start(), mw, rep))
    if not cands:
        return None
    _, m, rep = min(cands, key=lambda c: c[0])
    new = num_rep(m) if rep is None else _match_case(m.group(0), rep)
    return _tidy(text[: m.start()] + new + text[m.end():], lang)


def change_scope(text, lang, domain=None, rng=None):
    if lang == "en":
        rules = [
            (r"\b[Aa]ny\b", "some"), (r"\b[Aa]ll\b", "some"), (r"\b[Ff]ull\b", "partial"),
            (r"\b[Ee]ach\b", "the first"), (r"\b[Ee]very\b", "the first"),
            (r"\bonly\s+", ""), (r"\bvehicle\b", "car"), (r"\bEither side\b", "Only the landlord"),
        ]
        m_first = None
        for pat, _ in rules:
            m = re.search(pat, text)
            if m and (m_first is None or m.start() < m_first.start()):
                m_first = m
        out = _earliest(text, rules)
        if out and m_first is not None and m_first.group(0)[:1].isupper():
            out = out[: m_first.start()] + out[m_first.start():][:1].upper() + out[m_first.start() + 1:]
    else:
        rules = [
            ("किसी भी", "कुछ"), ("कोई भी", "कुछ"), ("सभी", "कुछ"), ("पूरा", "आंशिक"),
            ("(?<!\\S)हर ", "केवल पहले "), ("केवल ", ""), ("वाहन", "कार"),
        ]
        out = _earliest(text, rules)
    return _tidy(out, lang) if out and out != text else None


def omission(text, lang, domain=None, rng=None):
    sents = _split_sentences(text, lang)
    if len(sents) >= 2:
        return _tidy(" ".join(sents[:-1]), lang)
    # Otherwise drop the last comma-separated clause (", " so Indian-format numbers survive),
    # but never a clause that is an exception/condition (those have their own perturbations)
    # and never the main clause.
    if ", " in text:
        head, tail = text.rsplit(", ", 1)
        tail_s = tail.strip()
        is_exc = re.match(r"(unless|provided|except|सिवाय|बशर्ते|जब तक|तो )", tail_s)
        if lang == "en":
            head_is_condition = re.match(r"(If|When)\b", head.strip())
            if len(tail_s.split()) >= 3 and not is_exc and not head_is_condition:
                return _tidy(head, lang)
        else:
            tail_has_verb = re.search(r"(होगा|होगी|होंगे|है|सकता|सकती|जाएगा|जाएगी|करेगा)\s*।?$", tail_s)
            if len(tail_s.split()) >= 2 and not is_exc and not tail_has_verb:
                return _tidy(head, lang)
            # drop the middle item of a list "A, B या C"
            out = re.sub(r", (?!तो )([^,]+?) या ", " या ", text, count=1)
            if out != text:
                return _tidy(out, lang)
    return None


_HALLUCINATIONS = {
    ("en", "insurance"): [
        "The insurer will also cover any legal costs connected with the claim.",
        "This cover also applies to damage caused by earthquakes.",
        "The insured can claim this benefit twice a year.",
    ],
    ("en", "tenancy"): [
        "The tenant may also sublet one room without asking the landlord.",
        "The landlord will also pay the tenant's electricity bills.",
        "This rule does not apply during the first three months.",
    ],
    ("hi", "insurance"): [
        "बीमाकर्ता दावे से जुड़े सभी कानूनी खर्च भी उठाएगा।",
        "यह कवर भूकंप से हुए नुकसान पर भी लागू होता है।",
        "बीमाधारक साल में दो बार यह लाभ ले सकता है।",
    ],
    ("hi", "tenancy"): [
        "किरायेदार मकान-मालिक से पूछे बिना एक कमरा किराये पर दे सकता है।",
        "मकान-मालिक किरायेदार का बिजली बिल भी भरेगा।",
        "यह नियम पहले तीन महीनों में लागू नहीं होता।",
    ],
}


def hallucination(text, lang, domain="insurance", rng=None):
    rng = rng or random.Random(0)
    extra = rng.choice(_HALLUCINATIONS[(lang, domain)])
    return _tidy(text + " " + extra, lang)


def entity_swap(text, lang, domain=None, rng=None):
    if lang == "en":
        swap = {"insured": "insurer", "insurer": "insured", "tenant": "landlord",
                "landlord": "tenant", "policyholder": "insurer"}
        out = re.sub(r"\b(the|The) (insured|insurer|tenant|landlord|policyholder)\b",
                     lambda m: f"{m.group(1)} {swap[m.group(2)]}", text)
    else:
        swap = {"बीमाधारक": "बीमाकर्ता", "बीमाकर्ता": "बीमाधारक", "किरायेदार": "मकान-मालिक",
                "मकान-मालिक": "किरायेदार", "पॉलिसीधारक": "बीमाकर्ता"}
        out = re.sub(r"(बीमाधारक|बीमाकर्ता|पॉलिसीधारक|मकान-मालिक|किरायेदार(?!ी))",
                     lambda m: swap[m.group(1)], text)
    return _tidy(out, lang) if out != text else None


def benign_paraphrase(text, lang, domain=None, rng=None):
    """Meaning-preserving rewording (should keep a high LMP)."""
    if lang == "en":
        rules = [(r"\bmust not\b", "is not allowed to"), (r"\bmust\b", "has to"),
                 (r"\bwithin\b", "no later than"), (r"\bwritten notice\b", "notice in writing"),
                 (r"\bat least\b", "not less than"), (r"\bthe insurer\b", "the insurance company")]
    else:
        rules = [(r"ना होगा", "ना पड़ेगा"), (r"नी होगी", "नी पड़ेगी"), (r"ने होंगे", "ने पड़ेंगे"),
                 (r"अंदर", "भीतर"), (r"खत्म", "समाप्त"), (r"नुकसान", "हानि")]
    out = text
    for pat, rep in rules:
        out = re.sub(pat, rep, out)
    return _tidy(out, lang) if out != text else None


# name -> (function, error type, silver severity on the 1-10 scale)
PERTURBATIONS: Dict[str, Tuple[Callable, str, float]] = {
    "negation_flip": (negation_flip, "contradiction", 2.0),
    "entity_swap": (entity_swap, "entity", 2.5),
    "change_number": (change_number, "number_date", 3.5),
    "obligation_flip": (obligation_flip, "obligation_permission", 4.0),
    "drop_exception": (drop_exception, "exception", 4.0),
    "drop_condition": (drop_condition, "condition", 4.5),
    "hallucination": (hallucination, "hallucination", 4.5),
    "change_scope": (change_scope, "scope", 5.0),
    "omission": (omission, "omission", 5.0),
}


# --------------------------------------------------------------------------------------
# dataset builders
# --------------------------------------------------------------------------------------

def _clip(x):
    return float(np.clip(x, 1.0, 10.0))


def build_silver_dataset(seed: int = 13, doubles_per_source: int = 1) -> pd.DataFrame:
    """Faithful + benign + single + double perturbations for every seed clause."""
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    out = []

    def add(row, simp, score, errors, pert):
        out.append({**{k: row[k] for k in ("source_id", "concept_id", "lang", "domain", "context", "original")},
                    "simplified": simp, "lmp": round(_clip(score), 2),
                    "errors": ";".join(errors), "perturbation": pert,
                    "is_sanity": False, "label_source": "silver"})

    for row in seed_rows():
        lang, dom, faithful = row["lang"], row["domain"], row["faithful"]
        add(row, faithful, nrng.normal(9.3, 0.4), [], "faithful")
        b = benign_paraphrase(faithful, lang, dom, rng)
        if b:
            add(row, b, nrng.normal(8.8, 0.5), [], "benign")
        applicable = []
        for name, (fn, etype, sev) in PERTURBATIONS.items():
            p = fn(faithful, lang, dom, rng)
            if p and p != faithful:
                applicable.append(name)
                add(row, p, sev + nrng.normal(0, 0.5), [etype], name)
        for _ in range(doubles_per_source):
            if len(applicable) < 2:
                break
            a, c = rng.sample(applicable, 2)
            fa, ea, sa = PERTURBATIONS[a]
            fc, ec, sc = PERTURBATIONS[c]
            p1 = fa(faithful, lang, dom, rng)
            p2 = fc(p1, lang, dom, rng) if p1 else None
            if p2 and p2 != p1:
                add(row, p2, min(sa, sc) - 1.0 + nrng.normal(0, 0.4), sorted({ea, ec}), f"{a}+{c}")
    df = pd.DataFrame(out)
    df.insert(0, "pair_id", [f"P{i:04d}" for i in range(len(df))])
    return df


def build_sanity_pairs(df: pd.DataFrame, seed: int = 7) -> pd.DataFrame:
    """Identical pairs (expected LMP 10) and unrelated pairs (expected LMP 1).

    Unrelated pairs follow the JUDGEBERT paper: both sides are legal text with a shared
    lexicon (same language, same domain) but describe different clauses.
    """
    rng = random.Random(seed)
    src = df.drop_duplicates("source_id")[["source_id", "concept_id", "lang", "domain", "context", "original"]]
    pool = df[df.perturbation.isin(["faithful"])] if "perturbation" in df else df
    rows = []
    for _, r in src.iterrows():
        rows.append({**r.to_dict(), "simplified": r["original"], "lmp": 10.0, "errors": "",
                     "perturbation": "identical", "is_sanity": True, "label_source": "rule"})
        cands = pool[(pool.lang == r.lang) & (pool.domain == r.domain) & (pool.concept_id != r.concept_id)]
        if len(cands) == 0:
            cands = pool[(pool.lang == r.lang) & (pool.concept_id != r.concept_id)]
        if len(cands):
            other = cands.iloc[rng.randrange(len(cands))]
            rows.append({**r.to_dict(), "simplified": other["simplified"], "lmp": 1.0,
                         "errors": "omission;hallucination", "perturbation": "unrelated",
                         "is_sanity": True, "label_source": "rule"})
    out = pd.DataFrame(rows)
    out.insert(0, "pair_id", [f"S{i:04d}" for i in range(len(out))])
    return out


def perturbation_suite(base: pd.DataFrame) -> pd.DataFrame:
    """For every preserved (faithful) pair in `base`, create one variant per perturbation type.

    Works on human-annotated data too: pass the pairs whose human LMP >= 7.
    """
    rng = random.Random(0)
    rows = []
    for _, r in base.iterrows():
        rows.append({**r.to_dict(), "variant": "faithful"})
        for name, (fn, etype, _) in PERTURBATIONS.items():
            p = fn(r["simplified"], r["lang"], r["domain"], rng)
            if p and p != r["simplified"]:
                rows.append({**r.to_dict(), "simplified": p, "variant": name, "errors": etype})
    return pd.DataFrame(rows)
