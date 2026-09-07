---
id: US-4.4
epic: EPIC-4
title: Agent Ticket Queue & Assignment
slug: agent-ticket-queue-and-assignment
priority: HIGH
track: backend
source:
  type: github_issue
  repository: AndriiDobrovolskii/Customer_Portal
  issue_number: 28
  issue_url: https://github.com/AndriiDobrovolskii/Customer_Portal/issues/28
  last_synced_at: "2026-09-07T00:00:00Z"
---

# Epic 4 — Feedback / Support: Agent Ticket Queue & Assignment

**Story ID:** US-4.4
**Project:** Customer Portal
**Blocks:** US-5.5 (Agent Console frontend). Without this Story the `support_agent` persona has no reachable UI at all.

## Why this Story exists
`app/modules/support/dependencies.py::reject_agent_queue_access` **rejects** any caller holding `tickets:read` or `tickets:write` from `GET /support/tickets` with a 403. That was a deliberate US-4.1 scope cut (OD-4/DR-4), but its consequence is that:
- an agent cannot discover a single ticket — the only listing endpoint is closed to them;
- `POST /support/tickets/{id}/resolve` (agent-only) is unreachable except by guessing a UUID;
- the agent branches of `POST /{id}/replies` (internal visibility) and `GET /{id}` are likewise unreachable.

`tickets:read` already exists in the permission catalogue (`migrations/versions/e50fbe8161fc_add_roles_and_permissions.py`) and is already granted to `support_agent` and `admin`. It is currently used **only** to reject. This Story turns it into the scope it was named for.

Additionally, no `assignee_id` column exists on `tickets` anywhere in the model — US-4.3 TC-AC4's "the previously assigned agent is notified" describes behavior the schema cannot express today.

## User Story
As a support agent,
I want to see the queue of tickets needing attention, take ownership of one, and see what is assigned to me,
So that work is discoverable and divisible rather than something I can only reach by being handed a ticket id.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Queue endpoint shape | An **agent branch on the existing `GET /support/tickets`**, replacing `reject_agent_queue_access` — not a new `/queue` path | The customer branch already lives there; a second path would duplicate filtering, cursor and serialization logic for the same resource |
| 2 | Queue scope | `tickets:read` | Already in the catalogue, already granted to `support_agent`/`admin`, currently unused except to reject |
| 3 | Assignment model | A single nullable `assignee_id` on `tickets` (one owner at a time), not a join table | No multi-assignment requirement exists; a join table would be speculative |
| 4 | Assignment endpoints | `POST /support/tickets/{id}/assign` (`{assignee_id}`) and `DELETE /support/tickets/{id}/assign` (unassign) | Explicit verbs; assignment is audited like every other ticket transition |
| 5 | Self-assign vs. assign-others | Any `tickets:write` holder may assign to themselves **or** to another agent; assigning to a non-agent is a 422 | Matches US-4.3 Assumption #3's "assignment is not a prerequisite; the actor is audited" |
| 6 | Assignment is **not** a precondition for resolve/reply | Unchanged from US-4.3 Assumption #3 | This Story adds discoverability and ownership, not a new gate |
| 7 | Customer visibility | `assignee_id` is **not** exposed on any customer-facing response shape | Data minimization — the same reasoning that keeps `closed_by`/`resolution_note` off `TicketStateRead` |
| 8 | Default queue ordering | Oldest `updated_at` first (the longest-waiting ticket surfaces first), stable-tiebroken by `id` | A cursor paginator needs a total order; "longest waiting" is the only ordering the ACs actually require |
| 9 | Closed tickets | Excluded from the default queue; reachable only via an explicit `status=closed` filter | The queue is outstanding work |

## In Scope
- Agent branch on `GET /support/tickets` under `tickets:read`: filters `status`, `category`, `assignee_id` (including `assignee_id=me` and `assignee_id=none`), cursor paging
- `POST /support/tickets/{id}/assign` and `DELETE /support/tickets/{id}/assign` under `tickets:write`
- `assignee_id` column on `tickets` + migration + index supporting the queue's filter and ordering
- `assignee_id` exposed on the agent-facing read shapes only
- Audit entries for assign/unassign
- Removal of `reject_agent_queue_access` and its `AgentQueueNotAvailableError`, with the US-4.1 tests that assert the 403 updated to assert the new branch

