"""Early warning: NEWS2, qSOFA, a calibrated ML risk model with exact linear explanations, and a live vitals simulator.

The ML model is trained at start-up on a SYNTHETIC cohort whose outcome is generated from a
known formula. It exists to demonstrate the full pipeline (training, calibration, explanation,
drift and fairness monitoring), not to predict real deterioration.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import numpy as np

from .chart import Chart

# ------------------------------------------------------------------ NEWS2


def _band(value: float, bands: list[tuple[float, float, int]]) -> int:
    for lo, hi, pts in bands:
        if lo <= value <= hi:
            return pts
    return 0


def news2(v: dict[str, Any], *, scale2: bool = False) -> dict[str, Any]:
    """Royal College of Physicians NEWS2 aggregate score from a vitals dict.

    Keys: rr, spo2, o2 (bool, on supplemental oxygen), sbp, hr, acvpu, temp.
    """
    inf = float("inf")
    parts: dict[str, int] = {}
    parts["rr"] = _band(v["rr"], [(-inf, 8, 3), (9, 11, 1), (12, 20, 0), (21, 24, 2), (25, inf, 3)])
    spo2 = v["spo2"]
    on_o2 = bool(v.get("o2"))
    if scale2:
        if spo2 <= 83:
            s = 3
        elif spo2 <= 85:
            s = 2
        elif spo2 <= 87:
            s = 1
        elif spo2 <= 92:
            s = 0
        elif not on_o2:
            s = 0
        elif spo2 <= 94:
            s = 1
        elif spo2 <= 96:
            s = 2
        else:
            s = 3
        parts["spo2"] = s
    else:
        parts["spo2"] = _band(spo2, [(-inf, 91, 3), (92, 93, 2), (94, 95, 1), (96, inf, 0)])
    parts["o2"] = 2 if on_o2 else 0
    parts["sbp"] = _band(v["sbp"], [(-inf, 90, 3), (91, 100, 2), (101, 110, 1), (111, 219, 0), (220, inf, 3)])
    parts["hr"] = _band(v["hr"], [(-inf, 40, 3), (41, 50, 1), (51, 90, 0), (91, 110, 1), (111, 130, 2), (131, inf, 3)])
    parts["acvpu"] = 0 if str(v.get("acvpu", "Alert")).lower().startswith("a") else 3
    parts["temp"] = _band(v["temp"], [(-inf, 35.0, 3), (35.1, 36.0, 1), (36.1, 38.0, 0), (38.1, 39.0, 1), (39.1, inf, 2)])
    total = sum(parts.values())
    single3 = any(p == 3 for p in parts.values())
    if total >= 7:
        risk, response, freq = "high", "Emergency assessment by a critical-care competent team; consider transfer to higher level of care.", "Continuous monitoring"
    elif total >= 5:
        risk, response, freq = "medium", "Urgent review by a clinician with core competencies in acute illness.", "At least hourly"
    elif single3:
        risk, response, freq = "low-medium", "Urgent ward-based response: a single parameter scores 3.", "At least hourly"
    elif total >= 1:
        risk, response, freq = "low", "Ward-based response: registered nurse decides on frequency of monitoring and escalation.", "At least every 4-6 hours"
    else:
        risk, response, freq = "low", "Continue routine monitoring.", "At least every 12 hours"
    return {"score": total, "parts": parts, "risk": risk, "response": response, "frequency": freq, "scale": 2 if scale2 else 1, "single_3": single3}


def qsofa(v: dict[str, Any]) -> dict[str, Any]:
    items = {"rr_ge_22": v["rr"] >= 22, "sbp_le_100": v["sbp"] <= 100, "altered_mentation": not str(v.get("acvpu", "Alert")).lower().startswith("a")}
    score = sum(items.values())
    return {"score": score, "items": items, "risk": "high" if score >= 2 else "low"}


def chart_vitals_at(chart: Chart, idx: int = -1) -> dict[str, Any] | None:
    """Vitals dict at hourly index idx (aligned by HR series)."""
    hr = chart.vitals.get("hr")
    if not hr:
        return None
    t = hr[idx][0]

    def at(name: str) -> float | None:
        for tt, val in reversed(chart.vitals.get(name, [])):
            if tt <= t:
                return val
        return None

    acv = "Alert"
    for tt, a in chart.acvpu:
        if tt <= t:
            acv = a
    v = {k: at(k) for k in ("hr", "rr", "spo2", "temp", "sbp", "dbp", "o2flow")}
    if any(v[k] is None for k in ("hr", "rr", "spo2", "temp", "sbp")):
        return None
    v["o2"] = bool(v["o2flow"])
    v["acvpu"] = acv
    v["time"] = t
    return v


def chart_news2(chart: Chart, idx: int = -1) -> dict[str, Any] | None:
    v = chart_vitals_at(chart, idx)
    if v is None:
        return None
    out = news2(v, scale2="copd" in chart.condition_keys())
    out["time"] = v["time"]
    return out


def news2_series(chart: Chart, hours: int = 48) -> list[dict[str, Any]]:
    n = len(chart.vitals.get("hr", []))
    out = []
    for i in range(max(0, n - hours), n):
        r = chart_news2(chart, i)
        if r:
            out.append({"time": r["time"], "score": r["score"], "risk": r["risk"]})
    return out


# ------------------------------------------------------------- ML model
FEATURES = ["age", "hr", "rr", "spo2", "sbp", "temp", "altered", "lactate", "wbc", "creatinine"]
LABELS = {"age": "Age", "hr": "Heart rate", "rr": "Respiratory rate", "spo2": "SpO2", "sbp": "Systolic BP", "temp": "Temperature",
          "altered": "Altered consciousness", "lactate": "Lactate", "wbc": "White cell count", "creatinine": "Creatinine"}
DEFAULTS = {"age": 60, "hr": 80, "rr": 16, "spo2": 97, "sbp": 120, "temp": 36.8, "altered": 0, "lactate": 1.1, "wbc": 8, "creatinine": 1.0}
UNITS = {"age": "y", "hr": "/min", "rr": "/min", "spo2": "%", "sbp": "mmHg", "temp": "C", "altered": "", "lactate": "mmol/L", "wbc": "10^3/uL", "creatinine": "mg/dL"}


def simulate_cohort(n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return X (n x d), y, sex (0/1), and the true logit. Outcome rule is a documented formula."""
    z = rng.normal(size=n)  # latent illness severity
    age = np.clip(rng.normal(58, 17, n), 18, 95)
    sev = np.clip(z, -2, 3)
    hr = 78 + 11 * sev + rng.normal(0, 8, n)
    rr = 16 + 2.6 * sev + rng.normal(0, 2, n)
    spo2 = np.clip(97 - 1.6 * np.maximum(sev, 0) + rng.normal(0, 1.2, n), 70, 100)
    sbp = 126 - 9 * sev + rng.normal(0, 14, n)
    temp = 36.8 + 0.35 * np.maximum(sev, 0) + rng.normal(0, .35, n)
    altered = (rng.random(n) < 1 / (1 + np.exp(-(sev * 1.2 - 2.6)))).astype(float)
    lactate = np.clip(1.1 + 0.55 * np.maximum(sev, 0) + rng.gamma(2, 0.2, n) - .4, .4, 12)
    wbc = np.clip(8 + 2.2 * sev + rng.normal(0, 2.2, n), 1.5, 35)
    creat = np.clip(1.0 + 0.2 * np.maximum(sev, 0) + 0.004 * (age - 55) + rng.normal(0, .2, n), .4, 8)
    X = np.column_stack([age, hr, rr, spo2, sbp, temp, altered, lactate, wbc, creat])
    logit = (-3.6 + 0.022 * (age - 60) + 0.028 * (hr - 80) + 0.10 * (rr - 16) - 0.14 * (spo2 - 97) - 0.018 * (sbp - 120)
             + 0.28 * np.abs(temp - 37.0) + 1.5 * altered + 0.5 * (lactate - 1.1) + 0.025 * (wbc - 8) + 0.45 * (creat - 1.0))
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(float)
    sex = (rng.random(n) < .5).astype(int)
    return X, y, sex, logit


