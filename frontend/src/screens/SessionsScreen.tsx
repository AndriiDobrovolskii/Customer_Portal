// FR-6: list + revoke (FE-AC6, FE-AC11). OD-6 default (docs/decisions/US-5.1-open-decisions.md,
// still OPEN; recorded default per docs/tests/US-5.1-test-strategy.md): the
// current session's row disables its revoke control rather than letting the
// backend's 409 CurrentSessionError surface.
import { useSessions } from "../hooks/useSessions";
import { useRevokeSession } from "../hooks/useRevokeSession";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind } from "../components/apiErrorHelpers";

function formatLastUsed(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  return Number.isNaN(date.getTime()) ? isoTimestamp : date.toLocaleString();
}

export function SessionsScreen() {
  const sessionsQuery = useSessions();
  const revokeMutation = useRevokeSession();

  if (sessionsQuery.isPending) {
    return (
      <section>
        <h1>Active sessions</h1>
        <p>Loading sessions…</p>
      </section>
    );
  }

  if (sessionsQuery.isError) {
    const kind = getErrorKind(sessionsQuery.error) ?? "server";
    return (
      <section>
        <h1>Active sessions</h1>
        <ErrorState kind={kind} onRetry={() => sessionsQuery.refetch()} />
      </section>
    );
  }

  return (
    <section>
      <h1>Active sessions</h1>
      <ul>
        {sessionsQuery.data.sessions.map((session) => (
          <li key={session.family_id} role="listitem">
            <span>{session.device_label}</span>
            {session.location && <span>{session.location}</span>}
            <span>{formatLastUsed(session.last_used_at)}</span>
            {session.is_current && <span>Current session</span>}
            <button
              type="button"
              disabled={session.is_current}
              onClick={() => revokeMutation.mutate(session.family_id)}
            >
              {`Revoke ${session.device_label}`}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
