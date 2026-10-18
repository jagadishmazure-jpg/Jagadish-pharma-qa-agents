# Implementation guide

How to adopt this repo's patterns in a real QA organization.

## 1. Replace the synthetic data layer
`pharmaqa/telemetry.py` builds an in-memory SQLite database. Point `build_db`
at your real QA system instead: keep the 4 view definitions in `views.py` as
the contract, and reimplement them over your LIMS/QMS views. The gateway,
intents, and classifier do not change.

## 2. Wire the sign-off chain to your QMS
`release.py` evaluates criteria against the database. Map the three roles to
your approval workflow (many sites have more steps — add them as further
`RoleResult` entries in order). The "chain stops at first failure" semantics
should be preserved: it is what makes blocked releases explainable.

## 3. Tune the classifier, then validate it
`classify.py` rules are intentionally simple keyword rules. Replace them with
your site's classification procedure, then back-test: run every historical
deviation through the new rules and measure agreement with the recorded
classifications before trusting it.

## 4. Connect the regulatory feed
`LiveRegFeed` is a stub that reports a gap. Implement it against your
regulatory intelligence source, cache snapshots, and alert when the cache is
stale — a silent gap is worse than a reported one.

## 5. Human-in-the-loop placement
The agent prepares evidence; humans decide. Keep the confirmation gates on
batch rejections and critical-deviation closures, and route T3/T4 escalations
to the on-call QA manager / Qualified Person, not to a queue nobody watches.

## 6. Feedback loop
`feedback.py` captures thumbs and corrections with PII scrubbing. Feed
corrections into a golden eval set (see the agent-feedback-loop pattern) and
gate model or prompt changes on it.
