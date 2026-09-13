// One typed function per backend operation this Story's spec API Contract
// table names (docs/specifications/US-5.4-spec.md). Each translates a
// non-2xx response into a typed `ApiError` (via httpClient) the caller can
// branch on. No React, no TanStack Query, no store import — `api/` layer
// only (AGENTS.md §3).
//
// AD-AC7: no `deleteUser`/`DELETE /admin/users/{id}` function exists
// anywhere in this file — the backend returns 405 for every caller by
// design (story Assumption #6); this omission is enforced by
// `adminApi.test.ts`'s structural backstop.
import { httpGet, httpGetWithMeta, httpPatch, httpPost, httpPut, type HttpResult } from "./httpClient";
import type {
  AdminUserListResponse,
  AdminUserRead,
  AuditLogListResponse,
  CreateAdminUserRequest,
  DeactivateUserRequest,
  ReplaceUserRolesRequest,
  ReplaceUserRolesResponse,
  ResendInviteResponse,
  RoleListResponse,
  UpdateAdminUserRequest,
} from "./types";

export function listUsers(params: {
  q?: string;
  status?: string;
  role?: string;
  cursor?: string;
  limit?: number;
}): Promise<AdminUserListResponse> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.status) query.set("status", params.status);
  if (params.role) query.set("role", params.role);
  if (params.cursor) query.set("cursor", params.cursor);
  if (params.limit !== undefined) query.set("limit", params.limit.toString());

  const queryString = query.toString();
  return httpGet<AdminUserListResponse>(`/admin/users${queryString ? `?${queryString}` : ""}`);
}

// FR-2: returns the captured `ETag` response header alongside the body —
// `useAdminUser.ts` is the layer that decides where to cache it.
export async function getUser(id: string): Promise<{ data: AdminUserRead; etag: string | null }> {
  const result = await httpGetWithMeta<AdminUserRead>(`/admin/users/${encodeURIComponent(id)}`);
  return { data: result.data, etag: result.headers.get("etag") };
}

// FR-3: exactly `email`/`display_name`/`roles` — no password field anywhere.
export function createUser(payload: CreateAdminUserRequest): Promise<AdminUserRead> {
  return httpPost<AdminUserRead>("/admin/users", payload);
}

// FR-4: the caller supplies the `If-Match` value (the `ETag` captured by
// `getUser`, per `useAdminUser.ts`'s per-user-id cache key) — this stays
// transport-only, mirroring `profileApi.patchProfile`'s division of labor.
export function updateUser(
  id: string,
  payload: UpdateAdminUserRequest,
  ifMatch: string,
): Promise<HttpResult<AdminUserRead>> {
  return httpPatch<AdminUserRead>(`/admin/users/${encodeURIComponent(id)}`, payload, { ifMatch });
}

// FR-6.
export function deactivateUser(id: string, payload: DeactivateUserRequest): Promise<AdminUserRead> {
  return httpPost<AdminUserRead>(`/admin/users/${encodeURIComponent(id)}/deactivate`, payload);
}

// FR-6: the `202` body is never displayed by any screen.
export function resendInvite(id: string): Promise<ResendInviteResponse> {
  return httpPost<ResendInviteResponse>(`/admin/users/${encodeURIComponent(id)}/resend-invite`);
}

// FR-3 (Resolution OD-4)/FR-5 (Resolution OD-3): the single shared,
// unconditional role catalogue both the create-user form and the
// role-replacement control read.
export function listRoles(): Promise<RoleListResponse> {
  return httpGet<RoleListResponse>("/admin/roles");
}

// FR-5: full replacement, never a delta.
export function replaceUserRoles(
  id: string,
  payload: ReplaceUserRolesRequest,
): Promise<ReplaceUserRolesResponse> {
  return httpPut<ReplaceUserRolesResponse>(`/admin/users/${encodeURIComponent(id)}/roles`, payload);
}

// FR-8: the start-of-window query parameter's key must be literally `from`,
// not `from_` — this parameter object's own key name is what the story's
// own note pins, not merely the querystring this function builds from it.
export function listAuditLogs(params: {
  actor_id?: string;
  event?: string;
  target_id?: string;
  from?: string;
  to?: string;
  cursor?: string;
  limit?: number;
}): Promise<AuditLogListResponse> {
  const query = new URLSearchParams();
  if (params.actor_id) query.set("actor_id", params.actor_id);
  if (params.event) query.set("event", params.event);
  if (params.target_id) query.set("target_id", params.target_id);
  if (params.from) query.set("from", params.from);
  if (params.to) query.set("to", params.to);
  if (params.cursor) query.set("cursor", params.cursor);
  if (params.limit !== undefined) query.set("limit", params.limit.toString());

  const queryString = query.toString();
  return httpGet<AuditLogListResponse>(`/admin/audit-logs${queryString ? `?${queryString}` : ""}`);
}
