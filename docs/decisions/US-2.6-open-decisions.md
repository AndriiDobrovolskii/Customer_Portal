# Open Decisions: US-2.6 Active Session Management

**Story:** `docs/stories/US-2.6-active-sessions.md`
**Pre-existing spec:** `docs/specifications/US-2.6-spec.md` (drafted 2026-08-22, Pass with Issues, predates the actual US-2.1/US-2.2/US-2.3 codebase now in place).
**Logged:** 2026-09-02

## Resolutions (2026-09-02)

All four Open Decisions below were resolved by the user on 2026-09-02, recommended option accepted in every case:

- **OD-1:** Reject with `409 Conflict` (`type=".../errors/current-session"`) rather than silently revoking the caller's own current family.
- **OD-2:** On cap eviction, revoke the oldest family via the same US-2.2 revocation write and log `auth_audit_log` (`event=session_evicted`); no notification email.
- **OD-3:** Add the `user-agents` PyPI library; format `"{browser family} on {OS family}"`, fall back to `"Unknown device"`.
- **OD-4:** Bundle a local MaxMind GeoLite2-City database, queried in-process; `null`/omitted location on private/unresolvable IPs.

## Resolved by existing implementation (not logged as Open Decisions)

Checking the pre-existing spec's Open Questions against the real codebase (US-2.3's actual `RefreshToken` implementation, merged since the spec was drafted) resolves three of its six items outright:

- **"Capture and update of session metadata during rotation" (In Scope item with no AC)** — already fully implemented. `app/modules/users/models.py`'s `RefreshToken` already has `family_id`, `ip`, `user_agent`, `last_used_at`, and `revoked_at` columns (the spec's Data Model Notes describe these as columns *to add*, but US-2.3's real implementation already shipped them). `service.py`'s refresh/rotation path (`~L864-873`) already writes `ip`, `user_agent`, and `last_used_at=now` on every new `RefreshToken` row at rotation time. This story needs no new migration for these fields and no new capture logic — only the read side (`GET /v1/auth/sessions`) is new.
- **Dual `last_used_at` write strategy (async vs. throttled-to-one-per-minute)** — moot. `last_used_at` is written once per rotation (i.e., once per refresh-token use), not on every request, so there is no per-request write-amplification for either strategy to guard against. The existing synchronous write in the rotation path (same call as the DB write already happening) is the natural implementation; no separate async/throttle mechanism is needed.
- **Malformed/nonexistent `family_id` casing** — resolved by precedent. No endpoint in this codebase distinguishes a syntactically-invalid identifier from a well-formed-but-unknown one (e.g., `GET /v1/auth/refresh` and US-2.2's revoke path both fold "no matching row" and "malformed input" into the same not-found-shaped response). Recommend the identical treatment here: any `family_id` that doesn't resolve to a token the caller can act on returns `404`, whether malformed or simply unknown.

## OD-1 (Medium) — Revoking the caller's own current session

**Question:** `DELETE /v1/auth/sessions/{family_id}` is scoped by SM-AC2/FR-2 to "a family_id belonging to another of their devices," and the story's Out of Scope section excludes "Logout of the current session and logout-everywhere (US-2.2)." Neither the story nor the pre-existing spec states what happens when the caller passes their *own current* `family_id`.

**Why it can't be inferred:** `business-rules.md` BR-009 defines "logout" (ending the current session) and "logout everywhere" as the two existing mechanisms for ending one's own current session, both owned by US-2.2. This story's Out of Scope line reads as excluding those two *flows* (there's no new endpoint replicating them), not necessarily excluding the *outcome* of DELETE-ing one's own family_id through this endpoint. Both readings are defensible: (a) treat it identically to any other family — 204, revoke, done, since the story never says to special-case it; (b) reject it, since ending your own last active connection via a "manage other devices" endpoint is a confusing UX dead-end (the caller's next request has no valid session to retry with) and isn't validated by any AC.

**Impact if left unresolved:** `openapi-designer`/`db-designer` can't decide whether this endpoint needs a distinct error path (and error `type` slug) for the current-family case, and `test-writer` can't write a deterministic AC for it either way.

**Recommendation:** Reject with `409 Conflict` (`type=".../errors/current-session"`) rather than silently revoking. Ending your own only-currently-valid session through a "review your other devices" endpoint has no legitimate use case the story describes (logout already exists for that, per BR-009), and a distinct rejection is cheap to test and avoids leaving the caller's active token in a state where the family_id it's using is dead but nothing said so.

