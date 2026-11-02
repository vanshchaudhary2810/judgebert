"""Rule-based legal change detector (English + Hindi).

Compares the *legal signature* of the original and the simplified text:
modality (obligation / permission / prohibition), negation, exceptions, conditions,
quantifiers (scope), numbers/dates and legal parties (entities).

It is used for
  * human-readable evidence in the explanation of each prediction, and
  * a transparent rule baseline for the legal-error-type classification (Exp. 5).
"""
import re
from collections import Counter
from typing import Dict, List

LEX = {
    "en": {
        "obligation": [r"\bshall\b(?! not)", r"\bmust\b(?! not)", r"\brequired to\b", r"\bhas to\b", r"\bhave to\b",
                       r"\bliable to\b", r"\bresponsible for\b", r"\bbound to\b", r"\bwill\b(?! not)"],
        "permission": [r"\bmay\b(?! not)", r"\bcan\b", r"\bentitled to\b", r"\ballowed to\b(?<!not allowed to)"],
        "negation": [r"(?<!if )(?<!does )\bnot\b(?! less than)", r"\bno\b(?! later| less)", r"\bnever\b", r"\bcannot\b", r"\bnothing\b"],
        "exception": [r"\bunless\b", r"\bexcept\b", r"\bprovided\b", r"\bsave\b", r"\bsubject to\b",
                      r"\bwithout\b", r"\bother than\b", r"\bfailing which\b", r"\bfailure to\b", r"\botherwise\b",
                      r"\bif (?:he |she |they |it |you )?(?:does |do )?not\b"],
        "condition": [r"\bif\b", r"\bwhere\b", r"\bin the event\b", r"\bin case\b", r"\bwhen\b"],
        "scope": [r"\bany\b", r"\ball\b", r"\beach\b", r"\bevery\b", r"\bonly\b", r"\bsolely\b", r"\bfull\b",
                  r"\bin full\b", r"\beither\b", r"\bsome\b", r"\bpartial\b", r"\bpart of\b", r"\bfirst\b"],
        "entity": {"insured": r"\binsured\b(?! property| vehicle)|\bpolicyholder\b",
                   "insurer": r"\binsurer\b|\binsurance company\b",
                   "tenant": r"\btenant\b", "landlord": r"\blandlord\b", "police": r"\bpolice\b"},
    },
    "hi": {
        "obligation": [r"ना होगा", r"नी होगी", r"ने होंगे", r"ना पड़ेगा", r"नी पड़ेगी", r"ने पड़ेंगे",
                       r"करेगा", r"करेगी", r"देगा", r"उत्तरदायी", r"दायी", r"बाध्य", r"अनिवार्य", r"जाएगा", r"जाएगी"],
        "permission": [r"सकता", r"सकती", r"सकते", r"हकदार", r"अनुमति"],
        "negation": [r"नहीं", r"(?<!\S)न ही(?!\S)"],
        "exception": [r"सिवाय", r"बशर्ते", r"जब तक कि", r"के बिना", r"अन्यथा", r"न करने पर"],
        "condition": [r"यदि", r"अगर", r"की स्थिति में", r"होने पर", r"जहाँ", r"(?<!\S)तो(?!\S)", r"हों तो"],
        "scope": [r"किसी भी", r"कोई भी", r"सभी", r"प्रत्येक", r"(?<!\S)हर(?!\S)", r"केवल", r"पूरा", r"पूर्ण",
                  r"(?<!\S)कुछ(?!\S)", r"आंशिक"],
        "entity": {"insured": r"बीमाधारक|पॉलिसीधारक", "insurer": r"बीमाकर्ता", "tenant": r"किरायेदार(?!ी)",
                   "landlord": r"मकान-मालिक", "police": r"पुलिस"},
    },
}

NUM_WORDS = {
    "en": {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eleven": 11, "twelve": 12,
           "fifteen": 15, "thirty": 30, "double": "x2", "twice": "x2", "half": "x0.5"},
    "hi": {"एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "छह": 6, "ग्यारह": 11, "बारह": 12,
           "दोगुना": "x2", "दोगुने": "x2", "आधा": "x0.5", "आधे": "x0.5"},
}


def _count(text: str, pats: List[str]) -> int:
    return sum(len(re.findall(p, text, flags=re.I)) for p in pats)


def _numbers(text: str, lang: str) -> Counter:
    nums = [re.sub(r",", "", m) for m in re.findall(r"\d[\d,]*\d|\d", text)]
    words = NUM_WORDS[lang]
    for w, v in words.items():
        pat = rf"\b{w}\b" if lang == "en" else rf"(?<!\S){w}(?!\S)"
        nums += [str(v)] * len(re.findall(pat, text, flags=re.I if lang == "en" else 0))
    return Counter(nums)


