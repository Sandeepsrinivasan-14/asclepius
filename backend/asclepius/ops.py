"""Hospital operations digital twin: census, 7-day demand forecast, OPD queue model, length-of-stay model and patient flow.

History is simulated (synthetic). The live census comes from the FHIR store.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import numpy as np

from .synth import WARDS

CLINICS = {
    "General Medicine": {"rate": [2, 4, 9, 14, 16, 15, 11, 10, 12, 9, 5, 2], "servers": 4, "service_min": 11},
    "Cardiology": {"rate": [0, 2, 5, 8, 9, 9, 6, 5, 7, 6, 3, 1], "servers": 3, "service_min": 14},
    "Diabetes and Endocrine": {"rate": [1, 3, 6, 8, 9, 8, 5, 4, 6, 5, 2, 1], "servers": 2, "service_min": 12},
    "Paediatrics": {"rate": [1, 3, 7, 10, 11, 10, 7, 6, 8, 6, 3, 1], "servers": 3, "service_min": 10},
    "Orthopaedics": {"rate": [0, 2, 4, 6, 7, 7, 5, 4, 5, 4, 2, 1], "servers": 2, "service_min": 13},
}
HOURS = list(range(8, 20))  # 08:00 to 19:00


def erlang_c(arrivals_per_h: float, service_min: float, servers: int) -> dict[str, float]:
    """M/M/c queue metrics. Returns utilisation, probability of waiting and mean wait in minutes (inf if unstable)."""
    mu = 60.0 / service_min
    a = arrivals_per_h / mu
    rho = a / servers
    if rho >= 1:
        return {"utilisation": rho, "p_wait": 1.0, "mean_wait_min": float("inf")}
    s = sum(a ** k / math.factorial(k) for k in range(servers))
    top = a ** servers / math.factorial(servers) * (1 / (1 - rho))
    p_wait = top / (s + top)
    wq = p_wait / (servers * mu - arrivals_per_h) * 60.0
    return {"utilisation": rho, "p_wait": p_wait, "mean_wait_min": wq}


def holt_winters_weekly(y: np.ndarray, horizon: int, alpha: float = .35, beta: float = .05, gamma: float = .25) -> tuple[np.ndarray, float]:
    """Additive Holt-Winters with weekly seasonality. Returns forecast and residual std."""
    m = 7
    n = len(y)
    level = y[:m].mean()
    trend = (y[m:2 * m].mean() - y[:m].mean()) / m
    season = list(y[:m] - level)
    resid = []
    for t in range(n):
        s = season[t % m]
        fc = level + trend + s
        resid.append(y[t] - fc)
        new_level = alpha * (y[t] - s) + (1 - alpha) * (level + trend)
        trend = beta * (new_level - level) + (1 - beta) * trend
        season[t % m] = gamma * (y[t] - new_level) + (1 - gamma) * s
        level = new_level
    fcs = np.array([level + (h + 1) * trend + season[(n + h) % m] for h in range(horizon)])
    return fcs, float(np.std(resid[m:]))


class OpsTwin:
    def __init__(self, store: Any, cohort: Any, seed: int = 21) -> None:
        self.store, self.cohort = store, cohort
        self.rng = np.random.default_rng(seed)
        self.days = 84
        self.history = self._simulate_history()
        self.los_model = self._fit_los()

    # ----------------------------------------------------------- history
    def _simulate_history(self) -> dict[str, np.ndarray]:
        today = date.today()
        dates = [today - timedelta(days=self.days - 1 - i) for i in range(self.days)]
        out: dict[str, np.ndarray] = {}
        current = {w: sum(1 for p in self.cohort.inpatients if self.cohort.ward[p] == w) for w in WARDS}
        for w, spec in WARDS.items():
            base = max(current[w], spec["beds"] * .55)
            dow = np.array([1.08, 1.05, 1.02, 1.0, 0.98, 0.9, 0.88])  # Mon..Sun
            season = np.array([1 + (.12 if w in ("MED",) and i > self.days - 35 else 0) * (i - (self.days - 35)) / 35 for i in range(self.days)])
            census = np.array([base * dow[d.weekday()] * season[i] for i, d in enumerate(dates)]) + self.rng.normal(0, spec["beds"] * .04, self.days)
            census = np.clip(np.round(census), 1, spec["beds"])
            census[-1] = current[w]
            out[w] = census
        out["_dates"] = np.array([d.isoformat() for d in dates])
        return out

    # ----------------------------------------------------------- views
    def overview(self) -> dict[str, Any]:
        wards = []
        for w, spec in WARDS.items():
            occ = int(self.history[w][-1])
            prev = int(self.history[w][-2])
            wards.append({"code": w, "name": spec["name"], "beds": spec["beds"], "occupied": occ, "available": spec["beds"] - occ, "occupancy": round(occ / spec["beds"], 3), "change_vs_yesterday": occ - prev,
                          "sparkline": [int(v) for v in self.history[w][-14:]]})
        beds = sum(w["beds"] for w in wards)
        occ = sum(w["occupied"] for w in wards)
        return {"wards": wards, "total_beds": beds, "occupied": occ, "occupancy": round(occ / beds, 3), "as_of": self.history["_dates"][-1]}

    def forecast(self, horizon: int = 7) -> dict[str, Any]:
        rows = []
        tot = None
        dates = [date.fromisoformat(self.history["_dates"][-1]) + timedelta(days=i + 1) for i in range(horizon)]
        for w, spec in WARDS.items():
            fc, sd = holt_winters_weekly(self.history[w], horizon)
            fc = np.clip(fc, 0, spec["beds"] + 3)
            tot = fc if tot is None else tot + fc
            rows.append({"ward": w, "beds": spec["beds"], "forecast": [round(float(x), 1) for x in fc], "lower": [round(float(max(x - 1.28 * sd, 0)), 1) for x in fc], "upper": [round(float(x + 1.28 * sd), 1) for x in fc],
                         "breach_day": next((dates[i].isoformat() for i, x in enumerate(fc + 1.28 * sd) if x >= spec["beds"]), None), "history": [int(v) for v in self.history[w][-28:]]})
        return {"dates": [d.isoformat() for d in dates], "wards": rows, "total": [round(float(x), 1) for x in tot], "method": "Additive Holt-Winters (weekly seasonality), 80% interval from in-sample residuals",
                "history_dates": [str(d) for d in self.history["_dates"][-28:]]}

    def opd(self, extra_servers: dict[str, int] | None = None, seed: int = 4) -> dict[str, Any]:
        extra_servers = extra_servers or {}
        out = []
        for name, c in CLINICS.items():
            servers = c["servers"] + int(extra_servers.get(name, 0))
            hours = []
            for h, lam in zip(HOURS, c["rate"]):
                m = erlang_c(lam, c["service_min"], servers)
                hours.append({"hour": h, "arrivals": lam, "utilisation": round(m["utilisation"], 3), "p_wait": round(m["p_wait"], 3),
                              "mean_wait_min": None if math.isinf(m["mean_wait_min"]) else round(m["mean_wait_min"], 1), "overloaded": m["utilisation"] >= 1})
            q = self._simulate_queue(c["rate"], c["service_min"], servers, seed)
            peak = max(hours, key=lambda x: (x["mean_wait_min"] if x["mean_wait_min"] is not None else 1e9))
            out.append({"clinic": name, "servers": servers, "base_servers": c["servers"], "service_min": c["service_min"], "hours": hours, "queue_timeline": q, "peak_hour": peak["hour"],
                        "peak_wait_min": peak["mean_wait_min"], "overloaded_hours": sum(1 for x in hours if x["overloaded"])})
        return {"clinics": out, "method": "Erlang C (M/M/c) per hour plus a discrete-event simulation of the day"}

    @staticmethod
    def _simulate_queue(rates: list[int], service_min: float, servers: int, seed: int) -> list[dict[str, Any]]:
        rng = np.random.default_rng(seed)
        events = []
        for h, lam in zip(HOURS, rates):
            n = rng.poisson(lam)
            events += list(h * 60 + rng.uniform(0, 60, n))
        events.sort()
        free = [HOURS[0] * 60.0] * servers
        waits = []
        for t in events:
            i = int(np.argmin(free))
            start = max(t, free[i])
            free[i] = start + rng.exponential(service_min)
            waits.append((t, start - t))
        timeline = []
        for t in range(HOURS[0] * 60, (HOURS[-1] + 1) * 60, 30):
            waiting = sum(1 for arr, w in waits if arr <= t < arr + w)
            timeline.append({"time": f"{t // 60:02d}:{t % 60:02d}", "waiting": waiting})
        return timeline

    # ----------------------------------------------------------- length of stay
    def _fit_los(self) -> dict[str, Any]:
        n = 4000
        age = np.clip(self.rng.normal(58, 18, n), 18, 95)
        ward = self.rng.integers(0, len(WARDS), n)
        acuity = np.clip(self.rng.gamma(2.0, 1.6, n), 0, 15)
        comorb = self.rng.poisson(1.6, n)
        emerg = (self.rng.random(n) < .65).astype(float)
        wards = list(WARDS)
        w_eff = np.array([.55, .35, .0, .25])[ward]  # ICU, CCU, MED, NEURO effect on log LOS
        log_los = 0.9 + 0.012 * (age - 55) + w_eff + 0.07 * acuity + 0.09 * comorb + 0.2 * emerg + self.rng.normal(0, .32, n)
        X = np.column_stack([np.ones(n), age, np.eye(len(wards))[ward][:, :-1], acuity, comorb, emerg])
        split = 3000
        beta, *_ = np.linalg.lstsq(X[:split], log_los[:split], rcond=None)
        pred = X[split:] @ beta
        resid = log_los[:split] - X[:split] @ beta
        mae = float(np.mean(np.abs(np.exp(pred) - np.exp(log_los[split:]))))
        ss_res, ss_tot = float(np.sum((log_los[split:] - pred) ** 2)), float(np.sum((log_los[split:] - log_los[split:].mean()) ** 2))
        return {"beta": beta, "wards": wards, "q10": float(np.quantile(resid, .1)), "q90": float(np.quantile(resid, .9)), "mae_days": round(mae, 2), "r2_log": round(1 - ss_res / ss_tot, 3), "n_train": split, "n_test": n - split}

    def predict_los(self, *, age: float, ward: str, acuity: float, comorbidities: int, emergency: bool) -> dict[str, Any]:
        m = self.los_model
        if ward not in m["wards"]:
            raise ValueError(f"ward must be one of {m['wards']}")
        oh = np.zeros(len(m["wards"]) - 1)
        if m["wards"].index(ward) < len(oh):
            oh[m["wards"].index(ward)] = 1
        x = np.concatenate([[1, age], oh, [acuity, comorbidities, float(emergency)]])
        mu = float(x @ m["beta"])
        return {"median_days": round(math.exp(mu), 1), "p10_days": round(math.exp(mu + m["q10"]), 1), "p90_days": round(math.exp(mu + m["q90"]), 1)}

    def flow(self) -> dict[str, Any]:
        ed = 420
        to = {"ICU": int(ed * .12), "CCU": int(ed * .10), "MED": int(ed * .42), "NEURO": int(ed * .07)}
        direct = ed - sum(to.values())
        nodes = [{"id": "ED", "label": "Emergency arrivals"}] + [{"id": w, "label": WARDS[w]["name"]} for w in WARDS] + [{"id": "HOME", "label": "Discharged home"}, {"id": "STEP", "label": "Stepped down"}, {"id": "UP", "label": "Escalated to higher care"}, {"id": "FOLLOW", "label": "Discharged to follow-up"}]
        links = [{"source": "ED", "target": w, "value": v} for w, v in to.items()] + [{"source": "ED", "target": "HOME", "value": direct}]
        for w, v in to.items():
            if w == "ICU":
                split = {"STEP": .55, "HOME": .12, "FOLLOW": .22, "UP": .0}
            elif w == "CCU":
                split = {"STEP": .25, "HOME": .30, "FOLLOW": .45, "UP": .0}
            else:
                split = {"STEP": .0, "HOME": .62, "FOLLOW": .30, "UP": .08}
            rest = v
            vals = {k: int(round(v * p)) for k, p in split.items()}
            diff = v - sum(vals.values())
            first = next(iter(k for k, p in split.items() if p > 0))
            vals[first] += diff
            links += [{"source": w, "target": k, "value": c} for k, c in vals.items() if c > 0]
            del rest
        return {"nodes": nodes, "links": links, "period_days": 30, "note": "Synthetic 30-day patient flow."}

    def census_detail(self, charts: list[Any], los_by_patient: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for c in charts:
            if c.inpatient and c.pid in los_by_patient:
                rows.append({"patient": c.pid, "ward": c.ward, "bed": c.bed, **los_by_patient[c.pid]})
        return rows
