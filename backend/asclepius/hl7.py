"""HL7 v2 ingestion pipeline: parse, validate, de-duplicate, queue, retry with backoff, dead-letter, map to FHIR."""

from __future__ import annotations

import re
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from . import terminology as T
from .db import Store, iso, utcnow
from .fhir import codeable, ref

MAX_ATTEMPTS = 3
SEG_SPLIT = re.compile(r"\r\n|\r|\n")


class HL7Error(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass
class Segment:
    name: str
    parts: list[str]

    def f(self, n: int) -> str:
        """Field n (1-based, HL7 convention; MSH-1 is the field separator)."""
        if self.name == "MSH":
            return "|" if n == 1 else (self.parts[n - 1] if n - 1 < len(self.parts) else "")
        return self.parts[n] if n < len(self.parts) else ""

    def c(self, n: int, comp: int) -> str:
        parts = self.f(n).split("^")
        return parts[comp - 1] if comp - 1 < len(parts) else ""


@dataclass
class Message:
    raw: str
    segments: list[Segment]

    def seg(self, name: str) -> Segment | None:
        return next((s for s in self.segments if s.name == name), None)

    def all(self, name: str) -> list[Segment]:
        return [s for s in self.segments if s.name == name]

    @property
    def type(self) -> str:
        msh = self.seg("MSH")
        return msh.f(9).replace("^", "^") if msh else ""

    @property
    def control_id(self) -> str:
        msh = self.seg("MSH")
        return msh.f(10) if msh else ""


def parse(raw: str) -> Message:
    text = raw.strip("\x0b\x1c \r\n\t")
    if not text.startswith("MSH|"):
        raise HL7Error("MSH_MISSING", "Message must start with an MSH segment using '|' as field separator.")
    segs = []
    for line in SEG_SPLIT.split(text):
        if not line.strip():
            continue
        parts = line.split("|")
        name = parts[0]
        if not re.fullmatch(r"[A-Z][A-Z0-9]{2}", name):
            raise HL7Error("BAD_SEGMENT", f"Invalid segment id '{name[:8]}'.")
        segs.append(Segment(name, parts))
    msg = Message(raw=text, segments=segs)
    if not msg.control_id:
        raise HL7Error("CONTROL_ID_MISSING", "MSH-10 (message control id) is required.")
    if not msg.type or "^" not in msg.type:
        raise HL7Error("TYPE_MISSING", "MSH-9 must carry message type and trigger event, e.g. ORU^R01.")
    return msg


def hl7_ts(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    for fmt, n in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12), ("%Y%m%d", 8)):
        if len(value) >= n and value[:n].isdigit():
            return iso(datetime.strptime(value[:n], fmt).replace(tzinfo=timezone.utc))
    return None


def ack(msg: Message | None, code: str, text: str, error: str | None = None) -> str:
    ts = utcnow().strftime("%Y%m%d%H%M%S")
    app = msg.seg("MSH").f(3) if msg and msg.seg("MSH") else ""
    fac = msg.seg("MSH").f(4) if msg and msg.seg("MSH") else ""
    cid = msg.control_id if msg else ""
    event = msg.type.split("^")[1] if msg and "^" in msg.type else "UNK"
    out = f"MSH|^~\\&|ASCLEPIUS|ASCLEPIUS|{app}|{fac}|{ts}||ACK^{event}|ACK{int(time.time() * 1000) % 10**9}|P|2.5.1\rMSA|{code}|{cid}|{text}"
    if error:
        out += f"\rERR||||{error}"
    return out


@dataclass
class Job:
    id: int
    msg: Message
    attempts: int = 0
    last_error: str = ""
    status: str = "queued"  # queued | done | dead
    due_at: float = 0.0
    history: list[str] = field(default_factory=list)


