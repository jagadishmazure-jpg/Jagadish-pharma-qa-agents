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
> Person) that blocks with the exact missing criterion named. 66 tests, all
> green; the demo batch BATCH-2026-0142 is correctly blocked by its open
> critical sterility deviation while BATCH-2026-0145 releases clean.

## Problem → approach → outcome

**Problem.** QA teams drown in deviation paperwork: which batches are blocked
and why, which root causes keep recurring, whether the site is audit-ready.
Answers live across disconnected QMS records.

**Approach.** One agent over one synthetic-but-faithful data model:
- 5 natural-language intents → fixed SQL templates → SELECT-only gateway
  (cited rule IDs SEC-SELECT-01/02/03) → 4 read-only views
- Deviation classifier: critical/major/minor with the firing rule cited
  (CLASS-01…CLASS-05, plus repeat-escalation rules)
- Batch-release sign-off chain: QA reviewer (no open criticals) →
  QA manager (no overdue CAPAs) → Qualified Person (record complete);
  the chain stops at the first failing role and names it
- TF-IDF SOP retrieval with citations and explicit not-found;
  regulatory feed with fake backend and an honest live gap
- T1–T4 escalation with confirmation gates on batch rejections and
  critical-deviation closures; hash-chained audit; PII-scrubbed feedback

**Outcome.** Real run on the seeded data: 5 open deviations
(1 critical, 3 major, 1 minor), repeat root cause "cleaning validation gap"
(3 occurrences), 1 overdue CAPA (CAPA-009, 6 days), BATCH-2026-0142 blocked
at the reviewer gate, BATCH-2026-0145 released.

## How this differs from coldchain/retail

The cold-chain repo tracks reefer telemetry and temperature compliance; the
retail repo tracks stores, SKUs, and promotions. This repo models **regulated
manufacturing quality**: nothing here exists in those repos — the deviation
classifier with cited rules, the three-role sign-off chain with ordered
gates, CAPA linkage and overdue blocking, and audit-readiness reporting.
The shared spine (gateway, RAG, orchestrator, audit, feedback) is the same
engineering; the domain logic is entirely QA.

## Quickstart

```bash
python -m pytest tests/ -q          # 66 tests, stdlib only
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
| `views.py` | 4 read-only views + SELECT-only gateway (SEC-SELECT-01/02/03) |
| `text2sql.py` | 5 intents, fixed templates, one retry → escalation |
| `classify.py` | Deviation classifier, cited rules CLASS-00…CLASS-05 |
| `release.py` | Batch-release sign-off chain, ordered roles |
| `regsignal.py` | Regulatory feed: fake seeded / live gap |
| `sop_rag.py` | TF-IDF SOP retrieval with citations |
| `orchestrator.py` | ReAct planner, multi-intent fan-out, audited turns |
| `escalation.py` | T1–T4 tiers, confirmation gates |
| `audit.py` | Hash-chained log with tamper detection |
| `feedback.py` / `pii.py` | Thumbs/corrections, PII scrubbed before storage |
| `demo_helpers.py` | Stdlib logic behind the Streamlit demo |

## Guardrails and security controls

- SELECT-only gateway: write keywords rejected even inside statements;
  string literals stripped before the scan (no false positives); 100-row cap
- Gateway and escalation errors never echo raw row data
- Batch rejections and critical-deviation closures are confirmation-gated
- Feedback free text PII-scrubbed before it reaches the audit log
- Threat model: `docs/threat-model.md`

## Limitations and known failures

- The keyword classifier is intentionally simple — production use needs
  validated rules back-tested against historical deviations (see
  `docs/implementation-guide.md`).
- TF-IDF retrieval suits 4 SOPs; past a few dozen documents it needs
  embeddings.
- The live regulatory feed is a stub that reports a gap; wire a real source
  before relying on it.

## Built / Written-not-run / Planned

| Item | Status |
|---|---|
| Synthetic QA telemetry + 4 views + gateway | Built |
| 5 text-to-SQL intents | Built |
| Deviation classifier + repeat escalation | Built |
| 3-role sign-off chain | Built |
| SOP RAG, regulatory feed, orchestrator, escalation, audit, feedback | Built |
| Streamlit demo | Built |
| Live regulatory feed integration | Planned |
| Real QMS connector (replace SQLite) | Planned |

## Docs

- [knowledge/domain-notes.md](knowledge/domain-notes.md) — distilled domain notes
- [knowledge/architecture.md](knowledge/architecture.md) — Mermaid architecture
- [docs/implementation-guide.md](docs/implementation-guide.md) — adopting this in a real QA org
- [docs/interview-points.md](docs/interview-points.md) — interview talking points
- [docs/threat-model.md](docs/threat-model.md) — STRIDE-lite

## Disclaimer

All companies, products, people, and data are fictional and synthetic,
created for demonstration. This project is independent and unaffiliated
with any pharmaceutical company or regulator.
