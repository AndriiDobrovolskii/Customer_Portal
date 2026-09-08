---
artifact_type: clarification_report
story: US-5.2
version: 1
status: ARCHIVED
created_at: "2026-09-08T06:22:35Z"
updated_at: "2026-09-08T18:25:00Z"
produced_by: us-clarifier
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

# US-5.2 — Clarification Report

**Story:** `docs/stories/US-5.2-account-self-service-ui.md` — Account & Profile Self-Service (Frontend)
**Stage:** CLARIFICATION
**Active-story check:** Confirmed. `docs/workflow/active-story.yaml` names `US-5.2` / `docs/stories/US-5.2-account-self-service-ui.md` as the active Story (`status: IN_PROGRESS`), matching the requested target. `docs/workflow/workflow-state.yaml` independently confirms `story: US-5.2` at `current_stage: CLARIFICATION`/`status: IN_PROGRESS` — the two agree. No mismatch to report.
**Prior Open Decisions log:** None existed for US-5.2 before this run.

## Scope, Actor, and Business Value

**Actor:** the Customer persona (`docs/product/personas.md`) — an already-authenticated user of the Customer Portal. This Story is explicitly frontend-only and depends on US-5.1 (auth store, API client, route guards, problem+json rendering), which is `ARCHIVED` and shipped (`docs/catalog/stories.yaml`).

**Trigger/business value:** stated directly and clearly in the User Story — this Story turns four already-shipped backend capabilities (US-1.2 email verification, US-1.3 profile update, US-1.4 deactivation, and the enrollment half of US-2.5 MFA) into a real, usable web UI, closing the gap between "the API exists" and "a Customer can actually use it." This aligns with the product vision's "user self-service" goal and the Customer persona's stated goals for profile management, MFA-linked account security, and account deactivation/reactivation.

**In scope:** profile edit (write-only, pending a backend gap — see below), email change + confirmation, email verification landing/resend, MFA enrollment (enroll → activate → one-time recovery codes) and disable, account deactivation, plus two changes to already-shipped US-5.1 code (the MFA-deadline banner link, and extending the shared API client to expose response headers for ETag/If-Match). **Out of scope:** the admin console (US-5.4), support tickets UI (US-5.3), and anything US-5.1 already delivered (login, registration, sessions, password reset, MFA challenge). The story is explicit and unambiguous about this boundary; no gap found here.

**No backend changes:** Assumption #7 states `API_DESIGN`/`DB_DESIGN` should record `NOT_APPLICABLE`. This is accurate for the endpoints the story actually implements against, but see OD-5 below — the story's own Dependencies & Blockers section already acknowledges one backend gap it cannot route around.

## What's Clear

- The `PATCH /profile` field whitelist (`display_name`, `locale`, `timezone`, `avatar_url`), the closed `locale` enum, and IANA-validated `timezone` were verified directly against `app/modules/profile/schemas.py` and match the story's claims exactly.
- `ProfileRead`'s field list matches the story's stated shape exactly (`app/modules/profile/schemas.py:45-56`).
- The 202-on-email-change / no-ETag-on-202 behavior (Client State Notes) matches `app/modules/profile/router.py:41-44` exactly.
- `POST /profile/confirm-email-change` genuinely works with or without an `Authorization` header (`router.py:53-61`, optional `authorization` param) — the story's "works signed-in and signed-out" claim is accurate.
- Anti-enumeration on email-verification resend is consistent with the project-wide rule (BR-005, `docs/product/business-rules.md`).
- Recovery-codes-shown-once and no-re-fetch-endpoint (Assumption #4) is accurate — `MfaActivateResponse` is the only place `recovery_codes` is ever returned.
- The security/never-persisted handling for MFA secret/URI/recovery codes and `current_password` (NFR section) is consistent with this project's established patterns for sensitive-field handling elsewhere (US-5.1's access-token-in-memory precedent).
- US-5.1's precedent for "no design system, hand-built components" (`docs/evidence/US-5.1-delivery-summary.md`, its OD-9 resolution, and the resulting `docs/ARCHITECTURE.md` §8 addition) already answers what would otherwise be an open design-system question for this Story too — carried forward as established fact, not re-opened here.

## What's Ambiguous or Contradicted (logged as Open Decisions)

