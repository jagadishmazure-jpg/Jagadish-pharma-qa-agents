"""Natural-language to SQL over the QA read-only views.

Five intents, each backed by a fixed template (no free-form generation).
On a database error the planner makes ONE simplified retry; if that fails
too it raises EscalationNeeded instead of guessing.
"""

from __future__ import annotations

import sqlite3

from .views import GatewayError, run_query


class EscalationNeeded(Exception):
    pass


_INTENTS = {
    "open_deviations_by_class": (
        "SELECT dev_class, COUNT(*) AS n FROM v_open_deviations GROUP BY dev_class",
        ("class", "deviation", "open deviation", "how many"),
    ),
    "batch_release_pipeline": (
        "SELECT batch_id, product, status, open_devs, signoffs_done "
        "FROM v_batch_pipeline WHERE status IN ('qa_review','on_hold')",
        ("pipeline", "release", "batch", "sign-off", "signoff"),
    ),
    "capa_backlog": (
        "SELECT capa_id, dev_id, title, status, owner, due_date, days_overdue "
        "FROM v_capa_backlog ORDER BY days_overdue DESC",
        ("capa", "corrective", "backlog", "overdue"),
    ),
    "repeat_deviations": (
        "SELECT root_cause, occurrences, dev_ids FROM v_repeat_deviations "
        "ORDER BY occurrences DESC",
        ("repeat", "recurring", "root cause", "same cause"),
    ),
    "audit_readiness": (
        "SELECT 'open_critical_devs' AS metric, COUNT(*) AS value FROM v_open_deviations "
        "WHERE dev_class='critical' UNION ALL "
        "SELECT 'overdue_capas', COUNT(*) FROM v_capa_backlog WHERE days_overdue > 0 UNION ALL "
        "SELECT 'batches_awaiting_qp', COUNT(*) FROM signoffs "
        "WHERE role='qualified_person' AND decision='pending'",
        ("audit", "readiness", "inspection", "ready"),
    ),
}


def detect_intent(question: str) -> str | None:
    q = question.lower()
    best, best_hits = None, 0
    for intent, (_, keywords) in _INTENTS.items():
        hits = sum(1 for kw in keywords if kw in q)
        if hits > best_hits:
            best, best_hits = intent, hits
    return best


def answer(conn: sqlite3.Connection, question: str) -> dict:
    """Answer a question. Returns {'intent', 'sql', 'columns', 'rows'}."""
    intent = detect_intent(question)
    if intent is None:
        raise EscalationNeeded(f"no intent matched: {question!r}")
    sql, _ = _INTENTS[intent]
    try:
        columns, rows = run_query(conn, sql)
    except (sqlite3.Error, GatewayError):
        # one simplified retry: drop the ORDER BY / UNION complexity
        simple = sql.split(" ORDER BY ")[0].split(" UNION ALL ")[0]
        try:
            columns, rows = run_query(conn, simple)
        except (sqlite3.Error, GatewayError) as exc:
            raise EscalationNeeded(f"query failed after retry: {exc}") from exc
    return {"intent": intent, "sql": sql, "columns": columns, "rows": rows}
