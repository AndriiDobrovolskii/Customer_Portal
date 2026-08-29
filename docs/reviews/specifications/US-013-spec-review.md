# Spec Review: View Audit Information

**Original Story:** docs/stories/US-3.3-view-audit-information.md
**Spec Reviewed:** docs/specifications/US-013-view-audit-information-spec.md
**Story ID:** US-3.3 (source) / US-013 (spec numbering)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All 9 Acceptance Criteria (AU-AC1–AU-AC9) are fully covered by the spec's Functional Requirements, and no contradictions with the original story were found. The spec's own Traceability Matrix flags FR-5 and FR-9 as only "partial" coverage, but on independent comparison against the literal AC text, both FRs fully implement what their ACs actually state — the flagged gaps are genuine open follow-up questions, not coverage shortfalls, and the self-labeling is itself a minor finding below. The main issues are omissions of supporting detail from the story (Data Model Notes, the RFC 7807 error envelope example) and a handful of unresolved edge cases around concurrency and pagination bounds that neither the story nor the spec addresses.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| AU-AC1 | "Given an authenticated actor holding the audit:read permission When GET /v1/admin/audit-logs?actor_id=…&event=login_failed&from=…&to=…&limit=50 is called Then respond 200 with a cursor-paginated, newest-first list And each entry contains occurred_at, actor_id, actor_role, event, target_id, request_id, ip, user_agent, and an outcome" | Covered | FR-1 | Field list and 200/cursor/newest-first behavior match exactly. |
| AU-AC2 | "Given any successful call to GET /v1/admin/audit-logs When the response is returned Then an audit entry is written (event=audit_log_viewed) recording the actor and the exact filter parameters used" | Covered | FR-2 | |
| AU-AC3 | "Given an authenticated support agent, who does not hold audit:read When GET /v1/admin/audit-logs is called Then respond 403 with type \".../errors/insufficient-permission\" And the denied attempt is itself recorded in the audit log" | Covered | FR-3 | |
| AU-AC4 | "Given any actor, including an administrator When PATCH, PUT or DELETE is attempted on /v1/admin/audit-logs or any entry Then respond 405 Method Not Allowed And the application's database role holds INSERT and SELECT grants only on audit tables" | Covered | FR-4 | |
| AU-AC5 | "Given a request whose from/to range exceeds 90 days, or which omits both bounds When GET /v1/admin/audit-logs is called Then respond 422 with type \".../errors/range-too-wide\" And the message states the maximum window and suggests the asynchronous export instead" | Covered | FR-5 | FR-5's text matches the AC's literal conditions verbatim. The spec's own Traceability Matrix labels this "partial," but the gap it points to (single missing bound) is not something AU-AC5 itself specifies either — see Ambiguities. |
| AU-AC6 | "Given any audit entry of any event type When it is returned or inspected directly in storage Then no password, password hash, raw token, session cookie or full payment identifier appears in any field And fields marked sensitive are stored redacted (e.g. \"changed\" rather than the value)" | Covered | FR-6 | "Fields marked sensitive" is undefined in both story and spec — see Ambiguities. |
| AU-AC7 | "Given every audit entry carries a previous_hash computed by a PostgreSQL BEFORE INSERT trigger over (previous row's hash, occurred_at, actor_id, event, target_id, payload) When the chain verification job runs over any day's partition Then it reports \"intact\" for an untouched chain And when any historical row is altered or removed by any means, the job reports the exact row at which the chain breaks And the hash column is computed server-side only — the application may never supply it" | Covered | FR-7 | |
| AU-AC8 | "Given a user account permanently deleted or anonymised by the US-1.4 DA-AC9 retention job When their historical audit entries are queried Then the entries remain, with actor_id retained as an opaque UUID And every direct identifier they contained (email, display_name, ip) is redacted or anonymised Because the audit trail must stay intact while the link to the natural person is severed" | Covered | FR-8 | |
| AU-AC9 | "Given an audit entry older than the 400-day retention period When the scheduled retention job runs Then the entry is moved to cold storage (not silently dropped) And the job's own execution is recorded" | Covered | FR-9 | FR-9's text matches the AC verbatim. The Traceability Matrix labels this "cold-storage target — see Open Questions," but that question (which system, who may retrieve, how long) was already an unresolved Open Question in the source story itself, not a gap the spec introduced. |

## Ambiguities & Non-Verifiable Statements

