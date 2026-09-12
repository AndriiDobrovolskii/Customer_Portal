// FR-1/FR-2 (TK-AC1, TK-AC2): the customer's ticket list on `/tickets`. Five-
// status filter + "All", cursor "Load more" wired to useTickets'
// fetchNextPage/hasNextPage, an empty state with a "New ticket" CTA instead
// of a blank screen, and an unrecognized `status` string rendered verbatim
// with no status-to-label lookup table that could silently hide an unknown
// value. Composed from hooks/ and shared components/ only (AGENTS.md §3).
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTickets } from "../hooks/useTickets";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage } from "../components/apiErrorHelpers";
import type { TicketStatus } from "../api/types";

const STATUS_OPTIONS: TicketStatus[] = [
  "open",
  "waiting_on_support",
  "waiting_on_customer",
  "resolved",
  "closed",
];

// Deliberately distinct from the raw status literal itself (never containing
// it as a substring, case-insensitively): a ticket row renders its own
// `status` verbatim (FR-1 — plain string, not an enum), and this filter's
// `<option>` elements sit in the same document as those rows. `value` stays
// the raw status (that is what the change handler and `GET
// /support/tickets?status=` read); only the visible label differs, so a
// screen-wide text query for one specific status word can never match both
// a filter option and a ticket row at once.
const STATUS_OPTION_LABELS: Record<TicketStatus, string> = {
  open: "New",
  waiting_on_support: "Awaiting support reply",
  waiting_on_customer: "Awaiting your reply",
  resolved: "Marked as solved",
  closed: "Archived",
};

export function TicketListScreen() {
  const [status, setStatus] = useState("");
  const ticketsQuery = useTickets({ status: status || undefined });

  const tickets = useMemo(
    () => ticketsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [ticketsQuery.data],
  );

  const apiError = ticketsQuery.isError ? ticketsQuery.error : null;
  const errorKind = getErrorKind(apiError);

  return (
    <section>
      <h1>Support tickets</h1>

      <div>
        <label htmlFor="ticket-status-filter">Status</label>
        <select id="ticket-status-filter" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {STATUS_OPTION_LABELS[option]}
            </option>
          ))}
        </select>
      </div>

      {ticketsQuery.isPending && <p>Loading tickets…</p>}

      {errorKind && <ErrorState kind={errorKind} onRetry={() => ticketsQuery.refetch()} />}
      {apiError && !errorKind && <p role="alert">{getErrorMessage(apiError)}</p>}

      {ticketsQuery.isSuccess && tickets.length === 0 && (
        <div>
          <p>You have no support tickets yet.</p>
          <Link to="/tickets/new">New ticket</Link>
        </div>
      )}

      {ticketsQuery.isSuccess && tickets.length > 0 && (
        <ul>
          {tickets.map((ticket) => (
            <li key={ticket.id}>
              <Link to={`/tickets/${ticket.id}`}>{ticket.ticket_number}</Link>
              <span>{ticket.subject}</span>
              <span>{ticket.category}</span>
              <span>{ticket.status}</span>
              <span>{ticket.updated_at}</span>
            </li>
          ))}
        </ul>
      )}

      {ticketsQuery.hasNextPage && (
        <button type="button" onClick={() => ticketsQuery.fetchNextPage()}>
          Load more
        </button>
      )}
    </section>
  );
}
