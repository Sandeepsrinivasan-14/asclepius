"""ABDM-aligned helpers: ABHA number/address handling and a mock consent-manager flow.

The ABHA numbers produced here are SYNTHETIC. They use a Verhoeff check digit so typos are
detectable in the demo; this is a demo scheme, not a claim about how real ABHA numbers are
issued. The consent flow mirrors ABDM concepts (consent request, grant, HI types, purposes)
but is a self-contained mock and does not talk to any ABDM gateway or sandbox.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

ABHA_SYSTEM = "https://healthid.ndhm.gov.in"
ABHA_PROFILE = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Patient"
PURPOSES = {
    "CAREMGT": "Care management",
    "BTG": "Break the glass",
    "PUBHLTH": "Public health",
    "HPAYMT": "Healthcare payment",
    "DSRCH": "Disease-specific healthcare research",
    "PATRQT": "Self requested",
}
HI_TYPES = ["Prescription", "DiagnosticReport", "OPConsultation", "DischargeSummary", "ImmunizationRecord", "HealthDocumentRecord", "WellnessRecord"]

_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
      [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
      [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
      [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
      [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
      [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_check_digit(number: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


def verhoeff_valid(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def make_abha(rng: Any) -> str:
    """Return a synthetic 14-digit ABHA number formatted XX-XXXX-XXXX-XXXX."""
    body = "".join(str(rng.randint(0, 9)) for _ in range(13))
    digits = body + verhoeff_check_digit(body)
    return f"{digits[:2]}-{digits[2:6]}-{digits[6:10]}-{digits[10:]}"


def validate_abha(value: str) -> dict[str, Any]:
    v = value.strip()
    if not re.fullmatch(r"\d{2}-\d{4}-\d{4}-\d{4}", v):
        return {"valid": False, "reason": "Expected format XX-XXXX-XXXX-XXXX (14 digits)."}
    digits = v.replace("-", "")
    if not verhoeff_valid(digits):
        return {"valid": False, "reason": "Check digit mismatch (demo Verhoeff scheme): probable typo."}
    return {"valid": True, "reason": "Format and check digit OK (synthetic demo scheme).", "digits": digits}


def validate_abha_address(value: str) -> dict[str, Any]:
    ok = bool(re.fullmatch(r"[a-z0-9._]{4,32}@(abdm|sbx)", value.strip().lower()))
    return {"valid": ok, "reason": "OK" if ok else "Expected name@abdm (or name@sbx for sandbox); 4-32 letters, digits, dot or underscore."}


def make_address(first: str, last: str, rng: Any) -> str:
    return f"{first.lower()}.{last.lower()}{rng.randint(10, 99)}@abdm"


@dataclass
class ConsentRequest:
    id: str
    abha: str
    requester: str
    purpose: str
    hi_types: list[str]
    date_from: str
    date_to: str
    expires: str
    status: str = "REQUESTED"
    created: str = ""
    granted_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class ConsentManager:
    """In-memory mock of an ABDM-style consent manager."""

    def __init__(self) -> None:
        self.items: dict[str, ConsentRequest] = {}

    def create(self, *, abha: str, requester: str, purpose: str, hi_types: list[str], date_from: str, date_to: str, valid_days: int = 7) -> ConsentRequest:
        if purpose not in PURPOSES:
            raise ValueError(f"Unknown purpose '{purpose}'. Allowed: {', '.join(PURPOSES)}")
        bad = [t for t in hi_types if t not in HI_TYPES]
        if bad or not hi_types:
            raise ValueError(f"hi_types must be a non-empty subset of {HI_TYPES}")
        if not validate_abha(abha)["valid"]:
            raise ValueError("Invalid ABHA number")
        now = datetime.now(timezone.utc)
        req = ConsentRequest(
            id=str(uuid.uuid4()), abha=abha, requester=requester, purpose=purpose, hi_types=list(hi_types),
            date_from=date_from, date_to=date_to,
            expires=(now + timedelta(days=valid_days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            created=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self.items[req.id] = req
        return req

    def decide(self, cid: str, grant: bool, granted_types: list[str] | None = None) -> ConsentRequest:
        req = self.items[cid]
        if req.status != "REQUESTED":
            raise ValueError(f"Consent already {req.status}")
        if datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") > req.expires:
            req.status = "EXPIRED"
            raise ValueError("Consent request expired")
        if not grant:
            req.status = "DENIED"
            return req
        chosen = granted_types if granted_types is not None else req.hi_types
        req.granted_types = [t for t in chosen if t in req.hi_types]
        req.status = "GRANTED"
        return req

    def revoke(self, cid: str) -> ConsentRequest:
        req = self.items[cid]
        req.status = "REVOKED"
        req.granted_types = []
        return req
