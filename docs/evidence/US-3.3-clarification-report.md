# Clarification Report: US-3.3 (View Audit Information)

**Story:** docs/stories/US-3.3-view-audit-information.md
**Run date:** 2026-09-02 (updated 2026-09-02 — all 4 blocking Open Decisions resolved by the user)
**Verdict: Ready for Specification**

## Scope, Actor, Business Value

An `admin` or `auditor` (both roles, per `docs/product/business-glossary.md` and `BR-010`, already shipped by US-3.2) needs to query a tamper-evident, append-only record of security- and admin-relevant events — one filtered, cursor-paginated `GET /v1/admin/audit-logs` endpoint — to investigate an incident or answer a compliance request. In scope: the query endpoint, immutability/tamper-evidence guarantees, and retention/post-erasure behavior. Out of scope: async bulk export, SIEM forwarding, infra-log ingestion. This matches the story text; no ambiguity in scope, actor, or value.

## What's Clear

- **Permission dependency is satisfied.** `docs/stories/README.md` states "US-3.3 depends on US-3.2 (`audit:read` scope)." Confirmed live: migration `e50fbe8161fc_add_roles_and_permissions.py` seeds `audit:read` and grants it to the `auditor` role (and, being a catalogue-wide grant, to `admin`). `app.modules.roles.router`'s `Depends(require_scope(...))` pattern is an established, reusable precedent for AU-AC3's 403 gate.
- **Immutability precedent exists.** `BR-014` (sourced from this story's own pre-existing spec) already documents the INSERT/SELECT-only DB-grant rule; no new decision needed there.
- **`limit`/`cursor` bounds** — resolved by precedent from `app/modules/admin_users/service.py::list_users` (max `limit`=100 → 422 field error; invalid cursor → 422 field error). See OD-5.
- **Job architecture precedent** — this project's one shipped scheduled job (`scripts/purge_unverified_accounts.py`) establishes the pattern (a standalone script under `scripts/`, externally triggered) that AU-AC7's chain-verification job and AU-AC9's retention job should follow, and that a DA-AC9 permanent-deletion job (OD-2) would follow too.
- **Nine ACs, zero contradictions** with `docs/product/business-rules.md`/`business-glossary.md` — this corroborates the pre-existing spec review's finding (`docs/reviews/specifications/US-013-spec-review.md`, Pass with Issues, 2026-08-22).

## What's Ambiguous or Blocking

A pre-existing draft spec and review (`docs/specifications/US-013-view-audit-information-spec.md`, `docs/reviews/specifications/US-013-spec-review.md`, both 2026-08-22) already exist and are largely sound, but both predate US-3.1/US-3.2 landing on `main` and so could not check the story's assumptions against the real codebase, nor cross-check the story against itself as closely as this run did. That check surfaced four **blocking** issues:

- **OD-1 (blocking):** the story's own Assumptions table and Data Model Notes disagree on whether `audit_log` is a new central write-target table or a read-only view — and under either reading, the name collides with a real, already-shipped, unrelated table of the same name (`app/modules/email_verification/models.py::AuditLog`, serving BR-002's 7-day unverified-account purge).
- **OD-2 (blocking):** AU-AC8 is written as if "the US-1.4 DA-AC9 retention job" already exists and can be exercised end-to-end. It doesn't — DA-AC9 is explicitly deferred in its own story (`[manual]`, pending DPO sign-off) and in `BR-007`; only a different, narrower job (7-day unverified-account purge, not 30-day deactivated-account erasure) is actually implemented.
- **OD-11 (blocking):** the story contradicts itself on partition granularity — Assumption #4 and AU-AC7 both say "daily," Data Model Notes says "monthly." This is upstream of the hash-chain trigger design and the migration's partitioning DDL.
- **OD-12 (blocking):** AU-AC4 requires database-grant-enforced immutability, `[gate]`-tested, but no migration in this codebase contains a `GRANT`/`REVOKE` statement, and the app's configured DB connection (`app/core/config.py`, `.env.example`) is the PostgreSQL **superuser** role (`postgres`), which cannot be restricted by grants at all. This is real, previously-unscoped infrastructure work, not a coding gap.

Plus two Medium, non-blocking scope-sizing notes (OD-3: the four existing per-domain audit tables need new columns before the view can work; OD-4: the view's fifth source table, `ticket_audit_log`, doesn't exist because Epic 4 is unbuilt), and five carried-forward Low/Medium items from the pre-existing spec review that remain genuinely unresolved by anything in the current codebase (OD-6 hash-chain concurrency, OD-7 sensitive-field enumeration, OD-8 payload-JSONB redaction scope, OD-9 cold-storage target, OD-10 single missing from/to bound).

Full detail, options, and recommendations for all twelve items: `docs/decisions/US-3.3-open-decisions.md`.

## Resolution (2026-09-02)

The user resolved all four blocking items, accepting the recommended option in every case:

- **OD-1:** Rename `email_verification.AuditLog`/`audit_log` to `unverified_account_purge_log` via a migration; `audit_log` becomes this story's new central artifact.
- **OD-2:** Build a minimal, provisional DA-AC9 script (anonymizes the `users` row + redacts identifiers on that user's existing audit rows) — enough to make AU-AC8 testable. The anonymize-vs-hard-delete legal/DPO question stays open as a separate, tracked item.
- **OD-11:** Daily partitions, chain scoped per day — the Data Model Notes' "monthly" line is superseded.
- **OD-12:** Ship only the API-level `405` for this story (gate-tested); the DB-role/`GRANT`-`REVOKE` infrastructure is deferred to a separate, project-wide follow-up ticket, disclosed as not yet enforced.

Full resolution text: `docs/decisions/US-3.3-open-decisions.md` (Resolved notes under OD-1/OD-2/OD-11/OD-12).

## Verdict

**Ready for Specification.** All blocking items resolved. OD-3/OD-4 need no user decision (recommendations stated, feed straight into DESIGN sizing) but are noted so PLANNING doesn't under-scope the story. OD-5 is resolved by precedent. OD-6–OD-10 are pre-existing open items, restated rather than newly discovered, and don't block moving to SPECIFICATION on their own — carried forward for `story-spec-writer` to fold in or flag, per this skill's job to never silently drop a still-open item.
