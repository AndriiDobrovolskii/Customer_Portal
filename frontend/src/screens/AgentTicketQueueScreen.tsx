// FR-1, FR-2 (AG-AC1, AG-AC2): the agent queue at /agent/tickets. Renders
// every non-closed ticket (ticket_number, subject, category, status,
// assignee, updated_at), oldest-updated first (server-ordered — this screen
// applies no client-side sort). status/category/assignee_id filters each
// re-issue the request and reset the cursor by changing useAgentTickets'
// own query key. assignee_id=me/none are one-click, mutually-exclusive
// presets; a raw-UUID "specific agent" text input is a third, independent
// way to populate the same single assignee_id value (Resolution OD-2) — the
// preset and the free-text input clear one another so only one is ever
// live. Per-row Assign-to-me / Unassign / Assign-to-another-agent controls
// live on AgentQueueRow, a small local subcomponent so each row can call
// useAssignTicket(ticket.id)/useUnassignTicket(ticket.id) as its own hook
// instance (React's Rules of Hooks: one call per component instance, safe
// to multiply across a keyed list). Composed from hooks/, store/
// (read-only), and shared components/ only — never api/ or fetch directly
// (AGENTS.md §3).
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAgentTickets } from "../hooks/useAgentTickets";
import { useAssignTicket } from "../hooks/useAssignTicket";
import { useUnassignTicket } from "../hooks/useUnassignTicket";
import { useAuthStore } from "../store/authStore";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage, getFieldErrors } from "../components/apiErrorHelpers";
import { FieldError } from "../components/FieldError";
import { formatAssigneeId } from "./agentTicketHelpers";
import type { AgentTicketRead } from "../api/types";

const STATUS_OPTIONS = ["open", "waiting_on_support", "waiting_on_customer", "resolved"];

interface AgentQueueRowProps {
  ticket: AgentTicketRead;
  canWrite: boolean;
  currentUserId: string | undefined;
  onOpen: (ticket: AgentTicketRead) => void;
}

function AgentQueueRow({ ticket, canWrite, currentUserId, onOpen }: AgentQueueRowProps) {
  const [assigneeInput, setAssigneeInput] = useState("");
  const assignMutation = useAssignTicket(ticket.id);
  const unassignMutation = useUnassignTicket(ticket.id);

  const assignError = assignMutation.isError ? assignMutation.error : null;
  const unassignError = unassignMutation.isError ? unassignMutation.error : null;
  // FR-8/AG-AC7: a 422's errors[] array is mapped onto the assign-to-agent
  // UUID field via the project's shared getFieldErrors()/FieldError
  // mechanism (NewTicketScreen.tsx's established pattern), in addition to
  // the generic top-level detail rendered below.
  const assignFieldErrors = getFieldErrors(assignError);

  function handleAssignToMe() {
    if (!currentUserId) {
      return;
    }
    assignMutation.mutate({ assignee_id: currentUserId });
  }

  function handleAssignToAgent() {
    const trimmed = assigneeInput.trim();
    if (!trimmed) {
      return;
    }
    assignMutation.mutate({ assignee_id: trimmed }, { onSuccess: () => setAssigneeInput("") });
  }

  return (
    <tr>
      <td>
        <button type="button" onClick={() => onOpen(ticket)}>
          {ticket.ticket_number}
        </button>
      </td>
      <td>{ticket.subject}</td>
      <td>{ticket.category}</td>
      <td>{ticket.status}</td>
      <td>
        {ticket.assignee_id === null ? (
          formatAssigneeId(ticket.assignee_id)
        ) : (
          <span title={ticket.assignee_id}>{formatAssigneeId(ticket.assignee_id)}</span>
        )}
      </td>
      <td>{ticket.updated_at}</td>
      <td>
        <button
          type="button"
          disabled={!canWrite || assignMutation.isPending || !currentUserId}
          onClick={handleAssignToMe}
        >
          Assign to me
        </button>
        <button
          type="button"
          disabled={!canWrite || ticket.assignee_id === null || unassignMutation.isPending}
          onClick={() => unassignMutation.mutate()}
        >
          Unassign
        </button>
        <label htmlFor={`assign-to-agent-${ticket.id}`}>Assign to agent (UUID)</label>
        <input
          id={`assign-to-agent-${ticket.id}`}
          type="text"
          value={assigneeInput}
          disabled={!canWrite}
          onChange={(event) => setAssigneeInput(event.target.value)}
        />
        <button
          type="button"
          disabled={!canWrite || assignMutation.isPending || !assigneeInput.trim()}
          onClick={handleAssignToAgent}
        >
          Assign
        </button>
        <FieldError fieldErrors={assignFieldErrors} field="assignee_id" />
        {Boolean(assignError) && !assignFieldErrors && <p role="alert">{getErrorMessage(assignError)}</p>}
        {Boolean(unassignError) && <p role="alert">{getErrorMessage(unassignError)}</p>}
      </td>
    </tr>
  );
}

