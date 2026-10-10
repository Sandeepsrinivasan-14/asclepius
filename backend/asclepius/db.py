"""A small thread-safe SQLite store for FHIR resources and the audit chain."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS resources (
  rtype TEXT NOT NULL,
  rid TEXT NOT NULL,
  patient TEXT,
  code TEXT,
  effective TEXT,
  status TEXT,
  body TEXT NOT NULL,
  PRIMARY KEY (rtype, rid)
);
CREATE INDEX IF NOT EXISTS idx_res_patient ON resources (rtype, patient);
CREATE INDEX IF NOT EXISTS idx_res_code ON resources (rtype, code);
CREATE TABLE IF NOT EXISTS audit (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  role TEXT NOT NULL,
  action TEXT NOT NULL,
  patient TEXT,
  resource TEXT,
  outcome TEXT NOT NULL,
  detail TEXT,
  break_glass INTEGER NOT NULL DEFAULT 0,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL
);
"""

GENESIS = "0" * 64


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ref_patient(res: dict[str, Any]) -> str | None:
    if res.get("resourceType") == "Patient":
        return res.get("id")
    for key in ("subject", "patient"):
        ref = (res.get(key) or {}).get("reference")
        if isinstance(ref, str) and ref.startswith("Patient/"):
            return ref.split("/", 1)[1]
    return None


def _first_code(res: dict[str, Any]) -> str | None:
    for key in ("code", "medicationCodeableConcept", "vaccineCode", "type"):
        cc = res.get(key)
        if isinstance(cc, dict):
            for coding in cc.get("coding", []):
                if coding.get("code"):
                    return str(coding["code"])
    return None


def _effective(res: dict[str, Any]) -> str | None:
    for key in ("effectiveDateTime", "authoredOn", "date", "issued", "recordedDate", "onsetDateTime", "created"):
        if res.get(key):
            return str(res[key])
    period = res.get("period") or {}
    return period.get("start")


class Store:
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)
        self._counters: dict[str, int] = {}

    # ---- resources -------------------------------------------------
    def next_id(self, rtype: str, prefix: str | None = None) -> str:
        with self.lock:
            n = self._counters.get(rtype, 0) + 1
            self._counters[rtype] = n
        return f"{prefix or rtype[:3].lower()}-{n:05d}"

    def put(self, res: dict[str, Any]) -> dict[str, Any]:
        rtype = res["resourceType"]
        if not res.get("id"):
            res["id"] = self.next_id(rtype)
        meta = res.setdefault("meta", {})
        meta["lastUpdated"] = iso(utcnow())
        row = (
            rtype,
            res["id"],
            _ref_patient(res),
            _first_code(res),
            _effective(res),
            res.get("status"),
            json.dumps(res, separators=(",", ":")),
        )
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO resources (rtype, rid, patient, code, effective, status, body) VALUES (?,?,?,?,?,?,?)",
                row,
            )
            self.conn.commit()
        return res

    def put_many(self, resources: Iterable[dict[str, Any]]) -> int:
        rows = []
        stamp = iso(utcnow())
        for res in resources:
            if not res.get("id"):
                res["id"] = self.next_id(res["resourceType"])
            res.setdefault("meta", {})["lastUpdated"] = stamp
            rows.append(
                (
                    res["resourceType"],
                    res["id"],
                    _ref_patient(res),
                    _first_code(res),
                    _effective(res),
                    res.get("status"),
                    json.dumps(res, separators=(",", ":")),
                )
            )
        with self.lock:
            self.conn.executemany(
                "INSERT OR REPLACE INTO resources (rtype, rid, patient, code, effective, status, body) VALUES (?,?,?,?,?,?,?)",
                rows,
            )
            self.conn.commit()
        return len(rows)

    def get(self, rtype: str, rid: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT body FROM resources WHERE rtype=? AND rid=?", (rtype, rid)).fetchone()
        return json.loads(row["body"]) if row else None

    def delete(self, rtype: str, rid: str) -> bool:
        with self.lock:
            cur = self.conn.execute("DELETE FROM resources WHERE rtype=? AND rid=?", (rtype, rid))
            self.conn.commit()
        return cur.rowcount > 0

    def search(
        self,
        rtype: str,
        *,
        patient: str | None = None,
        code: str | None = None,
        status: str | None = None,
        since: str | None = None,
        until: str | None = None,
        order: str = "asc",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = ["SELECT body FROM resources WHERE rtype=?"]
        args: list[Any] = [rtype]
        if patient:
            sql.append("AND patient=?")
            args.append(patient)
        if code:
            codes = code.split(",")
            sql.append(f"AND code IN ({','.join('?' * len(codes))})")
            args.extend(codes)
        if status:
            sql.append("AND status=?")
            args.append(status)
        if since:
            sql.append("AND effective>=?")
            args.append(since)
        if until:
            sql.append("AND effective<=?")
            args.append(until)
        sql.append(f"ORDER BY effective {'DESC' if order == 'desc' else 'ASC'}, rid")
        if limit is not None:
            sql.append("LIMIT ? OFFSET ?")
            args.extend([limit, offset])
        with self.lock:
            rows = self.conn.execute(" ".join(sql), args).fetchall()
        return [json.loads(r["body"]) for r in rows]

    def count(self, rtype: str, **kw: Any) -> int:
        return len(self.search(rtype, **kw))

    def all_of(self, rtype: str) -> list[dict[str, Any]]:
        return self.search(rtype)

    # ---- audit chain -----------------------------------------------
    @staticmethod
    def _entry_hash(prev: str, fields: dict[str, Any]) -> str:
        blob = json.dumps(fields, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256((prev + blob).encode()).hexdigest()

    def audit(
        self,
        *,
        actor: str,
        role: str,
        action: str,
        patient: str | None = None,
        resource: str | None = None,
        outcome: str = "ok",
        detail: str | None = None,
        break_glass: bool = False,
    ) -> dict[str, Any]:
        with self.lock:
            last = self.conn.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            prev = last["hash"] if last else GENESIS
            fields = {
                "ts": iso(utcnow()),
                "actor": actor,
                "role": role,
                "action": action,
                "patient": patient,
                "resource": resource,
                "outcome": outcome,
                "detail": detail,
                "break_glass": int(break_glass),
            }
            h = self._entry_hash(prev, fields)
            cur = self.conn.execute(
                "INSERT INTO audit (ts, actor, role, action, patient, resource, outcome, detail, break_glass, prev_hash, hash)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (*fields.values(), prev, h),
            )
            self.conn.commit()
            return {"seq": cur.lastrowid, **fields, "prev_hash": prev, "hash": h}

    def audit_rows(self, limit: int = 100, *, break_glass_only: bool = False, patient: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM audit"
        where, args = [], []
        if break_glass_only:
            where.append("break_glass=1")
        if patient:
            where.append("patient=?")
            args.append(patient)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY seq DESC LIMIT ?"
        args.append(limit)
        with self.lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def verify_audit(self) -> dict[str, Any]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM audit ORDER BY seq ASC").fetchall()
        prev = GENESIS
        for r in rows:
            fields = {k: r[k] for k in ("ts", "actor", "role", "action", "patient", "resource", "outcome", "detail", "break_glass")}
            if r["prev_hash"] != prev or self._entry_hash(prev, fields) != r["hash"]:
                return {"valid": False, "entries": len(rows), "broken_at": r["seq"]}
            prev = r["hash"]
        return {"valid": True, "entries": len(rows), "head": prev}
