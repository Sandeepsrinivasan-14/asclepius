"""Application state: wires the store, cohort, models and services together."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

import numpy as np

from . import abdm, copilot, hl7, ops, synth, warning
from .chart import Chart, build_chart
from .config import Settings
from .db import Store
from .governance import Feedback
from .security import Security


class AppState:
    def __init__(self, settings: Settings, *, now: datetime | None = None) -> None:
        self.settings = settings
        self.store = Store(settings.db_path)
        self.cohort = synth.generate(self.store, seed=settings.seed, n_patients=settings.n_patients, now=now or datetime.now(timezone.utc))
        self.sec = Security(self.store, settings)
        self.model = warning.train_model()
        self.pipeline = hl7.Pipeline(self.store)
        self.consents = abdm.ConsentManager()
        self.feedback = Feedback()
        self.ops = ops.OpsTwin(self.store, self.cohort)
        self._lock = threading.RLock()
        self._charts: dict[str, Chart] = {}
        self.exports: dict[str, dict] = {}
        self._diff: dict[str, dict[str, Any]] = {}
        self.stats = {"verified": 0, "blocked": 0, "coder_calls": 0}
        self._copilot_eval: dict[str, Any] | None = None
        self.sim = warning.VitalsSimulator([c for c in (self.chart(p) for p in self.cohort.inpatients) if c], self.cohort.trajectory)
        threading.Thread(target=self.copilot_eval, daemon=True, name="eval-warmup").start()

    # ---- chart cache -------------------------------------------------
    def chart(self, pid: str) -> Chart | None:
        with self._lock:
            if pid not in self._charts:
                ch = build_chart(self.store, pid)
                if ch is None:
                    return None
                self._charts[pid] = ch
            return self._charts[pid]

    def invalidate(self, pid: str | None = None) -> None:
        with self._lock:
            if pid:
                self._charts.pop(pid, None)
                self._diff.pop(pid, None)
            else:
                self._charts.clear()
                self._diff.clear()
        self.sec.refresh_attributes()

    def differential(self, pid: str) -> dict[str, Any] | None:
        with self._lock:
            if pid in self._diff:
                return self._diff[pid]
        ch = self.chart(pid)
        if ch is None:
            return None
        d = copilot.differential(ch, self.settings)
        with self._lock:
            self._diff[pid] = d
        return d

    # ---- evaluation (lazy) -----------------------------------------
    def copilot_eval(self) -> dict[str, Any]:
        if self._copilot_eval is None:
            n = top1 = top3 = blocked = 0
            for pid, scen in self.cohort.truth.items():
                d = self.differential(pid)
                if d is None:
                    continue
                if d["verification"]["status"] == "Fail":
                    blocked += 1
                acc = copilot.SCENARIO_TO_KB.get(scen)
                if not acc:
                    continue
                keys = [r["key"] for r in d["differential"]]
                n += 1
                top1 += int(bool(keys) and keys[0] in acc)
                top3 += int(bool(set(keys[:3]) & acc))
            self._copilot_eval = {"n": n, "top1": round(top1 / max(n, 1), 3), "top3": round(top3 / max(n, 1), 3), "blocked": blocked}
        return self._copilot_eval

    def current_feature_matrix(self) -> np.ndarray:
        rows = []
        for pid in self.cohort.inpatients:
            ch = self.chart(pid)
            if not ch:
                continue
            n = len(ch.vitals.get("hr", []))
            for idx in range(max(0, n - 48), n, 2):
                x = warning.chart_features(ch, idx)
                if x is not None:
                    rows.append(x)
        return np.array(rows) if rows else np.empty((0, len(warning.FEATURES)))
