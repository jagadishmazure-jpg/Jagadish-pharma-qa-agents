# Jagadish-pharma-qa-agents

End-to-end pharmaceutical QA deviation management: an agent that triages
deviations, checks batch-release readiness through a multi-role sign-off
chain, tracks CAPAs, and answers audit-readiness questions — all from
controlled records, with citations.

> **Recruiter summary.** Pharma batches can't ship until QA releases them, and
> every deviation must be classified, investigated, and closed first. This repo
> models that world end-to-end: synthetic QA telemetry on SQLite, text-to-SQL
> over read-only views, a deviation classifier with cited rules, and a
> three-role batch-release sign-off chain (reviewer → manager → Qualified
> Person) that releases only on recorded signatures in order and blocks with the
> exact missing criterion named. 93 tests, all green; the demo batch
> BATCH-2026-0142 is blocked by its open critical sterility deviation while
> BATCH-2026-0145 releases with all three signatures.

## Problem → approach → outcome

**Problem.** QA teams drown in deviation paperwork: which batches are blocked
and why, which root causes keep recurring, whether the site is audit-ready.
Answers live across disconnected QMS records.

**Approach.** One agent over one synthetic-but-faithful data model:
- 5 natural-language intents → fixed SQL templates → SELECT-only gateway
  (cited rule IDs SEC-SELECT-01/02/03, plus SEC-SELECT-04: views only, enforced
  by a SQLite authorizer) → 4 read-only views
- Deviation classifier: critical/major/minor with the firing rule cited
  (CLASS-01…CLASS-05, plus repeat-escalation rules)
- Batch-release sign-off chain: QA reviewer (no open criticals) →
  QA manager (no overdue CAPAs, by status or due date) → Qualified Person
  (record complete). Each role needs its criterion *and* a recorded approved
  sign-off dated after the previous role's; the chain stops at the first
  failing role and names it. Unknown and rejected batches never release.
- TF-IDF SOP retrieval with citations and explicit not-found;
  regulatory feed with fake backend and an honest live gap
- T1–T4 escalation with confirmation gates on batch rejections and
  critical-deviation closures; hash-chained audit; PII-scrubbed feedback

**Outcome.** Real run on the seeded data: 5 open deviations
(1 critical, 3 major, 1 minor), repeat root cause "cleaning validation gap"
(3 occurrences), 1 overdue CAPA (CAPA-009, 6 days), BATCH-2026-0142 blocked
at the reviewer gate, BATCH-2026-0143 blocked at the manager gate by
CAPA-009, BATCH-2026-0144 and BATCH-2026-0146 awaiting the reviewer's
signature, BATCH-2026-0147 (rejected) refused, BATCH-2026-0145 released.

## How this differs from coldchain/retail

The cold-chain repo tracks reefer telemetry and temperature compliance; the
retail repo tracks stores, SKUs, and promotions. This repo models **regulated
manufacturing quality**: nothing here exists in those repos — the deviation
classifier with cited rules, the three-role sign-off chain with ordered
gates, CAPA linkage and overdue blocking, and audit-readiness reporting.
The shared spine (gateway, RAG, orchestrator, audit, feedback) is the same
engineering; the domain logic is entirely QA.

**Boundary with the healthcare repos.** clinical-ops handles clinical
paperwork for patients (referral triage, prior-auth packets, discharge
drafts) and healthcare-ops handles hospital bed flow. This repo is the
manufacturer's quality unit: deviations, CAPAs and batch release under
GMP. It never touches patients or clinical records; the only overlap is
the word "critical", which here means product impact, not patient acuity.

## Quickstart

```bash
python -m pytest tests/ -q          # 93 tests, stdlib only
pip install streamlit               # optional, demo only
streamlit run demo/app.py
```

```python
from pharmaqa.telemetry import build_db
from pharmaqa.views import create_views
from pharmaqa.release import evaluate

conn = build_db(); create_views(conn)
dec = evaluate(conn, "BATCH-2026-0142")
print(dec.released)          # False
print(dec.roles[0].detail)   # blocked by DEV-CRIT-007
```

Real output:

