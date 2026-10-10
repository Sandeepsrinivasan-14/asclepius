"""FHIR R4 helpers: constructors, bundles, a light structural validator and the capability statement."""

from __future__ import annotations

import base64
from typing import Any

from . import __version__
from .db import iso, utcnow

FHIR_VERSION = "4.0.1"
SUPPORTED = [
    "Patient", "Practitioner", "Encounter", "Observation", "Condition", "MedicationRequest",
    "AllergyIntolerance", "DocumentReference", "DiagnosticReport", "Composition", "ServiceRequest", "Location",
]
SEARCH_PARAMS: dict[str, list[str]] = {
    "Patient": ["_id", "name", "identifier", "gender", "birthdate"],
    "Observation": ["patient", "code", "date", "category"],
    "Condition": ["patient", "code"],
    "MedicationRequest": ["patient", "status"],
    "AllergyIntolerance": ["patient"],
    "Encounter": ["patient", "status"],
    "DocumentReference": ["patient"],
    "DiagnosticReport": ["patient"],
    "Composition": ["patient"],
    "ServiceRequest": ["patient"],
    "Practitioner": ["name"],
    "Location": ["name"],
}

REQUIRED: dict[str, list[str]] = {
    "Patient": [],
    "Observation": ["status", "code", "subject"],
    "Condition": ["subject", "code"],
    "MedicationRequest": ["status", "intent", "medicationCodeableConcept", "subject"],
    "AllergyIntolerance": ["patient"],
    "Encounter": ["status", "class"],
    "DocumentReference": ["status", "content"],
    "Composition": ["status", "type", "date", "author", "title"],
    "ServiceRequest": ["status", "intent", "subject", "code"],
}


def ref(rtype: str, rid: str, display: str | None = None) -> dict[str, str]:
    out = {"reference": f"{rtype}/{rid}"}
    if display:
        out["display"] = display
    return out


def codeable(system: str, code: str, display: str, text: str | None = None) -> dict[str, Any]:
    return {"coding": [{"system": system, "code": code, "display": display}], "text": text or display}


def encode_text(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def decode_text(res: dict[str, Any]) -> str:
    try:
        data = res["content"][0]["attachment"]["data"]
        return base64.b64decode(data).decode()
    except (KeyError, IndexError, ValueError):
        return ""


def bundle(entries: list[dict[str, Any]], *, btype: str = "searchset", total: int | None = None, self_link: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": btype,
        "timestamp": iso(utcnow()),
        "total": total if total is not None else len(entries),
        "entry": [{"fullUrl": f"{e['resourceType']}/{e['id']}", "resource": e} for e in entries],
    }
    if self_link:
        out["link"] = [{"relation": "self", "url": self_link}]
    return out


def operation_outcome(severity: str, code: str, diagnostics: str) -> dict[str, Any]:
    return {"resourceType": "OperationOutcome", "issue": [{"severity": severity, "code": code, "diagnostics": diagnostics}]}


def validate_resource(res: dict[str, Any]) -> list[str]:
    """A deliberately small structural validator. It is not a replacement for the HL7 validator."""
    problems: list[str] = []
    rtype = res.get("resourceType")
    if not rtype:
        return ["resourceType is required"]
    if rtype not in SUPPORTED:
        problems.append(f"resourceType '{rtype}' is not supported by this server")
        return problems
    for field in REQUIRED.get(rtype, []):
        if field not in res:
            problems.append(f"{rtype}.{field} is required")
    if rtype == "Observation":
        if not any(k.startswith("value") for k in res) and "component" not in res and "dataAbsentReason" not in res:
            problems.append("Observation needs value[x], component or dataAbsentReason")
    for key in ("subject", "patient"):
        r = (res.get(key) or {}).get("reference")
        if r is not None and not (isinstance(r, str) and "/" in r):
            problems.append(f"{key}.reference must look like 'Patient/<id>'")
    return problems


def capability_statement(base: str) -> dict[str, Any]:
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": iso(utcnow()),
        "kind": "instance",
        "software": {"name": "Asclepius", "version": __version__},
        "implementation": {"description": "Asclepius synthetic FHIR server", "url": base},
        "fhirVersion": FHIR_VERSION,
        "format": ["application/fhir+json", "json"],
        "rest": [
            {
                "mode": "server",
                "security": {
                    "service": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/restful-security-service", "code": "SMART-on-FHIR"}]}],
                    "description": "OAuth2 authorization code flow with PKCE (S256); bearer tokens.",
                },
                "resource": [
                    {
                        "type": t,
                        "interaction": [{"code": "read"}, {"code": "search-type"}] + ([{"code": "create"}] if t in REQUIRED else []),
                        "searchParam": [{"name": p, "type": "token" if p in {"code", "gender", "status", "identifier"} else "string"} for p in SEARCH_PARAMS.get(t, [])],
                        **({"operation": [{"name": "everything", "definition": "http://hl7.org/fhir/OperationDefinition/Patient-everything"}]} if t == "Patient" else {}),
                    }
                    for t in SUPPORTED
                ],
            }
        ],
    }
