# Open Decisions: US-3.3 (View Audit Information)

**Story:** docs/stories/US-3.3-view-audit-information.md
**Pre-existing draft:** docs/specifications/US-013-view-audit-information-spec.md (2026-08-22) + docs/reviews/specifications/US-013-spec-review.md — both predate US-3.1/US-3.2 landing in the real codebase and did not have the current code to check against.
**Run date:** 2026-09-02

## OD-1 — BLOCKING: `audit_log` name collision with an existing, unrelated table (and the story disagrees with itself on whether `audit_log` is a table or a view)

The story is internally ambiguous about what `audit_log` even is: Assumption #1 says "One append-only `audit_log` **table** with a `category` discriminator; existing per-domain tables exposed through a union view" (implying a new central write-target table, distinct from the union view), while the Data Model Notes describe `audit_log` itself as "Union view over `auth_audit_log`, `profile_audit_log`, ...". These are two different designs — a new table every module writes into centrally, versus a read-only view over the existing per-domain tables — with different write-path implications for every module that currently writes its own domain audit table. The collision below is blocking under either reading, but which reading is intended changes which resolution is cheapest, so the user should resolve both together.

A real table already named `audit_log` exists in production schema: `app/modules/email_verification/models.py::AuditLog` (`__tablename__ = "audit_log"`), created by migration `430aa1b298fb_add_email_verification.py`. Its shape (`id`, `event`, `subject_user_id`, `detail`, `occurred_at`) and purpose (recording BR-002's 7-day unverified-account purge job's deletions — see `EmailVerificationRepository.create_audit_log`) are unrelated to this story's security/admin audit trail.

PostgreSQL cannot have a table and a view share a name in the same schema, so this is a hard technical conflict, not a style question.

**Why it can't be inferred:** the story was drafted before this table existed in the real codebase (drafted 2026-08-22; the table shipped as part of US-1.2 email verification, already on `main`). Neither `docs/product/*` nor the story anticipates the collision.

