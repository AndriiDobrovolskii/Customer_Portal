---
artifact_type: open_decisions
story: US-5.4
version: 2
status: DRAFT
created_at: "2026-09-13T07:10:29Z"
updated_at: "2026-09-13T13:15:00Z"
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
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/workflow/active-story.yaml
    version: 1
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 1
supersedes: docs/decisions/US-5.4-open-decisions.md (v1)
---

# Open Decisions: US-5.4 — Admin Console (Frontend)

This is a re-run of `CLARIFICATION` for US-5.4, ordered by `story-orchestrator`'s
`HUMAN_REDIRECTED` routing from `PLAN_REVIEW` back to `CLARIFICATION`
(`docs/workflow/history.jsonl` at `2026-09-13T12:45:00Z`). `PLAN_REVIEW`
returned `BLOCKED` because the four Open Decisions below were still `OPEN` in
the `APPROVED` v1 specification and were tied directly to task-breakdown
tasks T16, T19, T20, T21. A human stakeholder (`sbruhov@gmail.com`) supplied
an explicit resolution for each of the four items in that same 2026-09-13
session. This revision records those human-supplied resolutions; it does not
invent, infer, or guess any of them.

All four items carried in `docs/decisions/US-5.4-open-decisions.md` (version 1,
`status: DRAFT`, all `OPEN`) are resolved below. Re-reading the story,
`docs/product/*`, and the codebase for this pass surfaced no further
genuinely new Open Decisions beyond the normal responsibilities checklist —
see "Re-check of the normal Open-Decision triggers" at the end of this file.

---

## OD-1 — Default `from`/`to` window for the Audit Log screen's initial load — RESOLVED

**Question:** What `from`/`to` values does the Audit Log screen send on first
load (before the admin has chosen any filter), and what does the UI show
while no explicit range has been picked?

**Why it couldn't be inferred:** `GET /v1/admin/audit-logs` rejects a request
missing *either* bound with `422 range-too-wide`
(`app/modules/audit/service.py:124-129`), and neither AD-AC8, the story's
Assumptions & Defaults table, nor any `docs/product/*` source stated a
default reporting window.

**Resolution:** Default window is the last 7 days: `from = now - 7 days`,
`to = now`, both in ISO 8601 UTC. Both dates are pre-filled **visibly** in the
date-picker inputs on first load — the default is not applied silently behind
the scenes.

**Rationale:** Satisfies the backend's requirement that both bounds be
present (`GET /admin/audit-logs` 422s otherwise with `range-too-wide`), stays
within the 90-day maximum window, and the admin immediately sees what time
slice is being queried.

**Source:** human decision, 2026-09-13.

---

## OD-2 — Audit log `event` filter: free text or a fixed vocabulary? — RESOLVED

**Question:** Should the Audit Log screen's `event` filter be a free-text
input, or should it offer a discoverable list of known event names?

**Why it couldn't be inferred:** `event` is typed as an unconstrained string
everywhere it appears (`docs/designs/api/US-3.3-openapi.yaml:164-165`, no
`enum`), event names are scattered as string literals across many stories
with no single enumerated source of truth, and no catalogue endpoint exists
for this field the way `GET /admin/roles` exists for role names.

**Resolution:** Free-text input, with an illustrative placeholder (e.g. "e.g.
user_created, authz_denied").

**Rationale:** No event-catalogue endpoint exists; a hardcoded frontend enum
would drift as new event types are added elsewhere.

**Source:** human decision, 2026-09-13.

---

## OD-3 — Role replacement UI: full-replace multi-select or add/remove controls? — RESOLVED

**Question:** Should the role-editing control on the user-edit screen be
presented as a multi-select showing the resulting final role set, or as
separate add/remove actions that compute the same final set behind the
scenes?

**Why it couldn't be inferred:** `PUT /admin/users/{id}/roles` is confirmed a
full replacement, not a delta (`docs/designs/api/US-3.2-openapi.yaml:164-167`).
AD-AC5 requires "an explicit confirmation naming what the user will gain and
lose" but did not say how the admin arrives at that final set, and no other
Story or product document specified a role-editing interaction pattern to
reuse.

**Resolution:** Multi-select component displaying the final target role set,
matching `PUT /admin/users/{id}/roles`'s full-replacement semantics. The
required confirmation dialog computes and displays:
- **Gained roles** = `selected_roles - current_roles`
- **Lost roles** = `current_roles - selected_roles`

If neither set changed, save stays disabled.

**Source:** human decision, 2026-09-13.

---

## OD-4 — Create User's role picker: catalogue-driven or free text? — RESOLVED

**Question:** Does the Create User form's `roles` field source its options
from `GET /admin/roles` (the same catalogue AD-AC5 uses for role
replacement), or is a different input mechanism intended?

**Why it couldn't be inferred:** The story's In Scope list mentioned the role
catalogue only in the same bullet as role *replacement*; AD-AC3 (create user)
never stated where its `roles` values come from. This mattered more here
than generically, because the create-user backend path
(`app/modules/roles/service.py:231-236`, `resolve_role_ids_for_grant`)
silently excludes any unrecognized role name from the returned id list rather
than rejecting the request — unlike `replace_user_roles`
(`app/modules/roles/service.py:137-142`), which explicitly rejects an
invalid role list with a `422`.

**Resolution:** Catalogue-driven, sourced from `GET /admin/roles` — reusing
the same query hook used for role replacement.

**Rationale:** The backend create-user endpoint silently drops unrecognized
role names rather than rejecting them, so sourcing strictly from the
catalogue prevents administrators from creating under-permissioned accounts
via typos.

**Source:** human decision, 2026-09-13.

---

## Re-check of the normal Open-Decision triggers (this pass)

Re-reading `docs/product/product-vision.md`, `personas.md`, `business-rules.md`,
`business-glossary.md`, and `docs/stories/US-5.4-admin-console-ui.md` against
this skill's own Responsibilities list (business intent, acceptance criteria,
security expectations, validation expectations, dependencies, assumptions)
surfaced no additional item that cannot be reliably inferred from those
sources or the story itself. The two prior "Findings Resolved by Citation"
items from version 1 of this artifact (the `UserRead.status` enum being
already documented in `docs/designs/api/US-3.1-openapi.yaml`, and the
Create-User empty-role-list edge case already covered by XC-AC3) remain
resolved by citation and are not reopened here — nothing in the human's four
resolutions or in this re-read touches either of them.

**No new Open Decisions are recorded in this revision.**
