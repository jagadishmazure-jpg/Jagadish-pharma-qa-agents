"""Gateway bypasses found in review (2026-10-18); each used to succeed.

Before the SQLite-authorizer backstop the gateway had no view allowlist:
base tables and sqlite_master were readable, including through a comma join,
a quoted name or a comment used as whitespace (the 100-row cap already held at fetch time).
"""
import pytest

from pharmaqa.telemetry import build_db
from pharmaqa.views import _VIEWS, GatewayError, create_views, run_query


@pytest.fixture
def conn():
    c = build_db()
    create_views(c)
    yield c
    c.close()


def _run(conn, sql):
    return run_query(conn, sql)[1]


@pytest.mark.parametrize("sql", [
    "SELECT * FROM signoffs",                                   # base table named directly
    "SELECT * FROM v_batch_pipeline, signoffs",                           # comma join
    'SELECT name, sql FROM "sqlite_master"',                  # quoted schema table
    "SELECT * FROM/**/signoffs",                                # comment as whitespace
])
def test_base_table_and_schema_reads_are_denied(conn, sql):
    with pytest.raises(GatewayError) as err:
        _run(conn, sql)
    assert "SEC-SELECT-04" in str(err.value)


@pytest.mark.parametrize("tail", ["LIMIT 100000", "LIMIT 100000 -- x", "LIMIT 100000 OFFSET 0"])
def test_caller_limit_cannot_exceed_the_cap(conn, tail):
    sql = f"SELECT a.* FROM v_batch_pipeline a JOIN v_batch_pipeline b JOIN v_batch_pipeline c {tail}"
    assert len(_run(conn, sql)) == 100


def test_view_self_join_is_not_falsely_denied(conn):
    # A flattened view whose tables supply no columns makes SQLite report an
    # empty-column read with no view name; that must still be allowed.
    assert _run(conn, "SELECT a.* FROM v_batch_pipeline a JOIN v_batch_pipeline b LIMIT 5")


def test_every_view_still_readable(conn):
    for v in _VIEWS:
        _run(conn, f"SELECT * FROM {v}")


def test_authorizer_is_removed_after_the_query(conn):
    _run(conn, "SELECT * FROM v_batch_pipeline")
    assert conn.execute("SELECT count(*) FROM signoffs").fetchone()[0] > 0
