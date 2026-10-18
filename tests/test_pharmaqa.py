"""Tests for pharmaqa. Deterministic; no network; stdlib only."""


import os

import pytest

from pharmaqa import demo_helpers as dh
from pharmaqa.audit import AuditLog
from pharmaqa.classify import classify, classify_repeat
from pharmaqa.escalation import ALWAYS_GATED, TIERS, ConfirmationGate, GateError, tier_for
from pharmaqa.feedback import FeedbackError, list_feedback, record_feedback
from pharmaqa.orchestrator import Orchestrator
from pharmaqa.pii import scrub
from pharmaqa.regsignal import FakeRegFeed, GapError, LiveRegFeed
from pharmaqa.release import evaluate
from pharmaqa.sop_rag import SopRetriever, load_chunks
from pharmaqa.telemetry import ANCHORS, build_db
from pharmaqa.text2sql import EscalationNeeded, answer
from pharmaqa.views import GatewayError, create_views, run_query

SOP_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "sops")


@pytest.fixture()
def conn():
    c = build_db()
    create_views(c)
    return c


@pytest.fixture()
def retriever():
    return SopRetriever(load_chunks(SOP_DIR))


# ---- deterministic anchors ----

def test_blocked_batch_anchor(conn):
    row = conn.execute("SELECT status FROM batches WHERE batch_id=?",
                       (ANCHORS["blocked_batch"],)).fetchone()
    assert row["status"] == "on_hold"


def test_critical_deviation_open(conn):
    row = conn.execute("SELECT dev_class, status FROM deviations WHERE dev_id=?",
                       (ANCHORS["critical_deviation"],)).fetchone()
    assert (row["dev_class"], row["status"]) == ("critical", "open")


def test_repeat_root_cause_anchor(conn):
    n = conn.execute("SELECT COUNT(*) c FROM deviations WHERE root_cause=?",
                     (ANCHORS["repeat_root_cause"],)).fetchone()["c"]
    assert n == 3


def test_overdue_capa_anchor(conn):
    row = conn.execute("SELECT status FROM capas WHERE capa_id=?",
                       (ANCHORS["overdue_capa"],)).fetchone()
    assert row["status"] == "overdue"


def test_released_batch_all_approved(conn):
    rows = conn.execute("SELECT decision FROM signoffs WHERE batch_id='BATCH-2026-0145'").fetchall()
    assert {r["decision"] for r in rows} == {"approved"}


# ---- gateway security ----

def test_gateway_select_ok(conn):
    cols, rows = run_query(conn, "SELECT dev_id FROM v_open_deviations")
    assert cols and rows


