# US-5.1 — Open Decisions

**Story:** Authentication & Session Management (Frontend)
**Stage:** CLARIFICATION
**Status of this log:** All entries below are `OPEN`. This is the first clarification pass for US-5.1 — no prior `US-5.1-open-decisions.md` existed to reconcile against.

Each entry: the question, why it cannot be inferred from `docs/product/*`, the story, or backend source, and the concrete impact of leaving it unresolved.

---

## OD-1 — Cross-origin/CORS configuration for the new frontend origin

**Question:** How does the browser reach the backend during development (and later, in a deployed environment) given the backend's current CORS policy, and does this Story's Assumption #7 ("no backend changes") actually hold?

**Why it can't be inferred:** `app/main.py` hardcodes
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Location", "ETag"],
)
```
with a comment stating this exists only for the gitignored `dev-gui/` static test page. It does not include a Vite dev-server origin (default `http://localhost:5173`), and it does not set `allow_credentials=True`. The Story's own Assumption #3 depends on the browser automatically attaching the `httpOnly` refresh cookie the backend sets — that only works cross-origin if the server responds with `Access-Control-Allow-Credentials: true` to a matching, explicit (non-wildcard) origin. Neither `docs/product/*` nor the story states whether the frontend is expected to run same-origin (via a Vite dev proxy, requiring no backend change) or cross-origin (requiring a CORS/config change, which would contradict Assumption #7).

