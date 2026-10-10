# Contributing

1. `make install`, then `make test` (backend, 80% coverage gate in CI) and `make lint`.
2. Browser tests: `cd frontend && npm run e2e:install && npm run e2e` (starts both servers itself).
3. Rules that every change must follow:
   - Synthetic data only. No real patient data, institution names or logos.
   - Every new endpoint authorises through `state.sec`, audits patient-data access and has a test.
   - Intelligence modules stay pure functions; AI output must be cited and pass the verifier.
4. Keep pull requests small and describe the clinical-safety impact, if any.
