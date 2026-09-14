// FR-3 through FR-7 (AG-AC3 through AG-AC6): the agent ticket detail screen
// at /agent/tickets/:id. Reuses useTicketDetail.ts/useReplyToTicket.ts/
// useCloseTicket.ts/useReopenTicket.ts unmodified except Architectural
// Change 2's additive `visibility` field (GET /support/tickets/{id} returns
// the same TicketDetailRead shape for both actor kinds) — Architectural
// Change 6: written as its own independent JSX tree, no shared component
// extracted with TicketDetailScreen.tsx (that file has zero diff from this
// Story).
//
// Resolution OD-3 / Architectural Change 7: the assignee display is a
// navigation-state handoff — `assigneeId` local state is undefined
// ("unknown/stale", direct-URL entry, Architectural Change 8's "—"
// placeholder), null (a genuinely unassigned ticket, "Unassigned"), or a
// string (a shortened/truncated UUID, Resolution OD-1) — and is updated
// afterward by this screen's own assign/unassign calls, never by re-reading
// TicketDetailRead (which carries no assignee_id field).
//
// Implementation Plan Risk 2: the composer's visibility control is
// re-asserted to "public" on every successful submit via
// `reset({ body: "", visibility: "public" })` — never left sticky.
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useLocation, useParams } from "react-router-dom";
import { useTicketDetail } from "../hooks/useTicketDetail";
import { useReplyToTicket, type ReplyToTicketFormValues } from "../hooks/useReplyToTicket";
import { useAssignTicket } from "../hooks/useAssignTicket";
import { useUnassignTicket } from "../hooks/useUnassignTicket";
import { useResolveTicket } from "../hooks/useResolveTicket";
import { useCloseTicket } from "../hooks/useCloseTicket";
import { useReopenTicket } from "../hooks/useReopenTicket";
import { useRetryAfterCountdown } from "../hooks/useRetryAfterCountdown";
import { useAuthStore } from "../store/authStore";
import { ErrorState } from "../components/ErrorState";
import {
  getErrorKind,
  getErrorMessage,
  getErrorStatus,
  getFieldErrors,
  getRetryAfterSeconds,
} from "../components/apiErrorHelpers";
import { FieldError } from "../components/FieldError";
import { offeredAgentActionsForStatus, describeAssignee } from "./agentTicketHelpers";

interface ResolveFormValues {
  resolution_note: string;
}

const CREATED_AT_FORMATTER = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });

function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : CREATED_AT_FORMATTER.format(date);
}