- **[Low] Traceability Matrix self-labels overstate coverage gaps** — Spec's Traceability Matrix (spec section "Traceability Matrix") marks AU-AC5 as "FR-5 (partial — see Open Questions)" and AU-AC9 as "FR-9 (cold-storage target — see Open Questions)." In both cases the corresponding FR text fully implements the AC's literal wording; the linked Open Questions are legitimate follow-up questions the AC itself doesn't answer, not evidence that the FR under-implements the AC. A reader skimming only the matrix could reasonably conclude AU-AC5/AU-AC9 are under-covered when they are not.

- **[Low] "Fields marked sensitive" is undefined** — Spec says: "Fields marked sensitive are stored redacted (e.g. `\"changed\"` rather than the actual value)." (FR-6). Neither the spec nor the source story (AU-AC6 uses the identical phrase) enumerates which fields are considered "sensitive" beyond the four named exclusions (password, password hash, raw token, session cookie, full payment identifier). A developer or QA engineer cannot write a concrete test for "fields marked sensitive" without a defined field list.

- **[Low] "Direct identifier" scope for AU-AC8 not enumerated beyond three examples** — Spec says: "every direct identifier the entries contained (email, display_name, ip) is redacted or anonymised" (FR-8). This is verbatim from the story (AU-AC8), so it is not a spec-introduced ambiguity, but it remains non-exhaustive ("email, display_name, ip" are examples, not a closed list) — whether identifiers embedded inside the `payload` JSONB field (per Data Model Notes) are also in scope is not stated in either document.

## Scope Creep

No findings — every Functional Requirement (FR-1–FR-9) and Non-Functional Requirement in the spec traces cleanly to a corresponding AC or the source's own Non-Functional / Security Requirements section, with no added fields, systems, or behaviors beyond what the story states.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low] Data Model Notes are not carried into the spec** — The source story's "Data Model Notes" section specifies the `audit_log` table shape, a union view over five per-domain audit tables (`auth_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`, `admin_audit_log`, `ticket_audit_log`), a covering index on `(occurred_at DESC, actor_id, event)`, monthly partitions, and keyset (not `OFFSET`) pagination. None of this appears in the spec's Functional Requirements or Non-Functional Requirements. FR-1 states the query must be "cursor-paginated" (consistent with AU-AC1's wording) but doesn't carry forward the explicit keyset-pagination constraint or the union-view architecture that AU-AC1's cross-category filtering implicitly depends on.

- **[Low] RFC 7807 error envelope structure is not reproduced** — The source story includes a full `application/problem+json` example (Error Envelope section) and states "Error `type` slugs introduced by this story: `range-too-wide`." The spec's FR-3 and FR-5 reference the error `type` values (`.../errors/insufficient-permission`, `.../errors/range-too-wide`) but do not reproduce the envelope schema/example. Since AU-AC3 and AU-AC5 only require specific `type` values and status codes (both of which are covered), this is a completeness/reference gap rather than an AC coverage gap.

- **[Low, question] Single missing `from`/`to` bound is unaddressed by both story and spec** — AU-AC5 only specifies behavior when the range "exceeds 90 days, or ... omits both bounds." Neither the story nor the spec's FR-5 states what happens when exactly one of `from`/`to` is supplied without the other (rejected, defaulted, or treated as open-ended). The spec appropriately raises this in its own Open Questions section rather than asserting behavior — noted here for completeness, not as a defect.

- **[Medium, question] Concurrency behavior of the hash-chain trigger is unaddressed** — AU-AC7 (and FR-7) describe a `BEFORE INSERT` trigger that computes `previous_hash` from "the previous row's hash." Neither the story nor the spec states how the chain remains correct under concurrent `INSERT`s into the same partition (e.g., whether row-level locking or serialization guarantees a well-ordered chain). Given that AU-AC7's entire purpose is tamper evidence, a race condition here would undermine the guarantee — does the source's scope intend for this to be addressed at the trigger/transaction-isolation level, or is it deferred as an implementation detail?

- **[Low, question] `limit`/`cursor` parameter bounds are unaddressed** — AU-AC1 shows `limit=50` as an example value but neither the story nor FR-1 states a maximum enforced `limit`, behavior for an invalid or expired `cursor`, or behavior for zero matching results. This may be intentionally left to standard API conventions elsewhere in the system, but it is not stated in either document.

## Verdict Rationale

Pass with Issues: full AC coverage (all 9 ACs Covered under independent review) and no contradictions were found, so the verdict does not fail. However, the spec's own Traceability Matrix understates coverage of AU-AC5/AU-AC9 in a way that could mislead readers, several supporting details from the story (Data Model Notes, error envelope schema) were not carried into the spec, and a few edge cases (concurrent writes to the hash chain, pagination parameter bounds) remain open questions in both documents. None of these block implementation outright, but they are worth resolving or explicitly deferring before build.
