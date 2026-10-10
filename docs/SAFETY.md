# AI safety case (educational)

| Risk | Control in Asclepius |
|---|---|
| Hallucinated clinical facts | Narratives are verified: every clinical sentence needs a resolvable `[E#]` citation, every number must trace to chart evidence, and statements may not contradict documented findings |
| Unsafe drug suggestion | Allergy check on every mentioned drug; scope guard blocks dosing directives and definitive diagnoses |
| Anchoring bias | Copilot ignores the clinician impression and encounter diagnoses by design |
| Overconfidence | Damped likelihood ratios; relative likelihoods, not probabilities; "cannot miss" conditions are flagged even when ranked low |
| Opaque risk scores | Exact per-feature explanation; NEWS2 shown beside the learned model; calibration published |
| Silent drift | PSI per feature with watch/drift thresholds and an interpretation note |
| Unfair performance | Subgroup AUC/TPR/FPR; four-fifths rule flag; flags are displayed rather than hidden |
| Automation bias | Accept / modify / reject is recorded; override rates per model are on a dashboard |
| Unreviewed chart writes | Scribe output is tagged `ai-draft`; only a physician signature writes resources |
| Patient-facing errors | Portal summaries are template-based (no free generation) and require clinician approval |
| Inappropriate access | Role, care team and consent checks; break-glass is time-boxed and reviewed; hash-chained audit |

## Known limits

All models are trained and evaluated on synthetic data generated from assumptions close to the models' own, so reported accuracy is optimistic and says nothing about real-world performance. Fairness results on synthetic data only demonstrate the tooling. The knowledge base is small and hand-written. No component has regulatory clearance and none should be used for care.
