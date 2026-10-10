"""Laboratory delta checks and KDIGO acute-kidney-injury staging.

Delta checks flag a result that moved implausibly fast against the previous one (a lab-information-system staple that
catches mislabelled specimens and real deterioration). Pure functions of the chart; thresholds are documented teaching values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .chart import Chart
from .terminology import LABS

# analyte -> (relative change that triggers a flag, absolute change that triggers a flag, window in hours)
DELTA_RULES: dict[str, tuple[float | None, float | None, float]] = {
    "potassium": (None, 1.0, 48), "sodium": (None, 8.0, 24), "hemoglobin": (0.25, 2.0, 72), "platelets": (0.5, None, 72),
    "wbc": (0.6, None, 72), "creatinine": (0.5, 0.3, 48), "glucose": (0.6, None, 24), "lactate": (None, 2.0, 24), "troponin": (1.0, None, 24),
}


def _hours(a: str, b: str) -> float | None:
    try:
        return (datetime.fromisoformat(b.replace("Z", "+00:00")) - datetime.fromisoformat(a.replace("Z", "+00:00"))).total_seconds() / 3600
    except ValueError:
        return None


def delta_checks(chart: Chart) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, (rel, absolute, window) in DELTA_RULES.items():
        series = chart.labs.get(key) or []
        if len(series) < 2:
            continue
        (t0, v0, _), (t1, v1, rid) = series[-2], series[-1]
        gap = _hours(t0, t1)
        if gap is None or gap <= 0 or gap > window:
            continue
        change = v1 - v0
        pct = change / v0 if v0 else None
        reasons = []
        if absolute is not None and abs(change) >= absolute:
            reasons.append(f"absolute change {change:+g} {LABS[key]['unit']}")
        if rel is not None and pct is not None and abs(pct) >= rel:
            reasons.append(f"relative change {pct:+.0%}")
        if reasons:
            out.append({"analyte": key, "display": LABS[key]["display"].split(" [")[0], "unit": LABS[key]["unit"], "previous": v0, "current": v1,
                        "hours_apart": round(gap, 1), "reasons": reasons, "observation": rid,
                        "action": "Confirm patient identity and specimen, repeat if unexpected, correlate clinically."})
    return out


def kdigo_aki(chart: Chart) -> dict[str, Any]:
    """KDIGO creatinine criteria: rise of 0.3 mg/dL within 48 h, or 1.5x or more the baseline within 7 days."""
    series = chart.labs.get("creatinine") or []
    if len(series) < 2:
        return {"stage": 0, "label": "No AKI signal", "basis": "Fewer than two creatinine results."}
    t_now, now, _ = series[-1]
    recent = [(t, v) for t, v, _ in series[:-1] if (h := _hours(t, t_now)) is not None and 0 < h <= 24 * 7]
    if not recent:
        return {"stage": 0, "label": "No AKI signal", "basis": "No creatinine in the previous 7 days to compare."}
    baseline = min(v for _, v in recent)
    within48 = [v for t, v in recent if (_hours(t, t_now) or 1e9) <= 48]
    ratio = now / baseline if baseline else 0.0
    stage = 0
    if ratio >= 3.0 or now >= 4.0:
        stage = 3
    elif ratio >= 2.0:
        stage = 2
    elif ratio >= 1.5 or (within48 and now - min(within48) >= 0.3):
        stage = 1
    labels = {0: "No AKI signal", 1: "AKI stage 1", 2: "AKI stage 2", 3: "AKI stage 3"}
    return {"stage": stage, "label": labels[stage], "current": now, "baseline": baseline, "ratio": round(ratio, 2),
            "basis": "KDIGO creatinine criteria (urine output not available).",
            "action": "Review nephrotoxic and renally cleared drugs, volume status and urine output." if stage else None}


def lab_review(chart: Chart) -> dict[str, Any]:
    return {"patient": chart.pid, "deltas": delta_checks(chart), "aki": kdigo_aki(chart),
            "note": "Delta checks flag rapid change; they do not diagnose. Thresholds are teaching values."}
