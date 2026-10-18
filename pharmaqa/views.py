"""Read-only views over the QA telemetry plus a SELECT-only SQL gateway.

Rule IDs (cited in tests and README):
  SEC-SELECT-01: only statements starting with SELECT (after stripping
                 comments/whitespace) are executed.
  SEC-SELECT-02: write keywords (INSERT/UPDATE/DELETE/DROP/ALTER/...) are
                 rejected even when hidden inside the statement — string
                 literals are stripped before the scan so 'UPDATE' inside a
                 quoted value does not false-positive.
  SEC-SELECT-03: every query is capped at 100 rows (rows past the cap are
                 never fetched).
  SEC-SELECT-04: only the read-only views may be read. Enforced by a SQLite
                 authorizer (pharmaqa/authz.py, ADR 0001), so comma joins,
                 quoted names and comments cannot reach base tables or
                 sqlite_master.
"""

from __future__ import annotations

import re
import sqlite3

from . import authz

ROW_CAP = 100

_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|merge|grant|revoke|exec|execute|call)\b",
    re.IGNORECASE,
)

_VIEWS = {
    "v_open_deviations": """
        SELECT d.dev_id, d.batch_id, d.title, d.dev_class, d.status,
               d.root_cause, d.due_date,
               CAST(julianday('2026-10-18') - julianday(d.due_date) AS INTEGER) AS days_overdue
        FROM deviations d
        WHERE d.status IN ('open', 'investigating')
    """,
    "v_batch_pipeline": """
        SELECT b.batch_id, b.product, b.status,
               (SELECT COUNT(*) FROM deviations d
                 WHERE d.batch_id = b.batch_id AND d.status IN ('open','investigating')) AS open_devs,
               (SELECT COUNT(*) FROM signoffs s
                 WHERE s.batch_id = b.batch_id AND s.decision = 'approved') AS signoffs_done
        FROM batches b
    """,
    "v_capa_backlog": """
        SELECT c.capa_id, c.dev_id, c.title, c.status, c.owner, c.due_date,
               CAST(julianday('2026-10-18') - julianday(c.due_date) AS INTEGER) AS days_overdue
        FROM capas c
        WHERE c.status IN ('open', 'in_progress', 'overdue')
    """,
    "v_repeat_deviations": """
        SELECT root_cause, COUNT(*) AS occurrences,
               GROUP_CONCAT(dev_id) AS dev_ids
        FROM deviations
        GROUP BY root_cause
        HAVING COUNT(*) > 1
    """,
}


def create_views(conn: sqlite3.Connection) -> None:
    for name, sql in _VIEWS.items():
        conn.execute(f"CREATE VIEW IF NOT EXISTS {name} AS {sql}")
    conn.commit()


def _strip_literals(sql: str) -> str:
    """Remove single/double-quoted literals so keyword scans don't false-positive."""
    return re.sub(r"('[^']*'|\"[^\"]*\")", "''", sql)


def _first_keyword(sql: str) -> str:
    """First SQL keyword after stripping leading whitespace and -- comments."""
    rest = sql.lstrip()
    while rest.startswith("--"):
        rest = rest.split("\n", 1)[1] if "\n" in rest else ""
        rest = rest.lstrip()
    m = re.match(r"([A-Za-z]+)", rest)
    return m.group(1).upper() if m else ""


class GatewayError(Exception):
    pass


def run_query(conn: sqlite3.Connection, sql: str):
    """Execute read-only SQL. Raises GatewayError on any rule violation."""
    cleaned = sql.strip()
    if _first_keyword(cleaned) != "SELECT":
        raise GatewayError("SEC-SELECT-01: only SELECT statements are allowed")
    if _WRITE_KEYWORDS.search(_strip_literals(cleaned)):
        raise GatewayError("SEC-SELECT-02: write keywords are not allowed")
    with authz.views_only(conn, _VIEWS) as denied:
        try:
            cur = conn.execute(cleaned)
        except sqlite3.DatabaseError:
            if denied:
                raise GatewayError(
                    f"SEC-SELECT-04: '{denied[0]}' is not a read-only view") from None
            raise
        rows = cur.fetchmany(ROW_CAP)  # SEC-SELECT-03
        cols = [d[0] for d in cur.description] if cur.description else []
    return cols, [dict(zip(cols, r)) for r in rows]
