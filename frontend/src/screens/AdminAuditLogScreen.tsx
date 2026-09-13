// AD-AC8/FR-8: /admin/audit-logs. Renders all nine AuditLogEntry columns; a
// nullable column shows an explicit placeholder, never an empty cell.
// Resolution OD-1: the From/To date-picker inputs are visibly pre-filled
// with useAuditLogs.ts's computed last-7-days default on first render (not
// applied silently). Resolution OD-2: `event` is a plain free-text input
// with an illustrative placeholder, never a <select>/combobox. Filters
// (including the literal `from` parameter name, enforced by adminApi.ts)
// are sent as query parameters. Cursor "Load more"; no total count or page
// number anywhere. Each row's key is synthesized (occurred_at + request_id
// + index) since AuditLogEntry has no `id` and rows accumulate across
// "Load more" pages. Never writes a row's ip/user_agent/request_id to the
// console. Composed from hooks/, store/ (read-only), and shared
// components/ only — never api/ or fetch directly (AGENTS.md §3).
import { useMemo, useState } from "react";
import { useAuditLogs } from "../hooks/useAuditLogs";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage, getErrorStatus } from "../components/apiErrorHelpers";
import type { AuditLogEntry } from "../api/types";

const PLACEHOLDER = "—";

function cell(value: string | null): string {
  return value ?? PLACEHOLDER;
}

export function AdminAuditLogScreen() {
  const [actorId, setActorId] = useState("");
  const [event, setEvent] = useState("");
  const [targetId, setTargetId] = useState("");
  const [from, setFrom] = useState<string | undefined>(undefined);
  const [to, setTo] = useState<string | undefined>(undefined);

  const {
    query: auditQuery,
    defaultFrom,
    defaultTo,
  } = useAuditLogs({
    actor_id: actorId || undefined,
    event: event || undefined,
    target_id: targetId || undefined,
    from,
    to,
  });

  // Resolution OD-1: displayed (and sent) as the computed default until the
  // admin explicitly edits either bound — pre-filled visibly, not applied
  // silently behind the scenes.
  const displayedFrom = from ?? defaultFrom;
  const displayedTo = to ?? defaultTo;

  const entries: AuditLogEntry[] = useMemo(
    () => auditQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [auditQuery.data],
  );

  const apiError = auditQuery.isError ? auditQuery.error : null;
  const errorKind = getErrorKind(apiError);
  const errorStatus = getErrorStatus(apiError);

  if (errorStatus === 403) {
    return (
      <section>
        <h1>Audit log</h1>
        <p role="alert">You do not have permission to view this page.</p>
      </section>
    );
  }

  return (
    <section>
      <h1>Audit log</h1>

      <div>
        <label htmlFor="audit-log-actor-id">Actor ID</label>
        <input
          id="audit-log-actor-id"
          type="text"
          value={actorId}
          onChange={(e) => setActorId(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor="audit-log-event">Event</label>
        <input
          id="audit-log-event"
          type="text"
          placeholder="e.g. user_created, authz_denied"
          value={event}
          onChange={(e) => setEvent(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor="audit-log-target-id">Target ID</label>
        <input
          id="audit-log-target-id"
          type="text"
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor="audit-log-from">From</label>
        <input
          id="audit-log-from"
          type="text"
          value={displayedFrom}
          onChange={(e) => setFrom(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor="audit-log-to">To</label>
        <input id="audit-log-to" type="text" value={displayedTo} onChange={(e) => setTo(e.target.value)} />
      </div>

      {auditQuery.isPending && <p>Loading audit log…</p>}

      {errorKind && <ErrorState kind={errorKind} onRetry={() => auditQuery.refetch()} />}
      {apiError && !errorKind && <p role="alert">{getErrorMessage(apiError)}</p>}

      {auditQuery.isSuccess && (
        <div style={{ overflowX: "auto" }}>
          <table>
            <caption>Audit log</caption>
            <thead>
              <tr>
                <th scope="col">Occurred at</th>
                <th scope="col">Actor ID</th>
                <th scope="col">Actor role</th>
                <th scope="col">Event</th>
                <th scope="col">Target ID</th>
                <th scope="col">Outcome</th>
                <th scope="col">Request ID</th>
                <th scope="col">IP</th>
                <th scope="col">User agent</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, index) => (
                <tr key={`${entry.occurred_at}-${entry.request_id ?? "none"}-${index}`}>
                  <td>{entry.occurred_at}</td>
                  <td>{cell(entry.actor_id)}</td>
                  <td>{cell(entry.actor_role)}</td>
                  <td>{entry.event}</td>
                  <td>{cell(entry.target_id)}</td>
                  <td>{cell(entry.outcome)}</td>
                  <td>{cell(entry.request_id)}</td>
                  <td>{cell(entry.ip)}</td>
                  <td>{cell(entry.user_agent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {auditQuery.hasNextPage && (
        <button type="button" onClick={() => auditQuery.fetchNextPage()}>
          Load more
        </button>
      )}
    </section>
  );
}