```
Batch BATCH-2026-0142: BLOCKED
  [FAIL] qa_reviewer: blocked by DEV-CRIT-007 (criterion: no open critical deviations)
```

## Module table

| Module | What it does |
|---|---|
| `telemetry.py` | Seeded SQLite: batches, deviations, CAPAs, sign-offs, findings |
| `views.py` | 4 read-only views + SELECT-only gateway (SEC-SELECT-01/02/03/04) |
| `authz.py` | SQLite authorizer: only the views are readable (ADR 0001) |
| `text2sql.py` | 5 intents, fixed templates, one retry → escalation |
| `classify.py` | Deviation classifier, cited rules CLASS-00…CLASS-05 |
| `release.py` | Batch-release sign-off chain: criteria + recorded signatures, in role order |
| `regsignal.py` | Regulatory feed: fake seeded / live gap |
| `sop_rag.py` | TF-IDF SOP retrieval with citations |
| `orchestrator.py` | ReAct planner, multi-intent fan-out, audited turns |
| `escalation.py` | T1–T4 tiers, confirmation gates |
| `audit.py` | Hash-chained log with tamper detection |
| `feedback.py` / `pii.py` | Thumbs/corrections, PII scrubbed before storage |
| `demo_helpers.py` | Stdlib logic behind the Streamlit demo |

## Guardrails and security controls

- SELECT-only gateway: write keywords rejected even inside statements;
  string literals stripped before the scan (no false positives); only the
  views are readable (SQLite authorizer, ADR 0001); 100-row cap at fetch time
- Gateway and escalation errors never echo raw row data
- Batch rejections and critical-deviation closures are confirmation-gated
- Feedback free text PII-scrubbed (email, phone incl. `(555) 123-4567`, SSN, card,
  account numbers) before it reaches the audit log
- Threat model: `docs/threat-model.md`

## Limitations and known failures

- The keyword classifier is intentionally simple — production use needs
  validated rules back-tested against historical deviations (see
  `docs/implementation-guide.md`).
- TF-IDF retrieval suits 4 SOPs; past a few dozen documents it needs
  embeddings.
- The live regulatory feed is a stub that reports a gap; wire a real source
  before relying on it.
- Sign-offs are rows in the synthetic `signoffs` table; there is no e-signature
  or identity check behind them (21 CFR Part 11 would require both).
- `AS_OF` is fixed at 2026-10-18 so the seeded figures stay reproducible.
- `classify_repeat` (CLASS-02/04) is a tested library function; nothing calls
  it on new deviations automatically yet.

## Standardization review (2026-10-18)

Reviewed against the portfolio standard after the build. Bugs found and fixed, each now pinned by a test:

1. **Gateway had no view allowlist.** It blocked writes, but `SELECT * FROM signoffs`, a comma join, `"sqlite_master"` and `FROM/**/signoffs` all read base tables or the schema (the 100-row cap already held at fetch time). A SQLite authorizer (`pharmaqa/authz.py`, ADR 0001) now refuses any read that is not a published view (`SEC-SELECT-04`).
2. **Batches released without a single signature.** `evaluate()` only checked the three criteria and never read the `signoffs` table, so BATCH-2026-0146 (still in manufacturing, no sign-offs), BATCH-2026-0147 (already rejected) and a batch ID that does not exist all came back RELEASED. A role now passes only when its criterion holds *and* an approved sign-off by that role is recorded, dated no earlier than the previous role's (SOP-QA-002: "three approvals in order"); unknown and rejected batches never release.
3. **A CAPA past its due date did not block.** Only `status = 'overdue'` counted, so an `open` CAPA 17 days late let the QA manager gate pass, against SOP-QA-003 ("A CAPA past its due date becomes overdue and blocks the QA manager sign-off"). Overdue now means status *or* due date before `AS_OF`.
4. **Classifier keywords matched inside words.** `oos` (out of specification) fired on "loose" and "boost", turning a documentation-only deviation into a major. Keywords now match at word starts (`oos` as a whole word).
5. **Phone scrubber missed `(555) 123-4567` and `+1 (555) 123-4567`.** The pattern had no parentheses form. It now uses the shared anchored phone pattern; card numbers are also redacted, and dates and batch IDs are left alone (tested).

