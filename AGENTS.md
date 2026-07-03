# Agent Operating Rules

Standing operating rules for this project, established over many sessions of real debugging.
For current project state, read `handoff.md`; do not duplicate that handoff here.

1. Read-only investigation before any write. Confirm current state with real queries and file reads; never trust a prior session's summary without checking.
2. Row-count guards on every ingestion script. Hard stop on mismatches; never silently partial-load.
3. Idempotent inserts and deterministic pagination. Use `ON CONFLICT` for repeat-safe loads and `$order=:id` on Socrata calls. A real bug in this project caused massive duplicate rows from non-deterministic pagination; never repeat it.
4. Documentation contract. Every functional change updates `README.md` in plain language in the same commit. Explain the why, not just the what.
5. Show diffs before schema or data changes. Never run destructive operations such as `DELETE`, `TRUNCATE`, or `ALTER` without an explicit go-ahead shown first.
6. Verify by running, not by trusting. Confirm claims with a live query, real command output, or real HTTP request instead of re-stating a prior report.
