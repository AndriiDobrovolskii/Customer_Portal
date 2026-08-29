# Epic 2 — Authentication: Active Session Management

**Story ID:** US-2.6
**Project:** Customer Portal

## User Story
As an authenticated user,
I want to see every device currently signed in to my account and sign any of them out individually,
So that I can spot and cut off access I do not recognise without logging myself out everywhere.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Session identity | The refresh-token `family_id` from US-2.3 | A family *is* a session; no second concept is needed |
| 2 | Location display | Coarsened to city/country | Street-level precision serves no purpose here |
| 3 | Metadata retention | Purged 90 days after the session ends | Its only purpose is device recognition; the 400-day audit window would be disproportionate |
| 4 | Live-session cap | 20 families per user, oldest evicted | Bounds both the UI and the store |
| 5 | Revocation of another user's family | 404, not 403 | A 403 would confirm the family_id exists |

## In Scope
- `GET /v1/auth/sessions` — list live sessions with recognisable metadata
- `DELETE /v1/auth/sessions/{family_id}` — revoke one session
- Capture and update of session metadata during rotation

## Out of Scope
- Logout of the current session and logout-everywhere (US-2.2)
- Admin-facing visibility into another user's sessions (not currently required; would need its own permission and audit story)

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| GET | `/v1/auth/sessions` | Required (self) | none | 200 `{"sessions": [...]}` |
| DELETE | `/v1/auth/sessions/{family_id}` | Required (self) | none | 204 |

## Data Model Notes
- Adds `ip`, `user_agent`, `last_used_at`, `revoked_at` to the refresh-token **family** row introduced in US-2.3 — this story adds columns, not a new store
- `auth_audit_log` `event=session_revoked` with `target_family`

## Acceptance Criteria

### Happy path
**SM-AC1 — Listing sessions**
```gherkin
Given an authenticated user with three live refresh-token families
When GET /v1/auth/sessions is called
Then respond 200 with one entry per family: family_id, created_at, last_used_at,
    approximate location (city/country from IP), a parsed device/browser label, and is_current
And exactly one entry is flagged is_current, matching the caller's own family
And no token value, hash or full IP address is returned
```

**SM-AC2 — Revoking one session**
```gherkin
Given an authenticated user and a family_id belonging to another of their devices
When DELETE /v1/auth/sessions/{family_id} is called
Then respond 204 and every token in that family is revoked (as in US-2.2 LO-AC1)
And the caller's own session is unaffected
And an auth_audit_log entry is written (event=session_revoked, target_family=…)
```

### Negative paths
**SM-AC3 — Another user's session**
```gherkin
Given a family_id that belongs to a different user
When DELETE /v1/auth/sessions/{family_id} is called
Then respond 404 with type ".../errors/not-found"
Because 403 would confirm that the family_id exists
```

**SM-AC4 — Already-revoked or unknown family**
```gherkin
Given a family_id that is already revoked or has expired
When DELETE /v1/auth/sessions/{family_id} is called
Then respond 204 — the operation is idempotent, mirroring LO-AC4
```

**SM-AC5 — Not authenticated**
```gherkin
Given a request with no valid access token
When GET /v1/auth/sessions is called
Then respond 401 and no session metadata is disclosed
```

## Error Envelope (RFC 7807 `application/problem+json`)
Error `type` slugs used by this story: `not-found` (shared).

## Non-Functional / Security Requirements
- IP and user-agent are personal data: document them in the privacy notice, display the location coarsened, and purge session metadata 90 days after the session ends.
- Revoking a session MUST reuse US-2.2's revocation path, so exactly one code path ends a session.
- `last_used_at` SHOULD be written asynchronously, or throttled to once per minute, to keep the refresh path fast.
- **Performance:** p95 ≤ 200 ms; sessions per user are bounded at 20 live families.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| SM-AC1 | Integration test asserting `is_current` and the absence of token material | `[gate]` |
| SM-AC2 | Integration test asserting the caller's own session survives | `[gate]` |
| SM-AC3–5 | Integration test suite | `[gate]` |
| 90-day purge | Unit test on the purge job; scheduled execution verified in staging | `[manual]` |

## Open Questions
None.