Differentiator on the seeded data (regenerated and checked by CI on every push):

<!-- run: python scripts/show_differentiator.py -->
```text
Batch-release sign-off chain (criterion AND recorded signature, in role order):
Batch BATCH-2026-0142: BLOCKED
  [FAIL] qa_reviewer: blocked by DEV-CRIT-007 (criterion: no open critical deviations)
Batch BATCH-2026-0143: BLOCKED
  [PASS] qa_reviewer: signed by J. Mensah on 2026-10-08 (criterion: no open critical deviations)
  [FAIL] qa_manager: overdue: CAPA-009 (criterion: no overdue CAPAs linked to the batch's deviations)
Batch BATCH-2026-0144: BLOCKED
  [FAIL] qa_reviewer: criterion met; awaiting signature (criterion: no open critical deviations)
Batch BATCH-2026-0145: RELEASED
  [PASS] qa_reviewer: signed by J. Mensah on 2026-09-20 (criterion: no open critical deviations)
  [PASS] qa_manager: signed by L. Fontaine on 2026-09-21 (criterion: no overdue CAPAs linked to the batch's deviations)
  [PASS] qualified_person: signed by D. Reyes on 2026-09-22 (criterion: batch record complete: no open deviations of any class)
Batch BATCH-2026-0146: BLOCKED
  [FAIL] qa_reviewer: criterion met; awaiting signature (criterion: no open critical deviations)
Batch BATCH-2026-0147: BLOCKED
  [FAIL] qa_reviewer: batch was rejected (criterion: batch exists and is not rejected)

Deviation classifier:
  'Sterility test failure': critical (CLASS-01)
  'Cleaning validation gap': major (CLASS-03)
  'Loose logbook binding': minor (CLASS-05)
  'Unlabelled tote found': major (CLASS-00)

Gateway: SEC-SELECT-04: 'signoffs' is not a read-only view
```
<!-- /run -->

Test count (also checked by CI):

<!-- run: python scripts/count_tests.py -->
```text
93 tests collected
```
<!-- /run -->

## Built / Written-not-run / Planned

| Item | Status |
|---|---|
| Synthetic QA telemetry + 4 views + gateway | Built |
| 5 text-to-SQL intents | Built |
| Deviation classifier + repeat escalation | Built |
| 3-role sign-off chain | Built |
| SOP RAG, regulatory feed, orchestrator, escalation, audit, feedback | Built |
| Streamlit demo | Built |
| CI on every push: ruff, tests, docs drift check, hashed brand check, gitleaks; CodeQL; Dependabot | Built |
| Live regulatory feed integration | Planned |
| Real QMS connector (replace SQLite) | Planned |

## Docs

- [knowledge/domain-notes.md](knowledge/domain-notes.md) — distilled domain notes
- [knowledge/architecture.md](knowledge/architecture.md) — Mermaid architecture
- [docs/implementation-guide.md](docs/implementation-guide.md) — adopting this in a real QA org
- [docs/interview-points.md](docs/interview-points.md) — interview talking points
- [docs/threat-model.md](docs/threat-model.md) — STRIDE-lite
- [docs/adr/0001-sqlite-authorizer-backstop.md](docs/adr/0001-sqlite-authorizer-backstop.md) — gateway backstop

## Related repos

- [Jagadish-clinical-ops-agents](https://github.com/jagadishmazure-jpg/Jagadish-clinical-ops-agents) — clinical paperwork, not manufacturing
- [Jagadish-healthcare-ops-agents](https://github.com/jagadishmazure-jpg/Jagadish-healthcare-ops-agents) — hospital bed flow
- [Jagadish-coldchain-logistics-agents](https://github.com/jagadishmazure-jpg/Jagadish-coldchain-logistics-agents) — same spine; ships what this repo releases

## Disclaimer

All companies, products, people, and data are fictional and synthetic,
created for demonstration. This project is independent and unaffiliated
with any pharmaceutical company or regulator.
