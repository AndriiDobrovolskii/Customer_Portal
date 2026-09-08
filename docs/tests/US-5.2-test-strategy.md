---
artifact_type: test_strategy
story: US-5.2
version: 1
status: ARCHIVED
created_at: "2026-09-08T10:00:00Z"
updated_at: "2026-09-08T18:25:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.2-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.2-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.2-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.2-plan-review.md
    version: 1
supersedes: null
---

# Test Strategy: Account & Profile Self-Service — Frontend (US-5.2)

## Scope: RED-state test source files, following US-5.1's own precedent

Same posture as `docs/tests/US-5.1-test-strategy.md`: this pass writes real
test source files against symbols `T1`–`T12` have not yet created, not only a
prose plan — the skill's Result Envelope `PASS` criterion requires "the
matrix rows name test functions that exist," and `IMPLEMENTATION`'s own
`changes_required_tests` loop-back target only makes sense if tests already
exist for it to route back to. Every file below is expected to fail at
**module-resolution time** (new `api/`, `hooks/`, `screens/`, `components/`
files T1–T12 have not yet created) until `IMPLEMENTATION` lands them — the
intended TDD-red state, not a defect in this pass. One exception: the QR
library (`qrcode.react`, Plan Change 9) is not yet in `package.json` — `T5`
adds it — so `QrCode.test.tsx` additionally fails at that import until then;
called out again in the generation report so it does not read as an
oversight.

Unlike US-5.1, `frontend/` and its scaffold (`test-utils.tsx`, `mswServer.ts`,
`setup.ts`, the existing api/hooks/screens/routes tree) already exist and are
reused unchanged except where this Story's own plan requires edits (see
below).

## Unit vs. Integration split (`AGENTS.md` §5's Frontend subsection)

- **Unit** (`frontend/src/components/apiErrorHelpers.test.ts`,
  `frontend/src/api/httpClient.test.ts`, `frontend/src/hooks/*.test.ts`) — a
  pure function or a hook in isolation via Vitest, MSW as the network
  boundary. Covers `httpPatch`'s status/headers-exposing shape and `If-Match`
  threading (Change 1); `getErrorStatus` alongside the existing
  `getErrorKind`/`getErrorMessage`/`getFieldErrors` trio (none of which had a
  dedicated test file before this Story — closed here, not left as a gap);
  each new hook's success/error mapping, with `useProfileUpdate`'s four
  branches (known-ETag echo, no-ETag `If-Match: *`, 202 clears the cached
  ETag, 412 sets the conflict flag) getting the deepest coverage per the
  plan's own Testing Strategy section.
- **Integration** (`frontend/src/screens/*.test.tsx`,
  `frontend/src/components/{RecoveryCodesDisplay,QrCode,MfaEnrollmentBanner}.test.tsx`,
  `frontend/src/routes/AppRoutes.test.tsx`) — React Testing Library renders
  the real component tree, MSW intercepts at the network boundary. No
  `vi.mock()` of the unit under test anywhere in this pass (confirmed by a
  repo-wide grep after writing all files — see the generation report).

## Test infrastructure changes made by this pass

- **`frontend/src/test/test-utils.tsx`** — extended (not rewritten) to seed
  Plan Change 6's `mfaEnabled` on `AuthStateSeed`: `RenderWithProvidersOptions`
  gains `mfaEnabled?: boolean`, and `buildAuthSeed` sets
  `mfaEnabled: options.mfaEnabled ?? false`. Without this, `T9`'s own
  verification command ("rendered with `authStore.mfaEnabled = false`...
  seeded via `test-utils`'s `AuthProvider` `initialState`") is unwritable —
  `AuthStateSeed.mfaEnabled` becomes a **required** field per Plan Change 6,
  so every existing call to `buildAuthSeed` needed a value regardless. This
  is this pass's own necessary, additive fix to shared test infrastructure it
  owns (the same category `test-utils.tsx` itself was placed in by
  `docs/tests/US-5.1-test-strategy.md`), not a `frontend-builder` deliverable.
- **`frontend/src/test/mswHandlers.ts` / `mswServer.ts`** — **not** written by
  this pass. Per US-5.1's own precedent, these encode real backend response
  shapes and are `T1`'s deliverable (bundled per the task breakdown's own
  note). Every test file below defines its own `server.use(...)` override(s)
  for the new endpoints it needs — MSW does not require a pre-existing
  baseline handler at a path to intercept it, and `setup.ts`'s
  `onUnhandledRequest: "bypass"` means an un-overridden new endpoint is
  simply not intercepted, not a fatal collection-time error.

