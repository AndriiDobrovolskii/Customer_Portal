---
artifact_type: open_decisions
story: US-5.2
version: 2
status: DRAFT
created_at: "2026-09-08T06:22:35Z"
updated_at: "2026-09-08T00:35:00Z"
produced_by: us-clarifier
resolutions_recorded_by: story-orchestrator
inputs:
  - path: docs/product/product-vision.md
    version: null
  - path: docs/product/personas.md
    version: null
  - path: docs/product/business-rules.md
    version: null
  - path: docs/product/business-glossary.md
    version: null
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/workflow/active-story.yaml
    version: null
  - path: docs/specifications/US-1.3-spec.md
    version: null
  - path: docs/specifications/US-2.5-spec.md
    version: null
  - path: docs/stories/US-1.3-update-profile.md
    version: null
supersedes: null
---

# US-5.2 — Open Decisions

**Story:** `docs/stories/US-5.2-account-self-service-ui.md` — Account & Profile Self-Service (Frontend)
**Stage:** CLARIFICATION
**Status of this log:** First clarification pass for US-5.2 — no prior `US-5.2-open-decisions.md` existed to reconcile against. OD-1, OD-2, and OD-4 were RESOLVED by human decision at the HUMAN_SPEC_APPROVAL rejection of spec v1 (see resolutions inline below); OD-3, OD-5, OD-6, OD-7 remain `OPEN`.

Each entry: the question, why it cannot be inferred from `docs/product/*`, the story, or the current backend implementation, and the concrete impact of leaving it unresolved. Four of the seven (OD-4 through OD-7) restate the story's own four "Open Questions" in this format rather than silently dropping them, per this skill's contract; OD-1 through OD-3 are new findings surfaced by reading the actual `app/modules/profile`, `app/modules/users`, and `app/modules/account` source the story's API Contract table claims to summarize — the table itself is incomplete/incorrect on three material points.

---

## OD-1 — `If-Match` is unconditionally required by the backend; the write-only-interim design (Assumption #2/#3) cannot make its own first write

**RESOLVED (2026-09-08, by sbruhov@gmail.com at HUMAN_SPEC_APPROVAL rejection):** The client must send `If-Match: *` for the first `PATCH /profile` write in a session, when no ETag is yet known from a prior write. This makes the first write's precondition unconditional-overwrite semantics explicit rather than "omitted," resolving the contradiction with the backend's unconditional `If-Match` requirement.

**Question:** Given `PATCH /profile` rejects **every** request with no `If-Match` header (`400 precondition-required`), not just requests with a *stale* one, how is the very first profile edit in a session supposed to succeed when there is no `GET /profile` to seed an ETag from and Assumption #3 explicitly plans to "omit `If-Match`" on that first write?