class Pipeline:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.seen: set[str] = set()
        self.queue: deque[Job] = deque()
        self.dlq: list[Job] = []
        self.done: list[Job] = []
        self.stats: Counter[str] = Counter()
        self.counter = 0

    # --------------------------------------------------------- receive
    def receive(self, raw: str) -> str:
        self.stats["received"] += 1
        try:
            msg = parse(raw)
        except HL7Error as exc:
            self.stats["rejected"] += 1
            return ack(None, "AR", exc.message, f"{exc.code}")
        if msg.type.split("^")[0] not in ("ORU", "ADT"):
            self.stats["rejected"] += 1
            return ack(msg, "AR", f"Unsupported message type {msg.type}", "UNSUPPORTED_TYPE")
        key = f"{msg.seg('MSH').f(3)}|{msg.seg('MSH').f(4)}|{msg.control_id}"
        if key in self.seen:
            self.stats["duplicates"] += 1
            return ack(msg, "AA", "Duplicate control id: already accepted, ignored (idempotent)")
        self.seen.add(key)
        self.counter += 1
        self.queue.append(Job(self.counter, msg))
        self.stats["accepted"] += 1
        return ack(msg, "AA", "Accepted for processing")

    # --------------------------------------------------------- process
    def process(self, *, respect_backoff: bool = False, max_passes: int = 1) -> dict[str, int]:
        processed = failed = 0
        for _ in range(max_passes):
            batch = list(self.queue)
            self.queue.clear()
            for job in batch:
                if respect_backoff and job.due_at > time.time():
                    self.queue.append(job)
                    continue
                job.attempts += 1
                try:
                    note = self._apply(job.msg)
                    job.status = "done"
                    job.history.append(f"attempt {job.attempts}: ok ({note})")
                    self.done.append(job)
                    self.stats["processed"] += 1
                    processed += 1
                except HL7Error as exc:
                    job.last_error = f"{exc.code}: {exc.message}"
                    job.history.append(f"attempt {job.attempts}: {job.last_error}")
                    failed += 1
                    if job.attempts >= MAX_ATTEMPTS:
                        job.status = "dead"
                        self.dlq.append(job)
                        self.stats["dead_lettered"] += 1
                    else:
                        job.due_at = time.time() + 2 ** job.attempts
                        self.queue.append(job)
                        self.stats["retries"] += 1
        return {"processed": processed, "failed_attempts": failed, "queued": len(self.queue), "dead": len(self.dlq)}

    def replay(self, job_id: int) -> bool:
        for j in list(self.dlq):
            if j.id == job_id:
                self.dlq.remove(j)
                j.status, j.attempts, j.due_at = "queued", 0, 0.0
                j.history.append("replayed from dead-letter queue")
                self.queue.append(j)
                return True
        return False

    # --------------------------------------------------------- mapping
    def _find_patient(self, pid_seg: Segment) -> dict[str, Any] | None:
        idents = {pid_seg.f(3).split("^")[0], *(x.split("^")[0] for x in pid_seg.f(3).split("~"))}
        for p in self.store.all_of("Patient"):
            for i in p.get("identifier", []):
                if i.get("value") in idents:
                    return p
        return None

    def _apply(self, msg: Message) -> str:
        kind, event = msg.type.split("^")[:2]
        pid_seg = msg.seg("PID")
        if not pid_seg:
            raise HL7Error("PID_MISSING", "PID segment is required.")
        if kind == "ORU":
            return self._oru(msg, pid_seg)
        if event in ("A01", "A04"):
            return self._admit(msg, pid_seg)
        if event == "A03":
            return self._discharge(msg, pid_seg)
        raise HL7Error("UNSUPPORTED_EVENT", f"No mapping for {msg.type}.")

    def _oru(self, msg: Message, pid_seg: Segment) -> str:
        patient = self._find_patient(pid_seg)
        if not patient:
            raise HL7Error("PATIENT_NOT_FOUND", f"No patient with identifier {pid_seg.f(3).split('^')[0]} yet (an ADT message may be late).")
        obr = msg.seg("OBR")
        base_time = hl7_ts(obr.f(7)) if obr else None
        made = 0
        for obx in msg.all("OBX"):
            code, name = obx.c(3, 1), obx.c(3, 2)
            if not code:
                raise HL7Error("OBX_CODE_MISSING", "OBX-3 observation identifier is required.")
            res: dict[str, Any] = {"resourceType": "Observation", "status": "final", "category": [codeable("http://terminology.hl7.org/CodeSystem/observation-category", "laboratory", "Laboratory")],
                                   "code": {"coding": [{"system": T.SYS_LOINC if obx.c(3, 3) in ("LN", "") else T.SYS_LOCAL, "code": code, "display": name or code}], "text": name or code},
                                   "subject": ref("Patient", patient["id"]), "effectiveDateTime": hl7_ts(obx.f(14)) or base_time or iso(utcnow()),
                                   "extension": [{"url": "https://asclepius.example/ext/source", "valueString": f"HL7v2 {msg.control_id}"}]}
            value = obx.f(5)
            if obx.f(2) == "NM":
                try:
                    res["valueQuantity"] = {"value": float(value), "unit": obx.c(6, 1), "system": T.SYS_UCUM, "code": obx.c(6, 1)}
                except ValueError as exc:
                    raise HL7Error("OBX_VALUE_INVALID", f"OBX-5 '{value}' is not numeric for type NM.") from exc
            else:
                res["valueString"] = value
            if obx.f(7):
                res["referenceRange"] = [{"text": obx.f(7)}]
            flag = obx.f(8)
            if flag:
                res["interpretation"] = [codeable("http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", flag, {"H": "High", "L": "Low", "HH": "Critical high", "LL": "Critical low", "N": "Normal"}.get(flag, flag))]
            self.store.put(res)
            made += 1
        if not made:
            raise HL7Error("OBX_MISSING", "ORU^R01 carried no OBX segments.")
        return f"{made} Observation(s) for {patient['id']}"

    def _admit(self, msg: Message, pid_seg: Segment) -> str:
        patient = self._find_patient(pid_seg)
        created = False
        if not patient:
            name = pid_seg.f(5).split("^")
            dob = hl7_ts(pid_seg.f(7))
            sex = {"M": "male", "F": "female"}.get(pid_seg.f(8).upper(), "unknown")
            ident = pid_seg.f(3).split("^")[0]
            patient = self.store.put({"resourceType": "Patient", "id": self.store.next_id("Patient", "pat-hl7"), "meta": {"tag": [{"system": "https://asclepius.example/tags", "code": "synthetic"}]},
                                      "identifier": [{"system": "https://asclepius.example/mrn", "value": ident, "type": {"text": "MRN"}}], "active": True,
                                      "name": [{"family": name[0], "given": [name[1]] if len(name) > 1 else [], "text": f"{name[1] if len(name) > 1 else ''} {name[0]}".strip()}],
                                      "gender": sex, "birthDate": (dob or "1970-01-01")[:10]})
            created = True
        pv1 = msg.seg("PV1")
        loc = pv1.f(3).split("^") if pv1 else [""]
        enc = {"resourceType": "Encounter", "status": "in-progress", "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": (pv1.f(2) if pv1 else "I") or "I"},
               "subject": ref("Patient", patient["id"]), "period": {"start": (hl7_ts(pv1.f(44)) if pv1 else None) or iso(utcnow())}}
        if loc[0]:
            enc["location"] = [{"location": {"display": loc[0]}, "physicalType": {"text": loc[1] if len(loc) > 1 and loc[1] else loc[0]}}]
        self.store.put(enc)
        return f"Encounter {enc['id']} for {patient['id']}" + (" (patient registered)" if created else "")

    def _discharge(self, msg: Message, pid_seg: Segment) -> str:
        patient = self._find_patient(pid_seg)
        if not patient:
            raise HL7Error("PATIENT_NOT_FOUND", "Cannot discharge an unknown patient.")
        encs = self.store.search("Encounter", patient=patient["id"], status="in-progress")
        if not encs:
            raise HL7Error("NO_ACTIVE_ENCOUNTER", "No in-progress encounter to discharge.")
        pv1 = msg.seg("PV1")
        encs[0]["status"] = "finished"
        encs[0].setdefault("period", {})["end"] = (hl7_ts(pv1.f(45)) if pv1 else None) or iso(utcnow())
        self.store.put(encs[0])
        return f"Encounter {encs[0]['id']} finished"

    # --------------------------------------------------------- views
    def snapshot(self) -> dict[str, Any]:
        def row(j: Job) -> dict[str, Any]:
            return {"id": j.id, "type": j.msg.type, "control_id": j.msg.control_id, "attempts": j.attempts, "status": j.status, "last_error": j.last_error, "history": j.history}
        return {"stats": dict(self.stats), "queued": [row(j) for j in self.queue], "dead_letter": [row(j) for j in self.dlq], "recent": [row(j) for j in self.done[-10:]],
                "max_attempts": MAX_ATTEMPTS}


