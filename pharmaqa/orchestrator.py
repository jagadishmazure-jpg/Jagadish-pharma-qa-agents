"""ReAct-style orchestrator: plans, fans out to tools, audits every turn."""

from __future__ import annotations

import sqlite3

from .audit import AuditLog
from .classify import classify
from .escalation import ConfirmationGate, tier_for
from .regsignal import FakeRegFeed, GapError
from .release import evaluate
from .sop_rag import SopRetriever
from .text2sql import EscalationNeeded, answer


class Orchestrator:
    def __init__(self, conn: sqlite3.Connection, retriever: SopRetriever,
                 audit: AuditLog | None = None):
        self.conn = conn
        self.retriever = retriever
        self.audit = audit or AuditLog()
        self.gate = ConfirmationGate()
        self.feed = FakeRegFeed()

    def _intents(self, question: str) -> list[str]:
        """Detect possibly multiple intents for fan-out."""
        q = question.lower()
        found = []
        if any(k in q for k in ("deviation", "critical", "major", "minor", "class")):
            found.append("deviations")
        if any(k in q for k in ("batch", "release", "sign")):
            found.append("release")
        if any(k in q for k in ("capa", "corrective", "overdue")):
            found.append("capa")
        if any(k in q for k in ("audit", "inspection", "ready")):
            found.append("audit")
        if any(k in q for k in ("sop", "procedure", "guideline", "how do")):
            found.append("sop")
        if any(k in q for k in ("regulat", "guidance update", "annex")):
            found.append("regulatory")
        return found or ["sop"]

    def ask(self, question: str, session_id: str = "demo") -> dict:
        turn = {"question": question, "steps": []}
        for intent in self._intents(question):
            step = {"intent": intent}
            try:
                if intent == "deviations":
                    step["result"] = answer(self.conn, "open deviations by class")["rows"]
                elif intent == "release":
                    dec = evaluate(self.conn, self._batch_from(question))
                    step["result"] = {
                        "batch": dec.batch_id, "released": dec.released,
                        "roles": [(r.role, r.passed, r.detail) for r in dec.roles],
                    }
                elif intent == "capa":
                    step["result"] = answer(self.conn, "capa backlog")["rows"]
                elif intent == "audit":
                    step["result"] = answer(self.conn, "audit readiness")["rows"]
                elif intent == "regulatory":
                    try:
                        step["result"] = [u.__dict__ for u in self.feed.latest()]
                    except GapError as e:
                        step["result"] = {"gap": str(e)}
                else:
                    step["result"] = self.retriever.answer(question)
            except EscalationNeeded as e:
                tier = tier_for("query", "major")
                step["result"] = {"escalated": str(e), "tier": tier.name}
            turn["steps"].append(step)
        self.audit.record("agent", "ask",
                          {"session": session_id, "q": question,
                           "intents": [s["intent"] for s in turn["steps"]]})
        return turn

    @staticmethod
    def _batch_from(question: str) -> str:
        import re
        m = re.search(r"BATCH-\d{4}-\d+", question.upper())
        return m.group(0) if m else "BATCH-2026-0142"

    def classify_deviation(self, title: str, description: str) -> dict:
        c = classify(title, description)
        self.audit.record("agent", "classify",
                          {"title": title, "class": c.dev_class, "rule": c.rule_id})
        return {"class": c.dev_class, "rule_id": c.rule_id,
                "rule": c.rule_text, "evidence": c.evidence}