**Impact if left unresolved:** db-designer cannot create the view as specified; whichever design is chosen changes either an already-shipped table (touching the unverified-account purge feature, out of this story's stated scope) or the name of this story's own central artifact (touching every FR/AC that references `audit_log`).

**Options for the user:**

1. Rename the existing `email_verification` table (e.g. to `unverified_account_purge_log`) via a migration, freeing `audit_log` for the new view. Touches a shipped feature outside this story's scope but keeps this story's naming as specified.
2. Name the new view something else (e.g. `audit_log_view` or `security_audit_log`) and update the story/spec's Data Model Notes and every AC/FR that says `audit_log`. Keeps the existing table untouched but diverges from the story's literal wording.
3. Fold the existing purge-audit rows into the new union view as a sixth source (its shape would need `category`/`actor_id`/etc. added or synthesized), and rename only if still colliding.

**Recommended:** Option 1 (rename the pre-existing table) — it is the narrower blast radius (one small, single-purpose table used only by one purge job, versus rewriting nine ACs' worth of story/spec text), and it removes an accidental, confusing overlap between two unrelated "AuditLog" concepts going forward.

**Resolved 2026-09-02 (user):** Option 1. Rename `email_verification.AuditLog`/`audit_log` to `unverified_account_purge_log` via a migration, freeing `audit_log` for this story's new central artifact. Recommended option accepted.

---

## OD-2 — BLOCKING: AU-AC8's cited dependency (US-1.4 DA-AC9 retention job) does not exist in code

AU-AC8/FR-8 requires proving that audit entries survive "a user account permanently deleted or anonymised by the US-1.4 DA-AC9 retention job." That job does not exist:

- `app/modules/account/models.py`'s own `AccountLifecycleAuditLog.user_id` column comment says "a **future** permanent-deletion job removes the users row this entry describes" (future tense).
- `docs/stories/US-1.4-deactivate-account.md`'s Enforcement Matrix marks DA-AC9 `[manual]` ("scheduled execution verified in staging") and its Open Questions #1 says the anonymization-vs-hard-deletion policy needs DPO/legal sign-off, still unresolved.
- `docs/product/business-rules.md` BR-007 states the same job's "exact mechanics [are] pending legal/DPO sign-off."
- The only account-erasure job actually implemented is `scripts/purge_unverified_accounts.py` (BR-002's 7-day *unverified*-account purge) — a different job, different trigger condition (never-verified, not deactivated-30-days), different table (`email_verification.AuditLog`, itself the subject of OD-1).

AU-AC8 cannot be integration-tested end-to-end against a job that doesn't exist yet.

**Why it can't be inferred:** the story cites DA-AC9 as already-built ("Given a user account permanently deleted... by the US-1.4 DA-AC9 retention job"), but reading the real US-1.4 codebase and its own story file shows the job was deliberately deferred pending a policy decision, not merely undocumented.

**Impact if left unresolved:** AU-AC8 either can't be built as an integration test against a real job, or this story silently expands scope to include building DA-AC9 itself (a decision with its own DPO/legal dependency this story's Assumptions table doesn't own).

**Options for the user:**

1. Build a minimal version of DA-AC9's job now, scoped only to what AU-AC8 needs to prove (anonymize `users` row + redact identifiers on already-written audit rows), deferring the still-open anonymization-vs-deletion policy question to a follow-up — i.e., pick one reasonable interim mechanic (e.g., anonymize, don't hard-delete, matching this story's own "redacted or anonymised" wording) and flag it explicitly as provisional.
2. Test AU-AC8 against a synthetic/simulated erasure event (directly anonymizing a `users` row and its identifiers in a test, without a real scheduled job), and track building the actual DA-AC9 job as a separate backlog item this story does not close.
3. Defer AU-AC8 entirely out of this story's scope until DA-AC9 ships, shipping AU-AC1–7 and AU-AC9 only.

**Recommended:** Option 1 — this story already needs DA-AC9's job to exist for AU-AC8 to mean anything in practice (BR-007's own wording: "anonymize" is already the leaning default), and per `docs/stories/README.md`'s dependency notes this was already understood as an implicit prerequisite ("US-3.1 depends on US-1.4 (DA-AC10 invariant)" shows this project already builds cross-story admin-side prerequisites inline rather than blocking). Scope the job narrowly and flag the retained legal/DPO policy question as still open, exactly as DA-AC9's own Open Question already states.

**Resolved 2026-09-02 (user):** Option 1. Build a minimal, provisional DA-AC9 script now (`scripts/`-pattern, per the project's one existing job precedent): anonymizes the `users` row and redacts direct identifiers on that user's existing audit rows — enough to make AU-AC8 testable. The anonymize-vs-hard-delete legal/DPO sign-off question stays open, tracked separately, exactly as DA-AC9's own story already flags it. Recommended option accepted.

---

## OD-11 — BLOCKING: the story contradicts itself on partition granularity (daily vs. monthly)

Three places in the story disagree on the hash chain's/table's partitioning unit:

- Assumptions & Defaults #4: "Chain scope | **Per daily partition**, seeded with the previous partition's final hash | Keeps verification cheap and preserves partition pruning"
- AU-AC7: "When the chain verification job runs over any **day's** partition"
- Data Model Notes: "covering index on `(occurred_at DESC, actor_id, event)`; **monthly** partitions; keyset (not `OFFSET`) pagination"

This isn't cosmetic: the partition boundary defines the hash chain's scope (where a new chain starts, what "the previous partition's final hash" seeds from), the unit AU-AC7's verification job operates over, and the partition-pruning performance claim Assumption #4's own rationale rests on. A monthly partition with a "per daily partition" hash chain is a materially different trigger/verification design than a daily partition with a daily chain.

**Why it can't be inferred:** both readings are stated explicitly and directly contradict each other; there's no established precedent in this codebase (no existing partitioned table) to break the tie by.

**Impact if left unresolved:** db-designer cannot write the partitioning DDL or the `BEFORE INSERT` trigger's chain-seeding logic without knowing which unit is authoritative — this is upstream of OD-3's migration sizing.

**Options for the user:**

1. Daily partitions, chain scoped per day (matches Assumption #4 and AU-AC7, the majority — 2 of 3 mentions — and the more conservative/cheaper-to-verify unit given Assumption #4's own stated rationale).
2. Monthly partitions, chain scoped per month (matches Data Model Notes only; AU-AC7's "any day's partition" wording would need to be read loosely as "the partition containing that day," not literally a daily partition).

**Recommended:** Option 1 (daily) — it's consistent across two of the three mentions including the AC text itself (the highest-authority source, since ACs are what gets tested), and Assumption #4's own stated rationale ("keeps verification cheap") is a daily-partition argument.

**Resolved 2026-09-02 (user):** Option 1. Daily partitions, chain scoped per day. The Data Model Notes' "monthly partitions" line was the outlier and is superseded — db-designer should treat Assumption #4/AU-AC7's "daily" as authoritative. Recommended option accepted.

---

## OD-12 — BLOCKING: AU-AC4's database-grant enforcement has no infrastructure to enforce it, and the app's current DB role cannot be restricted by grants at all

AU-AC4's NFR is emphatic: "Immutability MUST be enforced by database grants (AU-AC4), not by application code alone," and its Enforcement Matrix marks it `[gate]`: "Test executing an UPDATE/DELETE as the application role and asserting a permission error." Checking the actual infrastructure:

- No migration in `migrations/versions/` (12 files) contains a `GRANT` or `REVOKE` statement — grants-based enforcement doesn't exist anywhere in this codebase yet, for any table.
- `app/core/config.py`'s `database_url` default (and `.env.example`) connects as **`postgres`** — PostgreSQL's own superuser role. A superuser bypasses all `GRANT`/`REVOKE` restrictions and all Row-Level Security by definition; no combination of `GRANT INSERT, SELECT` statements can restrict a superuser connection. Even for a non-superuser role, if the app's role is also the *owner* of the audit tables (which Alembic's `CREATE TABLE` would make it, run as this same connection), table ownership independently grants full privileges regardless of explicit grants — `REVOKE` doesn't remove an owner's implicit rights either.

Satisfying AU-AC4 as written requires provisioning a second, non-owner, non-superuser application database role (used only for the audit-log read/write path, or project-wide) plus grant migrations — real deployment/infrastructure scope this story's Assumptions table doesn't mention and that no prior story has needed.

**Why it can't be inferred:** the story states the DB-grant requirement as if the underlying role model already supports it; nothing in `docs/product/*` or prior stories' shipped code establishes a non-superuser/non-owner application role.

**Impact if left unresolved:** AU-AC4's `[gate]` test cannot pass against local/dev config as configured today, and PLANNING would need to scope a role/credentials change that reaches beyond this story's own module into deployment configuration (`.env.example`, `app/core/config.py`, possibly CI/staging DB provisioning) — a different class of change than every prior story's DB work.

**Options for the user:**

1. Provision a dedicated non-owner `audit_writer` (or similarly-scoped) Postgres role for local/dev/CI now, with a grant migration, and update `.env.example`/config to use it for the audit-table connection (or project-wide, if simplest) — satisfies AU-AC4 as literally specified.
2. Treat AU-AC4's `[gate]` test as `[manual]`/deferred for this story (test only the `405` on `PATCH`/`PUT`/`DELETE` at the API layer, which needs no DB-role change), and track the DB-grant infrastructure as a separate, project-wide follow-up (it would also apply to every other audit table already shipped, e.g. `admin_audit_log`, `auth_audit_log` — this isn't unique to US-3.3).
3. Scope a narrower role just for the new `audit_log` artifact only, accepting that the four pre-existing per-domain audit tables remain writable by the current superuser connection (partial enforcement, disclosed as a known gap).

**Recommended:** Option 2 for this story's own scope, with Option 1 recorded as a named follow-up story/ticket — a project-wide DB-role change is a bigger, cross-cutting change than "view + query endpoint," and it would be inconsistent to give this one story its own bespoke role while every other already-shipped audit table stays superuser-writable. The API-level 405 (the other half of AU-AC4) still ships as a real, gate-tested control either way.

**Resolved 2026-09-02 (user):** Option 2. This story ships only the API-level `405` on `PATCH`/`PUT`/`DELETE` (gate-tested). Provisioning a non-superuser, non-owner Postgres role plus `GRANT`/`REVOKE` migrations is deferred to a separate, project-wide infrastructure follow-up (it would apply to every audit table already shipped, not just this story's). AU-AC4's DB-grant half is disclosed as not yet enforced pending that follow-up. Recommended option accepted.

---

## OD-3 — Medium: existing per-domain audit tables don't have the columns the union view needs, and their shapes are inconsistent

The four already-shipped per-domain tables the story's union view is meant to sit over are missing most of what AU-AC1/AU-AC7 require, and disagree with each other on which identity/context columns they even carry:

| Table | Has `previous_hash`/`row_hash`? | Has `category`/`outcome`/`payload`? | Has `ip`/`user_agent`? | Actor column | Target column |
| --- | --- | --- | --- | --- | --- |
| `auth_audit_log` | No | No | Yes | `actor_id` | — (`target_family` only, session-specific) |
| `admin_audit_log` | No | No | No | `actor_id` | `target_id` |
| `profile_audit_log` | No | No | No | `actor_id` | — |
| `account_lifecycle_audit_log` | No | No | No | — (`user_id`, `actor` as free-text string, not a role) | — |

None has `previous_hash`/`row_hash` (AU-AC7), and none has `category`/`outcome`/`payload` (AU-AC1's response shape, Data Model Notes). This isn't a gap the story leaves genuinely ambiguous — it's simply not yet built — but it means the union view is not a thin `UNION ALL` over ready-made rows; each of the four tables needs new columns (a migration touching four already-shipped tables) before the view can satisfy AU-AC1/AU-AC7, which changes this story's actual size versus what "add a query endpoint + a view" suggests.

**Why it can't be inferred:** the story's Data Model Notes describe the target shape but say nothing about the current shape of the tables it's unioning, because those tables didn't exist when the story was drafted (2026-08-22).

**Impact if left unresolved:** PLANNING would under-scope this story as "one new endpoint + one view" when it actually requires four migrations plus backfill decisions for the hash chain's `previous_hash` on pre-existing rows.

**Recommended:** carry this forward as DESIGN/db-designer input rather than resolving here — flagging it now so PLANNING sizes the migration work correctly. No user decision needed yet beyond acknowledging the scope.

---

## OD-4 — Medium: `ticket_audit_log` (5th union-view source) doesn't exist yet — Epic 4 is unbuilt

The Data Model Notes list `ticket_audit_log` as one of the five tables the `audit_log` view unions over, but no ticket module exists in `app/modules/` yet (Epic 4 — US-4.1/4.2/4.3 — is still spec-only per `docs/stories/README.md`).

**Why it can't be inferred:** the story assumes a codebase state (all five domain tables live) that doesn't hold yet at this project's current build order (`README.md`: "...then US-3.1, US-3.3, US-2.6, US-2.5, then Epic 4...").

**Impact if left unresolved:** db-designer needs to know whether to build the view over 4 sources now and extend it when Epic 4 ships, or treat the 5-source view as blocked on Epic 4.

**Recommended:** build the view over the four tables that exist today (`auth_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`, `admin_audit_log`); extend the view definition (a small migration) when Epic 4 ships `ticket_audit_log` — mirrors this project's own precedent of `admin_audit_log` being added to the audit-table set ahead of every other consumer needing it (per its own docstring, "added during T4... the other four: US-3.1, not yet built").

---

## OD-5 — Resolved by precedent: `limit`/`cursor` bounds

AU-AC1 shows `limit=50` as an example but states no maximum, and neither story nor pre-existing spec states invalid-cursor behavior (flagged as an Open Question in both `docs/specifications/US-013-view-audit-information-spec.md` and its review). This is resolved by the shipped precedent in `app/modules/admin_users/service.py` (`list_users`): `limit` capped at 100 with a `422` field error (`code="max"`) if exceeded, and an invalid `cursor` also rejected with a `422` field error. Recommend the same shape for this story's endpoint (independent constant, not a shared one, since `admin_users` and `audit-logs` are separate list endpoints).

---

## OD-6 — Carried forward, unresolved: hash-chain trigger concurrency

`docs/reviews/specifications/US-013-spec-review.md`'s own Medium finding: AU-AC7/FR-7 describe a `BEFORE INSERT` trigger computing `previous_hash` from "the previous row's hash," but neither the story nor spec states how correctness is preserved under concurrent `INSERT`s into the same day's partition. Nothing in the current codebase (no existing trigger-based hash chain anywhere in this project) resolves this by precedent. Still needs a DESIGN-stage decision (e.g., row-level locking on the partition's last row, or a `SERIALIZABLE`-adjacent guarantee) — carried forward unchanged, not resolved by this run.

---

## OD-7 — Carried forward, unresolved: "fields marked sensitive" enumeration

AU-AC6/FR-6 says "fields marked sensitive are stored redacted" but names only four excluded value types (password, password hash, raw token, session cookie, full payment identifier) as things that must never appear — it does not enumerate the complete list of fields subject to redaction. Flagged as Low by the pre-existing spec review; nothing in the current codebase resolves it (no audit-write call sites exist yet to infer a list from). Still open.

---

## OD-8 — Carried forward, unresolved: does AU-AC8 redaction reach into the `payload` JSONB field?

AU-AC8/FR-8 names three example direct identifiers (email, display_name, ip) as things that must be redacted/anonymized on account erasure, not a closed list. Whether identifiers embedded inside the `payload` JSONB column (Data Model Notes) are also in scope for that redaction is unstated in both story and spec. Still open — flagged by the pre-existing spec review, unresolved by anything in the current codebase.

---

## OD-9 — Carried forward, unresolved: cold-storage target for AU-AC9

The story's own Open Questions #1: "Cold-storage target and access procedure for AU-AC9 (which system, who may retrieve, how long). Needs legal/DPO sign-off." Unchanged by this run — still genuinely open, same as DA-AC9's own retention-policy question in OD-2.

---

## OD-13 — High: AU-AC8 identifier-redaction mechanism for fields not stored in a dedicated column

Raised by `docs/reviews/specifications/US-013-spec-review.md` (SPEC_REVIEW, 2026-09-02), not by the original `us-clarifier` run: `profile_audit_log` stores profile changes as `field`/`old_value`/`new_value` free text — a row with `field="display_name"` has the changed `display_name` value sitting directly in `old_value`/`new_value`, not in a dedicated identifier column. AU-AC8/FR-8 requires that `display_name` (one of its three named identifiers) be redacted or anonymised on account erasure, but neither the story nor the spec stated how the erasure script would find a value it doesn't know is an identifier in advance.

**Options presented:**
1. Field-aware redaction: the erasure script knows which `profile_audit_log.field` values are identifier-bearing (e.g. `display_name`) and redacts `old_value`/`new_value` on any of that user's rows where `field` matches — targeted, no scanning of arbitrary text.
2. Value-matching scan: look up the user's current/historical identifier values and scrub any audit row (across all four tables, including `payload` JSONB) whose text contains a matching value — broader coverage, fuzzier and more expensive mechanism.
3. Defer: ship AU-AC8 only for columns that already have dedicated identifier fields (`actor_id`, `ip`); treat identifiers embedded in free-text/JSONB fields as a disclosed, separate gap.

**Resolved 2026-09-02 (user):** Option 1, field-aware redaction. The erasure script (OD-2's minimal provisional job) maintains a known list of identifier-bearing `field` values for `profile_audit_log` (starting with `display_name`) and redacts `old_value`/`new_value` on that user's matching rows. `payload` JSONB scanning (the pre-existing, still-open Open Question about `payload` scope) is not addressed by this resolution and remains open separately.

---

## OD-14 — High: does every existing audit-write call site get repointed to the new `audit_log` table, or only this story's two new events?

Raised by `db-designer` (DESIGN, 2026-09-02), while resolving OD-1's remaining table-vs-view ambiguity. That resolution is technically forced (a view can't be partitioned, and AU-AC7's hash chain needs a physical table to fire a `BEFORE INSERT` trigger on) — `audit_log` must be a new, real, daily-partitioned table. What's genuinely undecided is *what writes into it*:

- **Narrow reading:** only this story's own two new event types (`audit_log_viewed`, the `audit:read`-denial event) write into `audit_log`. AU-AC7's "every audit entry carries a `previous_hash`" is satisfied for every row that exists in `audit_log` — the four existing per-domain tables (`auth_audit_log`, `admin_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`) keep being written by their existing call sites, untouched, unchained.
- **Broad reading:** every existing audit-write call site across the `users`, `roles`, `profile`, and `account`/`admin_users` modules is repointed to write `audit_log` instead of its own table, so login failures, role changes, profile edits, and deactivations are all tamper-evident too — not just "someone viewed the log."

Both readings satisfy AU-AC7's text equally (its "every entry" scope is whatever set of rows the story decides belongs in `audit_log`). What actually favors the broad reading is a product argument, not a technical one: a tamper-evident log containing only "someone viewed the log" doesn't serve the story's own stated purpose ("investigate a security incident or answer a compliance request with evidence"). But nothing in the story, its Assumptions table, the amended spec, or the SPEC_REVIEW that just passed authorizes touching four already-shipped modules' write paths — this is new scope `db-designer` cannot decide alone.

**Cost of the broad reading, priced from this codebase:** `require_scope`'s shared `authz_denied` write (used by every scope-gated endpoint project-wide, not just four modules); `roles.repository.UserRoleRepositoryProtocol.create_admin_audit_log_entry` and its existing hand-written test fakes; every integration test across US-1.4/US-2.x/US-3.1/US-3.2 that asserts a row landed in a specific per-domain table (509 tests as of US-3.1's gate); and `pr-preparer`'s AGENTS.md §7.8 commit-hygiene check, which will read a four-module diff as scope sprawl unless pre-authorized here.

**Options for the user:**
1. Narrow: only this story's two new events write to `audit_log`. Smallest footprint; the log's tamper-evidence guarantee applies only to audit-log access itself, not to the security events the story's own Background narrative describes investigating.
2. Broad, this story: repoint all four modules' write call sites now. Fully serves the story's stated purpose in one pass; largest footprint, touches shipped code across 4+ modules and their test suites.
3. Staged: ship `audit_log` + the hash chain + this story's own two events now; repoint each existing module's write path as its own follow-up story (expand → migrate → contract per `AGENTS.md` §4's own convention for structural changes), one module at a time.

**Resolved 2026-09-02 (user):** Option 3, staged. `audit_log` + the hash chain + this story's own two new events ship in this story. Repointing each existing module's audit-write call site (auth, profile, roles/admin, account) to `audit_log` is a separate, future follow-up story, one module at a time — matches this project's own expand → migrate → contract convention for structural changes (`AGENTS.md` §4). This story's own tamper-evidence guarantee (AU-AC7) covers only the events it itself writes; the four existing per-domain tables remain outside the hash chain until their own follow-up ships.

---

## OD-15 — Resolved: `scripts/verify_audit_chain.py` ownership

Raised by `implementation-planner` (PLANNING, 2026-09-02): no execution skill in this project's roster (`schema-builder`/`data-layer-builder`/`migration-manager`/`service-and-router-builder`) owns plain `scripts/` files. **Resolved 2026-09-02 (user):** `service-and-router-builder` builds it — closest fit, plain application logic reading the repository, structurally like a service method with no router/schema involved.

---

## OD-16 — Resolved: `audit_log` partition-maintenance safety net

Raised by `planner`/advisor (PLANNING, 2026-09-02): with no `DEFAULT` partition, the first `INSERT` past the migration-created partition's date range fails outright, including this story's own FR-2 self-audit write — `GET /v1/admin/audit-logs` would start `500`ing the moment the clock crosses into an unprovisioned day. **Resolved 2026-09-02 (user):** the migration (T3b) also creates a `DEFAULT` partition as a safety net. Rows land there, ungrouped but not lost, until a real daily partition exists. No partition-provisioning job ships with this story; that automation is future work.

---

## OD-10 — Carried forward, unresolved: single missing `from`/`to` bound

AU-AC5/FR-5 only specifies behavior when the range exceeds 90 days or omits *both* bounds. Behavior when exactly one bound is supplied (reject, default, or treat as open-ended) is unstated in both story and spec. Flagged Low/question by the pre-existing spec review; nothing in the current codebase resolves it by precedent (no comparable single-bound-optional filter exists elsewhere in this project — `admin_users`'s filters are independent, not a paired range). Still open.

---

## OD-17 — Resolved: hash-chain genesis rule (first partition / empty prior day)

Raised by `advisor` at TESTS-stage review (2026-09-02): `previous_hash`'s seeding rule was left as a carried-forward Open Question, but it blocks `migration-manager`'s `BEFORE INSERT` trigger SQL (T3b), which in turn blocks T4/T8/T9 — the whole implementation chain past the migration. This is the same shape as OD-14/OD-15/OD-16 (a real blocker, not a footnote) and should not be carried into IMPLEMENTATION undecided.

**Options presented:**
1. Fixed sentinel for the very first partition ever created; every subsequent day's first row seeds from the most recent non-empty prior partition's final `row_hash`, skipping empty days entirely.
2. Always seed from the immediately-prior day's final hash; an empty day carries its incoming hash/sentinel forward unchanged.

Both converge to the same practical tamper-detection behavior (a wiped day still surfaces as a hash mismatch at the next real row, satisfying AU-AC7's "reports the exact row at which the chain breaks" without per-day placeholder rows) — Option 1 was preferred as the more explicit/self-documenting rule for the trigger's own logic.

**Resolved 2026-09-02 (user):** Option 1. First-ever partition's first row seeds `previous_hash` from a fixed sentinel (hash of empty string). Every subsequent day's first row seeds from the most recent non-empty prior partition's final `row_hash`, skipping empty days. Recommended option accepted.

---

## OD-18 — Resolved: AU-AC9 (retention job) scope for this story

Raised by `advisor` at TESTS-stage review (2026-09-02): AU-AC9/FR-9 (move entries older than 400 days to cold storage) has no file, task, or test row anywhere in `docs/plans/US-013-implementation-plan.md`, `docs/plans/US-013-task-breakdown.md`, or the traceability matrix — a second missing job, same class as `scripts/verify_audit_chain.py` (OD-15) before it was caught. Unlike that one, this gap traces to OD-9's still-open, legal/DPO-pending cold-storage-target question: the job's core mechanic (where rows go) cannot be built without that decision.

**Options presented:**
1. Defer explicitly: do not build the retention job in this story; state the deferral plainly in the plan/task-breakdown/matrix (matching how AU-AC4's DB-grant half was deferred under OD-12) so `reconciliation-reviewer` sees a disclosed gap, not a silently dropped AC.
2. Build now with a placeholder cold-storage target (e.g. a separate DB table), to be repointed once legal/DPO decide.

**Resolved 2026-09-02 (user):** Option 1. AU-AC9's retention job is explicitly out of this story's build scope, blocked on OD-9 (cold-storage target, legal/DPO sign-off pending). AU-AC9 remains `[manual]` per the story's own Enforcement Matrix, with no code, test, or task delivered against it in US-3.3. Recommended option accepted.
