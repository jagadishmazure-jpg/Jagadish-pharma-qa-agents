# Threat model (STRIDE-lite)

## Spoofing
- Feedback endpoints require session/turn linkage; orphan feedback is
  rejected, not stored anonymously.
- Sign-off roles are evaluated from database state, never from user claims.

## Tampering
- Audit log is hash-chained; `verify_chain()` detects modification, deletion,
  or reordering. Tested with a tamper test.
- The SQLite telemetry is read-only through the gateway; the views expose no
  write path.

## Repudiation
- Every agent turn, classification, and gate decision is recorded with actor,
  timestamp, and details.

## Information disclosure
- Gateway errors never echo row data. Escalation messages carry error classes,
  not raw output.
- Feedback free text is PII-scrubbed (email/phone/SSN/account patterns)
  before storage; redaction counts are kept for audit.

## Denial of service
- Row cap (100) on every query bounds result sizes. TF-IDF retrieval is
  in-memory over 4 documents — linear and tiny.

## Elevation of privilege
- The SELECT-only gateway rejects write keywords even inside string literals
  (literals stripped pre-scan). Comment-prefixed injections are handled by
  first-keyword parsing.

## LLM-specific (OWASP LLM Top 10, where relevant)
- **Prompt injection:** user questions are keyword-routed to fixed intents;
  there is no free-form SQL generation to hijack.
- **Insecure output handling:** the gateway is the choke point — every query
  passes SEC-SELECT-01/02/03 regardless of which intent produced it.
- **Over-reliance:** the agent never releases batches; gated actions require
  named human approvers.
