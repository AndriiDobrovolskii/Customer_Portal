// DTOs mirrored from docs/specifications/US-5.1-spec.md's API Contract table
// (itself mirroring app/modules/users/schemas.py). This file is the `api/`
// layer's own type boundary — no React, no TanStack Query, per AGENTS.md §3's
// Frontend table.

export interface UserRead {
  id: string;
  email: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  expires_in: number;
  user: UserRead;
  /** Present only for privileged roles inside their 14-day MFA grace period. */
  mfa_enrollment_deadline?: string | null;
}

export interface MfaRequiredResponse {
  mfa_token: string;
}

/** Discriminates POST /auth/login's two possible success shapes. */
export function isMfaRequiredResponse(
  response: LoginResponse | MfaRequiredResponse,
): response is MfaRequiredResponse {
  return "mfa_token" in response;
}

export interface MfaVerifyRequest {
  mfa_token: string;
  code: string;
}

/** Same shape as LoginResponse — MFA verify completes login identically. */
export type MfaVerifyResponse = LoginResponse;

export interface RefreshResponse {
  access_token: string;
  expires_in: number;
  mfa_enrollment_deadline?: string | null;
}

export interface SessionEntry {
  family_id: string;
  device_label: string;
  location: string | null;
  last_used_at: string;
  is_current: boolean;
}

export interface SessionListResponse {
  sessions: SessionEntry[];
}

export interface PasswordResetRequestRequest {
  email: string;
}

export interface PasswordResetRequestResponse {
  message: string;
}

export interface PasswordResetConfirmRequest {
  token: string;
  new_password: string;
}

