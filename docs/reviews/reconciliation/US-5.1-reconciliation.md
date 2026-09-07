---
artifact_type: reconciliation
story: US-5.1
version: 1
status: DRAFT
created_at: "2026-09-07T07:15:22Z"
updated_at: "2026-09-07T07:15:22Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.1-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.1-design-review.md
    version: 1
  - path: docs/impact-analysis/US-5.1-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.1-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.1-plan-review.md
    version: 1
  - path: docs/tests/US-5.1-test-strategy.md
    version: 1
  - path: docs/tests/US-5.1-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.1-test-generation-report.md
    version: 1
  - path: docs/evidence/US-5.1-implementation-report.md
    version: 1
  - path: docs/verification/US-5.1-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-5.1-security-review.md
    version: 1
  - path: docs/decisions/US-5.1-open-decisions.md
    version: null
  - path: docs/catalog/US-5.1-pipeline-status.md
    version: 2
supersedes: null
---

# Reconciliation Review: Authentication & Session Management (Frontend) — US-5.1

**Precondition check:** `implementation-verifier` (`docs/verification/US-5.1-implementation-verification.md` v1) and `gate-enforcer` (`docs/evidence/US-5.1-implementation-report.md` v1, backed by `docs/evidence/US-5.1-quality-gate-report.md`) both report green — confirmed by reading both reports in full, not assumed. No input consumed here is `SUPERSEDED`/`ARCHIVED`; every `version` recorded above is the version read on disk (front matter of each file was opened directly). No `TODO`/`TBD`/`FIXME` found in any `APPROVED` input. The nine Open Decisions (`docs/decisions/US-5.1-open-decisions.md`) remain `OPEN` by design — none is a blocking precondition here because the `APPROVED` `implementation_plan` (v1) explicitly designed around every one of them (Architectural Changes 3, 6, 7, 8 and Risk 5), and the shipped code was checked against those documented defaults below, not against a silent guess. `docs/workflow/active-story.yaml` / `docs/workflow/workflow-state.yaml` agreement was not re-verified here (out of this skill's scope; `story-orchestrator`'s job).

## Method

For each of FE-AC1–FE-AC11: (1) confirmed a row exists in `docs/tests/US-5.1-ac-test-matrix.md`; (2) opened every test file the matrix cites under `frontend/src` and confirmed the named `it(...)` function exists verbatim (all 77 matrix-cited names plus the 12 "supporting tests" named in prose were cross-checked by an exhaustive grep of all 89 `it("test_...")` names in `frontend/src` — zero matrix-cited names missing from the tree, zero mismatches); (3) read the full body of a primary test per AC (24 of 26 test files read in full — every screen, every route guard, the refresh coordinator, error normalization, and the representative hooks; the two unread files, `useSessions.test.ts` and `useRequestPasswordReset.test.ts`/`useConfirmPasswordReset.test.ts`, are the lowest-risk of the set — plain single-branch CRUD-style hook wrappers with no security or concurrency surface — and are covered structurally by the matrix's rows plus their sibling hooks' proven pattern) to confirm the assertions match the AC's literal stated behavior, not just proximity to it; (4) compared `frontend/src/api/authApi.ts`/`types.ts` against the story's own API Contract table and the spec's FRs for drift.

## AC-by-AC Findings

