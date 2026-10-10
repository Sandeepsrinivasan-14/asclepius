"""Clinical note coder: negation-aware, hedge-aware term spotting with confidence scores and a human review queue."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from . import terminology as T

NEG_CUES = ["no evidence of", "negative for", "free of", "absence of", "denies", "denied", "without", "ruled out", "no", "not", "nil", "never"]
NEG_STOP = ["but", "however", "although", "except", "apart from", "though"]
HEDGES = ["?", "possible", "probable", "suspected", "likely", "query", "rule out", "r/o", "cannot exclude", "consider", "features of", "?"]
LIST_BREAK = re.compile(r"\b(?:on examination|impression|allergies|current medication|past history)\b", re.I)
ABBREV_MAX = 3
REVIEW_THRESHOLD = 0.80


def _sentences(text: str) -> list[tuple[int, str]]:
    out, pos = [], 0
    for part in re.split(r"(?<=[.;])\s+|\n+", text):
        if not part.strip():
            pos += len(part) + 1
            continue
        start = text.find(part, pos)
        out.append((start, part))
        pos = start + len(part)
    return out


def _vocab() -> list[dict[str, Any]]:
    items = []
    for key, c in T.CONDITIONS.items():
        for syn in sorted(set(c["synonyms"] + [c["display"].lower()]), key=len, reverse=True):
            items.append({"kind": "condition", "key": key, "syn": syn.lower(), "display": c["display"], "codes": {"ICD-10": c["icd10"], "SNOMED CT": c["snomed"]}})
    for key, s in T.SYMPTOMS.items():
        for syn in s["synonyms"]:
            items.append({"kind": "symptom", "key": key, "syn": syn.lower(), "display": s["display"], "codes": {"SNOMED CT": s["snomed"]} if s.get("snomed") else {}})
    for key, m in T.MEDS.items():
        for syn in [m["display"].split(" (")[0].lower(), *m["brands"]]:
            items.append({"kind": "medication", "key": key, "syn": syn.lower(), "display": m["display"], "codes": {"RxNorm": m["rxnorm"]}})
    items.sort(key=lambda i: -len(i["syn"]))
    return items


VOCAB = _vocab()
LAB_PATTERNS = {key: re.compile(r"\b(" + "|".join(re.escape(s) for s in sorted(spec["synonyms"], key=len, reverse=True)) + r")\b\s*(?:of|is|was|:|=)?\s*(\d+(?:\.\d+)?)", re.I)
                for key, spec in T.LABS.items()}


def _negated(sentence: str, start: int) -> bool:
    before = sentence[:start].lower()
    last_cue = -1
    for cue in NEG_CUES:
        for m in re.finditer(r"(?<![a-z])" + re.escape(cue) + r"(?![a-z])", before):
            last_cue = max(last_cue, m.end())
    if last_cue < 0:
        return False
    between = before[last_cue:]
    if any(re.search(r"\b" + s + r"\b", between) for s in NEG_STOP):
        return False
    return not LIST_BREAK.search(between)


def _hedged(sentence: str, start: int) -> bool:
    before = sentence[:start].lower()
    last = -1
    for h in HEDGES:
        idx = before.rfind(h)
        if idx >= 0:
            last = max(last, idx + len(h))
    if last < 0:
        return False
    between = before[last:]
    return not re.search(r"[,;:]|\band\b|\bbut\b", between)


def analyze(text: str) -> dict[str, Any]:
    mentions: list[dict[str, Any]] = []
    for s_start, sent in _sentences(text):
        low = sent.lower()
        taken: list[tuple[int, int]] = []

        def free(a: int, b: int) -> bool:
            return all(b <= x or a >= y for x, y in taken)

        for item in VOCAB:
            syn = item["syn"]
            for m in re.finditer(r"(?<![a-z0-9])" + re.escape(syn) + r"(?![a-z0-9])", low):
                a, b = m.span()
                if not free(a, b):
                    continue
                if len(syn) <= ABBREV_MAX and item["kind"] == "condition":
                    if sent[a:b].upper() != sent[a:b]:
                        continue
                    base, match = 0.82, "abbreviation"
                else:
                    base, match = 0.96, "exact"
                taken.append((a, b))
                neg = _negated(sent, a) and item["kind"] != "medication"
                hedge = _hedged(sent, a) and not neg
                conf = base * (0.7 if hedge else 1.0)
                mentions.append({"text": sent[a:b], "offset": s_start + a, "kind": item["kind"], "key": item["key"], "display": item["display"], "codes": item["codes"],
                                 "assertion": "absent" if neg else "possible" if hedge else "present", "confidence": round(conf, 2), "match": match, "sentence": sent.strip()})
        # fuzzy: unmatched alphabetic tokens vs condition/symptom synonyms
        tokens = [(m.group(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z][A-Za-z\-]{5,}", sent)]
        for tok, a, b in tokens:
            if not free(a, b):
                continue
            best, best_r = None, 0.0
            for item in VOCAB:
                if item["kind"] == "medication" or " " in item["syn"] or len(item["syn"]) < 6:
                    continue
                r = SequenceMatcher(None, tok.lower(), item["syn"]).ratio()
                if r > best_r:
                    best, best_r = item, r
            if best and 0.82 <= best_r < 1.0:
                taken.append((a, b))
                neg = _negated(sent, a)
                hedge = _hedged(sent, a) and not neg
                conf = (0.45 + 0.45 * (best_r - 0.82) / 0.18) * (0.8 if hedge else 1.0)
                mentions.append({"text": tok, "offset": s_start + a, "kind": best["kind"], "key": best["key"], "display": best["display"], "codes": best["codes"],
                                 "assertion": "absent" if neg else "possible" if hedge else "present", "confidence": round(conf, 2), "match": "fuzzy", "sentence": sent.strip()})
    # labs with values
    labs = []
    for key, pat in LAB_PATTERNS.items():
        for m in pat.finditer(text):
            labs.append({"key": key, "text": m.group(0), "value": float(m.group(2)), "unit": T.LABS[key]["unit"], "loinc": T.LABS[key]["loinc"], "display": T.LABS[key]["display"], "confidence": 0.93})
    mentions.sort(key=lambda m: m["offset"])
    for m in mentions:
        m["needs_review"] = m["confidence"] < REVIEW_THRESHOLD or m["assertion"] == "possible" or m["match"] == "fuzzy"
    # aggregate suggested codes (conditions only)
    best: dict[str, dict[str, Any]] = {}
    for m in mentions:
        if m["kind"] != "condition" or m["assertion"] == "absent":
            continue
        cur = best.get(m["key"])
        if cur is None or m["confidence"] > cur["confidence"]:
            best[m["key"]] = m
    codes = [{"key": k, "display": m["display"], "icd10": T.CONDITIONS[k]["icd10"], "snomed": T.CONDITIONS[k]["snomed"], "confidence": m["confidence"], "status": "provisional" if m["assertion"] == "possible" else "confirmed",
              "auto_accept": not m["needs_review"], "evidence": m["sentence"]} for k, m in best.items()]
    return {"mentions": mentions, "labs": labs, "codes": sorted(codes, key=lambda c: -c["confidence"]),
            "summary": {"mentions": len(mentions), "needs_review": sum(1 for m in mentions if m["needs_review"]), "negated": sum(1 for m in mentions if m["assertion"] == "absent"),
                        "auto_codes": sum(1 for c in codes if c["auto_accept"]), "review_codes": sum(1 for c in codes if not c["auto_accept"])}}


def symptom_findings(text: str) -> dict[str, list[dict[str, Any]]]:
    """Return {'present': {...}, 'absent': {...}} symptom evidence from free text, ignoring the clinician impression."""
    kept = " ".join(s for _, s in _sentences(text) if not s.strip().lower().startswith("impression"))
    res = analyze(kept)
    out: dict[str, dict[str, Any]] = {"present": {}, "absent": {}}
    for m in res["mentions"]:
        if m["kind"] != "symptom" or m["match"] == "fuzzy":
            continue
        if m["assertion"] == "absent":
            out["absent"].setdefault(m["key"], m)
        elif m["assertion"] == "present":
            out["present"].setdefault(m["key"], m)
    if "productive_cough" in out["present"]:
        out["present"].setdefault("cough", out["present"]["productive_cough"])
    return out