// US-5.2 DTOs. FR-6/OD-6 (still OPEN): shipped as one shared constant so a
// later resolution widening the list is a one-line change, not a
// find-and-replace across the form and its validator (Plan Architectural
// Change 7).
export const SUPPORTED_LOCALES = ["en-US", "en-GB"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

// FR-2's write-only interim ProfileRead (no GET /profile exists yet, FR-1).
export interface ProfileRead {
  id: string;
  email: string;
  pending_email: string | null;
  display_name: string;
  locale: string;
  timezone: string;
  avatar_url: string | null;
  email_verified: boolean;
  created_at: string;
}

// FR-2's field-edit PATCH /profile payload — only the changed fields.
export interface ProfileUpdateRequest {
  display_name?: string;
  locale?: string;
  timezone?: string;
  avatar_url?: string;
}

// FR-3's email-change PATCH /profile payload (returns 202, not 200).
export interface EmailChangeRequest {
  email: string;
  current_password: string;
}

export interface ConfirmEmailChangeRequest {
  token: string;
}

export interface ConfirmEmailChangeResponse {
  email: string;
}

export interface VerifyEmailRequest {
  token: string;
}

export interface VerifyEmailResponse {
  email_verified: boolean;
}

export interface ResendVerificationRequest {
  email: string;
}

export interface ResendVerificationResponse {
  message: string;
}

// FR-5's enroll step: current_password per OD-2's resolution (PS-AC5 itself
// names no such field).
export interface MfaEnrollRequest {
  current_password: string;
}

export interface MfaEnrollResponse {
  secret: string;
  otpauth_uri: string;
}

export interface MfaActivateRequest {
  code: string;
}

export interface MfaActivateResponse {
  recovery_codes: string[];
}

// FR-6's disable step: current_password + code per OD-2's resolution.
export interface MfaDisableRequest {
  current_password: string;
  code: string;
}

// FR-7: current_password unconditionally required per OD-4's resolution.
export interface AccountDeactivateRequest {
  current_password: string;
}

export interface AccountDeactivateResponse {
  status: string;
  deactivated_at: string;
}

// US-5.3 Support Tickets DTOs
export type TicketStatus = "open" | "waiting_on_support" | "waiting_on_customer" | "resolved" | "closed";

export interface TicketRead {
  id: string;
  ticket_number: string;
  subject: string;
  category: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TicketListResponse {
  items: TicketRead[];
  next_cursor: string | null;
}

export interface CreateTicketRequest {
  subject: string;
  body: string;
  category: string;
  attachment_ids: string[];
}

// US-5.5 Architectural Change 1: `visibility` is a required field — the
// backend (`app/modules/support/schemas.py::ReplyRead`) has always returned
// it; this closes impact analysis v2's carried-forward Non-Blocking Finding.
// It is a hard prerequisite for FR-3's internal/public thread rendering and
// FR-4's composer, not an optional cleanup.
export interface ReplyRead {
  id: string;
  author_id: string;
  author_kind: string;
  visibility: "public" | "internal";
  body: string;
  created_at: string;
}

export interface ReplyThreadPage {
  items: ReplyRead[];
  next_cursor: string | null;
}

export interface TicketDetailRead {
  id: string;
  ticket_number: string;
  subject: string;
  category: string;
  status: string;
  created_at: string;
  updated_at: string;
  first_response_at?: string | null;
  replies: ReplyThreadPage;
}

// `visibility` is optional and additive — the existing customer call site
// (useReplyToTicket.ts's default path) never sets it, keeping its request
// body byte-for-byte identical to before this Story (Architectural Change 2).
export interface CreateReplyRequest {
  body: string;
  visibility?: "public" | "internal";
  attachment_ids: string[];
}

export interface TicketStateRead {
  id: string;
  status: string;
  updated_at: string;
}

export interface CloseTicketRequest {
  reason?: string;
}

export interface ReopenTicketRequest {
  reason?: string;
}

// US-5.4 Admin Console DTOs. `AdminUserRead.status`/`.roles` stay plain
// `string`/`string[]` (never a union) — the story's own "an unrecognized
// value renders verbatim" rule (Client State Notes); the fixed
// invited/active/deactivated set FR-1's filter <select> offers is a UI-only
// constant in AdminUserListScreen.tsx, not a change to this field's type —
// the same split types.ts already has between TicketRead.status: string and
// the separate TicketStatus union.
export interface AdminUserRead {
  id: string;
  email: string;
  display_name: string;
  status: string;
  roles: string[];
  created_at: string;
  last_login_at: string | null;
}

export interface AdminUserListResponse {
  items: AdminUserRead[];
  next_cursor: string | null;
}

// FR-3: exactly these three fields, no password field anywhere.
export interface CreateAdminUserRequest {
  email: string;
  display_name: string;
  roles: string[];
}

// FR-4: `roles` is deliberately absent — roles are a separate save path
// (FR-5). `reason` is always required by the form, never optional here.
export interface UpdateAdminUserRequest {
  display_name?: string;
  locale?: string;
  timezone?: string;
  avatar_url?: string;
  reason: string;
}

export interface DeactivateUserRequest {
  reason: string;
}

// FR-6: the 202 body is never displayed by any screen (only its receipt).
export interface ResendInviteResponse {
  message: string;
}

export interface RoleRead {
  name: string;
  permissions: string[];
}

export interface RoleListResponse {
  roles: RoleRead[];
}

export interface ReplaceUserRolesRequest {
  roles: string[];
}

export interface ReplaceUserRolesResponse {
  roles: string[];
}

// FR-8: explicitly no `id` field — AdminAuditLogScreen.tsx must synthesize
// its own stable per-row key. `event` is free text; `actor_role`, `outcome`,
// `ip`, `user_agent`, `actor_id`, `target_id` are all nullable.
export interface AuditLogEntry {
  occurred_at: string;
  actor_id: string | null;
  actor_role: string | null;
  event: string;
  target_id: string | null;
  outcome: string | null;
  request_id: string | null;
  ip: string | null;
  user_agent: string | null;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  next_cursor: string | null;
}

// US-5.5 Agent Console DTOs. FR-1's queue response (Resolution OD-1):
// every TicketRead field plus assignee_id — confirmed against
// app/modules/support/schemas.py::AgentTicketRead, mirrored here at this
// frontend's own simplified TicketRead field set (no requester_id/body,
// matching the existing TicketRead/TicketStateRead precedent of not
// mirroring every backend field).
export interface AgentTicketRead {
  id: string;
  ticket_number: string;
  subject: string;
  category: string;
  status: string;
  assignee_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentTicketListResponse {
  items: AgentTicketRead[];
  next_cursor: string | null;
}

// FR-2: `{ assignee_id }` populated by "assign to me" (the caller's own id)
// or the Resolution-OD-2 raw-UUID "assign to another agent" input.
export interface AssignTicketRequest {
  assignee_id: string;
}

// Implementation Plan Risk 3: the ACTUAL assign/unassign response shape
// (router.py declares response_model=AgentTicketStateRead on both routes) —
// distinct from AgentTicketRead. Carries assignee_id/status/updated_at but
// never subject/category/body/requester_id; must never be conflated with a
// full queue row.
export interface AgentTicketStateRead {
  id: string;
  status: string;
  updated_at: string;
  assignee_id: string | null;
}

// FR-5: a non-empty (1-5000 char) resolution_note.
export interface ResolveTicketRequest {
  resolution_note: string;
}
