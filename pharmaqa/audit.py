"""Hash-chained audit log: every entry commits to the previous hash."""

from __future__ import annotations

import hashlib
import json
import time


class AuditLog:
    def __init__(self):
        self.entries: list[dict] = []

    def record(self, actor: str, action: str, details: dict | None = None) -> dict:
        prev = self.entries[-1]["hash"] if self.entries else "GENESIS"
        entry = {
            "seq": len(self.entries) + 1,
            "ts": time.time(),
            "actor": actor,
            "action": action,
            "details": details or {},
            "prev": prev,
        }
        entry["hash"] = hashlib.sha256(
            json.dumps(entry, sort_keys=True).encode()).hexdigest()
        self.entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        prev = "GENESIS"
        for e in self.entries:
            if e["prev"] != prev:
                return False
            h = e["hash"]
            check = dict(e)
            del check["hash"]
            if hashlib.sha256(json.dumps(check, sort_keys=True).encode()).hexdigest() != h:
                return False
            prev = h
        return True