def demo_messages(existing_mrn: str, existing_name: str = "") -> list[dict[str, str]]:
    ts = utcnow().strftime("%Y%m%d%H%M%S")

    def oru(cid: str, mrn: str, name: str, code: str, label: str, val: str, unit: str, rng: str, flag: str) -> str:
        return (f"MSH|^~\\&|LIS|LAB1|ASCLEPIUS|HOSP|{ts}||ORU^R01|{cid}|P|2.5.1\rPID|1||{mrn}^^^HOSP^MR||{name}||19700101|M\r"
                f"OBR|1||ORD{cid}|{code}^{label}^LN|||{ts}\rOBX|1|NM|{code}^{label}^LN||{val}|{unit}|{rng}|{flag}|||F|||{ts}")

    return [
        {"label": "Valid creatinine result for an existing patient", "raw": oru("DEMO-1001", existing_mrn, existing_name or "TEST^PATIENT", "2160-0", "Creatinine", "1.9", "mg/dL", "0.6-1.3", "H")},
        {"label": "Exact duplicate of the first message (idempotency)", "raw": oru("DEMO-1001", existing_mrn, existing_name or "TEST^PATIENT", "2160-0", "Creatinine", "1.9", "mg/dL", "0.6-1.3", "H")},
        {"label": "Result arrives BEFORE the admission (out of order: will retry)", "raw": oru("DEMO-1002", "MRN-DEMO-77", "ROY^ASHOK", "718-7", "Hemoglobin", "9.1", "g/dL", "13.0-17.0", "L")},
        {"label": "Admission for the new patient (unblocks the retry)", "raw": f"MSH|^~\\&|ADT|HOSP1|ASCLEPIUS|HOSP|{ts}||ADT^A01|DEMO-1003|P|2.5.1\rPID|1||MRN-DEMO-77^^^HOSP^MR||ROY^ASHOK||19620412|M\rPV1|1|I|MED^MED-90^1"},
        {"label": "Malformed message (rejected)", "raw": "PID|1||X\rOBX|1|NM"},
        {"label": "Result for a patient who never arrives (dead-letter)", "raw": oru("DEMO-1004", "MRN-GHOST-1", "GHOST^NOBODY", "2951-2", "Sodium", "128", "mmol/L", "135-145", "L")},
        {"label": "Non-numeric value in a numeric field (dead-letter)", "raw": oru("DEMO-1005", existing_mrn, existing_name or "TEST^PATIENT", "2823-3", "Potassium", "five", "mmol/L", "3.5-5.1", "H")},
    ]
