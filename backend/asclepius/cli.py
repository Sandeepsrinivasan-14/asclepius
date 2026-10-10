"""Command-line entry point: `asclepius serve`, `asclepius doctor`, `asclepius import-synthea`."""

from __future__ import annotations

import argparse


def main() -> None:
    ap = argparse.ArgumentParser(prog="asclepius", description="Asclepius synthetic healthcare IT platform")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the API server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    sub.add_parser("doctor", help="print configuration and a data summary")
    i = sub.add_parser("import-synthea", help="import Synthea FHIR bundles (files or folders) into the configured database")
    i.add_argument("paths", nargs="+")
    i.add_argument("--attending", default="prac-rao", help="practitioner id given care-team access to imported patients")
    args = ap.parse_args()
    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("asclepius.main:create_app", factory=True, host=args.host, port=args.port)
    elif args.cmd == "import-synthea":
        from . import synthea
        from .config import get_settings
        from .state import AppState

        st = AppState(get_settings())
        print(synthea.import_files(st.store, args.paths, attending=args.attending))
    else:
        from .config import get_settings
        from .state import AppState

        st = AppState(get_settings())
        print(f"patients={st.store.count('Patient')} observations={st.store.count('Observation')} inpatients={len(st.cohort.inpatients)} model_auc={st.model.metrics['auc']}")
        print("demo_auth=", st.settings.demo_auth, "secret_default=", st.settings.secret == "dev-only-secret-change-me")


if __name__ == "__main__":
    main()
