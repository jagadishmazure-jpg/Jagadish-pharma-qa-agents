"""Batch-release sign-off chain.

A batch releases only when three roles sign off IN ORDER, each against
explicit, checkable criteria:

  1. qa_reviewer      — no open critical deviations on the batch
  2. qa_manager       — no overdue CAPAs linked to the batch's deviations
  3. qualified_person — batch record complete: no open deviations of any class

A role passes only when its criterion holds AND an "approved" sign-off by
that role is recorded, dated no earlier than the previous role's. Criteria
alone never release a batch. Unknown and rejected batches never release.
CAPAs count as overdue by status or by due date (``AS_OF``).

Each role's evaluation returns pass/fail with the criterion cited, so a
blocked release always names exactly what is missing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

AS_OF = "2026-10-18"  # same "today" as the views in views.py
ROLES = ("qa_reviewer", "qa_manager", "qualified_person")


@dataclass
class RoleResult:
    role: str
    passed: bool
    criterion: str
    detail: str
    signed_by: str = ""


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


def _overdue_capas(conn: sqlite3.Connection, batch_id: str, as_of: str = AS_OF) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT c.capa_id FROM capas c
           JOIN deviations d ON d.dev_id = c.dev_id
           WHERE d.batch_id = ?
             AND (c.status = 'overdue' OR (c.status <> 'closed' AND c.due_date < ?))""",
        (batch_id, as_of)).fetchall()


def _signoff(conn: sqlite3.Connection, batch_id: str, role: str):
    """Latest recorded sign-off for a role, or None."""
    return conn.execute(
        "SELECT approver, decision, decided_on FROM signoffs "
        "WHERE batch_id = ? AND role = ? ORDER BY decided_on DESC LIMIT 1",
        (batch_id, role)).fetchone()


def _gate(conn, batch_id, role, criterion, ok, fail_detail, prev_date):
    """Criterion first, then the recorded signature. Returns (RoleResult, date)."""
    if not ok:
        return RoleResult(role, False, criterion, fail_detail), None
    so = _signoff(conn, batch_id, role)
    if so is None or so[1] != "approved" or not so[2]:
        state = "rejected by " + so[0] if so is not None and so[1] == "rejected" else "awaiting signature"
        return RoleResult(role, False, criterion, f"criterion met; {state}"), None
    if prev_date and so[2] < prev_date:
        return RoleResult(role, False, criterion,
                          f"signed {so[2]}, before the previous role ({prev_date})"), None
    return RoleResult(role, True, criterion, f"signed by {so[0]} on {so[2]}", signed_by=so[0]), so[2]


def evaluate(conn: sqlite3.Connection, batch_id: str, as_of: str = AS_OF) -> ReleaseDecision:
    """Evaluate the full sign-off chain for a batch, in role order.

    The chain stops at the first failing role: later roles cannot sign a
    batch whose earlier gate failed.
    """
    decision = ReleaseDecision(batch_id=batch_id, released=False)
    row = conn.execute("SELECT status FROM batches WHERE batch_id = ?", (batch_id,)).fetchone()
    if row is None or row[0] == "rejected":
        decision.roles.append(RoleResult(
            role="qa_reviewer", passed=False, criterion="batch exists and is not rejected",
            detail="unknown batch" if row is None else "batch was rejected"))
        return decision

    criticals = _open_devs(conn, batch_id, ["critical"])
    result, prev = _gate(conn, batch_id, "qa_reviewer", "no open critical deviations",
                         not criticals, "blocked by " + ", ".join(r[0] for r in criticals), None)
    decision.roles.append(result)
    if not result.passed:
        return decision

    overdue = _overdue_capas(conn, batch_id, as_of)
    result, prev = _gate(conn, batch_id, "qa_manager",
                         "no overdue CAPAs linked to the batch's deviations",
                         not overdue, "overdue: " + ", ".join(r[0] for r in overdue), prev)
    decision.roles.append(result)
    if not result.passed:
        return decision

    remaining = _open_devs(conn, batch_id)
    result, prev = _gate(conn, batch_id, "qualified_person",
                         "batch record complete: no open deviations of any class",
                         not remaining, "still open: " + ", ".join(r[0] for r in remaining), prev)
    decision.roles.append(result)
    decision.released = result.passed
    return decision
