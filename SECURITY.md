# Security policy

Asclepius is an engineering portfolio project. It contains **only synthetic data** and is **not a medical device**; do not deploy it with real patient data.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security tab, "Report a vulnerability") rather than a public issue. Include the affected endpoint or file, steps to reproduce and the impact. I aim to acknowledge reports within a week.

## Known, documented limitations

- Demo sign-in has no passwords. Set `ASCLEPIUS_DEMO_AUTH=0` and configure an identity provider before any shared deployment.
- Set `ASCLEPIUS_SECRET` to a long random value; the built-in default is for local development only.
- ABDM and SMART flows are mocks. Audit storage is a local SQLite table, not write-once storage.