def _sig(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 25) -> np.ndarray:
    """L2-regularised logistic regression via IRLS (Newton). X includes an intercept column."""
    w = np.zeros(X.shape[1])
    reg = np.eye(X.shape[1]) * l2
    reg[0, 0] = 0
    for _ in range(iters):
        p = _sig(X @ w)
        g = X.T @ (p - y) + reg @ w
        h = X.T @ (X * (p * (1 - p))[:, None]) + reg + 1e-8 * np.eye(X.shape[1])
        step = np.linalg.solve(h, g)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


def auc_score(y: np.ndarray, s: np.ndarray) -> float:
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    allv = np.concatenate([pos, neg])[order]
    i = 0
    r = np.empty(len(allv))
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        r[i:j + 1] = (i + j) / 2 + 1
        i = j + 1
    ranks[order] = r
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


@dataclass
class RiskModel:
    mean: np.ndarray
    std: np.ndarray
    w: np.ndarray
    metrics: dict[str, Any]
    ref_X: np.ndarray
    test_X: np.ndarray
    test_y: np.ndarray
    test_p: np.ndarray
    test_sex: np.ndarray

    def predict_row(self, x: np.ndarray) -> float:
        z = (x - self.mean) / self.std
        return float(_sig(np.concatenate([[1.0], z]) @ self.w))

    def explain_row(self, x: np.ndarray) -> list[dict[str, Any]]:
        z = (x - self.mean) / self.std
        contrib = self.w[1:] * z
        out = [{"feature": f, "label": LABELS[f], "value": round(float(x[i]), 2), "unit": UNITS[f], "reference": round(float(self.mean[i]), 2), "contribution": round(float(contrib[i]), 3)}
               for i, f in enumerate(FEATURES)]
        return sorted(out, key=lambda r: -abs(r["contribution"]))

    def base_rate(self) -> float:
        return float(_sig(self.w[0]))