## Out of Scope
- Auto-assignment, round-robin, load balancing, or any routing rule
- SLA targets, breach reporting, queue-level metrics
- Multi-assignee / team-level ownership
- Attachments (still blocked on the unwritten attachment-upload story)
- Any change to the resolve/close/reopen state machine (US-4.3)

## API Contract
| Method | Path | Auth | Request | Success |
|---|---|---|---|---|
| GET | `/v1/support/tickets` | `tickets:read` (agent branch) | `?status=&category=&assignee_id=&cursor=&limit=` | 200 `TicketListResponse` (agent shape, incl. `assignee_id`) |
| GET | `/v1/support/tickets` | none beyond identity (customer branch) | unchanged | 200 `TicketListResponse` (customer shape, **no `assignee_id`**) |
| POST | `/v1/support/tickets/{id}/assign` | `tickets:write` | `{"assignee_id": uuid}` | 200 `TicketStateRead` (agent shape) |
| DELETE | `/v1/support/tickets/{id}/assign` | `tickets:write` | — | 200 `TicketStateRead` (agent shape) |

`assignee_id` query values: a UUID, the literal `me` (the calling agent), or `none` (unassigned).

## Data Model Notes
- `tickets.assignee_id UUID NULL REFERENCES users(id)` — nullable, no cascade delete (US-1.4's retention job owns erasure)
- Index supporting the queue: `(status, updated_at, id)` for the default ordering, plus `(assignee_id, updated_at, id)` for the per-agent view
- Audit events: `ticket_assigned`, `ticket_unassigned`, each recording `actor_id` and the target `assignee_id`
- Migration is additive only — a nullable column plus indexes; no backfill and no destructive step, so no expand→migrate→contract cycle is required

## Acceptance Criteria

### Happy path
**AQ-AC1 — Agent sees the queue**
```gherkin
Given an agent holding tickets:read
When GET /v1/support/tickets is called
Then respond 200 with every non-closed ticket regardless of requester, ordered oldest-updated first
And each item carries assignee_id
And the response pages by cursor with no total count
```

**AQ-AC2 — Queue filters**
```gherkin
Given an agent holding tickets:read
When GET /v1/support/tickets is called with status, category or assignee_id
Then only matching tickets are returned
And assignee_id=me resolves to the calling agent's own id
And assignee_id=none returns only unassigned tickets
And status=closed is the only way a closed ticket appears
```

**AQ-AC3 — Assign**
```gherkin
Given an agent holding tickets:write and a ticket with no assignee
When POST /v1/support/tickets/{id}/assign is called with another agent's id
Then respond 200 with assignee_id set
And an audit entry is written (event=ticket_assigned, actor=the caller, target=the ticket)
And re-assigning an already-assigned ticket replaces the assignee and audits the change
```

**AQ-AC4 — Unassign**
```gherkin
Given a ticket with an assignee
When DELETE /v1/support/tickets/{id}/assign is called by a tickets:write holder
Then respond 200 with assignee_id null
And an audit entry is written (event=ticket_unassigned)
```

**AQ-AC5 — Customer branch is unchanged**
```gherkin
Given a customer holding no tickets:* scope
When GET /v1/support/tickets is called
Then they receive only their own tickets, exactly as US-4.1 specified
And no response field exposes assignee_id
```

### Negative paths
**AQ-AC6 — Customer cannot reach the queue**
```gherkin
Given a customer holding no tickets:read
When GET /v1/support/tickets is called with assignee_id or another agent's filter
Then the filter is ignored and only their own tickets are returned — never another customer's
Because the customer branch already ignores query parameters it does not declare;
  a 422 here would let an unauthenticated-for-the-queue caller probe which agent-only
  parameters exist, and the ownership filter is what actually protects the data
```

**AQ-AC7 — Assignment requires the scope**
```gherkin
Given a caller without tickets:write
When POST or DELETE /v1/support/tickets/{id}/assign is called
Then respond 404 for a customer (never confirming the ticket id exists, consistent with TR-AC4/TC-AC7)
And 403 with type ".../errors/insufficient-permission" for a tickets:read-only agent
```

**AQ-AC8 — Assignee must be an agent**
```gherkin
Given an assign request naming a user who holds no tickets:write
When POST /v1/support/tickets/{id}/assign is called
Then respond 422 with type ".../errors/validation-failed"
Because a ticket assigned to someone who cannot act on it is an invisible dead end
```

**AQ-AC9 — Assigning a closed ticket**
```gherkin
Given a ticket in status "closed"
When POST /v1/support/tickets/{id}/assign is called
Then respond 409 with type ".../errors/invalid-state-transition"
```

**AQ-AC10 — Concurrent assignment**
```gherkin
Given two agents assigning the same unassigned ticket simultaneously
When both requests are processed
Then exactly one wins via a conditional update scoped to the expected assignee_id
And the loser receives 409, not a silent overwrite
```

## Non-Functional / Security Requirements
- The agent branch MUST NOT widen what a customer sees: the two branches share one endpoint but not one query. A missing scope must fall through to the customer branch, never to an unfiltered list.
- `assignee_id` MUST NOT appear on any customer-facing response shape (Assumption #7).
- The queue query MUST be index-backed for its default ordering and every supported filter — a sequential scan over `tickets` is not acceptable as the queue grows.
- Every assign/unassign MUST write an audit entry in the same transaction as the write.
- Removing `reject_agent_queue_access` MUST update, not delete, the US-4.1 tests that assert its 403 — the replacement assertion is the new agent branch.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| AQ-AC1–2 | Integration tests against real PostgreSQL, seeded with tickets from multiple requesters | `[gate]` |
| AQ-AC3–4 | Integration tests asserting the column write and the audit row in one transaction | `[gate]` |
| AQ-AC5–6 | Integration test asserting a customer's result set is byte-identical to US-4.1's, with and without agent-only query params | `[gate]` |
| AQ-AC7 | Integration test asserting the 404/403 split by caller kind | `[gate]` |
| AQ-AC8–9 | Integration tests for the 422 and 409 branches | `[gate]` |
| AQ-AC10 | Concurrency test: two simultaneous assigns; asserts one 200, one 409 | `[gate]` |
| Index coverage | `EXPLAIN` assertion (or migration review) that the default queue query uses the new index | `[gate]` if enforceable, otherwise `[manual]` |
| Migration | `upgrade → downgrade → upgrade` proven, per AGENTS.md §4 | `[gate]` |

## Open Questions
1. Should assigning a ticket transition its status (e.g. `open` → `waiting_on_support`)? Default assumption: **no** — assignment is orthogonal to the US-4.3 state machine.
2. Should the assignee be notified by email on assignment? Default assumption: no notification in this Story; it is an additive follow-up.
3. US-4.3 TC-AC4 says "the previously assigned agent is notified" on a customer reply reopening a ticket. That behavior was specified before an assignee column existed. Confirm whether it is now in scope for this Story or stays deferred.
4. **Story/code drift, noted not fixed:** US-4.3's normative state machine lists a `reopened` status, but the shipped code has no such value — `_REOPEN_ELIGIBLE_STATUSES` transitions a reopened ticket to `waiting_on_support`, and the five live statuses are `open`, `waiting_on_support`, `waiting_on_customer`, `resolved`, `closed`. This Story uses the shipped five. Confirm whether US-4.3's document should be corrected or the code changed — out of scope here either way, but this Story is the first to touch the module since the drift appeared.
5. Should the agent queue expose a display name alongside `assignee_id`? `support_agent` may not hold `users:read`, so a UI cannot resolve the UUID itself (raised from US-5.5 Open Questions #1).
6. `TicketRead` currently has no `assignee_id`. Confirm whether the agent branch returns an extended `TicketRead` or a distinct `AgentTicketRead` shape — the latter keeps the customer contract provably unchanged.