export function AgentTicketQueueScreen() {
  const navigate = useNavigate();
  const { scopes, user } = useAuthStore();
  const canWrite = scopes.includes("tickets:write");

  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [assigneePreset, setAssigneePreset] = useState<"" | "me" | "none">("");
  const [assigneeIdInput, setAssigneeIdInput] = useState("");

  const assigneeId = assigneePreset || assigneeIdInput.trim() || undefined;

  const ticketsQuery = useAgentTickets({
    status: status || undefined,
    category: category || undefined,
    assigneeId,
  });

  const tickets = useMemo(
    () => ticketsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [ticketsQuery.data],
  );

  const apiError = ticketsQuery.isError ? ticketsQuery.error : null;
  const errorKind = getErrorKind(apiError);
  // FR-8/AG-AC7: a 422's errors[] array (e.g. the "specific agent" raw-UUID
  // filter) is mapped onto its matching field, not just rendered generically.
  const fieldErrors = getFieldErrors(apiError);

  function togglePreset(preset: "me" | "none") {
    setAssigneePreset((current) => (current === preset ? "" : preset));
    setAssigneeIdInput("");
  }

  function handleAssigneeIdInputChange(value: string) {
    setAssigneeIdInput(value);
    setAssigneePreset("");
  }

  function handleOpenTicket(ticket: AgentTicketRead) {
    navigate(`/agent/tickets/${ticket.id}`, { state: { assigneeId: ticket.assignee_id } });
  }

  return (
    <section>
      <h1>Agent queue</h1>

      <div>
        <label htmlFor="agent-queue-status-filter">Status</label>
        <select
          id="agent-queue-status-filter"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="">All</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="agent-queue-category-filter">Category</label>
        <input
          id="agent-queue-category-filter"
          type="text"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        />
      </div>

      <div>
        <span id="agent-queue-assignee-filter-label">Assignee</span>
        <button type="button" aria-pressed={assigneePreset === "me"} onClick={() => togglePreset("me")}>
          Assigned to me
        </button>
        <button type="button" aria-pressed={assigneePreset === "none"} onClick={() => togglePreset("none")}>
          No assignee
        </button>
        <label htmlFor="agent-queue-assignee-id-filter">Specific agent (UUID)</label>
        <input
          id="agent-queue-assignee-id-filter"
          type="text"
          value={assigneeIdInput}
          onChange={(event) => handleAssigneeIdInputChange(event.target.value)}
        />
        <FieldError fieldErrors={fieldErrors} field="assignee_id" />
      </div>

      {ticketsQuery.isPending && <p>Loading tickets…</p>}

      {errorKind && <ErrorState kind={errorKind} onRetry={() => ticketsQuery.refetch()} />}
      {apiError && !errorKind && !fieldErrors && <p role="alert">{getErrorMessage(apiError)}</p>}

      {ticketsQuery.isSuccess && tickets.length === 0 && <p>No tickets match these filters.</p>}

      {ticketsQuery.isSuccess && tickets.length > 0 && (
        <table>
          <caption>Agent queue</caption>
          <thead>
            <tr>
              <th scope="col">Ticket number</th>
              <th scope="col">Subject</th>
              <th scope="col">Category</th>
              <th scope="col">Status</th>
              <th scope="col">Assignee</th>
              <th scope="col">Updated</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((ticket) => (
              <AgentQueueRow
                key={ticket.id}
                ticket={ticket}
                canWrite={canWrite}
                currentUserId={user?.id}
                onOpen={handleOpenTicket}
              />
            ))}
          </tbody>
        </table>
      )}

      {ticketsQuery.hasNextPage && (
        <button type="button" onClick={() => ticketsQuery.fetchNextPage()}>
          Load more
        </button>
      )}
    </section>
  );
}