**Impact if unresolved:** A spec-writer/implementer would have to silently pick between (a) a Vite `server.proxy` pointing `/api` at the backend (keeps Assumption #7 true, but constrains how the frontend's HTTP client is configured — relative base URL, cookie automatically same-origin), or (b) modifying `app/main.py`'s CORS middleware (breaks Assumption #7, needs its own sign-off since it's a backend change). Guessing wrong means the entire cookie-based refresh flow (FE-AC2–FE-AC4) silently fails in dev with no clear error.

---

## OD-2 — Single-flight handling of concurrent 401s against `/auth/refresh`

**Question:** When multiple authenticated requests fail with `401` concurrently, must the client serialize them behind one in-flight `/auth/refresh` call, or may each failing request independently trigger its own refresh attempt?

**Why it can't be inferred:** BR-008 (`docs/product/business-rules.md`) states refresh tokens are single-use and that replaying an already-consumed token in a family is treated as **probable theft**, revoking the entire family and sending a security-notification email. FE-AC4 describes only the single-request case ("the client calls `POST /auth/refresh` exactly once, retries the original request on success") and does not address what happens when several requests fail with 401 in the same window (a realistic case once a token has actually expired, since several TanStack Query calls may be in flight together).

**Impact if unresolved:** Without an explicit single-flight/mutex requirement, an implementer could wire the refresh call per-failing-request. Because the server rotates the refresh cookie on every `/auth/refresh` call, a second concurrent call could present the browser's still-cached (now-superseded) cookie value and be treated as token reuse — silently logging the user out of every device and firing an unwanted security email, in normal use, not just under attack.

---

## OD-3 — Proactive vs. purely reactive token refresh

**Question:** Does this Story require a proactive, timer-based refresh (using `LoginResponse.expires_in`) before the access token actually expires, in addition to the reactive 401-triggered refresh?

**Why it can't be inferred:** FE-AC4's `Given` clause names two conditions ("access token has expired **or** is rejected with 401"), but its `When`/`Then` only specify behavior for the reactive case (a request that fails with 401). No acceptance criterion exercises a proactive/pre-emptive refresh path, and `docs/product/*` does not describe session-continuity mechanics at this level of detail.

**Impact if unresolved:** A purely reactive design (refresh only after a 401) is simpler and satisfies the letter of the ACs, but produces a visible failed-request-then-retry stutter on every natural expiry, and interacts with OD-2 (multiple simultaneous requests all failing near the expiry boundary). Left undecided, an implementer must guess whether to also build and test a timer-based pre-emptive refresh.

---

## OD-4 — Non-uniform error response shapes on this Story's own endpoints

**Question:** How should the client's error-normalization layer treat the two response shapes on `/auth/register` that do not follow the RFC 7807 `application/problem+json` envelope FE-AC9 assumes?

**Why it can't be inferred:** Confirmed directly in `app/main.py`:
- `RegistrationValidationError` (register-time field validation failure) → `400`, body `{"errors": [{"field", "message", "code"}]}` only, media type `application/json` (FastAPI's `JSONResponse` default) — no `type`/`title`/`status`/`detail`/`instance`.
- `DuplicateEmailError` (register-time email-already-registered) → `409`, body `{"detail": "Email is already registered."}` only, again plain `application/json`, no `type`/`errors`.

Every other endpoint in this Story's scope (`login`, `mfa/verify`, `refresh`, `logout`, `logout-all`, `sessions`, `password-reset/*`) raises a `ProblemError` subclass or `RequestValidationError`, both of which *do* produce the full RFC 7807 envelope FE-AC9 describes. FE-AC9 is written as if this were uniform across "any request in this Story"; it is not, for these two register-only cases.

**Impact if unresolved:** An error-handling layer built strictly to FE-AC9's stated shape will either crash/misrender on `/auth/register`'s two non-conforming responses (no `detail` field to read) or silently mask them as a generic "something went wrong." A spec-writer needs to decide whether the client special-cases these two response shapes for the Register screen specifically, or whether this is flagged back as a backend defect to fix before this Story implements against it (which would, again, touch Assumption #7's "no backend changes").

---

## OD-5 — Client-side validation rule set per screen (password policy and email format)

**Question:** What exact client-side rules should Register's, Login's, and Reset-Password's forms enforce before submission (FE-AC8), given the backend enforces two *different, undocumented-in-the-Story* password policies depending on screen, and at least one rule per policy is inherently server-only?

**Why it can't be inferred:** Confirmed in `app/modules/users/service.py`:
- **Register** (`_validate_password`, backing `RegistrationValidationError`): password required, minimum **8** characters, and must contain at least one uppercase letter, one lowercase letter, one digit, and one punctuation character.
- **Password-reset confirm** (`confirm_password_reset`): minimum **12** characters, must not be a breached password (`is_breached_password`, checked against a corpus the client has no access to), and must differ from the user's current password (checked against the stored hash, which the client never has).

These two policies share no length constant and differ in composition rules entirely; neither is stated anywhere in `docs/stories/US-5.1-*.md`, `docs/product/business-rules.md` (BR-003 covers hashing algorithm only, not policy), or `docs/product/business-glossary.md`. Register's email-format check is likewise a bespoke server-side validator (`_validate_email`) with no published regex/contract for the client to mirror. FE-AC8 requires the form to "block submission... without calling the API" for malformed input, which is only achievable for the rules a client can evaluate locally.

**Impact if unresolved:** Guessing a single shared password-strength rule (e.g. reusing Register's composition rules on the Reset-Password screen, or vice versa) will produce client/server disagreement: the client either blocks a password the server would accept, or — worse — passes a password the server rejects on the breach/reuse rule, which FE-AC8 cannot pre-empt at all and must instead fall through to FE-AC9's server-error handling (itself split per OD-4's non-uniform shapes for the Register case).

---

## OD-6 — UI affordance for the caller's own current session

**Question:** Should the Active Sessions screen (FE-AC6) disable/hide the "revoke" control on the row identified as the current session, or let the user attempt it and surface the resulting error?

**Why it can't be inferred:** FE-AC6 as written only exercises "revoke a non-current session." The backend's `CurrentSessionError` (409, `current-session` slug) exists specifically to reject a `DELETE /auth/sessions/{family_id}` against the caller's own current session ("ending your only active session through this endpoint has no described use case; logout already owns that" — `app/modules/users/exceptions.py`). Neither the story nor `docs/product/personas.md`'s Customer goals states whether this should be prevented at the UI level or left to the API's rejection.

**Impact if unresolved:** Left undecided, an implementer may ship a revoke button on every row including the current one, producing a confusing 409 the user cannot self-diagnose, or may guess at disabling it and inadvertently omit a test case reconciliation-reviewer would later expect against FE-AC6.

---

## OD-7 — `mfa_enrollment_deadline` banner copy and dismissal behavior

**Question:** What exact copy, tone, and re-appearance rule (e.g. does dismissal persist for the session only, or until the deadline changes) should the informational banner use?

**Why it can't be inferred:** This is the Story's own **Open Question #1**, explicitly left unresolved by its author (Assumptions & Defaults #6 proposes a default: "a dismissible informational banner naming the deadline... dismissal state may live in `sessionStorage`"). Neither `docs/product/personas.md` nor `docs/product/business-rules.md` (BR-013, the MFA grace-period rule) specifies UI copy. Carried forward here rather than silently dropped.

**Impact if unresolved:** A spec-writer would have to invent banner copy and exact dismissal semantics (per-tab vs. per-account, re-shown on next deadline change vs. never again) with no product-level source to cite.

---

## OD-8 — Placeholder authenticated home screen content

**Question:** What should the post-login placeholder route (Assumption #5, not `/tickets` since Story 5.2 doesn't exist yet) actually contain?

**Why it can't be inferred:** This is the Story's own **Open Question #2**. `docs/product/product-vision.md` and `docs/product/personas.md` describe the Customer's end goals (manage sessions, raise tickets, etc.) but nothing about an interim landing screen's content once authenticated. Carried forward here rather than silently dropped.

**Impact if unresolved:** An implementer must invent screen content (e.g. "Welcome, logged in" vs. a stub nav to the sessions/profile screens that do exist in this Story's scope) with no cited source, risking rework once Story 5.2 lands and the redirect target/placeholder content changes.

---

## OD-9 — Design system / component library choice

**Question:** Is a headless-UI kit (e.g. Radix/Headless UI + Tailwind) or hand-built components the intended foundation for this Story's forms and screens?

**Why it can't be inferred:** This is the Story's own **Open Question #3**, explicitly deferred by its author to "this Story's own pipeline pass" design work. `docs/product/*` states no frontend technology preference beyond the Assumptions table's React/Vite/TS/TanStack Query/React Hook Form stack (Assumption #1). Carried forward here rather than silently dropped, since it materially affects the API-design-equivalent (component/screen design) step that follows clarification for this Story.

**Impact if unresolved:** Left to be "decided ad hoc during implementation" (the story's own words), this risks inconsistent accessibility behavior across screens — a direct conflict with this Story's own stated NFR ("full keyboard navigation and visible focus states on every form and interactive control") if different screens hand-roll focus/keyboard handling independently instead of inheriting it from one chosen primitive layer.

---

## Summary

| # | Topic | Source of ambiguity |
|---|---|---|
| OD-1 | CORS / cross-origin cookie config | `app/main.py` vs. Story Assumption #3 & #7 |
| OD-2 | Concurrent-401 refresh single-flight | BR-008 vs. FE-AC4 |
| OD-3 | Proactive vs. reactive refresh | FE-AC4 internal wording |
| OD-4 | Non-uniform register error shapes | `app/main.py` vs. FE-AC9 |
| OD-5 | Per-screen client validation rules | `app/modules/users/service.py` vs. FE-AC8 |
| OD-6 | Current-session revoke affordance | `CurrentSessionError` vs. FE-AC6 |
| OD-7 | MFA-deadline banner copy/dismissal | Story's own Open Question #1 |
| OD-8 | Placeholder home content | Story's own Open Question #2 |
| OD-9 | Design system choice | Story's own Open Question #3 |

None of these are resolved by this pass — resolution happens at `HUMAN_SPEC_APPROVAL`, not here.
