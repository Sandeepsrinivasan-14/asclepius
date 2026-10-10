# Portfolio kit (for the repo owner)

## GitHub settings to paste (Settings → General)
- **Description:** Asclepius: synthetic-data healthcare IT platform with FHIR R4, SMART, HL7 v2, ABDM-aligned consent and verified, governed clinical AI
- **Topics:** `fhir` `hl7` `healthcare-ai` `fastapi` `nextjs` `abdm` `clinical-decision-support`
- Optional: rename the repo to `asclepius` (GitHub redirects the old URL). Pin it on your profile.

## Resume bullets (pick 3)
- Built **Asclepius**, a full-stack healthcare-IT platform (FastAPI, Next.js 15) implementing HL7 FHIR R4 search/`$everything`, SMART App Launch with PKCE S256, an HL7 v2 ingestion pipeline (idempotency, retry with backoff, dead-letter replay) and an ABDM-aligned consent flow; 83 backend tests at 92% coverage, CDS Hooks and bulk FHIR export, 23 Playwright end-to-end tests, CI with secret scanning.
- Designed a **verified clinical-AI layer**: a cited differential copilot and ambient scribe whose every sentence passes six checks (citation validity, numeric fidelity, chart consistency, allergy safety, scope guard) before release; exact per-feature explanations for a calibrated 24-hour deterioration model compared against NEWS2.
- Implemented **security and governance** for health data: role + care-team + consent access control, time-boxed break-glass with privacy-officer review, SHA-256 hash-chained audit log with tamper detection, model cards, PSI drift monitoring, subgroup fairness (four-fifths rule) and clinician-override tracking.

## LinkedIn post draft
I rebuilt a healthcare project from scratch around one question: how should clinical AI behave in a real hospital system?

Asclepius is a synthetic-data platform with FHIR R4, SMART on FHIR (PKCE), HL7 v2 and an ABDM-style consent layer. The AI part is deliberately small and strict: every suggestion cites chart evidence, is checked by an independent verifier, is explained, is logged, and its override rate is measured.

What I learned: most of "medical AI" is standards, access control, audit and guardrails, not the model.

Everything is synthetic and the limits are documented in the repo. Link in comments.

#HealthcareAI #FHIR #HealthTech

## 2-minute demo script
1. Login screen (3D helix) → sign in as Dr. Meera Rao.
2. Patient Joseph Thomas → Differential copilot → click a citation → "Break the verifier".
3. Early warning tab → explain the contribution bars.
4. HL7 pipeline → send all → run processor → replay a dead letter.
5. FHIR explorer → Run SMART flow (point out the 403s).
6. Press `t` to switch to Clinic day, open the 3D body map, click an organ, then open the discharge summary.
7. Terminology page → import the Synthea sample.
8. Dr. Chandran → locked patient → break glass → Nandini Menon → review and audit chain.
