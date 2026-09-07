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
