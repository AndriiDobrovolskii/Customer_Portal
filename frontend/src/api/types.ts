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
