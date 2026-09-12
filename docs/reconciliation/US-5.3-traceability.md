---
artifact_type: traceability
story: US-5.3
version: 1
status: DRAFT
created_at: "2026-09-12T01:05:00Z"
updated_at: "2026-09-12T01:05:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/reviews/designs/US-5.3-design-review.md
    version: 1
  - path: docs/tests/US-5.3-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.3-implementation-report.md
    version: 2
  - path: docs/verification/US-5.3-implementation-verification.md
    version: 1
supersedes: null
---

# Traceability: Support Tickets — Frontend (US-5.3)

End-to-end AC → specification → design → test → code mapping. Design is
`NOT_APPLICABLE` for every row: this story is frontend-only and makes no API/DB change
(`API_DESIGN`/`DB_DESIGN` both `NOT_APPLICABLE`; `design_review` recorded `NOT_APPLICABLE`
for the same reason — all six endpoints this story consumes were already contracted by
US-4.1–US-4.4).

| AC ID | Spec FR | Design | Test File(s) | Source Code |
|---|---|---|---|---|
| TK-AC1 | FR-1 | NOT_APPLICABLE | `screens/TicketListScreen.test.tsx`, `hooks/useTickets.test.ts` | `frontend/src/screens/TicketListScreen.tsx`, `frontend/src/hooks/useTickets.ts`, `frontend/src/api/supportApi.ts` |
| TK-AC2 | FR-2 | NOT_APPLICABLE | `screens/TicketListScreen.test.tsx`, `hooks/useTickets.test.ts` | `frontend/src/screens/TicketListScreen.tsx`, `frontend/src/hooks/useTickets.ts` |
| TK-AC3 | FR-3 | NOT_APPLICABLE | `screens/NewTicketScreen.test.tsx`, `hooks/useCreateTicket.test.ts` | `frontend/src/screens/NewTicketScreen.tsx`, `frontend/src/hooks/useCreateTicket.ts`, `frontend/src/api/supportApi.ts`, `frontend/src/api/httpClient.ts` (Idempotency-Key option) |
| TK-AC4 | FR-4 (OD-6's resolution) | NOT_APPLICABLE | `screens/NewTicketScreen.test.tsx`, `hooks/useCreateTicket.test.ts` | `frontend/src/hooks/useCreateTicket.ts` |
| TK-AC5 | FR-5 | NOT_APPLICABLE | `screens/TicketDetailScreen.test.tsx`, `hooks/useTicketDetail.test.ts` | `frontend/src/screens/TicketDetailScreen.tsx`, `frontend/src/hooks/useTicketDetail.ts` |
| TK-AC6 | FR-6 | NOT_APPLICABLE | `screens/TicketDetailScreen.test.tsx`, `hooks/useReplyToTicket.test.ts` | `frontend/src/screens/TicketDetailScreen.tsx`, `frontend/src/hooks/useReplyToTicket.ts` |
| TK-AC7 | FR-7 | NOT_APPLICABLE | `screens/TicketDetailScreen.test.tsx`, `hooks/useCloseTicket.test.ts` | `frontend/src/screens/TicketDetailScreen.tsx`, `frontend/src/hooks/useCloseTicket.ts` |
| TK-AC8 | FR-8 (OD-3's resolution) | NOT_APPLICABLE | `screens/TicketDetailScreen.test.tsx`, `hooks/useReopenTicket.test.ts` | `frontend/src/screens/TicketDetailScreen.tsx`, `frontend/src/hooks/useReopenTicket.ts` |
| TK-AC9 | FR-9 | NOT_APPLICABLE | `screens/TicketDetailScreen.test.tsx` (unit + integration) | `frontend/src/screens/TicketDetailScreen.tsx` (`offeredActionsForStatus`) |
| TK-AC10 | FR-10 | NOT_APPLICABLE | `screens/NewTicketScreen.test.tsx` | `frontend/src/screens/NewTicketScreen.tsx` |
| TK-AC11 | FR-11 | NOT_APPLICABLE | `screens/TicketListScreen.test.tsx`, `screens/NewTicketScreen.test.tsx`, `screens/TicketDetailScreen.test.tsx` | `frontend/src/components/apiErrorHelpers.ts`, `frontend/src/components/ErrorState.tsx` (reused, unmodified) |
| TK-AC12 | FR-12 (OD-1's resolution) | NOT_APPLICABLE | `screens/NewTicketScreen.test.tsx`, `screens/TicketDetailScreen.test.tsx`, `api/httpClient.test.ts`, `components/apiErrorHelpers.test.ts`, `hooks/useRetryAfterCountdown.test.ts` | `frontend/src/api/httpClient.ts` (`ApiError.retryAfterSeconds`), `frontend/src/components/apiErrorHelpers.ts` (`getRetryAfterSeconds`), `frontend/src/hooks/useRetryAfterCountdown.ts` |
| TK-AC13 | FR-13 | NOT_APPLICABLE | `screens/TicketListScreen.test.tsx`, `screens/NewTicketScreen.test.tsx`, `screens/TicketDetailScreen.test.tsx` | Shared `ErrorState`/`apiErrorHelpers` path (reused, unmodified) |
| TK-AC14 | FR-14 | NOT_APPLICABLE | `screens/TicketListScreen.test.tsx`, `screens/NewTicketScreen.test.tsx` | US-5.1's existing refresh coordinator (`api/httpClient.ts`, unmodified by this story) |
| FR-15 (not a numbered TK-AC) | FR-15 | NOT_APPLICABLE | `routes/AppRoutes.test.tsx`, `routes/GuestOnlyRoute.test.tsx`, `screens/LoginScreen.test.tsx`, `screens/MfaVerifyScreen.test.tsx`, `layouts/AppShell.test.tsx` | `frontend/src/routes/AppRoutes.tsx`, `frontend/src/routes/GuestOnlyRoute.tsx`, `frontend/src/screens/LoginScreen.tsx`, `frontend/src/screens/MfaVerifyScreen.tsx`, `frontend/src/layouts/AppShell.tsx`; deleted: `frontend/src/screens/PlaceholderHomeScreen.tsx` |
