# API overview

Interactive docs: `http://localhost:8000/api/docs` (OpenAPI). Auth: `Authorization: Bearer <token>` from `POST /api/auth/login {"username": "dr.rao"}` (demo personas listed by `GET /api/auth/personas`). Server-sent events also accept `?access_token=`.

| Area | Endpoints |
|---|---|
| Patients | `GET /api/patients`, `/patients/lookup`, `/patients/{id}`, `/vitals`, `/labs`, `/timeline`, `/notes` |
| AI | `/patients/{id}/copilot`, `/coding`, `/warning`, `/handoff`, `/portal?lang=en|ta|hi`; `POST /patients/{id}/medrec`, `/coding/analyze`, `/copilot/verify` |
| Monitoring | `GET /api/monitor/snapshot`, `/monitor/stream` (SSE), `/warning/overview` |
| Scribe | `GET /scribe/demos`; `POST /scribe/draft`, `/scribe/sign`, `/scribe/audio` (needs optional faster-whisper) |
| Interop | `POST /interop/hl7` (raw text), `/interop/process`, `GET /interop/queue`, `/interop/demo`, `POST /interop/dlq/{id}/replay` |
| ABDM (mock) | `/abdm/validate`, `/abdm/catalog`, `/abdm/consent-requests`, `/abdm/consents/{id}/revoke`, `/abdm/health-information/{id}` |
| Access | `POST /access/break-glass`, `GET /access/grants`, `/access/reviews`, `POST /access/reviews/{id}`, `GET /audit`, `/audit/verify` |
| Governance | `/governance/models`, `/drift`, `/fairness`, `/overrides`, `POST /governance/feedback` |
| Ops | `/ops/overview`, `/forecast`, `/opd?extra=Clinic:1`, `/flow`, `/census`, `POST /ops/los` |
| Imaging | `/imaging/studies`, `/imaging/studies/{id}`, `/slice/{i}.png`, `/overlay/{i}.png` |
| SMART | `/.well-known/smart-configuration`, `GET /api/smart/authorize`, `POST /api/smart/token` |
| Terminology | `GET /api/terminology/search`, `/systems`, `/lookup`, `/validate`, `/expand` (lookup also returns translations) |
| Synthea import | `GET /api/import/synthea/sample`, `POST /api/import/synthea` (audited) |
| Calculators | `GET /api/calculators`, `POST /api/calculators/{id}` (cha2ds2-vasc, curb65, cockcroft-gault, bmi-bsa, corrected-calcium) |
| CDS Hooks | `GET /cds-services` (open discovery), `POST /cds-services/asclepius-patient-view` (`{hook, context:{patientId}}` → `{cards}`) |
| Bulk export | `GET /fhir/$export` → 202 + `Content-Location`; `GET /fhir/export/{job}`; `GET /fhir/export/{job}/{Type}.ndjson` (owner only) |
| Chart extras | `GET /api/patients/{id}/bodymap`, `/patients/{id}/discharge` |
| FHIR R4 | `GET /fhir/metadata`, `/fhir/{Type}?patient=&_count=…`, `/fhir/{Type}/{id}`, `/fhir/Patient/{id}/$everything`, `POST /fhir/{Type}`, `GET /fhir/CodeSystem/$lookup`, `/fhir/ValueSet/$validate-code`, `/fhir/ConceptMap/$translate` |

Roles: physician, nurse (ward-scoped), pharmacist, admin (operations only), privacy_officer (audit and reviews).
