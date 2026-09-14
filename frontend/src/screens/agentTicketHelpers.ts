// Pure, non-component helpers shared by AgentTicketQueueScreen.tsx and
// AgentTicketDetailScreen.tsx. Extracted out of those screen files (rather
// than co-located as named exports alongside the components, as
// TicketDetailScreen.tsx's precedented `offeredActionsForStatus` is) so that
// `react-refresh/only-export-components` has nothing to flag: each screen
// file now exports only its component. No JSX, no React import, no
// `api/`/`fetch` — safe to import from either screen or their tests.

export interface OfferedAgentActions {
  reply: boolean;
  assign: boolean;
  resolve: boolean;
  close: boolean;
  reopen: boolean;
}

const RESOLVE_ELIGIBLE_STATUSES = new Set(["open", "waiting_on_support", "waiting_on_customer"]);

// FR-6's status table verbatim: open/waiting_on_support/waiting_on_customer
// -> reply, assign, resolve, close; resolved -> reply, assign, close,
// reopen; closed (and any unrecognized status, fail closed) -> none.
export function offeredAgentActionsForStatus(status: string): OfferedAgentActions {
  if (status === "resolved") {
    return { reply: true, assign: true, resolve: false, close: true, reopen: true };
  }
  if (RESOLVE_ELIGIBLE_STATUSES.has(status)) {
    return { reply: true, assign: true, resolve: true, close: true, reopen: false };
  }
  return { reply: false, assign: false, resolve: false, close: false, reopen: false };
}

// Resolution OD-1 / Architectural Change 8: three distinct facts that a
// shared blank/dash would conflate — never guessed, never collapsed.
export function describeAssignee(assigneeId: string | null | undefined): {
  text: string;
  ariaLabel?: string;
} {
  if (assigneeId === undefined) {
    return { text: "—", ariaLabel: "Assignee unknown" };
  }
  if (assigneeId === null) {
    return { text: "Unassigned" };
  }
  return { text: assigneeId.slice(0, 8) };
}

// Resolution OD-1: a shortened/truncated UUID, no name-resolution call.
// This plan's own concrete choice: the first 8 hex characters.
export function formatAssigneeId(assigneeId: string | null): string {
  if (assigneeId === null) {
    // Architectural Change 8: a genuinely unassigned ticket, distinct from
    // the detail screen's separate "unknown/stale" "—" placeholder.
    return "Unassigned";
  }
  return assigneeId.slice(0, 8);
}