def train_model(seed: int = 11) -> RiskModel:
    rng = np.random.default_rng(seed)
    X, y, sex, _ = simulate_cohort(9000, rng)
    n_train = 6500
    mean, std = X[:n_train].mean(0), X[:n_train].std(0) + 1e-9
    Z = (X - mean) / std
    A = np.column_stack([np.ones(len(Z)), Z])
    w = fit_logistic(A[:n_train], y[:n_train], l2=2.0)
    p = _sig(A[n_train:] @ w)
    yt = y[n_train:]
    # calibration table (10 equal-count bins)
    order = np.argsort(p)
    bins = []
    for chunk in np.array_split(order, 10):
        bins.append({"predicted": round(float(p[chunk].mean()), 4), "observed": round(float(yt[chunk].mean()), 4), "n": int(len(chunk))})
    ece = float(sum(abs(b["predicted"] - b["observed"]) * b["n"] for b in bins) / len(p))
    news_like = np.clip((X[n_train:, 2] > 24) * 2 + (X[n_train:, 3] < 92) * 3 + (X[n_train:, 4] < 101) * 2 + (X[n_train:, 1] > 110) * 2 + X[n_train:, 6] * 3 + (X[n_train:, 5] > 38.0), 0, 20)
    metrics = {"n_train": n_train, "n_test": int(len(yt)), "prevalence": round(float(yt.mean()), 4), "auc": round(auc_score(yt, p), 4),
               "auc_news2_like_rule": round(auc_score(yt, news_like.astype(float)), 4), "brier": round(float(np.mean((p - yt) ** 2)), 4), "ece": round(ece, 4), "calibration": bins}
    return RiskModel(mean=mean, std=std, w=w, metrics=metrics, ref_X=X[:n_train], test_X=X[n_train:], test_y=yt, test_p=p, test_sex=sex[n_train:])