export function AgentTicketDetailScreen() {
  const { id } = useParams<{ id: string }>();
  const ticketId = id ?? "";
  const location = useLocation();
  const { scopes, user } = useAuthStore();
  const canWrite = scopes.includes("tickets:write");

  const { ticketQuery, repliesQuery } = useTicketDetail(ticketId);
  const replyMutation = useReplyToTicket(ticketId);
  const assignMutation = useAssignTicket(ticketId);
  const unassignMutation = useUnassignTicket(ticketId);
  const resolveMutation = useResolveTicket(ticketId);
  const closeMutation = useCloseTicket(ticketId);
  const reopenMutation = useReopenTicket(ticketId);

  const navigationState = location.state as { assigneeId?: string | null } | null;
  const [assigneeId, setAssigneeId] = useState<string | null | undefined>(
    navigationState && "assigneeId" in navigationState ? (navigationState.assigneeId ?? null) : undefined,
  );
  const [assignAgentInput, setAssignAgentInput] = useState("");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ReplyToTicketFormValues>({ defaultValues: { body: "", visibility: "public" } });

  async function onSubmitReply(values: ReplyToTicketFormValues) {
    try {
      await replyMutation.mutateAsync(values);
      // Implementation Plan Risk 2: the visibility control is re-asserted to
      // "public" on every successful submit — never sticky.
      reset({ body: "", visibility: "public" });
    } catch {
      // surfaced via replyMutation.error below
    }
  }

  const {
    register: registerResolve,
    handleSubmit: handleResolveSubmit,
    reset: resetResolve,
    formState: { errors: resolveErrors },
  } = useForm<ResolveFormValues>({ defaultValues: { resolution_note: "" } });

  async function onSubmitResolve(values: ResolveFormValues) {
    try {
      await resolveMutation.mutateAsync({ resolution_note: values.resolution_note });
      resetResolve({ resolution_note: "" });
    } catch {
      // surfaced via resolveMutation.error below
    }
  }

  async function handleAssignToMe() {
    if (!user?.id) {
      return;
    }
    try {
      const data = await assignMutation.mutateAsync({ assignee_id: user.id });
      setAssigneeId(data.assignee_id);
    } catch {
      // surfaced via assignMutation.error below
    }
  }

  async function handleAssignToAgent() {
    const trimmed = assignAgentInput.trim();
    if (!trimmed) {
      return;
    }
    try {
      const data = await assignMutation.mutateAsync({ assignee_id: trimmed });
      setAssigneeId(data.assignee_id);
      setAssignAgentInput("");
    } catch {
      // surfaced via assignMutation.error below
    }
  }

  async function handleUnassign() {
    try {
      const data = await unassignMutation.mutateAsync();
      setAssigneeId(data.assignee_id);
    } catch {
      // surfaced via unassignMutation.error below
    }
  }

  const replyApiError = replyMutation.isError ? replyMutation.error : null;
  const replyRetryAfterSeconds = getRetryAfterSeconds(replyApiError);
  const replyCountdown = useRetryAfterCountdown(replyRetryAfterSeconds);
  const replyErrorKind = getErrorKind(replyApiError);
  // FR-8/AG-AC7: a 422's errors[] array is mapped onto the matching form
  // field via the project's shared getFieldErrors()/FieldError mechanism
  // (NewTicketScreen.tsx's established pattern), in addition to the
  // generic top-level detail rendered below.
  const replyFieldErrors = getFieldErrors(replyApiError);

  const assignApiError = assignMutation.isError ? assignMutation.error : null;
  const assignErrorKind = getErrorKind(assignApiError);
  const assignFieldErrors = getFieldErrors(assignApiError);
  const unassignApiError = unassignMutation.isError ? unassignMutation.error : null;
  const unassignErrorKind = getErrorKind(unassignApiError);
  const resolveApiError = resolveMutation.isError ? resolveMutation.error : null;
  const resolveErrorKind = getErrorKind(resolveApiError);
  const resolveFieldErrors = getFieldErrors(resolveApiError);
  const closeApiError = closeMutation.isError ? closeMutation.error : null;
  const reopenApiError = reopenMutation.isError ? reopenMutation.error : null;

  if (ticketQuery.isPending) {
    return (
      <section>
        <h1>Ticket</h1>
        <p>Loading ticket…</p>
      </section>
    );
  }

  if (ticketQuery.isError) {
    const status = getErrorStatus(ticketQuery.error);
    if (status === 404) {
      return (
        <section>
          <h1>Ticket</h1>
          <p>This ticket could not be found.</p>
        </section>
      );
    }
    const kind = getErrorKind(ticketQuery.error);
    if (kind) {
      return (
        <section>
          <h1>Ticket</h1>
          <ErrorState kind={kind} onRetry={() => ticketQuery.refetch()} />
        </section>
      );
    }
    return (
      <section>
        <h1>Ticket</h1>
        <p role="alert">{getErrorMessage(ticketQuery.error)}</p>
      </section>
    );
  }

  const ticket = ticketQuery.data;
  const offered = offeredAgentActionsForStatus(ticket.status);
  const replies = repliesQuery.data?.pages.flatMap((page) => page.items) ?? [];
  const assigneeDescription = describeAssignee(assigneeId);

  return (
    <section>
      <h1>{ticket.ticket_number}</h1>
      <dl>
        <dt>Status</dt>
        <dd>{ticket.status}</dd>
        <dt>Category</dt>
        <dd>{ticket.category}</dd>
        <dt>Created</dt>
        <dd>{formatCreatedAt(ticket.created_at)}</dd>
        {ticket.first_response_at && (
          <>
            <dt>First response</dt>
            <dd>{ticket.first_response_at}</dd>
          </>
        )}
        <dt>Assignee</dt>
        <dd aria-label={assigneeDescription.ariaLabel}>{assigneeDescription.text}</dd>
      </dl>

      {offered.assign && (
        <div>
          <h2>Assignment</h2>
          <button
            type="button"
            disabled={!canWrite || assignMutation.isPending || !user?.id}
            onClick={handleAssignToMe}
          >
            Assign to me
          </button>
          <button
            type="button"
            disabled={!canWrite || assigneeId === null || unassignMutation.isPending}
            onClick={handleUnassign}
          >
            Unassign
          </button>
          <label htmlFor="agent-detail-assign-input">Assign to agent (UUID)</label>
          <input
            id="agent-detail-assign-input"
            type="text"
            value={assignAgentInput}
            disabled={!canWrite}
            onChange={(event) => setAssignAgentInput(event.target.value)}
          />
          <button
            type="button"
            disabled={!canWrite || assignMutation.isPending || !assignAgentInput.trim()}
            onClick={handleAssignToAgent}
          >
            Assign
          </button>
          <FieldError fieldErrors={assignFieldErrors} field="assignee_id" />
          {assignErrorKind && <ErrorState kind={assignErrorKind} onRetry={() => assignMutation.reset()} />}
          {Boolean(assignApiError) && !assignErrorKind && !assignFieldErrors && (
            <p role="alert">{getErrorMessage(assignApiError)}</p>
          )}
          {unassignErrorKind && (
            <ErrorState kind={unassignErrorKind} onRetry={() => unassignMutation.reset()} />
          )}
          {Boolean(unassignApiError) && !unassignErrorKind && (
            <p role="alert">{getErrorMessage(unassignApiError)}</p>
          )}
        </div>
      )}

      <h2>Replies</h2>
      <ul>
        {replies.map((reply) => (
          <li
            key={reply.id}
            className={reply.visibility === "internal" ? "reply reply--internal" : "reply reply--public"}
            data-visibility={reply.visibility}
          >
            {reply.visibility === "internal" && <strong className="reply-visibility-label">Internal</strong>}
            <span>{reply.author_kind}</span>
            <span>{reply.body}</span>
            <span>{reply.created_at}</span>
          </li>
        ))}
      </ul>

      {repliesQuery.hasNextPage && (
        <button type="button" onClick={() => repliesQuery.fetchNextPage()}>
          Load older replies
        </button>
      )}

      {offered.reply && (
        <form onSubmit={handleSubmit(onSubmitReply)} noValidate>
          <div>
            <label htmlFor="agent-reply-body">Reply</label>
            <textarea
              id="agent-reply-body"
              {...register("body", {
                required: "Reply is required.",
                maxLength: { value: 5000, message: "Reply must be 5000 characters or fewer." },
              })}
            />
            {errors.body && <p role="alert">{errors.body.message}</p>}
            <FieldError fieldErrors={replyFieldErrors} field="body" />
          </div>
          <fieldset>
            <legend>Visibility</legend>
            <label>
              <input
                type="radio"
                value="public"
                {...register("visibility")}
                disabled={!canWrite || replyMutation.isPending}
              />
              Public
            </label>
            <label>
              <input
                type="radio"
                value="internal"
                {...register("visibility")}
                disabled={!canWrite || replyMutation.isPending}
              />
              Internal
            </label>
          </fieldset>
          <button type="submit" disabled={!canWrite || replyMutation.isPending || replyCountdown.isBlocked}>
            Post reply
          </button>
        </form>
      )}

      {replyCountdown.isBlocked && (
        <p role="alert">You can try again in {replyCountdown.secondsRemaining} seconds.</p>
      )}
      {replyErrorKind && <ErrorState kind={replyErrorKind} onRetry={() => handleSubmit(onSubmitReply)()} />}
      {Boolean(replyApiError) && !replyErrorKind && !replyCountdown.isBlocked && !replyFieldErrors && (
        <p role="alert">{getErrorMessage(replyApiError)}</p>
      )}

      {offered.resolve && (
        <form aria-label="Resolve ticket" onSubmit={handleResolveSubmit(onSubmitResolve)} noValidate>
          <h2>Resolve</h2>
          <div>
            <label htmlFor="agent-resolve-note">Resolution note</label>
            <textarea
              id="agent-resolve-note"
              {...registerResolve("resolution_note", {
                required: "Resolution note is required.",
                maxLength: { value: 5000, message: "Resolution note must be 5000 characters or fewer." },
                validate: (value) => value.trim().length > 0 || "Resolution note is required.",
              })}
            />
            {resolveErrors.resolution_note && <p role="alert">{resolveErrors.resolution_note.message}</p>}
            <FieldError fieldErrors={resolveFieldErrors} field="resolution_note" />
          </div>
          <button type="submit" disabled={!canWrite || resolveMutation.isPending}>
            Resolve
          </button>
        </form>
      )}
      {resolveErrorKind && (
        <ErrorState kind={resolveErrorKind} onRetry={() => handleResolveSubmit(onSubmitResolve)()} />
      )}
      {Boolean(resolveApiError) && !resolveErrorKind && !resolveFieldErrors && (
        <p role="alert">{getErrorMessage(resolveApiError)}</p>
      )}

      {offered.close && (
        <button
          type="button"
          onClick={() => closeMutation.mutate()}
          disabled={!canWrite || closeMutation.isPending}
        >
          Close ticket
        </button>
      )}
      {Boolean(closeApiError) && <p role="alert">{getErrorMessage(closeApiError)}</p>}

      {offered.reopen && (
        <button
          type="button"
          onClick={() => reopenMutation.mutate()}
          disabled={!canWrite || reopenMutation.isPending}
        >
          Reopen
        </button>
      )}
      {Boolean(reopenApiError) && <p role="alert">{getErrorMessage(reopenApiError)}</p>}
    </section>
  );
}
