# Architecture

## Layers

1. **Storage (`db.py`)** — SQLite holding FHIR resources as JSON with indexed `(type, id, patient)` columns, plus an append-only `audit` table. In-memory by default so every run is reproducible.
2. **Standards (`fhir.py`, `terminology.py`, `clinical.py`, `hl7.py`, `abdm.py`)** — resource builders, embedded terminology subsets, reference ranges and unit handling, HL7 v2 parsing/ACK generation, ABHA and consent logic.
3. **Security (`security.py`)** — signed bearer tokens, role permissions, attribute rules (care team, ward, restricted flag), break-glass grants with expiry, SMART scopes and patient context.
4. **Intelligence (`chart.py`, `coding.py`, `copilot.py`, `warning.py`, `medrec.py`, `scribe.py`, `sbar.py`, `portal.py`, `imaging.py`, `ops.py`, `governance.py`)** — each module is a pure function of a `Chart` or text, which makes them trivially testable.
5. **API (`api.py`, `main.py`, `state.py`)** — thin FastAPI routers that authorise, call a module, audit, and return JSON.
6. **Web (`frontend/`)** — Next.js app router; every screen talks only to the API through rewrites, so the browser never needs CORS.

## Newer components

- **`termservice.py`** implements `$lookup`, `$validate-code`, `$expand` and `$translate` over the embedded terminology subsets.
- **`synthea.py`** maps a Synthea FHIR bundle into the store and writes an audit entry per import.
- **`bodymap.py`** groups problems and abnormal results by organ system; the web 3D model and a keyboard-accessible list both render it.
- **`discharge.py`** assembles a draft discharge summary from the chart; it is never released without physician sign-off.
- **`calculators.py`** holds pure bedside score functions that validate inputs and return components and a band.
- **`cds.py`** builds CDS Hooks cards from a chart; the route authorises the patient and audits the call.
- **Bulk export** keeps job output in memory per owner; each exported patient is audited.
- **Frontend**: theming via `data-theme` / `data-contrast` on `<html>` (`app/themes.css`); widget layout and tour state live in `localStorage`.
- **`caregaps.py`** and **`deltacheck.py`** are pure functions of a `Chart`: preventive and monitoring gaps, lab delta checks and KDIGO AKI staging. Endpoints authorise and audit like any chart read.
- **Browser tests**: Playwright specs in `frontend/e2e` start both servers and exercise the real stack.

## Request path for a patient read

`token → Principal → permission check → attribute check (care team / ward / restricted) → break-glass grant? → audit entry (hash-chained) → module → JSON`

Denials are audited with the reason (`no_relationship`, `restricted`, `role not permitted`).

## Audit chain

Each row stores `hash = SHA256(prev_hash | ts | actor | action | patient | outcome | detail)`. `/api/audit/verify` recomputes the chain; editing any historical row breaks verification from that row onward (tested).

## HL7 pipeline

`receive` parses and validates, answers with an ACK immediately (`AA`, `AR` for malformed, duplicate control IDs acknowledged but ignored), and enqueues. `process` runs bounded attempts with backoff; a result that arrives before its patient (ADT) retries; exhausted jobs move to a dead-letter queue that can be replayed.

## Early-warning model

Logistic regression (L2) trained at start-up on a synthetic cohort generated from a documented formula. Because the model is linear, the explanation is exact: contribution = coefficient × (value − population mean) in log-odds. Calibration (ECE) and a NEWS2-like baseline AUC are reported alongside.

## Differential copilot

Knowledge base of 15 conditions with likelihood ratios per finding. Findings are extracted from structured observations and from notes with negation/hedging handling, each stored as cited evidence. Posterior shares use damped log-LR sums (damping 0.75) to reduce the independence assumption's overconfidence. The narrative is deterministic by default; an optional local LLM may rephrase it, but only the verifier decides if text is released.

## Why SQLite and in-process models

The goal is a project anyone can run in one command and read end to end. The module boundaries (store, FHIR facade, intelligence, API) map onto where a production system would introduce Postgres, a FHIR server such as HAPI, a queue such as Kafka or RabbitMQ, and a model service.
