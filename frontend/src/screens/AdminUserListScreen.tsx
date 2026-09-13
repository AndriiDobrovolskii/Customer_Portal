// AD-AC1/FR-1: /admin/users. q/status/role filters (status as the fixed
// invited/active/deactivated set, not free text) re-request the list and
// reset the cursor (a filter change is a queryKey change in
// useAdminUsers.ts, so TanStack Query starts the query fresh rather than
// the screen hand-rolling a cursor reset). Cursor "Load more"; no total
// count or page number anywhere. An unrecognized status/roles value renders
// verbatim (Client State Notes; Implementation Plan Risk 7) — no
// status-to-label lookup that could silently hide an unknown value.
// XC-AC1: a forced server 403 renders an explicit "not permitted" state,
// never a blank screen or infinite spinner; the "Create user" control is
// hidden without users:write. Composed from hooks/, store/ (read-only), and
// shared components/ only — never api/ or fetch directly (AGENTS.md §3).
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAdminUsers } from "../hooks/useAdminUsers";
import { useAuthStore } from "../store/authStore";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage, getErrorStatus } from "../components/apiErrorHelpers";

const STATUS_OPTIONS = ["invited", "active", "deactivated"] as const;

export function AdminUserListScreen() {
  const { scopes } = useAuthStore();
  const canCreateUsers = scopes.includes("users:write");

  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [role, setRole] = useState("");

  const usersQuery = useAdminUsers({
    q: q || undefined,
    status: status || undefined,
    role: role || undefined,
  });

  const users = useMemo(() => usersQuery.data?.pages.flatMap((page) => page.items) ?? [], [usersQuery.data]);

  const apiError = usersQuery.isError ? usersQuery.error : null;
  const errorKind = getErrorKind(apiError);
  const errorStatus = getErrorStatus(apiError);

  if (errorStatus === 403) {
    return (
      <section>
        <h1>Users</h1>
        <p role="alert">You do not have permission to view this page.</p>
      </section>
    );
  }

  return (
    <section>
      <h1>Users</h1>

      {canCreateUsers && <Link to="/admin/users/new">Create user</Link>}

      <div>
        <label htmlFor="admin-user-search">Search</label>
        <input id="admin-user-search" type="text" value={q} onChange={(event) => setQ(event.target.value)} />
      </div>
      <div>
        <label htmlFor="admin-user-status-filter">Status</label>
        <select
          id="admin-user-status-filter"
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
        <label htmlFor="admin-user-role-filter">Role</label>
        <input
          id="admin-user-role-filter"
          type="text"
          value={role}
          onChange={(event) => setRole(event.target.value)}
        />
      </div>

      {usersQuery.isPending && <p>Loading users…</p>}

      {errorKind && <ErrorState kind={errorKind} onRetry={() => usersQuery.refetch()} />}
      {apiError && !errorKind && <p role="alert">{getErrorMessage(apiError)}</p>}

      {usersQuery.isSuccess && (
        <table>
          <caption>Users</caption>
          <thead>
            <tr>
              <th scope="col">Email</th>
              <th scope="col">Display name</th>
              <th scope="col">Status</th>
              <th scope="col">Roles</th>
              <th scope="col">Created at</th>
              <th scope="col">Last login</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>
                  <Link to={`/admin/users/${user.id}`}>{user.email}</Link>
                </td>
                <td>{user.display_name}</td>
                <td>{user.status}</td>
                <td>{user.roles.length > 0 ? user.roles.join(", ") : "—"}</td>
                <td>{user.created_at}</td>
                <td>{user.last_login_at ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {usersQuery.hasNextPage && (
        <button type="button" onClick={() => usersQuery.fetchNextPage()}>
          Load more
        </button>
      )}
    </section>
  );
}
