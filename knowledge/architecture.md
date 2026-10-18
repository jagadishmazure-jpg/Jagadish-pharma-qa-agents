# Architecture

```mermaid
flowchart TD
    U[QA user question] --> O[Orchestrator: ReAct planner]
    O -->|intent: deviations/capa/audit| T[text2sql: 5 fixed intents]
    T --> G[SELECT-only gateway<br/>SEC-SELECT-01/02/03]
    G --> V[(4 read-only views<br/>on SQLite telemetry)]
    O -->|intent: sop| R[TF-IDF SOP retriever<br/>citations, explicit not-found]
    O -->|intent: regulatory| S[Regulatory signal<br/>fake seeded / live gap]
    O -->|classify| C[Deviation classifier<br/>CLASS-01..05 + repeat rules]
    O -->|release check| B[Sign-off chain<br/>reviewer → manager → QP]
    O --> E[T1–T4 escalation<br/>gates: rejections, critical closures]
    O --> A[Hash-chained audit log]
    O --> F[Feedback capture<br/>PII-scrubbed]
    B --> E
```

## Data flow
1. Synthetic telemetry (batches, deviations, CAPAs, sign-offs, findings) is
   seeded deterministically into SQLite; 4 read-only views expose it.
2. The orchestrator detects intents and fans out: SQL intents go through the
   SELECT-only gateway; SOP questions go to TF-IDF retrieval; regulatory
   questions go to the fake feed (the live stub reports a gap).
3. Release questions run the sign-off chain: each role's criterion is checked
   against live data and the first failing role blocks the chain with its
   reason cited.
4. Every turn, classification, and gate decision is appended to the
   hash-chained audit log; user feedback is PII-scrubbed before storage.