def test_gateway_rejects_insert(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-01"):
        run_query(conn, "INSERT INTO batches VALUES ('x','y','z','a','b')")


def test_gateway_rejects_update(conn):
    with pytest.raises(GatewayError):
        run_query(conn, "UPDATE deviations SET status='closed'")


def test_gateway_rejects_drop(conn):
    with pytest.raises(GatewayError):
        run_query(conn, "DROP TABLE batches")


def test_gateway_no_false_positive_in_literal(conn):
    # 'UPDATE' inside a string literal must not trip SEC-SELECT-02
    cols, rows = run_query(conn,
        "SELECT dev_id FROM v_open_deviations WHERE title LIKE '%UPDATE%'")
    assert cols is not None


def test_gateway_rejects_comment_prefixed_injection(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-01"):
        run_query(conn, "-- sneaky\nDELETE FROM deviations")


def test_gateway_row_cap(conn):
    cols, rows = run_query(conn, "SELECT 1 UNION ALL " +
                           " UNION ALL ".join(["SELECT 2"] * 200))
    assert len(rows) <= 100


def test_gateway_rejects_bare_expression(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-01"):
        run_query(conn, "1+1")


# ---- text2sql intents ----

@pytest.mark.parametrize("q", [
    "how many open deviations by class",
    "show the batch release pipeline",
    "capa backlog and overdue items",
    "which root causes repeat",
    "are we audit ready for inspection",
])
def test_intents_return_rows(conn, q):
    out = answer(conn, q)
    assert out["rows"], q
    assert out["intent"]


def test_unknown_intent_escalates(conn):
    with pytest.raises(EscalationNeeded):
        answer(conn, "what is the capital of France")


def test_repeat_intent_names_anchor(conn):
    out = answer(conn, "which root causes are repeating")
    causes = [r["root_cause"] for r in out["rows"]]
    assert ANCHORS["repeat_root_cause"] in causes


# ---- deviation classifier ----

def test_classify_sterility_critical():
    c = classify("Sterility failure", "fill room excursion")
    assert (c.dev_class, c.rule_id) == ("critical", "CLASS-01")


def test_classify_data_integrity_critical():
    c = classify("Chromatography review", "data integrity lapse found")
    assert c.dev_class == "critical"


def test_classify_validation_gap_major():
    c = classify("Cleaning validation gap", "residue above limit")
    assert (c.dev_class, c.rule_id) == ("major", "CLASS-03")


def test_classify_logbook_minor():
    c = classify("Logbook correction", "operator fixed a time typo")
    assert (c.dev_class, c.rule_id) == ("minor", "CLASS-05")


def test_classify_default_is_major():
    c = classify("Weird humming noise", "nobody knows what this is")
    assert (c.dev_class, c.rule_id) == ("major", "CLASS-00")


def test_classify_repeat_critical_escalates():
    c = classify_repeat("HVAC issue again", "filter lapse", ["critical"])
    assert (c.dev_class, c.rule_id) == ("critical", "CLASS-02")


def test_classify_repeat_major_escalates():
    c = classify_repeat("Cleaning gap again", "residue", ["major"])
    assert (c.dev_class, c.rule_id) == ("major", "CLASS-04")


def test_classification_cites_rule():
    c = classify("Sterility failure", "x")
    assert c.rule_id and c.rule_text and c.evidence


# ---- batch-release sign-off chain ----

def test_release_blocked_at_reviewer(conn):
    dec = evaluate(conn, "BATCH-2026-0142")
    assert not dec.released
    assert dec.roles[0].role == "qa_reviewer" and not dec.roles[0].passed
    assert "DEV-CRIT-007" in dec.roles[0].detail


def test_chain_stops_at_first_failure(conn):
    dec = evaluate(conn, "BATCH-2026-0142")
    assert len(dec.roles) == 1  # manager/QP never evaluated


def test_release_blocked_at_manager_overdue_capa(conn):
    dec = evaluate(conn, "BATCH-2026-0143")
    assert not dec.released
    assert dec.roles[0].passed  # reviewer ok: no open criticals
    assert dec.roles[1].role == "qa_manager" and not dec.roles[1].passed
    assert "CAPA-009" in dec.roles[1].detail


def test_release_all_approved(conn):
    dec = evaluate(conn, "BATCH-2026-0145")
    assert dec.released
    assert all(r.passed for r in dec.roles)
    assert [r.role for r in dec.roles] == ["qa_reviewer", "qa_manager", "qualified_person"]


def test_blocking_names_criterion(conn):
    dec = evaluate(conn, "BATCH-2026-0142")
    b = dec.blocking()
    assert len(b) == 1 and b[0].criterion == "no open critical deviations"


# ---- escalation tiers and gates ----

def test_reject_batch_is_t4_gated():
    t = tier_for("reject_batch")
    assert t == TIERS["T4"] and t.gated


def test_close_critical_is_gated():
    assert "close_critical_deviation" in ALWAYS_GATED
    assert tier_for("close_critical_deviation").gated


def test_gate_blocks_until_approved():
    g = ConfirmationGate()
    tok = g.request("reject_batch", "BATCH-2026-0147")
    with pytest.raises(GateError):
        g.check(tok)
    g.decide(tok, True)
    g.check(tok)  # no raise


def test_gate_unknown_token():
    g = ConfirmationGate()
    with pytest.raises(GateError):
        g.decide("gate-9999", True)


def test_tier_mapping_severity():
    assert tier_for("query", "critical").name == "T3"
    assert tier_for("query", "minor").name == "T1"


# ---- SOP RAG ----

def test_rag_cites_deviation_sop(retriever):
    out = retriever.answer("how are deviations classified and closed")
    assert "sop-01-deviation-handling.md" in out


def test_rag_explicit_not_found(retriever):
    out = retriever.answer("quantum cryptography key rotation policy")
    assert "No SOP section covers" in out


def test_rag_citation_format(retriever):
    out = retriever.answer("what does the QA manager check before release")
    assert "§" in out


# ---- regulatory signal ----

def test_fake_feed_seeded():
    updates = FakeRegFeed().latest()
    assert len(updates) == 2


def test_fake_feed_topic_filter():
    updates = FakeRegFeed().latest(topic="data-integrity")
    assert len(updates) == 1 and "data-integrity" in updates[0].headline


def test_live_feed_gap():
    with pytest.raises(GapError, match="unavailable"):
        LiveRegFeed().latest()


# ---- audit chain ----

def test_audit_verify_ok():
    a = AuditLog()
    a.record("agent", "ask", {"q": "x"})
    a.record("agent", "classify", {"class": "major"})
    assert a.verify_chain()


def test_audit_tamper_detected():
    a = AuditLog()
    a.record("agent", "ask", {"q": "x"})
    a.entries[0]["details"]["q"] = "tampered"
    assert not a.verify_chain()


# ---- PII scrubbing ----

def test_scrub_email():
    clean, n = scrub("contact qa.lead@example.com please")
    assert "[EMAIL]" in clean and n == 1


def test_scrub_phone():
    clean, n = scrub("call 555-123-4567")
    assert "[PHONE]" in clean


def test_scrub_ssn():
    clean, n = scrub("ssn 123-45-6789 on file")
    assert "[SSN]" in clean


def test_scrub_clean_text_untouched():
    clean, n = scrub("the batch record is complete")
    assert (clean, n) == ("the batch record is complete", 0)


# ---- feedback ----

def test_feedback_stored_and_audited():
    a = AuditLog()
    fb = record_feedback(a, "s1", "t1", "up")
    assert fb.rating == "up"
    assert a.verify_chain()
    assert len(list_feedback(a)) == 1


def test_feedback_down_scrubs_correction():
    a = AuditLog()
    fb = record_feedback(a, "s1", "t1", "down",
                         "wrong, email me at qa.lead@example.com")
    assert "[EMAIL]" in fb.correction and fb.redactions == 1


def test_feedback_bad_rating_rejected():
    with pytest.raises(FeedbackError):
        record_feedback(AuditLog(), "s1", "t1", "maybe")


def test_feedback_down_requires_correction():
    with pytest.raises(FeedbackError):
        record_feedback(AuditLog(), "s1", "t1", "down", "   ")


def test_feedback_blank_session_rejected():
    with pytest.raises(FeedbackError):
        record_feedback(AuditLog(), " ", "t1", "up")


def test_list_feedback_filters_session():
    a = AuditLog()
    record_feedback(a, "s1", "t1", "up")
    record_feedback(a, "s2", "t2", "up")
    assert len(list_feedback(a, "s1")) == 1


# ---- orchestrator ----

def test_orchestrator_fans_out(conn, retriever):
    o = Orchestrator(conn, retriever)
    turn = o.ask("show open deviations and the capa backlog")
    intents = [s["intent"] for s in turn["steps"]]
    assert "deviations" in intents and "capa" in intents


def test_orchestrator_release_evaluates_batch(conn, retriever):
    o = Orchestrator(conn, retriever)
    turn = o.ask("is BATCH-2026-0145 released")
    rel = next(s for s in turn["steps"] if s["intent"] == "release")
    assert rel["result"]["released"] is True


def test_orchestrator_blocked_batch_names_reason(conn, retriever):
    o = Orchestrator(conn, retriever)
    turn = o.ask("why is BATCH-2026-0142 blocked")
    rel = next(s for s in turn["steps"] if s["intent"] == "release")
    assert rel["result"]["released"] is False


def test_orchestrator_audits_turn(conn, retriever):
    a = AuditLog()
    o = Orchestrator(conn, retriever, a)
    o.ask("capa backlog")
    assert a.verify_chain() and len(a.entries) == 1


def test_orchestrator_classify_cites_rule(conn, retriever):
    o = Orchestrator(conn, retriever)
    out = o.classify_deviation("Sterility failure", "fill room")
    assert out["rule_id"] == "CLASS-01"


def test_orchestrator_regulatory_gap(conn, retriever):
    o = Orchestrator(conn, retriever)
    o.feed = LiveRegFeed()
    turn = o.ask("any regulatory updates")
    reg = next(s for s in turn["steps"] if s["intent"] == "regulatory")
    assert "gap" in reg["result"]


# ---- demo helpers ----

def test_demo_release_pipeline(conn):
    rows = dh.release_pipeline(conn)
    assert len(rows) == 3  # qa_review/on_hold batches
    blocked = next(r for r in rows if r["batch"] == "BATCH-2026-0142")
    assert not blocked["released"] and blocked["blocking"]


def test_demo_deviation_summary(conn):
    rows = dh.deviation_summary(conn)
    by_class = {r["dev_class"]: r["n"] for r in rows}
    assert by_class["critical"] == 1 and by_class["major"] == 3


def test_demo_capa_summary(conn):
    rows = dh.capa_summary(conn)
    overdue = next(r for r in rows if r["capa"] == "CAPA-009")
    assert overdue["days_overdue"] == 6


def test_format_release_blocked(conn):
    dec = evaluate(conn, "BATCH-2026-0142")
    text = dh.format_release(dec)
    assert "BLOCKED" in text and "qa_reviewer" in text


# ---------- review fixes (grokbot-portfolio, 2026-10-18) ----------

def _sign(conn, batch, role, date, decision="approved", who="T. Tester"):
    conn.execute("INSERT INTO signoffs VALUES (?,?,?,?,?,?,?)",
                 (f"SO-{batch}-{role}", batch, role, who, decision, "test", date))


@pytest.mark.parametrize("batch, detail", [
    ("BATCH-2026-0146", "criterion met; awaiting signature"),   # no sign-offs at all
    ("BATCH-2026-0147", "batch was rejected"),
    ("BATCH-9999-0000", "unknown batch"),
])
def test_review_release_needs_recorded_signatures_and_a_real_batch(conn, batch, detail):
    dec = evaluate(conn, batch)
    assert not dec.released and dec.blocking()[0].detail == detail


def test_review_release_with_all_three_signatures_in_order(conn):
    for role, day in (("qa_reviewer", "2026-10-13"), ("qa_manager", "2026-10-14"),
                      ("qualified_person", "2026-10-15")):
        _sign(conn, "BATCH-2026-0146", role, day)
    dec = evaluate(conn, "BATCH-2026-0146")
    assert dec.released and [r.signed_by for r in dec.roles] == ["T. Tester"] * 3


def test_review_signature_before_previous_role_blocks(conn):
    _sign(conn, "BATCH-2026-0146", "qa_reviewer", "2026-10-15")
    _sign(conn, "BATCH-2026-0146", "qa_manager", "2026-10-14")
    dec = evaluate(conn, "BATCH-2026-0146")
    assert not dec.released
    assert dec.blocking()[0].role == "qa_manager" and "before the previous role" in dec.blocking()[0].detail


def test_review_capa_past_due_date_blocks_even_if_status_is_not_overdue(conn):
    conn.execute("UPDATE capas SET status = 'in_progress' WHERE capa_id = 'CAPA-009'")  # due 2026-10-12
    dec = evaluate(conn, "BATCH-2026-0143")
    assert dec.blocking()[0].role == "qa_manager" and "CAPA-009" in dec.blocking()[0].detail


def test_review_released_anchor_cites_signers(conn):
    dec = evaluate(conn, "BATCH-2026-0145")
    assert dec.released and dec.roles[-1].detail == "signed by D. Reyes on 2026-09-22"


@pytest.mark.parametrize("title, rule", [
    ("Loose logbook binding", "CLASS-05"),       # "oos" inside "loose" used to fire CLASS-03
    ("Boost pump logbook typo", "CLASS-05"),
    ("OOS assay result", "CLASS-03"),
])
def test_review_classifier_matches_whole_keywords(title, rule):
    assert classify(title, "documentation only").rule_id == rule


@pytest.mark.parametrize("text", ["call (555) 123-4567", "call +1 (555) 123-4567", "call 555.123.4567"])
def test_review_phone_formats_scrubbed(text):
    out, n = scrub(text)
    assert "123" not in out and n == 1


def test_review_dates_and_batch_ids_kept():
    text = "BATCH-2026-0142 on 2026-10-18"
    assert scrub(text) == (text, 0)
