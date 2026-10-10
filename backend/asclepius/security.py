"""Authentication, role/attribute-based access control, consent and break-glass.

Design notes
- Tokens are HMAC-SHA256 signed JSON (compact, stateless, expiring). Swap for a real IdP in production.
- Demo mode lets a persona sign in by username; set ASCLEPIUS_DEMO_AUTH=0 to disable it.
- Access is checked as: role permission -> attribute rule (care team / ward / restricted) -> break-glass grant.
- Every PHI decision, allowed or denied, is written to a SHA-256 hash-chained audit log.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import Settings
from .db import Store, iso

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "physician": {"patient:read", "patient:write", "notes:read", "copilot:use", "coding:use", "scribe:use", "medrec:use", "handoff:read",
                  "monitor:read", "warning:read", "portal:read", "imaging:read", "fhir:read", "fhir:write", "ops:read", "governance:feedback",
                  "interop:use", "break_glass"},
    "nurse": {"patient:read", "notes:read", "handoff:read", "monitor:read", "warning:read", "portal:read", "medrec:read", "coding:read",
              "fhir:read", "ops:read", "interop:use", "break_glass"},
    "pharmacist": {"patient:read", "medrec:use", "medrec:read", "fhir:read", "ops:read"},
    "admin": {"ops:read", "governance:read", "users:read", "interop:use", "imaging:read"},
    "privacy_officer": {"audit:read", "access:review", "governance:read", "ops:read", "users:read"},
}
# every authenticated role may read governance metrics that contain no PHI
for _r in ("physician", "nurse", "pharmacist"):
    ROLE_PERMISSIONS[_r].add("governance:read")
ROLE_PERMISSIONS["physician"].add("imaging:read")
ROLE_PERMISSIONS["nurse"].add("imaging:read")

USERS: dict[str, dict[str, Any]] = {
    "dr.rao": {"name": "Dr. Meera Rao", "role": "physician", "practitioner": "prac-rao", "title": "Attending, Internal Medicine"},
    "dr.chandran": {"name": "Dr. Arvind Chandran", "role": "physician", "practitioner": "prac-chandran", "title": "Attending, Cardiology"},
    "dr.fernandes": {"name": "Dr. Lena Fernandes", "role": "physician", "practitioner": "prac-fernandes", "title": "Attending, Neurology"},
    "nurse.devi": {"name": "Devi Subramanian, RN", "role": "nurse", "practitioner": "prac-devi", "wards": ["ICU", "CCU"], "title": "Charge nurse, ICU and CCU"},
    "nurse.meena": {"name": "Meena Joseph, RN", "role": "nurse", "practitioner": "prac-meena", "wards": ["MED", "NEURO"], "title": "Staff nurse, Medicine and Neurology"},
    "pharm.iyer": {"name": "Ramesh Iyer, PharmD", "role": "pharmacist", "practitioner": "prac-iyer", "title": "Clinical pharmacist"},
    "admin.kumar": {"name": "Sanjay Kumar", "role": "admin", "title": "Hospital operations administrator"},
    "auditor.menon": {"name": "Nandini Menon", "role": "privacy_officer", "title": "Privacy and compliance officer"},
}


class AccessDenied(Exception):
    def __init__(self, code: str, message: str, status: int = 403):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class Principal:
    username: str
    name: str
    role: str
    practitioner: str | None = None
    wards: list[str] = field(default_factory=list)
    title: str = ""
    scopes: list[str] | None = None  # SMART scopes, None for first-party app tokens
    patient_ctx: str | None = None

    def public(self) -> dict[str, Any]:
        return {"username": self.username, "name": self.name, "role": self.role, "title": self.title, "wards": self.wards,
                "permissions": sorted(ROLE_PERMISSIONS.get(self.role, set())), "scopes": self.scopes, "patient_context": self.patient_ctx}


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class Security:
    def __init__(self, store: Store, settings: Settings) -> None:
        self.store, self.settings = store, settings
        self.grants: dict[tuple[str, str], datetime] = {}
        self.reviews: list[dict[str, Any]] = []
        self.codes: dict[str, dict[str, Any]] = {}
        self.attrs: dict[str, dict[str, Any]] = {}
        self.refresh_attributes()

    # ---------------------------------------------------------- attributes
    def refresh_attributes(self) -> None:
        enc_ward: dict[str, str] = {}
        for e in self.store.search("Encounter", status="in-progress"):
            pid = e["subject"]["reference"].split("/")[1]
            loc = (e.get("location") or [{}])[0]
            bed = (loc.get("physicalType") or {}).get("text", "")
            enc_ward[pid] = bed.split("-")[0] if bed else ""
        for p in self.store.all_of("Patient"):
            gp = [g["reference"].split("/")[1] for g in p.get("generalPractitioner", [])]
            restricted = any(s.get("code") == "R" for s in (p.get("meta") or {}).get("security", []))
            self.attrs[p["id"]] = {"attending": gp, "ward": enc_ward.get(p["id"]), "restricted": restricted}

    # ---------------------------------------------------------- tokens
    def issue(self, principal: Principal, *, ttl: int | None = None) -> str:
        payload = {"sub": principal.username, "exp": int(time.time()) + (ttl or self.settings.token_ttl_s), "scope": principal.scopes, "patient": principal.patient_ctx, "jti": secrets.token_hex(4)}
        body = _b64(json.dumps(payload, separators=(",", ":")).encode())
        sig = _b64(hmac.new(self.settings.secret.encode(), body.encode(), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def verify(self, token: str) -> Principal:
        try:
            body, sig = token.split(".", 1)
            expect = _b64(hmac.new(self.settings.secret.encode(), body.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(sig, expect):
                raise ValueError("bad signature")
            payload = json.loads(_unb64(body))
        except (ValueError, json.JSONDecodeError) as exc:
            raise AccessDenied("invalid_token", "Invalid or malformed token.", 401) from exc
        if payload["exp"] < time.time():
            raise AccessDenied("token_expired", "Token expired. Sign in again.", 401)
        user = USERS.get(payload["sub"])
        if not user:
            raise AccessDenied("invalid_token", "Unknown subject.", 401)
        return self._principal(payload["sub"], scopes=payload.get("scope"), patient=payload.get("patient"))

    def _principal(self, username: str, *, scopes: list[str] | None = None, patient: str | None = None) -> Principal:
        u = USERS[username]
        return Principal(username=username, name=u["name"], role=u["role"], practitioner=u.get("practitioner"), wards=u.get("wards", []),
                         title=u.get("title", ""), scopes=scopes, patient_ctx=patient)

    def login(self, username: str, password: str | None = None) -> tuple[str, Principal]:
        if username not in USERS:
            self.store.audit(actor=username, role="unknown", action="auth.login", outcome="denied", detail="unknown user")
            raise AccessDenied("invalid_credentials", "Unknown user.", 401)
        if not self.settings.demo_auth:
            self.store.audit(actor=username, role=USERS[username]["role"], action="auth.login", outcome="denied", detail="demo auth disabled")
            raise AccessDenied("demo_auth_disabled", "Demo sign-in is disabled; configure an identity provider.", 401)
        p = self._principal(username)
        self.store.audit(actor=username, role=p.role, action="auth.login")
        return self.issue(p), p

    # ---------------------------------------------------------- policy
    def has(self, principal: Principal, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(principal.role, set())

    def require(self, principal: Principal, permission: str) -> None:
        if not self.has(principal, permission):
            self.store.audit(actor=principal.username, role=principal.role, action=permission, outcome="denied", detail="role not permitted")
            raise AccessDenied("role_not_permitted", f"Role '{principal.role}' is not permitted to perform '{permission}'.")

    def _active_grant(self, username: str, pid: str) -> bool:
        exp = self.grants.get((username, pid))
        return bool(exp and exp > datetime.now(timezone.utc))

    def can_access_patient(self, principal: Principal, pid: str) -> tuple[bool, str]:
        """Return (allowed, reason) without raising or auditing. reason in {care_team, ward, pharmacy, break_glass, ...}."""
        a = self.attrs.get(pid)
        if a is None:
            return False, "not_found"
        if principal.patient_ctx and principal.patient_ctx != pid:
            return False, "smart_context"
        if principal.role == "pharmacist":
            return (not a["restricted"], "pharmacy" if not a["restricted"] else "restricted")
        if principal.role == "physician":
            if principal.practitioner in a["attending"]:
                return True, "care_team"
        elif principal.role == "nurse":
            if a["ward"] in principal.wards and not a["restricted"]:
                return True, "ward"
        else:
            return False, "role"
        if self._active_grant(principal.username, pid):
            return True, "break_glass"
        return False, "restricted" if a["restricted"] else "no_relationship"

    def authorize_patient(self, principal: Principal, permission: str, pid: str, *, resource: str | None = None, detail: str | None = None) -> str:
        self.require(principal, permission)
        ok, reason = self.can_access_patient(principal, pid)
        if reason == "not_found":
            raise AccessDenied("not_found", f"Patient/{pid} not found.", 404)
        bg = reason == "break_glass"
        if not ok:
            self.store.audit(actor=principal.username, role=principal.role, action=permission, patient=pid, resource=resource, outcome="denied", detail=reason)
            if self.has(principal, "break_glass") and reason in ("no_relationship", "restricted"):
                raise AccessDenied("break_glass_required", "No treating relationship with this patient. Emergency (break-glass) access is available with a documented reason.")
            raise AccessDenied("patient_access_denied", "You do not have access to this patient's record.")
        self.store.audit(actor=principal.username, role=principal.role, action=permission, patient=pid, resource=resource, detail=detail, break_glass=bg)
        return reason

    def visible_patients(self, principal: Principal) -> list[str]:
        return [pid for pid in self.attrs if self.can_access_patient(principal, pid)[0]]

    def listed_patients(self, principal: Principal) -> list[str]:
        """Patients shown in lists: accessible ones (no discovery of inaccessible records)."""
        return self.visible_patients(principal)

    # ---------------------------------------------------------- break glass
    def break_glass(self, principal: Principal, pid: str, reason: str) -> dict[str, Any]:
        self.require(principal, "break_glass")
        if pid not in self.attrs:
            raise AccessDenied("not_found", f"Patient/{pid} not found.", 404)
        reason = (reason or "").strip()
        if len(reason) < 15:
            raise AccessDenied("reason_required", "A documented clinical reason (at least 15 characters) is required for break-glass access.", 422)
        exp = datetime.now(timezone.utc) + timedelta(minutes=self.settings.break_glass_minutes)
        self.grants[(principal.username, pid)] = exp
        entry = self.store.audit(actor=principal.username, role=principal.role, action="access.break_glass", patient=pid, detail=reason, break_glass=True)
        rev = {"id": str(uuid.uuid4())[:8], "user": principal.username, "name": principal.name, "patient": pid, "reason": reason, "granted_at": iso(datetime.now(timezone.utc)),
               "expires": iso(exp), "status": "open", "reviewer": None, "note": None, "audit_seq": entry["seq"]}
        self.reviews.append(rev)
        return rev

    def review(self, principal: Principal, rid: str, decision: str, note: str = "") -> dict[str, Any]:
        self.require(principal, "access:review")
        if decision not in ("justified", "inappropriate"):
            raise AccessDenied("bad_request", "decision must be 'justified' or 'inappropriate'.", 422)
        for r in self.reviews:
            if r["id"] == rid:
                r.update(status=decision, reviewer=principal.username, note=note)
                self.store.audit(actor=principal.username, role=principal.role, action="access.review", patient=r["patient"], detail=f"{rid}:{decision}")
                return r
        raise AccessDenied("not_found", "Review item not found.", 404)

    # ---------------------------------------------------------- SMART on FHIR (mock)
    def smart_authorize(self, *, username: str, client_id: str, redirect_uri: str, scope: str, challenge: str, method: str, patient: str | None) -> str:
        if method != "S256":
            raise AccessDenied("invalid_request", "code_challenge_method must be S256.", 400)
        if username not in USERS:
            raise AccessDenied("access_denied", "Unknown user.", 401)
        code = secrets.token_urlsafe(24)
        self.codes[code] = {"username": username, "client_id": client_id, "redirect_uri": redirect_uri, "scope": scope.split(), "challenge": challenge,
                            "patient": patient, "exp": time.time() + 120}
        self.store.audit(actor=username, role=USERS[username]["role"], action="smart.authorize", detail=f"client={client_id} scope={scope}")
        return code

    def smart_token(self, *, code: str, verifier: str, client_id: str, redirect_uri: str) -> dict[str, Any]:
        item = self.codes.pop(code, None)
        if not item or item["exp"] < time.time():
            raise AccessDenied("invalid_grant", "Authorization code invalid or expired.", 400)
        if item["client_id"] != client_id or item["redirect_uri"] != redirect_uri:
            raise AccessDenied("invalid_grant", "client_id or redirect_uri mismatch.", 400)
        digest = _b64(hashlib.sha256(verifier.encode()).digest())
        if not hmac.compare_digest(digest, item["challenge"]):
            raise AccessDenied("invalid_grant", "PKCE verification failed.", 400)
        p = self._principal(item["username"], scopes=item["scope"], patient=item["patient"])
        token = self.issue(p, ttl=3600)
        out = {"access_token": token, "token_type": "Bearer", "expires_in": 3600, "scope": " ".join(item["scope"])}
        if item["patient"]:
            out["patient"] = item["patient"]
        return out

    @staticmethod
    def scope_allows(principal: Principal, rtype: str, action: str = "read") -> bool:
        if principal.scopes is None:
            return True
        for s in principal.scopes:
            if "/" not in s or "." not in s:
                continue
            ctx, rest = s.split("/", 1)
            res, perm = rest.rsplit(".", 1)
            if ctx not in ("patient", "user"):
                continue
            if res in ("*", rtype) and perm in ("*", action, "rs" if action == "read" else action):
                return True
        return False
