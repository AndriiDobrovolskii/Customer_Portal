// FR-5 through FR-10 (TK-AC5-TK-AC9, TK-AC11, TK-AC12, TK-AC13), OD-3/OD-4.
// `offeredActionsForStatus` is a pure, exported function (test-strategy item
// 10) implementing FR-9's table exactly: `resolved` -> all three, `closed`
// -> none, every other listed status -> reply+close only, any unrecognized
// status defaults to no actions offered (fail closed). It never has a
// `resolve` key at all — FR-9's "never offered to a customer under any
// status" is a structural guarantee, not a runtime check.
import { useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { useTicketDetail } from "../hooks/useTicketDetail";
import { useReplyToTicket, type ReplyToTicketFormValues } from "../hooks/useReplyToTicket";
import { useCloseTicket } from "../hooks/useCloseTicket";
import { useReopenTicket } from "../hooks/useReopenTicket";
import { useRetryAfterCountdown } from "../hooks/useRetryAfterCountdown";
import { ErrorState } from "../components/ErrorState";
import {
  getErrorKind,
  getErrorMessage,
  getErrorStatus,
  getRetryAfterSeconds,
} from "../components/apiErrorHelpers";

export interface OfferedActions {
  reply: boolean;
  close: boolean;
  reopen: boolean;
}

const REPLY_AND_CLOSE_STATUSES = new Set(["open", "waiting_on_support", "waiting_on_customer"]);

// The "Created" header field is rendered in a distinct, human-readable
// format (never the raw ISO string) so it can never collide, in the DOM's
// flat text-search space, with `first_response_at`'s or a reply's own raw
// ISO `created_at` timestamp when both happen to fall on the same calendar
// day (OD-4: `first_response_at` itself stays a plain, unstyled raw
// timestamp — this formatting choice is scoped to "Created" only).
const CREATED_AT_FORMATTER = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });

function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : CREATED_AT_FORMATTER.format(date);
}

export function offeredActionsForStatus(status: string): OfferedActions {
  if (status === "resolved") {
    return { reply: true, close: true, reopen: true };
  }
  if (REPLY_AND_CLOSE_STATUSES.has(status)) {
    return { reply: true, close: true, reopen: false };
  }
  // Includes "closed" and any unrecognized status — fail closed.
  return { reply: false, close: false, reopen: false };
}

export function TicketDetailScreen() {
  const { id } = useParams<{ id: string }>();
  const ticketId = id ?? "";
  const { ticketQuery, repliesQuery } = useTicketDetail(ticketId);
  const replyMutation = useReplyToTicket(ticketId);
  const closeMutation = useCloseTicket(ticketId);
  const reopenMutation = useReopenTicket(ticketId);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ReplyToTicketFormValues>();

  async function onSubmitReply(values: ReplyToTicketFormValues) {
    try {
      await replyMutation.mutateAsync(values);
      reset({ body: "" });
    } catch {
      // surfaced via replyMutation.error below
    }
  }

  const replyApiError = replyMutation.isError ? replyMutation.error : null;
  const replyRetryAfterSeconds = getRetryAfterSeconds(replyApiError);
  const replyCountdown = useRetryAfterCountdown(replyRetryAfterSeconds);
  const replyErrorKind = getErrorKind(replyApiError);

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
  const offered = offeredActionsForStatus(ticket.status);
  const replies = repliesQuery.data?.pages.flatMap((page) => page.items) ?? [];

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
      </dl>

      <h2>Replies</h2>
      <ul>
        {replies.map((reply) => (
          <li key={reply.id}>
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
            <label htmlFor="ticket-reply-body">Reply</label>
            <textarea
              id="ticket-reply-body"
              {...register("body", {
                required: "Reply is required.",
                maxLength: { value: 5000, message: "Reply must be 5000 characters or fewer." },
              })}
            />
            {errors.body && <p role="alert">{errors.body.message}</p>}
          </div>
          <button type="submit" disabled={replyMutation.isPending || replyCountdown.isBlocked}>
            Post reply
          </button>
        </form>
      )}

      {replyCountdown.isBlocked && (
        <p role="alert">You can try again in {replyCountdown.secondsRemaining} seconds.</p>
      )}
      {replyErrorKind && <ErrorState kind={replyErrorKind} onRetry={() => handleSubmit(onSubmitReply)()} />}
      {Boolean(replyApiError) && !replyErrorKind && !replyCountdown.isBlocked && (
        <p role="alert">{getErrorMessage(replyApiError)}</p>
      )}

      {offered.close && (
        <button type="button" onClick={() => closeMutation.mutate()} disabled={closeMutation.isPending}>
          Close ticket
        </button>
      )}

      {offered.reopen && (
        <button type="button" onClick={() => reopenMutation.mutate()} disabled={reopenMutation.isPending}>
          Reopen
        </button>
      )}
      {Boolean(reopenApiError) && <p role="alert">{getErrorMessage(reopenApiError)}</p>}
    </section>
  );
}