def chart_features(chart: Chart, idx: int = -1) -> np.ndarray | None:
    v = chart_vitals_at(chart, idx)
    if v is None:
        return None
    row = dict(DEFAULTS)
    row.update(age=chart.age, hr=v["hr"], rr=v["rr"], spo2=v["spo2"], sbp=v["sbp"], temp=v["temp"], altered=0.0 if str(v["acvpu"]).lower().startswith("a") else 1.0)
    for lab, key in (("lactate", "lactate"), ("wbc", "wbc"), ("creatinine", "creatinine")):
        val = chart.latest_lab(lab)
        if val is not None:
            row[key] = val
    return np.array([row[f] for f in FEATURES], dtype=float)


def risk_tier(p: float) -> str:
    return "high" if p >= 0.35 else "medium" if p >= 0.15 else "low"


# ------------------------------------------------------ live simulator
class VitalsSimulator:
    """Random-walk vitals with mean reversion; deteriorating patients drift toward worse values."""

    def __init__(self, charts: list[Chart], trajectories: dict[str, str], seed: int = 5) -> None:
        self.rng = random.Random(seed)
        self.state: dict[str, dict[str, Any]] = {}
        self.traj = trajectories
        self.scale2: dict[str, bool] = {}
        for c in charts:
            lv = c.latest_vitals()
            if lv["hr"] is None:
                continue
            self.state[c.pid] = {"hr": lv["hr"], "rr": lv["rr"], "spo2": lv["spo2"], "sbp": lv["sbp"], "dbp": lv["dbp"], "temp": lv["temp"], "o2": bool(lv["o2flow"]), "acvpu": lv["acvpu"]}
            self.scale2[c.pid] = "copd" in c.condition_keys()
        self.anchor = {pid: dict(s) for pid, s in self.state.items()}
        self.tick = 0

    def step(self) -> dict[str, dict[str, Any]]:
        self.tick += 1
        out: dict[str, dict[str, Any]] = {}
        for pid, s in self.state.items():
            tr = self.traj.get(pid, "stable")
            drift = {"deteriorating": 1, "critical": 1.4, "improving": -1, "stable": 0}.get(tr, 0)
            a = self.anchor[pid]
            s["hr"] = float(np.clip(s["hr"] + .15 * (a["hr"] - s["hr"]) + self.rng.gauss(0, 1.1) + drift * .03, 35, 190))
            s["rr"] = float(np.clip(s["rr"] + .2 * (a["rr"] - s["rr"]) + self.rng.gauss(0, .35) + drift * .012, 6, 42))
            s["spo2"] = float(np.clip(s["spo2"] + .2 * (a["spo2"] - s["spo2"]) + self.rng.gauss(0, .3) - drift * .01, 70, 100))
            s["sbp"] = float(np.clip(s["sbp"] + .15 * (a["sbp"] - s["sbp"]) + self.rng.gauss(0, 1.5) - drift * .05, 55, 230))
            s["dbp"] = float(np.clip(s["dbp"] + .15 * (a["dbp"] - s["dbp"]) + self.rng.gauss(0, 1.0), 30, 130))
            s["temp"] = float(np.clip(s["temp"] + .1 * (a["temp"] - s["temp"]) + self.rng.gauss(0, .03), 34.5, 41.5))
            snap = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in s.items()}
            n2 = news2({**snap, "o2": s["o2"]}, scale2=self.scale2[pid])
            q = qsofa({**snap})
            out[pid] = {**snap, "news2": n2["score"], "risk": n2["risk"], "qsofa": q["score"]}
        return out