def _scope_words(text: str, lang: str) -> Counter:
    out = Counter()
    for p in LEX[lang]["scope"]:
        for m in re.findall(p, text, flags=re.I):
            out[m.lower().strip()] += 1
    # normalise near-synonyms so original vs plain-language wording is not flagged
    norm = {"solely": "only", "in full": "full", "पूर्ण": "पूरा", "प्रत्येक": "हर", "किसी भी": "any", "कोई भी": "any",
            "each": "every"}
    return Counter({norm.get(k, k): v for k, v in out.items()})


def _entities(text: str, lang: str) -> List[str]:
    hits = []
    for name, pat in LEX[lang]["entity"].items():
        for m in re.finditer(pat, text, flags=re.I):
            hits.append((m.start(), name))
    return [n for _, n in sorted(hits)]


def signature(text: str, lang: str) -> Dict:
    L = LEX[lang]
    return {
        "obligation": _count(text, L["obligation"]),
        "permission": _count(text, L["permission"]),
        "negation": _count(text, L["negation"]),
        "exception": _count(text, L["exception"]),
        "condition": _count(text, L["condition"]),
        "numbers": _numbers(text, lang),
        "scope": _scope_words(text, lang),
        "entities": _entities(text, lang),
        "n_tokens": len(text.split()),
        "n_sents": max(1, len(re.findall(r"(?<!Rs)[.!?।](?:\s|$)", text))),
    }


def legal_diff(original: str, simplified: str, lang: str) -> Dict:
    """Return detected legal changes as {'findings': [...], 'error_types': set(...)}."""
    if lang not in LEX:            # rules exist for English and Hindi only
        return {"findings": [], "error_types": set(), "orig_sig": {}, "simp_sig": {}}
    a, b = signature(original, lang), signature(simplified, lang)
    findings, types = [], set()

    # numbers / dates
    missing = a["numbers"] - b["numbers"]
    added = b["numbers"] - a["numbers"]
    if missing or added:
        types.add("number_date")
        findings.append(f"Numbers/dates differ: original has {sorted(missing.elements()) or '-'}, "
                        f"simplified has {sorted(added.elements()) or '-'}.")

    # negation polarity
    if (a["negation"] % 2) != (b["negation"] % 2) or (a["negation"] > 0) != (b["negation"] > 0):
        types.add("contradiction")
        findings.append(f"Negation polarity changed ({a['negation']} negation(s) in original vs {b['negation']} in simplified).")

    # modality
    if a["obligation"] > 0 and b["obligation"] == 0 and b["permission"] > 0:
        types.add("obligation_permission")
        findings.append("An obligation (shall/must) became a permission (may/can).")
    elif a["obligation"] == 0 and a["permission"] > 0 and b["obligation"] > 0 and b["permission"] == 0:
        types.add("obligation_permission")
        findings.append("A permission (may/can) became an obligation (shall/must).")
    elif b["permission"] > a["permission"] and b["obligation"] < a["obligation"]:
        types.add("obligation_permission")
        findings.append("Modality shifted from obligation towards permission.")

    if a["exception"] > 0 and b["exception"] == 0:
        types.add("exception")
        findings.append("An exception/proviso (unless, provided that, without ...) was dropped.")
    if a["condition"] > 0 and b["condition"] == 0:
        types.add("condition")
        findings.append("A condition (if, where, in the event of ...) was dropped.")

    # scope: flag a universal quantifier replaced by a restrictive one, or an added/removed "only"
    sa, sb = a["scope"], b["scope"]
    universal = {"any", "all", "every", "full", "either", "हर", "सभी", "पूरा"}
    restrictive = {"some", "partial", "part of", "first", "कुछ", "आंशिक"}
    lost, gained = set(sa) - set(sb), set(sb) - set(sa)
    only_changed = ({"only", "केवल"} & (lost | gained))
    if (lost & universal and gained & restrictive) or only_changed:
        types.add("scope")
        findings.append(f"Scope changed: lost {sorted(lost) or '-'}, gained {sorted(gained) or '-'}.")

    # entities / party roles: same parties, but a different party is mentioned first (role swap)
    ea, eb = a["entities"], b["entities"]
    if lang == "en" and ea and eb and set(ea) == set(eb) and len(set(ea)) > 1 and ea[0] != eb[0]:
        types.add("entity")
        findings.append(f"Party roles may be swapped: {ea} -> {eb}.")

    # length-based omission / hallucination hints
    ratio = b["n_tokens"] / max(a["n_tokens"], 1)
    if ratio < 0.45:
        types.add("omission")
        findings.append(f"Simplified text is much shorter ({ratio:.0%} of the original length).")
    elif ratio > 1.6 or b["n_sents"] >= a["n_sents"] + 2:
        types.add("hallucination")
        findings.append(f"Simplified text is much longer ({ratio:.0%} of the original length) - possible added content.")

    return {"findings": findings, "error_types": types, "orig_sig": a, "simp_sig": b}