## Collaborator-shape assumptions this pass had to fix to write concrete assertions

No design doc (API/DB design are both `NOT_APPLICABLE`) fixes an internal
hook contract beyond the plan's prose. Where the plan describes behavior
without naming an exact function signature, this pass fixes one, consistent
with the plan's own stated behavior, and records it here so
`frontend-builder`/`reconciliation-reviewer` can check the shipped shape
against what this suite assumes:

- **`frontend/src/api/httpClient.ts`'s `httpDelete`** gains an **additive**
  `body?: unknown` field on its existing `options` bag —
  `httpDelete<T>(path: string, options: { auth?: boolean; body?: unknown } = {})`
  — rather than a new positional parameter. This is a finding beyond the
  plan's literal Architectural Change 1 (which names only `httpPatch` as new
  and says existing verb signatures are otherwise unchanged): FR-6 requires
  `DELETE /auth/mfa` to carry a body (`current_password`, `code`), which the
  current zero-body `httpDelete<T>(path, options)` cannot express, and
  `AGENTS.md` §3's Frontend table already allows `api/` files to call `fetch`
  directly — but routing `mfaApi.disableMfa` around `httpClient.ts` entirely
  would silently lose the 401→refresh→retry and error-normalization behavior
  every other call gets. Adding `body` to the *existing* options object (not
  a new parameter) keeps `revokeSession`'s only existing call site
  (`httpDelete<void>(path, { auth: true })`) byte-for-byte valid — genuinely
  additive, the same bar Risk 6 sets for `httpPatch`. Flagged as a
  non-blocking finding in the generation report; `frontend-builder` may
  choose a different mechanism, in which case `useMfaDisable.test.ts` is the
  file to update.
