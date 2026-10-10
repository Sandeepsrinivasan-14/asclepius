"""CDS Hooks (v1.1 shape): discovery document and a patient-view service that returns advisory cards.

Cards are deterministic functions of the chart, always cite their source and never take an action.
"""

from __future__ import annotations

from typing import Any

from . import warning
from .chart import Chart
from .clinical import lab_flag
from .terminology import LABS

SERVICES = [
    {"hook": "patient-view", "id": "asclepius-patient-view", "title": "Asclepius patient summary alerts",
     "description": "Deterioration (NEWS2), critical results and unrecognised allergy conflicts when a chart is opened.",
     "prefetch": {"patient": "Patient/{{context.patientId}}"}},
]

_INDICATOR = {"high": "critical", "medium": "warning", "low-medium": "warning", "low": "info"}


def discovery() -> dict[str, Any]:
    return {"services": SERVICES}


def patient_view_cards(chart: Chart) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    src = {"label": "Asclepius (synthetic data, not a medical device)"}
    n2 = warning.chart_news2(chart) if chart.inpatient else None
    if n2 and n2["score"] >= 5:
        cards.append({"summary": f"NEWS2 {n2['score']}: {n2['risk']} clinical risk", "indicator": _INDICATOR.get(n2["risk"], "warning"),
                      "detail": n2["response"], "source": src,
                      "suggestions": [{"label": "Open early-warning view", "uuid": "ew-" + chart.pid}]})
    for key, series in chart.labs.items():
        if not series or key not in LABS:
            continue
        value = series[-1][1]
        flag = lab_flag(key, value, chart.sex)
        if flag.startswith("critical"):
            cards.append({"summary": f"Critical result: {LABS[key]['display'].split(' [')[0]} {value:g} {LABS[key]['unit']}", "indicator": "critical",
                          "detail": f"Latest value is {flag.replace('-', ' ')}. Review and act per local policy.", "source": src})
    return cards