## OD-2 (Medium) — Live-session cap eviction behavior

**Question:** The story's Assumptions & Defaults table sets a cap of "20 families per user, oldest evicted," repeated in the Non-Functional Requirements, but no Acceptance Criterion describes what happens when a new login/session pushes the count past 20: is the oldest family revoked via the identical US-2.2 revocation path, is an `auth_audit_log` entry written for the eviction (and under what `event` name), and does the evicted device receive any signal (e.g. a security-notification email, mirroring BR-008's stolen-refresh-token pattern)?

**Why it can't be inferred:** No cap-enforcement logic of any kind exists in the codebase today (confirmed via search — no `20`, no session-cap constant, no eviction call site). This is new behavior with no precedent to borrow from; BR-008's theft-detection email is the closest analogue but is triggered by a security event, not routine capacity management, so applying it here isn't automatic.

**Impact if left unresolved:** `planner`/`data-layer-builder` can't decide where the eviction check runs (on login, forming part of FR-1 of the *login* spec rather than this one) or whether this story's own FR-1/FR-2 need to describe the evicted family showing up in the list response history or audit trail.

**Recommendation:** On login, when creating a new family would exceed 20 live families for the user, revoke the single oldest family (by `issued_at` of its earliest surviving token, or equivalently its `created_at`) via the exact same revocation write US-2.2's logout path uses, and write `auth_audit_log` (`event=session_evicted`, `target_family=<family_id>`) — audit-log everything per BR-014's posture, distinct from `session_revoked` so an eviction is distinguishable from an explicit user action. No notification email: this is routine capacity management, not the theft scenario BR-008 targets.

## OD-3 (Low) — Device/browser label derivation

**Question:** SM-AC1/FR-1 require "a parsed device/browser label" but neither the story nor the spec defines how it's derived from the `User-Agent` string, or what value (if any) is returned when the header is missing or unparseable.

**Why it can't be inferred:** No user-agent-parsing library exists in `pyproject.toml` today, and no other story in this codebase performs this kind of parsing — there's no internal precedent to reuse.

**Impact if left unresolved:** `data-layer-builder`/`service-and-router-builder` can't decide whether this needs a new third-party dependency, and `test-writer` can't assert an exact label without a defined format and fallback.

**Recommendation:** Add a small, actively-maintained UA-parsing library (e.g. `user-agents` on PyPI) and format the label as `"{browser family} on {OS family}"` (e.g. `"Chrome on Windows"`); fall back to the literal string `"Unknown device"` when the header is missing or the parse yields no recognizable browser/OS. Parse at read time (`GET /v1/auth/sessions`), not at capture time, so a future library upgrade improves historical labels for free.

## OD-4 (Low) — Geo-IP location derivation mechanism

**Question:** SM-AC1/FR-1 require "approximate location (city/country from IP)" but neither the story nor the spec names a mechanism. Is this a local offline database (e.g. MaxMind GeoLite2), a live third-party API call, or something else?

**Why it can't be inferred:** No geo-IP library, dataset, or config setting exists anywhere in the codebase. `docs/decisions/US-2.4-open-decisions.md` OD-1 already established a project-wide precedent when this exact tension came up for breached-password checking: this codebase's entire integration-test suite runs network-free against real Postgres/Valkey via testcontainers, and every existing "external-looking" check is self-contained — a live third-party geo-IP call would be a first, and would need to be mocked or would make the suite flaky.

**Impact if left unresolved:** `db-designer`/`planner` can't size the dependency (a bundled binary GeoLite2 database file + its license/update-cadence questions, vs. an outbound HTTP client and its settings), and can't decide how the integration suite exercises this path.

**Recommendation:** Bundle a local MaxMind GeoLite2-City database (free tier, city/country resolution) and query it in-process, consistent with the project's established no-live-external-call precedent (OD-1, US-2.4). Fall back to `null`/omitted location fields when the IP is private/loopback (common in tests) or has no entry in the database — do not fail the request.

---

## Verdict input

All 4 Open Decisions above plus the 3 items resolved by precedent are believed to be the complete set of ambiguities; nothing else in the story, the pre-existing spec, or its review appears unresolved.
