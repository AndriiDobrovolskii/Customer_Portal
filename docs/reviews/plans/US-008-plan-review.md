# Plan Review: Password Reset (US-2.4 / spec US-008)

**Story ID:** US-2.4
**Plan Reviewed:** docs/plans/US-008-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-008-task-breakdown.md
**Reviewed:** 2026-09-01
**Overall Verdict:** Pass with Issues

## Summary

The plan covers every file `impact-analysis.md` named, the task breakdown's T1–T8 sequence respects AGENTS.md §3's downward-only layering (schemas/models-repo-cache in parallel → migration → service → router → tests → gate, mirroring US-2.3's own T1–T8 shape exactly), and both the Risks and Testing Strategy sections are concrete rather than boilerplate. Verdict is "Pass with Issues" for two Low, non-blocking gaps: `tests/conftest.py`'s contingent status (flagged as uncertain by impact-analysis) isn't picked up as an explicit task-breakdown item, and the new bundled breached-password data asset's size/provenance/load-cost is never addressed in Risks despite being the first data file of its kind in this codebase.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `app/modules/users/models.py` | Covered | Files To Modify; Task T2 | `PasswordResetToken` per db-design. |
| `app/modules/users/schemas.py` | Covered | Files To Modify; Task T1 | |
| `app/modules/users/repository.py` | Covered | Files To Modify; Task T2 | Atomic-consume method named explicitly. |
| `app/modules/users/cache.py` | Covered | Files To Modify; Architectural Change #2; Task T2 | |
| `app/core/cache_keys.py` | Covered | Files To Modify; Task T2 | |
| `app/modules/users/exceptions.py` | Covered | Architectural Change #4; Files To Modify; Task T4 | Resolves the `TokenInvalidError` 401-vs-400 conflict impact-analysis flagged. |
| `app/modules/users/router.py` | Covered | Files To Modify; Task T5 | |
| `app/modules/users/dependencies.py` | Covered | Files To Modify; Task T5 | |
| `app/core/email.py` | Covered | Files To Modify; Task T4 | |
| `app/core/config.py` | Covered | Files To Modify; Task T2 | |
| New breach-check helper (`app/core/security.py` or new module) | Covered | Architectural Change #3 (resolved as new `app/core/breached_passwords.py`); Task T4 | Impact-analysis left the exact location open (OQ-1); plan resolves it. |
| Cross-module: `email_verification`/`profile` `RecordingEmailSender` fakes | Covered | Files To Modify; Task T7's verification command | |
| Migration: new `password_reset_tokens` table, additive only | Covered | Risks ("Migration risk: low"); Task T3 | |
| Test surface: `test_users_service.py` (existing, extended) | Covered | Testing Strategy; Task T6 | |
| Test surface: `test_users_router.py` (existing, extended) | Covered | Testing Strategy; Task T7 | |
| Test surface: `tests/conftest.py` (uncertain — impact-analysis: "not certain until implementation-planner sequences the tasks") | Partially Covered | — | See Scope/Coverage note below — impact-analysis's own uncertainty is neither resolved nor tracked as a task. |

## Risk Realism

- **[Low] Breached-password data asset's provenance/size/load-cost not addressed** — Plan's Architectural Change #3 says: "A bundled flat wordlist (`app/core/data/common_passwords.txt` or similar), loaded once into a module-level `frozenset[str]`... A plain set lookup is O(1) and needs no bloom-filter complexity at this list's expected scale (tens of thousands of entries)." The Risks section covers migration, concurrency, anti-enumeration timing, rate-limit keying, and the `EmailSender` ripple, but never mentions this new bundled asset — where its contents come from, how large it actually ends up being, or whether loading it adds meaningfully to process startup time. This is the first data file of its kind shipped with this application (every other artifact in this codebase is code or a migration), so it's a genuinely new category of risk the plan is silent on, even though it's a small one at the stated scale.

## Test-Strategy Realism

No findings — the plan concretely names the unit (`FakeUserRepository` extensions, no `MagicMock`, including a `simulate_race_on_consume`-style flag) vs. integration (real Postgres+Valkey via testcontainers, `asyncio.gather` concurrency proof) split per AGENTS.md §5, and cites the specific US-2.3 precedent it's modeled on for the race test.

## Scope Creep

No findings — every plan item traces to a spec FR, an impact-analysis item, or an explicitly-flagged impact-analysis gap (the `TokenInvalidError` conflict) that the plan appropriately resolves rather than leaves dangling.

## Verdict Rationale

Pass with Issues: full impact-analysis coverage (with one Partially Covered item — `tests/conftest.py`'s own pre-existing uncertainty, not a new gap the plan introduced) and correct §3 layering order in the task breakdown, so nothing here blocks implementation outright. The one Risk-Realism gap (breach-list asset characteristics) is worth a one-line addition before or during T4, not a re-plan.