**Why it can't be inferred:** The story's own text is internally inconsistent with the backend it describes:
- Assumption #2/#3 state `If-Match` is sent "only when an ETag from a previous write in this session is known, and is omitted otherwise," and gloss the FastAPI parameter type (`if_match: str | None = None`) as meaning "the header is optional server-side."
- The **source story this contract derives from**, `docs/stories/US-1.3-update-profile.md`, states the opposite in its own Assumptions table (#4): *"Concurrency control — `If-Match` header with resource ETag is **required** on every PATCH."* Its UP-AC2 tests exactly this: a missing `If-Match` header is rejected.
- The shipped code confirms UP-AC2, not US-5.2's gloss: `app/modules/profile/service.py:151-152` — `if if_match is None: raise PreconditionRequiredError` — runs unconditionally, before any other validation, with no carve-out for "no ETag known yet." `docs/specifications/US-1.3-spec.md` FR-2 documents the same `400 .../errors/precondition-required` response.
- The FastAPI parameter being typed `str | None = None` only means the *header* is optional at the transport level (so a request without it still routes); it says nothing about what the service does once it sees `None` — and what it does is reject.

The one documented escape hatch is a wildcard: `if_match not in ("*", current_etag)` accepts a literal `"*"` as matching any ETag (same pattern independently duplicated in `app/modules/admin_users/service.py:283`, so it is an intentional, reused convention, not incidental). Nothing in `docs/product/*`, this story, or `US-1.3-update-profile.md`/`US-1.3-spec.md` states that `If-Match: *` is the client's sanctioned way to make an unconditional first write.

**Impact if unresolved:** As literally written, PS-AC2's write-only interim mode is guaranteed to fail on every account's first profile edit ever (400, not the described happy path or even the described 412 conflict path), because there is no way to have "an ETag from a previous write in this session" before any write has happened, and omitting the header is rejected outright. A spec-writer must decide — and this decision cannot be deferred to implementation without risking a shipped screen that cannot save on first use — whether the client sends `If-Match: *` whenever no ETag is known (accepting an unconditional overwrite semantics for the first write only), or whether some other mechanism is intended.

---

## OD-2 — MFA enroll and disable both require request bodies the story's contract table and ACs omit entirely

**RESOLVED (2026-09-08, by sbruhov@gmail.com at HUMAN_SPEC_APPROVAL rejection):** Add a required `current_password` field to the MFA-enroll form. Add required `current_password` and TOTP `code` fields to the MFA-disable form, plus an explicit warning in that form's confirmation step that disabling MFA revokes every other active session.

**Question:** `POST /auth/mfa/enroll` and `DELETE /auth/mfa` both require fields never mentioned by PS-AC5/PS-AC6 or the story's API Contract table — should the spec add a password (and, for disable, a TOTP code) input step to these two flows, and what confirmation copy should disable use given it also silently revokes every other session?

**Why it can't be inferred:** Confirmed directly against `app/modules/users/schemas.py` and `service.py`:
- `MfaEnrollRequest` (`schemas.py:89-92`) requires `current_password: SecretStr`. `service.py:1301-1305` (`enroll_mfa`) verifies it and raises `InvalidCredentialsError` on mismatch. `docs/specifications/US-2.5-spec.md` MF-AC1 confirms this is deliberate: "...When `POST /v1/auth/mfa/enroll` is called **with the correct `current_password`**..."
- `MfaDisableRequest` (`schemas.py:133-140`) requires **both** `current_password` and a 6-digit `code`, checked jointly (`service.py:1515-1554`) and collapsed to one generic `InvalidCredentialsError` on either failing — a deliberate anti-enumeration design documented in the surrounding comment ("a caller who has the password but not the code... cannot distinguish which factor was wrong"). Disabling MFA also sets `revoke_before` for the account (`docs/specifications/US-2.5-spec.md` OD-6/OD-8: "...all recovery codes deleted... and `revoke_before:{user_id}` set — revoking every other active session"), which is not named anywhere in PS-AC6 or the NFR's "confirmation naming the consequence" bullet.
- US-5.2's own API Contract table lists both endpoints' Request column as `—`, and PS-AC5 ("When they start enrollment Then `POST /auth/mfa/enroll` is called...") and PS-AC6 ("When they confirm disabling it Then `DELETE /auth/mfa` is called...") describe both as needing no input beyond the confirmation click (enroll) or the 6-digit activation code (enroll's *second* step, `MfaActivateRequest`, which correctly needs no password).

**Impact if unresolved:** A spec/screen built strictly to the story's stated contract and ACs would omit the password field from the enrollment screen and both the password and TOTP-code fields from the disable screen — every real call to either endpoint would then fail (401/422) for every user, 100% of the time, since the fields the backend requires are never collected. This is not a corner case; it is the endpoints' primary success path.

---

## OD-3 — Enrollment-scoped access tokens 403 on every route except `/mfa/enroll` and `/mfa/activate` — no navigation behavior is specified for that state

**Question:** When a privileged-role account (`admin`/`auditor`/`support_agent`) is inside its 14-day MFA grace period and holds an enrollment-scoped access token, every route other than `/mfa/enroll` and `/mfa/activate` rejects it with `403 mfa-enrollment-required` by default (`app/modules/users/service.py:716,726-732,774-775`; `app/modules/users/dependencies.py:104-119`). Should the authenticated app shell force-navigate such a caller straight to the MFA enrollment screen, or is US-5.1's existing dismissible banner-plus-link (Assumption #6) considered sufficient even though dismissing it (or navigating anywhere else first) leads to 403s on every other screen?

**Why it can't be inferred:** BR-013 (`docs/product/business-rules.md`) states the grace period and mandate but not UI navigation behavior for it. `docs/product/personas.md`'s Administrator/Auditor/Support Agent goals don't describe this state either. US-5.2's own scope is written for the Customer persona and treats the banner-link as the entire integration point (Assumption #6: "the link target finally exists"); it does not address that this token-scoping mechanism makes *every other authenticated screen* actively hostile (a confusing 403, not just an unlinked banner) until enrollment completes.

**Impact if unresolved:** Left undecided, an implementer may ship only the banner link (satisfying Assumption #6's literal wording) while leaving every other route to surface a raw `403 mfa-enrollment-required` problem+json via XC-AC1's generic handling — technically "handled" per XC-AC1, but a confusing dead-end for the exact users (privileged staff mid-grace-period) BR-013 exists to nudge toward enrolling. Whether that is acceptable-for-now or requires a redirect guard is a product decision, not something inferable from source.

---

## OD-4 — `POST /account/deactivate`'s `current_password` optionality is real but the story doesn't say when the UI should treat it as required

**RESOLVED (2026-09-08, by sbruhov@gmail.com, confirmed via /so:next clarifying question):** The deactivation form always requires `current_password`. Password-less (invited, never-completed-setup) accounts are out of scope for self-service deactivation through this Story's UI.

**Question:** The story's own Open Question #4 asks whether `current_password` should always be required by the UI. Given the schema (`current_password: SecretStr | None = None`) and the confirmed service behavior, should the deactivation form always require the field, and if not, how does the client know when to omit it?

**Why it can't be inferred:** Confirmed in `app/modules/account/service.py:47-53`: when `current_password` is omitted, the service substitutes an empty string and still calls `verify_password("", user.hashed_password)` — for any account that has ever set a real password, this deterministically fails (`InvalidPasswordError`, generic 401-style rejection). The optionality is only meaningful for a password-less account (an admin-created `invited`-status account whose owner never completed setup). Nothing in `docs/product/*`, this story, or `ProfileRead` (profile view is itself blocked — see OD-5/Dependencies & Blockers #1) gives the client a signal for whether the current account has a password at all.

**Impact if unresolved:** If the UI always requires the field (simplest, and correct for every Customer persona case named in `docs/product/personas.md`), a password-less account can never self-deactivate through this screen — no error path in the story covers that case either. If the UI makes the field optional to accommodate that account type, most submissions with it blank will hard-fail with no way for the user to tell why (there's no account-state signal to explain "you don't need a password" vs. "you forgot your password").

---

## OD-5 — No backend Story has been raised yet for the missing `GET /profile` / `GET /users/me`

**Question:** The story's own Open Question #1 and its Dependencies & Blockers #1 both flag that PS-AC1 is blocked because no read endpoint exists, and that "a backend Story must be raised." Should `CLARIFICATION`/`SPECIFICATION` proceed now, permanently treating PS-AC1 as out-of-scope/deferred for this Story, or should progression wait until that backend Story exists (or is at least scheduled)?

**Why it can't be inferred:** Confirmed by direct inspection: `app/modules/profile/router.py` defines only `PATCH ""` and `POST "/confirm-email-change"` — no `GET`. No file matching a `GET /profile` or `GET /users/me` backend story exists under `docs/stories/`, and `docs/stories/README.md` independently documents the same gap ("US-5.2's profile *view* is blocked... the edit path ships write-only") without naming a story number to track it. `docs/catalog/stories.yaml`'s US-5.2 entry repeats the same open-ended framing. Nothing commits to when or whether that backend Story will be raised.

**Impact if unresolved:** Left open, the spec-writer must independently decide whether to word PS-AC1 as "deferred" (this Story ships without it, cleanly) or leave it in a limbo state that later blocks `RECONCILIATION`/`SECURITY_REVIEW` on a criterion no implementation can satisfy. This also compounds OD-1: even the write-only path's happy case depends on resolving how the client handles "no known ETag" without a `GET`.

---

## OD-6 — `SupportedLocale`'s two-item list is confirmed a placeholder — ship it anyway?

**Question:** The story's own Open Question #2 asks whether the UI should ship the current two-item locale list (`en-US`, `en-GB`) as-is, given the backend's own code says it is provisional.

**Why it can't be inferred:** Confirmed in `app/modules/profile/schemas.py:9-13`: `SupportedLocale` is a two-value `StrEnum`, preceded by the comment *"Placeholder set pending product confirmation — no authoritative locale list exists anywhere in this codebase or its docs yet."* `docs/product/business-rules.md` and `business-glossary.md` are both silent on supported locales entirely.

**Impact if unresolved:** If the spec proceeds with a hard-coded two-item dropdown and product later expands the list, the frontend needs a follow-up change with no client-side extensibility built in today. If instead the spec is written to treat the list as forward-compatible (e.g. driven by a constant the client re-derives rather than duplicates by hand), that needs to be decided now, not discovered during implementation.

---

## OD-7 — Timezone input: full IANA list vs. curated subset

**Question:** The story's own Open Question #3 asks whether the timezone field should present the full ~600-entry `zoneinfo.available_timezones()` set or a curated subset, given no curated list exists anywhere in the codebase.

**Why it can't be inferred:** Confirmed in `app/modules/profile/schemas.py:16,36-42`: the server validates against the complete `zoneinfo.available_timezones()` with no allow-list narrower than that. No curated/regional subset appears anywhere else in the repository (`docs/product/*` included).

**Impact if unresolved:** A ~600-entry unfiltered dropdown is a materially different (and worse) UX/a11y surface than a searchable curated list, and this Story's own NFR bar requires "full keyboard navigation" on every control — an implementer choosing the full list without deciding on a search/typeahead affordance risks failing that NFR on this field specifically. Left undecided, the choice would be made ad hoc during implementation with no product-level source to point to.

---

## Summary

| # | Topic | Source of ambiguity |
|---|---|---|
| OD-1 | `If-Match` unconditionally required; write-only-interim's first write cannot succeed as described | `US-1.3-update-profile.md` Assumption #4 / UP-AC2, `US-1.3-spec.md` FR-2, `app/modules/profile/service.py:151-156` vs. US-5.2 Assumption #2/#3, PS-AC2 |
| OD-2 | MFA enroll/disable request bodies (password; password+code) and disable's session-revocation side effect, all omitted from the story | `app/modules/users/schemas.py` (`MfaEnrollRequest`, `MfaDisableRequest`), `service.py:1301-1554`, `US-2.5-spec.md` MF-AC1/OD-6/OD-8 vs. PS-AC5/PS-AC6, API Contract table |
| OD-3 | Enrollment-scoped tokens 403 everywhere except enroll/activate — no forced-navigation behavior specified | `app/modules/users/service.py:716-775`, `dependencies.py:104-119`, BR-013 vs. Assumption #6 |
| OD-4 | Deactivation `current_password` optionality only meaningful for password-less accounts; UI behavior unspecified | `app/modules/account/service.py:47-53` vs. story's own Open Question #4 |
| OD-5 | No backend Story yet raised for `GET /profile`/`GET /users/me` | `app/modules/profile/router.py`, `docs/stories/README.md`, story's own Open Question #1 / Dependencies & Blockers #1 |
| OD-6 | `SupportedLocale` two-item list confirmed provisional | `app/modules/profile/schemas.py:9-13`, story's own Open Question #2 |
| OD-7 | Timezone picker: full IANA list vs. curated subset | `app/modules/profile/schemas.py:16,36-42`, story's own Open Question #3 |

OD-1, OD-2, and OD-4 were resolved at `HUMAN_SPEC_APPROVAL` (see inline resolutions above); OD-3, OD-5, OD-6, OD-7 remain open and unresolved by this pass.
