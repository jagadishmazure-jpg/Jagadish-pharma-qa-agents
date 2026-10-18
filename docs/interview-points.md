# Interview points

Talking points this repo earns you in an agentic-AI interview.

1. **"Why a sign-off chain instead of a single release check?"**
   Each role checks something different — reviewer: criticals, manager: CAPA
   pace, QP: record completeness. Evaluating in order means a blocked release
   always names the exact missing criterion. One boolean can't explain itself.

2. **"How do you stop the agent from hallucinating QA answers?"**
   Three layers: fixed SQL templates over read-only views (no free-form SQL),
   a SELECT-only gateway with literal-stripping, and SOP retrieval that says
   "not covered" instead of inventing. The regulatory feed reports a gap
   rather than fabricating updates.

3. **"What happens when the same deviation keeps recurring?"**
   The classifier escalates repeats (CLASS-02/CLASS-04) and the
   repeat-deviations view surfaces the root cause with all linked deviation
   IDs — the agent turns a pattern into an evidence pack.

4. **"How do you keep auditors happy?"**
   Every turn, classification, and gate decision is hash-chained; tampering
   breaks `verify_chain()`. Feedback text is PII-scrubbed before storage, and
   error paths never echo raw row data.

5. **"Where does the human stay in the loop?"**
   Batch rejections and critical-deviation closures are gated actions; T3/T4
   escalations route to named roles. The agent prepares evidence — humans
   release batches.

6. **"What would break first in production?"**
   The keyword classifier is the weakest link — real classification needs
   validated rules back-tested against historical deviations. The TF-IDF
   retriever is second: fine for 4 SOPs, needs embeddings past a few dozen
   documents. Both limitations are documented and tested as known misses.