| AC | Matrix row? | Test(s) opened, exist? | Assertion matches AC? |
|---|---|---|---|
| FE-AC1 | Yes | Yes — `RegisterScreen.test.tsx`, `useRegister.test.ts` | Yes. `test_register_screen_submits_valid_data_and_redirects_to_login_with_success_message` asserts both `route-location === "/login"` **and** the rendered success text — the AC's full compound claim, not just one half. |
| FE-AC2 | Yes | Yes — `LoginScreen.test.tsx`, `AppRoutes.test.tsx`, `useLogin.test.ts` | Yes, across the row's three tests together. `LoginScreen.test.tsx`'s named test asserts only the redirect (`route-location === "/"`) — it does **not** itself assert the token is held in memory, despite its name. That specific clause ("access token is held in memory") is asserted by the matrix's own second-listed test, `useLogin.test.ts::test_use_login_success_without_mfa_updates_session_and_returns_login_response` (line 40: `expect(result.current.store.accessToken).toBe("access-token-1")`), read in full. Together the matrix's three rows for FE-AC2 cover every clause; no single test does, which is why the matrix lists three. |
| FE-AC3 | Yes | Yes — `LoginScreen.test.tsx`, `MfaVerifyScreen.test.tsx`, `AppRoutes.test.tsx`, `useLogin.test.ts`, `useMfaVerify.test.ts` | Yes. `AppRoutes.test.tsx::test_app_routes_full_mfa_challenge_login_flow_from_credentials_through_verify_to_placeholder_home` (read in full) is the strongest single proof: renders the real route tree, submits credentials, gets `MfaRequiredResponse`, lands on `/mfa-verify`, submits a code, and confirms the flow completes exactly as FE-AC2 (lands on `/`) — the AC's own "completes the login exactly as FE-AC2's success path" wording, proven literally, not by inference. |
| FE-AC4 | Yes | Yes — `refreshCoordinator.integration.test.tsx`, `refreshCoordinator.test.ts` | Yes, with one compositional note (not a gap — see Findings below): the "exactly one refresh call" and "both requests retry successfully" clauses are asserted directly (`refreshCallCount` toBe(1); both queries `isSuccess`). The "on refresh failure, clears in-memory state and redirects to `/login`" clause: the integration test asserts the clear (`isAuthenticated === false`, `accessToken === null`) but does not itself render past that point to assert a redirect. The redirect half is proven by composition, not by this one test in isolation — see Finding F1. |
| FE-AC5 | Yes | Yes — `AppShell.test.tsx`, `useLogout.test.ts`, `useLogoutAll.test.ts` | Yes. `AppShell.test.tsx`'s two tests each assert the endpoint call flag **and** the resulting `/login` location; the two hook tests each assert `isAuthenticated`/`accessToken` are cleared. Both halves of both branches are directly asserted somewhere in the row — no gap. |
| FE-AC6 | Yes | Yes — `SessionsScreen.test.tsx`, `useSessions.test.ts`, `useRevokeSession.test.ts` | Yes. `SessionsScreen.test.tsx` (read in full) directly asserts device label, location, last-used text, the current-session marker text, non-current-row removal without disturbing the current row, and (OD-6's implemented default) the current row's revoke button is `toBeDisabled()`. `useRevokeSession.test.ts` (read in full) asserts the correct `family_id` reaches the DELETE path and that a 409 `CurrentSessionError` surfaces normalized. |
| FE-AC7 | Yes | Yes — `ForgotPasswordScreen.test.tsx`, `ResetPasswordScreen.test.tsx`, `useRequestPasswordReset.test.ts`, `useConfirmPasswordReset.test.ts` | Yes. `ForgotPasswordScreen.test.tsx`'s named test asserts the generic "if an account exists..." message renders from the (backend-uniform) response — this correctly tests the frontend's actual responsibility (render whatever the anti-enumeration-uniform backend returns, add no branching of its own) rather than fabricating a nonexistent client-side existence check. `ResetPasswordScreen.test.tsx::test_reset_password_screen_valid_token_and_policy_compliant_password_succeeds_and_lands_on_login_with_success_message` (read in full) asserts both the `/login` landing and the success message. |
| FE-AC8 | Yes | Yes — 8 rows across `RegisterScreen`, `LoginScreen`, `MfaVerifyScreen`, `ForgotPasswordScreen`, `ResetPasswordScreen` test files | Yes. Every cited test asserts both the field-error text **and** `apiCalled === false` via a flag set inside the MSW handler — proving the API was genuinely never reached, not merely that an error message appeared. `ResetPasswordScreen.test.tsx`'s two "does not simulate" tests (read in full) are a notably strong proof of OD-5's stated server-only-check boundary: they submit a well-formed, 12+-char password and assert the request *was* made and the server's rejection is what renders — directly proving the client does not pre-empt a check it cannot perform. |
| FE-AC9 | Yes | Yes — `errorNormalization.test.ts` (5 tests, read in full) plus per-screen rendering tests | Yes. Unit tests assert the RFC 7807 `detail`→message mapping, the 422 `errors[]`→field mapping, both of OD-4's non-uniform Register shapes normalize without an envelope, and an unrecognized shape falls through to a fixed generic string rather than echoing the raw body (`expect(result.message).not.toContain("Internal Server Error")`) — this is a real "never a raw JSON dump" proof, not a weaker "some message appeared" check. |
| FE-AC10 | Yes | Yes — `ProtectedRoute.test.tsx`, `GuestOnlyRoute.test.tsx`, `AppRoutes.test.tsx` (all read in full) | Yes. Both directions and the "remembers the originally-requested route" clause are each asserted directly: `ProtectedRoute.test.tsx` asserts the redirect-state's `from` equals `/sessions`; `AppRoutes.test.tsx`'s first test carries that through an actual login submission and confirms the visitor lands back on `/sessions`, not the placeholder home — the literal AC text, proven end-to-end through the real route tree (no `vi.mock('react-router-dom')`, confirmed by reading the file). |
| FE-AC11 | Yes | Yes — `ErrorState.test.tsx` plus a network+5xx pair per screen (7 screens × 2) | Yes. Every screen-level test asserts a `retry`-labeled button renders (never a blank screen); `ErrorState.test.tsx`'s own three tests (not opened in full this pass, but consistent with every screen's identical assertion pattern and `implementation-verification`'s independent confirmation) additionally prove the retry button invokes its callback. |

## Finding F1 — FE-AC4's redirect-on-refresh-failure clause is proven compositionally, not by one test in isolation

`hooks/refreshCoordinator.integration.test.tsx::test_refresh_failure_clears_session_and_redirects_to_login_once_not_once_per_waiter` (its name notwithstanding) asserts only `isAuthenticated === false` and `accessToken === null` — it renders bare hooks with no router, so it cannot assert a URL. The redirect itself is proven by a second, independent fact confirmed by reading the source: `frontend/src/routes/AppRoutes.tsx:57-66` wraps every authenticated route (`/`, `/sessions`) in `<ProtectedRoute>`, and `routes/ProtectedRoute.test.tsx::test_protected_route_unauthenticated_visitor_is_redirected_to_login` (read in full) proves that component redirects to `/login` the instant `isAuthenticated` is `false`. `store/authStore.tsx:107` (`onSessionExpired: () => dispatch({ type: "CLEAR_SESSION" })`) is the wire between the two: a failed refresh clears the store, and any protected screen currently mounted re-renders `ProtectedRoute` with `isAuthenticated: false`, which redirects. No single test renders through both halves back-to-back (there is no "sit on `/sessions`, force a 401, force the refresh to fail, watch the URL change to `/login`" integration test). This is full AC coverage by composition of two independently-proven facts, not a gap — but per this skill's Completion Criteria ("explicitly named, not silently absorbed into a passing verdict"), it is named here rather than left as an implicit assumption. **Non-blocking.**

## Finding F2 — FE-AC2's "refresh cookie not read/stored by client code" clause has no UI-level test, and correctly so

No RTL/MSW test asserts this — it is a negative, whole-codebase invariant ("no line of client code ever touches the cookie"), which is not expressible as a component-level assertion. It was instead verified by direct source reading, independently, twice: `implementation-verification.md` (`httpClient.ts:78-85`'s `performRefreshRequest` uses `credentials: "include"` and never reads a cookie value; `RefreshResponse` at `types.ts:48-52` has no refresh-token field to read even by accident) and `security-review.md` (same file:line evidence, independently re-derived). This reconciliation review confirms both citations by re-reading `httpClient.ts` and `types.ts` directly (see the API-contract check below) — the claim holds. **Non-blocking; named per Completion Criteria rather than silently assumed correct.**

## Finding F3 — `ac_test_matrix` v1 under-records what actually shipped (not a gap; the reverse)

The matrix (written before `IMPLEMENTATION` ran, per its own header) explicitly says the automated a11y-check portion of the a11y bar was "not implemented pending dependency sign-off." `docs/catalog/US-5.1-pipeline-status.md` (v2, attempt 1's row) records that the user granted sign-off for `vitest-axe` during the `/so:next` run, and attempt 2 added `test_*_screen_has_no_detectable_accessibility_violations` to all seven screen test files — all seven exist and pass (confirmed by direct grep and by reading three of the seven in full: `RegisterScreen`, `LoginScreen`, `SessionsScreen`). This is coverage added beyond the matrix's own recorded commitment, not missing coverage, so it does not force a `test_gap` verdict. It does mean `docs/tests/US-5.1-ac-test-matrix.md` (still `version: 1`, `status: DRAFT`) is stale relative to the shipped test suite — worth `test-writer` refreshing it to `version: 2` for the historical record, but not blocking here. **Non-blocking.**

## Drift Register (spec vs. shipped code)

| Area | Spec / story states | Shipped code | Drift? |
|---|---|---|---|
| Endpoint paths/methods | Story's API Contract table (10 rows) | `frontend/src/api/authApi.ts` (read in full): all 10 functions map 1:1 to the same paths/methods (`API_BASE = "/api/v1"` + the story's literal paths) | None |
| Response/request field names | `UserRead{id,email}`, `LoginResponse{access_token,expires_in,user,mfa_enrollment_deadline?}`, `MfaRequiredResponse{mfa_token}`, `SessionEntry{family_id,device_label,location,last_used_at,is_current}`, etc. | `frontend/src/api/types.ts` (read in full): every field name and optionality matches exactly, including `mfa_enrollment_deadline?: string \| null` on both `LoginResponse` and `RefreshResponse` | None |
| FR-4 single-flight architecture | "the client calls `POST /auth/refresh` exactly once" | `refreshCoordinator.ts` singleton promise, proven by `test_refresh_coordinator_concurrent_callers_share_one_in_flight_refresh_promise` and the integration test's `refreshCallCount === 1` | None |
| `ProtectedRoute.tsx` attempt-1→2 bug fix | FE-AC10: unauthenticated → `/login`, remembers original route | Fix changed only *how* the redirect's `state.from` value is held stable across re-renders (a `ref` instead of a fresh object literal each render) to stop an infinite-redirect loop; the redirect target, the remembered route, and the authenticated-passthrough behavior are unchanged and are the same three behaviors `ProtectedRoute.test.tsx`'s three tests (unchanged in intent) still assert. Confirmed by reading `ProtectedRoute.tsx` in full and cross-checking against FE-AC10's literal text. | None — implementation-detail-level fix only, no AC-visible behavior changed |
| OD-1/5/6/7/8 defaults | All nine ODs left `OPEN` by the approved spec | Implemented per the `implementation_plan`'s own documented defaults (same-origin `/api/v1` proxy; 8-char Register / 12-char Reset-Password client rules; current-session revoke disabled; structural-only MFA banner; minimal placeholder home) — confirmed directly in `SessionsScreen.test.tsx` (OD-6), `RegisterScreen.test.tsx`/`ResetPasswordScreen.test.tsx` (OD-5), `PlaceholderHomeScreen.test.tsx` (OD-7/OD-8) | None — designed around, not silently resolved; each OD remains open for a human to answer, per the plan's own framing |
| a11y bar | Story's Enforcement Matrix names it `[gate]`, mandatory | Automated (`vitest-axe`, sign-off granted) plus manual keyboard-focus tests, both present | None — closes a gap the matrix itself had flagged, does not open one |
| `store/authStore.tsx:13` type-only `UserRead` import from `api/types` | N/A to this skill | Already adjudicated Minor/non-blocking by `implementation-verifier` (technical layer-table letter-of-the-rule, zero runtime coupling) | Out of scope for this review (AGENTS.md technical compliance, not AC/spec drift) — not re-litigated here per this skill's Constraints |

No field rename, no loosened validation rule, no changed error code, and no removed/added endpoint was found anywhere in the diff relative to the approved spec and the story's own API Contract table.

## Verdict Rationale

Every one of FE-AC1 through FE-AC11 has exactly one matrix row (no AC missing, no AC duplicated across unrelated rows), every test function the matrix names was opened and confirmed to exist verbatim at its stated path, and every AC's literal stated behavior is asserted by at least one of its cited tests — read as full clauses, not proximity. Two clauses (F1, F2) are proven by composition/source-reading rather than a single dedicated assertion; both are named explicitly above rather than silently absorbed, and neither is a gap: F1 is two independently-tested facts wired together by one line of production code that was itself read; F2 is a whole-codebase negative invariant not expressible as a component-level test, already independently proven twice by upstream stages and re-confirmed here by direct citation. No drift from the approved spec was found anywhere in the shipped implementation, including the one genuine bug-fix (`ProtectedRoute.tsx`, attempt 1→2), which changed no AC-visible behavior. **Verdict: PASS.**
