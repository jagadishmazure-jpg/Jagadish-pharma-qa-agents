"""User feedback capture with PII scrubbing before storage."""

from __future__ import annotations

from dataclasses import dataclass, field
import time

from .audit import AuditLog
from .pii import scrub


class FeedbackError(Exception):
    pass


@dataclass
class Feedback:
    session_id: str
    turn_id: str
    rating: str            # "up" | "down"
    correction: str = ""   # scrubbed
    redactions: int = 0
    ts: float = field(default_factory=time.time)


def record_feedback(audit: AuditLog, session_id: str, turn_id: str,
                    rating: str, correction: str = "") -> Feedback:
    if not session_id.strip() or not turn_id.strip():
        raise FeedbackError("session_id and turn_id are required")
    if rating not in ("up", "down"):
        raise FeedbackError("rating must be 'up' or 'down'")
    if rating == "down" and not correction.strip():
        raise FeedbackError("thumbs-down requires a non-blank correction")
    clean, n = scrub(correction)
    fb = Feedback(session_id=session_id, turn_id=turn_id, rating=rating,
                  correction=clean, redactions=n)
    audit.record("user", "user_feedback",
                 {"session": session_id, "turn": turn_id, "rating": rating,
                  "correction": clean, "redactions": n})
    return fb


def list_feedback(audit: AuditLog, session_id: str = "") -> list[dict]:
    out = []
    for e in audit.entries:
        if e["action"] == "user_feedback":
            if not session_id or e["details"]["session"] == session_id:
                out.append(e["details"])
    return out
