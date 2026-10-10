"""Small clinical calculators and interpretation helpers shared across modules."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .terminology import LABS


def age_years(birth: str, today: date | None = None) -> int:
    today = today or date.today()
    b = datetime.strptime(birth[:10], "%Y-%m-%d").date()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def age_band(age: int) -> str:
    if age < 18:
        return "0-17"
    if age < 40:
        return "18-39"
    if age < 65:
        return "40-64"
    return "65+"


def egfr_ckd_epi_2021(creatinine_mg_dl: float, age: int, sex: str) -> float:
    """CKD-EPI 2021 race-free creatinine equation (mL/min/1.73 m2)."""
    female = sex.lower().startswith("f")
    kappa = 0.7 if female else 0.9
    alpha = -0.241 if female else -0.302
    ratio = creatinine_mg_dl / kappa
    egfr = 142 * (min(ratio, 1) ** alpha) * (max(ratio, 1) ** -1.200) * (0.9938 ** age)
    return round(egfr * (1.012 if female else 1.0), 1)


def ckd_stage(egfr: float) -> str:
    if egfr >= 90:
        return "G1"
    if egfr >= 60:
        return "G2"
    if egfr >= 45:
        return "G3a"
    if egfr >= 30:
        return "G3b"
    if egfr >= 15:
        return "G4"
    return "G5"


def lab_range(key: str, sex: str | None = None) -> tuple[float | None, float | None]:
    spec = LABS[key]
    low, high = spec.get("low"), spec.get("high")
    if key == "hemoglobin":
        if (sex or "").lower().startswith("f"):
            return 12.0, 15.5
        return 13.0, 17.0
    return low, high


def lab_flag(key: str, value: float, sex: str | None = None) -> str:
    """Return one of: critical-low, low, normal, high, critical-high."""
    spec = LABS[key]
    low, high = lab_range(key, sex)
    if spec.get("crit_low") is not None and value <= spec["crit_low"]:
        return "critical-low"
    if spec.get("crit_high") is not None and value >= spec["crit_high"]:
        return "critical-high"
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def obs_value(obs: dict[str, Any]) -> float | None:
    q = obs.get("valueQuantity")
    if q and q.get("value") is not None:
        return float(q["value"])
    return None


def obs_code(obs: dict[str, Any]) -> str | None:
    for c in (obs.get("code") or {}).get("coding", []):
        if c.get("code"):
            return str(c["code"])
    return None
