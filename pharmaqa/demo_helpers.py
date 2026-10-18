"""Demo helpers: pure-stdlib logic behind the thin Streamlit demo (fully tested)."""

from __future__ import annotations

import sqlite3

from .release import evaluate
from .text2sql import answer


def release_pipeline(conn: sqlite3.Connection) -> list[dict]:
    """One row per batch in review/on_hold with release status."""
    data = answer(conn, "batch release pipeline")
    out = []
    for r in data["rows"]:
        dec = evaluate(conn, r["batch_id"])
        out.append({
            "batch": r["batch_id"], "product": r["product"], "status": r["status"],
            "released": dec.released,
            "blocking": [f"{b.role}: {b.detail}" for b in dec.blocking()],
        })
    return out


def deviation_summary(conn: sqlite3.Connection) -> list[dict]:
    return answer(conn, "open deviations by class")["rows"]


def capa_summary(conn: sqlite3.Connection) -> list[dict]:
    rows = answer(conn, "capa backlog")["rows"]
    return [{"capa": r["capa_id"], "title": r["title"], "status": r["status"],
             "days_overdue": r["days_overdue"]} for r in rows]


def format_release(decision) -> str:
    lines = [f"Batch {decision.batch_id}: "
             f"{'RELEASED' if decision.released else 'BLOCKED'}"]
    for r in decision.roles:
        mark = "PASS" if r.passed else "FAIL"
        lines.append(f"  [{mark}] {r.role}: {r.detail} (criterion: {r.criterion})")
    return "\n".join(lines)
