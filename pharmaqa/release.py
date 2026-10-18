"""Batch-release sign-off chain.

A batch releases only when three roles sign off IN ORDER, each against
explicit, checkable criteria:

  1. qa_reviewer      — no open critical deviations on the batch
  2. qa_manager       — no overdue CAPAs linked to the batch's deviations
  3. qualified_person — batch record complete: no open deviations of any class

Each role's evaluation returns pass/fail with the criterion cited, so a
blocked release always names exactly what is missing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field


@dataclass
class RoleResult:
    role: str
    passed: bool
    criterion: str
    detail: str


@dataclass
class ReleaseDecision:
    batch_id: str
    released: bool
    roles: list[RoleResult] = field(default_factory=list)

    def blocking(self) -> list[RoleResult]:
        return [r for r in self.roles if not r.passed]


def _open_devs(conn: sqlite3.Connection, batch_id: str, classes=None) -> list[sqlite3.Row]:
    q = ("SELECT dev_id, dev_class FROM deviations "
         "WHERE batch_id = ? AND status IN ('open','investigating')")
    params: list = [batch_id]
    if classes:
        q += " AND dev_class IN (%s)" % ",".join("?" * len(classes))
        params += list(classes)
    return conn.execute(q, params).fetchall()


def _overdue_capas(conn: sqlite3.Connection, batch_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT c.capa_id FROM capas c
           JOIN deviations d ON d.dev_id = c.dev_id
           WHERE d.batch_id = ? AND c.status = 'overdue'""",
        (batch_id,)).fetchall()


def evaluate(conn: sqlite3.Connection, batch_id: str) -> ReleaseDecision:
    """Evaluate the full sign-off chain for a batch, in role order."""
    decision = ReleaseDecision(batch_id=batch_id, released=False)

    criticals = _open_devs(conn, batch_id, ["critical"])
    decision.roles.append(RoleResult(
        role="qa_reviewer",
        passed=not criticals,
        criterion="no open critical deviations",
        detail=("blocked by " + ", ".join(r["dev_id"] for r in criticals)
                if criticals else "no open critical deviations"),
    ))
    if criticals:
        # chain stops at the first failing role — later roles cannot sign
        # a batch whose reviewer gate failed
        return decision

    overdue = _overdue_capas(conn, batch_id)
    decision.roles.append(RoleResult(
        role="qa_manager",
        passed=not overdue,
        criterion="no overdue CAPAs linked to the batch's deviations",
        detail=("overdue: " + ", ".join(r["capa_id"] for r in overdue)
                if overdue else "all CAPAs on track"),
    ))
    if overdue:
        return decision

    remaining = _open_devs(conn, batch_id)
    decision.roles.append(RoleResult(
        role="qualified_person",
        passed=not remaining,
        criterion="batch record complete: no open deviations of any class",
        detail=("still open: " + ", ".join(r["dev_id"] for r in remaining)
                if remaining else "record complete"),
    ))
    decision.released = not remaining
    return decision