Cross-checking the story's API Contract table against the actual `app/modules/profile`, `app/modules/users`, and `app/modules/account` source surfaced three material gaps the story itself doesn't state, in addition to the four the story's own author already flagged as Open Questions. All seven are recorded in `docs/decisions/US-5.2-open-decisions.md`:

1. **OD-1 (new, load-bearing):** `PATCH /profile` unconditionally requires `If-Match` — confirmed both by the shipped code (`app/modules/profile/service.py:151-152`) and by the *source* story `US-1.3-update-profile.md`'s own Assumption #4 ("required on every PATCH") and UP-AC2. This directly contradicts US-5.2's Assumption #2/#3 framing of `If-Match` as optional, and means the write-only-interim design as literally described cannot even complete its own first write (no ETag exists yet, and omitting the header is rejected, not merely conflict-checked). A wildcard `If-Match: *` escape hatch exists in the code but is never mentioned by the story.
2. **OD-2 (new):** `POST /auth/mfa/enroll` requires `current_password` and `DELETE /auth/mfa` requires both `current_password` and a TOTP `code` (jointly validated) — confirmed in `app/modules/users/schemas.py`/`service.py` and `US-2.5-spec.md` MF-AC1. The story's contract table lists both as bodyless, and neither PS-AC5 nor PS-AC6 describes collecting these fields. Disabling MFA also revokes every other session (`US-2.5-spec.md` OD-6/OD-8), which isn't named in PS-AC6's confirmation-consequence NFR.
3. **OD-3 (new):** enrollment-scoped access tokens (privileged roles mid-grace-period) get `403 mfa-enrollment-required` on every route except `/mfa/enroll`/`/mfa/activate` (`app/modules/users/service.py`, `dependencies.py`) — no navigation behavior beyond a dismissible banner link is specified for that state.
4. **OD-4 (the story's own Open Question #4, formalized):** `current_password`'s optionality on `/account/deactivate` is real in the schema but only meaningful for password-less accounts — verified in `app/modules/account/service.py`, which otherwise deterministically fails password verification when the field is omitted.
5. **OD-5 (the story's own Open Question #1, formalized):** no backend Story has actually been raised yet for `GET /profile`/`GET /users/me` — confirmed absent from `docs/stories/`, though the gap is independently documented in `docs/stories/README.md` and `docs/catalog/stories.yaml`.
6. **OD-6 (the story's own Open Question #2, formalized):** `SupportedLocale`'s two-item list is confirmed provisional by its own code comment.
7. **OD-7 (the story's own Open Question #3, formalized):** timezone validation is confirmed to be the full, uncurated `zoneinfo.available_timezones()` set.

None of these were silently resolved; each is logged in `docs/decisions/US-5.2-open-decisions.md` with its source citation and impact if left unresolved, per this skill's contract.

## Dependencies

- **US-5.1** (auth store, API client, route guards, problem+json rendering): `ARCHIVED`/shipped — a real, satisfied dependency, not a risk.
- **US-5.4** (Admin Console) is documented as *depending on* this Story's API-client header-exposure work (Assumption #2) — this Story is upstream of US-5.4, not the reverse; no circular dependency.
- The missing `GET /profile`/`GET /users/me` backend endpoint (OD-5) is a one-directional gap this Story cannot close itself (Assumption #7: no backend changes) — it can only be designed around (write-only interim), and OD-1 shows that workaround is not yet fully specified either.

## Readiness Verdict

**PASS.** The story's scope, actor, and business value are understood and restated above; every ambiguity found is either resolved by a cited source or logged as an Open Decision — none silently dropped. Nothing found here makes the story unintelligible or blocks understanding its scope; the seven logged decisions in `docs/decisions/US-5.2-open-decisions.md` are business/technical judgment calls a spec-writer must not make silently, not defects in the story's readability.

Per `docs/workflow/artifact-lifecycle.md`, Open Decisions may remain `OPEN` at this stage — they are resolved at `HUMAN_SPEC_APPROVAL`, not here. Three of the seven (`OD-1`, `OD-2`, `OD-3`) are flagged as non-blocking findings in this stage's Result Envelope rather than left to be found only by opening the decisions file: they are factual inaccuracies in the story's own API Contract table (not just unresolved judgment calls), and each would produce a screen that fails on its primary success path 100% of the time if `SPECIFICATION` builds strictly to the story's literal text.