- **`frontend/src/hooks/useProfileUpdate.ts`** returns
  `{ mutateAsync: (payload: ProfileUpdatePayload) => Promise<ProfileRead>, isPending: boolean, conflict: boolean, resetConflict: () => void }`.
  `mutateAsync` unwraps `profileApi.patchProfile`'s `{ data, status, headers }`
  envelope (Change 1's shape) down to the `ProfileRead` body before resolving
  to the caller, so `ProfileScreen.tsx` never needs to read `status`
  directly — it reads the returned `ProfileRead.pending_email` to decide
  whether to show the "confirm the link sent" state (FR-3), matching
  `ProfileRead` already carrying that field. Internally: on `200`, the ETag
  read off `headers.get("etag")` is cached at `queryClient.setQueryData(["profile","etag"], etag)`;
  on `202`, `queryClient.removeQueries({ queryKey: ["profile","etag"] })`;
  the outgoing `If-Match` is `queryClient.getQueryData<string>(["profile","etag"]) ?? "*"`,
  read fresh on every call (OD-1's resolution, FR-2). A `412` sets local
  `conflict` state to `true` in `onError` (read via the new
  `getErrorStatus` helper, Change 4) without touching the cached ETag — the
  screen's "reload" action is what actually resolves a stale ETag, not this
  hook.
- **`ProfileUpdatePayload`** (this pass's own name for `useProfileUpdate`'s
  argument type) is `{ display_name?: string; locale?: string; timezone?:
  string; avatar_url?: string; email?: string; current_password?: string }`
  — a partial covering both the field-edit and the email-change payload
  shapes FR-2/FR-3 describe, matching `ProfileUpdateRequest`'s expected
  `types.ts` shape (Plan Files To Create, `api/` section).
- **`frontend/src/components/RecoveryCodesDisplay.tsx`** accepts
  `{ codes: string[]; onConfirmed: () => void }`: renders the codes in a
  keyboard-selectable list, a "Copy" control calling
  `navigator.clipboard.writeText`, a "Download" control building a local
  `Blob`/object-URL (no network), and an "I have saved these" checkbox that
  gates a "Continue" button calling `onConfirmed` — never enabled before the
  checkbox is checked.
- **`frontend/src/components/QrCode.tsx`** accepts `{ value: string }` (the
  `otpauth_uri`) and renders `qrcode.react`'s `<QRCodeSVG>` (or equivalent)
  with that value as its sole prop — no network call, no third-party host.
- **`frontend/src/screens/SecurityScreen.tsx`** reads `authStore.mfaEnabled`
  to choose its enroll vs. disable branch (Plan Change 6), never defaulting
  to enroll for an already-enrolled session.
- **`frontend/src/components/MfaEnrollmentBanner.tsx`**'s new link (spec
  Assumption #6, `T12`) is implemented as a plain `<a href="/settings/security">`,
  not `react-router-dom`'s `<Link>` — this keeps the three existing
  `MfaEnrollmentBanner.test.tsx` assertions (which render the component with
  a bare `render()`, no `MemoryRouter`) passing unmodified, per Plan Risk 7's
  "additive, not a rewrite" requirement; `<Link>` would throw outside a
  Router context and break that existing coverage. This pass's own new
  assertion for the link is written to hold under either element, checking
  only `getByRole("link", { name: ... })`'s accessible name and `href`.

## Open-Decision defaults this pass tested against (not resolved by this pass)

- **OD-3 (enrollment-scoped-token 403 navigation)** — not tested, matching
  Plan Change 11's "explicitly not built" scope; no forced-navigation
  assertion exists anywhere in this suite.
- **OD-6 (locale set)** — `ProfileScreen`'s tests exercise exactly the
  two-item `en-US`/`en-GB` set the plan's `SUPPORTED_LOCALES` constant fixes
  (Change 7), not a placeholder for a future expanded set.
- **OD-7 (timezone set)** — tested against `Intl.supportedValuesOf("timeZone")`
  membership generically (a known-valid IANA name from that runtime list
  succeeds; an unrecognized string like `"Not/ARealZone"` is blocked
  client-side), never against a specific curated subset.
- **OD-5 (`GET /profile` backend gap)** — `ProfileScreen`'s
  `test_profile_screen_starts_blank_write_only_interim_with_no_prefilled_values`
  pins FR-1's deferral as a positive assertion instead of leaving the gap
  implicit.

## PS-AC1 — explicitly untestable this pass, not silently dropped

PS-AC1 ("profile view") has no passing-shaped test: no `GET /profile`
endpoint exists to test against (FR-1, `[blocked]` in the story's own
Enforcement Matrix). The AC-test matrix carries an explicit row for PS-AC1
marked deferred, citing FR-1; this is recorded as a known, spec-sanctioned
gap in the generation report and surfaced as a `non_blocking_findings` entry
in this stage's Result Envelope — the verdict stays `PASS` because the
deferral is the approved spec's own decision, not a defect this pass
introduced or a gap it is hiding.

## a11y bar — closed this pass (a US-5.1 gap now resolved)

`vitest-axe` was already a devDependency and already used in six existing
screen test files (confirmed by direct read of `package.json` and
`SessionsScreen.test.tsx`/`RegisterScreen.test.tsx`) — no new sign-off
needed. `ProfileScreen`, `SecurityScreen`, and `DeactivateAccountScreen` each
get a real `axe(container)` assertion (Enforcement Matrix `[gate]` row),
closing the gap US-5.1's own strategy had to leave open pending dependency
approval.

## Security-sensitive-value assertion mechanism (stated once, reused per test)

PS-AC5/NFR's "never reaches storage, console, or a third party" is asserted
the same way across every test that needs it: spy on
`Storage.prototype.setItem` (covers both `localStorage`/`sessionStorage`)
and every `console.*` method via `vi.spyOn`, assert none of them were ever
called with a payload containing the `secret`/`otpauth_uri`/recovery-code
values in scope, and separately assert MSW recorded no request to any host
outside `/api/v1/...` (the QR renderer in particular must fire zero network
requests of its own).

## Coverage floor

85% minimum via `test:coverage` (`AGENTS.md` §5/§6's Frontend subsection),
enforced by `gate-enforcer` at `QUALITY_GATE`/`T13`, not measured by this
stage — there is no built scaffold yet for the new files to run coverage
against.
