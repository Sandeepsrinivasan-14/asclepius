"""AI governance: model cards, drift (PSI), subgroup fairness, clinician override tracking and verifier statistics."""

from __future__ import annotations

import random
import uuid
from collections import Counter
from typing import Any

import numpy as np

from .db import iso, utcnow
from .warning import FEATURES, LABELS, RiskModel, auc_score

PSI_WATCH, PSI_DRIFT = 0.10, 0.25
OVERRIDE_REASONS = {
    "copilot": ["Clinical context not captured in the chart", "Alternative diagnosis more likely", "Finding already excluded", "Patient preference"],
    "early-warning": ["Known baseline for this patient", "Already escalated", "Sensor or charting artefact", "Palliative plan in place"],
    "coder": ["Wrong assertion (negation missed)", "More specific code needed", "Copied-forward text"],
    "scribe": ["Misheard word", "Wrong speaker attribution", "Plan item not agreed with patient"],
}


def psi(ref: np.ndarray, cur: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index using reference-quantile bins."""
    if len(cur) < 30:
        return float("nan")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(ref, edges)[0] / len(ref)
    c = np.histogram(cur, edges)[0] / len(cur)
    r, c = np.clip(r, 1e-4, None), np.clip(c, 1e-4, None)
    return float(np.sum((c - r) * np.log(c / r)))


def drift_report(model: RiskModel, current: np.ndarray) -> dict[str, Any]:
    rows = []
    for i, f in enumerate(FEATURES):
        if f == "altered":
            r_rate, c_rate = float(model.ref_X[:, i].mean()), float(current[:, i].mean()) if len(current) else float("nan")
            rows.append({"feature": f, "label": LABELS[f], "psi": None, "level": "info", "reference": round(r_rate, 3), "current": round(c_rate, 3), "note": "Binary: compared as a rate."})
            continue
        v = psi(model.ref_X[:, i], current[:, i]) if len(current) else float("nan")
        level = "unknown" if np.isnan(v) else "stable" if v < PSI_WATCH else "watch" if v < PSI_DRIFT else "drift"
        rows.append({"feature": f, "label": LABELS[f], "psi": None if np.isnan(v) else round(v, 3), "level": level, "reference": round(float(model.ref_X[:, i].mean()), 2),
                     "current": round(float(current[:, i].mean()), 2) if len(current) else None})
    worst = max((r for r in rows if r["psi"] is not None), key=lambda r: r["psi"], default=None)
    return {"features": rows, "window_rows": int(len(current)), "thresholds": {"watch": PSI_WATCH, "drift": PSI_DRIFT},
            "summary": {"drifting": sum(r["level"] == "drift" for r in rows), "watch": sum(r["level"] == "watch" for r in rows), "worst": worst["label"] if worst else None},
            "interpretation": "The live inpatient population is sicker than the training cohort, so shifts in vital signs are expected. Drift flags prompt a recalibration review; they do not by themselves mean the model is wrong."}


def fairness_report(model: RiskModel, threshold: float = 0.15) -> dict[str, Any]:
    y, p, age, sex = model.test_y, model.test_p, model.test_X[:, 0], model.test_sex

    def metrics(mask: np.ndarray) -> dict[str, Any]:
        yy, pp = y[mask], p[mask]
        pred = pp >= threshold
        tpr = float(pred[yy == 1].mean()) if (yy == 1).any() else float("nan")
        fpr = float(pred[yy == 0].mean()) if (yy == 0).any() else float("nan")
        return {"n": int(mask.sum()), "prevalence": round(float(yy.mean()), 4), "mean_predicted": round(float(pp.mean()), 4), "auc": round(auc_score(yy, pp), 4),
                "tpr": round(tpr, 3), "fpr": round(fpr, 3), "alert_rate": round(float(pred.mean()), 3)}

    groups = {"Sex": {"Female": sex == 0, "Male": sex == 1},
              "Age band": {"18-39": age < 40, "40-64": (age >= 40) & (age < 65), "65+": age >= 65}}
    out, flags = [], []
    for attr, gm in groups.items():
        rows = {name: metrics(mask) for name, mask in gm.items()}
        aucs = [r["auc"] for r in rows.values()]
        tprs = [r["tpr"] for r in rows.values()]
        gap = round(max(aucs) - min(aucs), 4)
        ratio = round(min(tprs) / max(tprs), 3) if max(tprs) > 0 else None
        flagged = gap > 0.05 or (ratio is not None and ratio < 0.8)
        if flagged:
            flags.append(attr)
        out.append({"attribute": attr, "groups": rows, "auc_gap": gap, "tpr_ratio": ratio, "flagged": flagged})
    return {"threshold": threshold, "attributes": out, "flagged": flags,
            "rule": "Flag when the AUC gap exceeds 0.05 or the lowest sensitivity is under 80% of the highest (four-fifths rule).",
            "caveat": "The synthetic outcome formula contains no group effects, so parity is expected here. The monitor exists to catch real disparities once real data is used."}


class Feedback:
    """Records what clinicians do with AI suggestions."""

    def __init__(self, seed: int = 3) -> None:
        self.rows: list[dict[str, Any]] = []
        rng = random.Random(seed)
        mix = {"copilot": (.62, .25, .13), "early-warning": (.71, .17, .12), "coder": (.78, .15, .07), "scribe": (.58, .30, .12)}
        for model, probs in mix.items():
            for _ in range(rng.randint(26, 40)):
                action = rng.choices(["accepted", "modified", "rejected"], probs)[0]
                self.rows.append({"id": str(uuid.uuid4())[:8], "ts": iso(utcnow()), "user": rng.choice(["dr.rao", "dr.chandran", "dr.fernandes", "nurse.devi", "nurse.meena"]), "model": model,
                                  "patient": None, "action": action, "reason": rng.choice(OVERRIDE_REASONS[model]) if action != "accepted" else None, "simulated": True})

    def add(self, *, user: str, model: str, patient: str | None, action: str, reason: str | None) -> dict[str, Any]:
        if action not in ("accepted", "modified", "rejected"):
            raise ValueError("action must be accepted, modified or rejected")
        row = {"id": str(uuid.uuid4())[:8], "ts": iso(utcnow()), "user": user, "model": model, "patient": patient, "action": action, "reason": reason, "simulated": False}
        self.rows.append(row)
        return row

    def stats(self) -> dict[str, Any]:
        by_model: dict[str, Any] = {}
        for model in sorted({r["model"] for r in self.rows}):
            rows = [r for r in self.rows if r["model"] == model]
            c = Counter(r["action"] for r in rows)
            reasons = Counter(r["reason"] for r in rows if r["reason"])
            by_model[model] = {"total": len(rows), "accepted": c["accepted"], "modified": c["modified"], "rejected": c["rejected"],
                               "override_rate": round((c["modified"] + c["rejected"]) / len(rows), 3), "top_reasons": [{"reason": k, "count": v} for k, v in reasons.most_common(3)],
                               "live_events": sum(1 for r in rows if not r["simulated"])}
        return {"models": by_model, "recent": sorted(self.rows, key=lambda r: r["ts"], reverse=True)[:12],
                "note": "Rows marked simulated seed the dashboard for demonstration; live clinician feedback is appended in real time."}


def model_cards(model: RiskModel, copilot_eval: dict[str, Any], coder_eval: dict[str, Any]) -> list[dict[str, Any]]:
    common_limits = "Built and tested only on synthetic data. Not a medical device. Not validated for any clinical use."
    return [
        {"id": "copilot-kb", "name": "Differential copilot", "version": "1.0", "kind": "Transparent likelihood-ratio model + verifier", "status": "monitoring",
         "intended_use": "Show clinicians a ranked list of candidate conditions with chart citations, to prompt consideration and next tests.",
         "out_of_scope": ["Autonomous diagnosis", "Treatment or dosing decisions", "Paediatric or obstetric care"],
         "data": "Hand-written teaching knowledge base (15 conditions). Evaluated on a synthetic cohort generated from similar assumptions, so results are optimistic.",
         "metrics": {"Top-1 concordance (synthetic)": copilot_eval["top1"], "Top-3 concordance (synthetic)": copilot_eval["top3"], "Cases evaluated": copilot_eval["n"], "Narratives blocked by verifier": copilot_eval["blocked"]},
         "limitations": [common_limits, "Findings are treated as independent, so ratios are damped.", "Ignores the clinician impression by design to avoid anchoring."],
         "oversight": "Every suggestion is cited and verified; clinicians accept, modify or reject and the override is logged."},
        {"id": "ew-news2", "name": "NEWS2 early-warning score", "version": "RCP 2017", "kind": "Published rule", "status": "monitoring",
         "intended_use": "Standardised bedside score that triggers a graded clinical response.", "out_of_scope": ["Children", "Pregnancy"],
         "data": "Rule published by the Royal College of Physicians; implemented exactly, SpO2 Scale 2 applied when COPD is on the problem list.",
         "metrics": {"Parameters": 7, "Unit tests on published bands": "passing"}, "limitations": [common_limits, "Scale 2 is selected from the problem list; a clinician should confirm it."],
         "oversight": "Escalation remains a nursing and medical decision."},
        {"id": "ew-ml", "name": "24-hour deterioration risk", "version": "1.0", "kind": "L2 logistic regression", "status": "monitoring",
         "intended_use": "Second opinion alongside NEWS2 with exact per-feature explanations.", "out_of_scope": ["Replacing NEWS2", "Triage of real patients"],
         "data": f"Synthetic cohort ({model.metrics['n_train']} train / {model.metrics['n_test']} test) whose outcome is generated from a documented formula.",
         "metrics": {"AUC": model.metrics["auc"], "AUC (NEWS2-like rule)": model.metrics["auc_news2_like_rule"], "Brier": model.metrics["brier"], "Calibration error (ECE)": model.metrics["ece"], "Prevalence": model.metrics["prevalence"]},
         "limitations": [common_limits, "Discrimination reflects the synthetic generator, not real patients."], "oversight": "Shown with its explanation; never auto-escalates."},
        {"id": "coder", "name": "Clinical note coder", "version": "1.0", "kind": "Rule-based NLP (negation, hedging, fuzzy match)", "status": "monitoring",
         "intended_use": "Suggest ICD-10 and SNOMED CT codes with confidence; low-confidence items go to a human reviewer.", "out_of_scope": ["Billing without review"],
         "data": "Embedded vocabulary subset (19 conditions, 31 symptoms, 18 labs, 35 drugs).", "metrics": {"Mentions on test notes": coder_eval["mentions"], "Auto-accepted": coder_eval["auto"], "Sent to review": coder_eval["review"]},
         "limitations": [common_limits, "Small vocabulary; coverage is not clinical-grade."], "oversight": "Codes below 0.80 confidence, hedged or fuzzy matches require approval."},
        {"id": "scribe", "name": "Ambient scribe", "version": "1.0", "kind": "Rule-based extraction over a transcript", "status": "monitoring",
         "intended_use": "Draft a SOAP note and FHIR resources from a consultation transcript.", "out_of_scope": ["Signing without review"],
         "data": "Works on text transcripts; audio uses an optional local Whisper model if installed.", "metrics": {"Output status": "draft until signed"},
         "limitations": [common_limits, "Speaker labels are required for best results."], "oversight": "Nothing is stored in the chart until a physician signs."},
    ]
