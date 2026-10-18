# Domain notes — pharmaceutical QA operations

Distilled notes on the domain this repo models. All entities are fictional.

## Why QA deviations matter
In pharmaceutical manufacturing, a batch cannot be sold until Quality Assurance
releases it. Every departure from an approved procedure — a deviation — must be
recorded, classified, investigated, and closed. Unreleased batches tie up
inventory and delay supply; wrongly released batches risk patient safety and
regulatory action. The operating tension is speed of release versus rigor of
review.

## The three concepts that run this repo
1. **Deviation classification** (critical / major / minor) decides how much
   investigation a departure gets. Critical means sterility, data-integrity, or
   patient-safety impact. Repeats escalate: the same root cause twice is never
   "just minor" again.
2. **The sign-off chain** (QA reviewer → QA manager → Qualified Person) is the
   release gate. Each role checks something different, in order, and a batch
   moves only when every gate passes. The Qualified Person is the legally
   accountable release authority.
3. **CAPA linkage** connects fixes to causes. A CAPA that is overdue blocks the
   manager's sign-off, which blocks release — the quality system paces the
   factory, not the other way around.

## What the agent is for
QA staff ask operational questions — "which batches are blocked and why?",
"what repeats are we seeing?", "are we audit-ready?" — and the agent answers
from the controlled records with citations, escalating anything it cannot
prove. It never makes release decisions; it prepares the evidence humans
decide on.
