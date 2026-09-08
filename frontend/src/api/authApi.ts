// One typed function per backend operation this Story's spec names (spec's
// API Contract table). Each translates a non-2xx response into a typed
// `ApiError` (via httpClient) the caller can branch on. No React, no
// TanStack Query, no store import — `api/` layer only (AGENTS.md §3).
import { httpDelete, httpGet, httpPost } from "./httpClient";
import type {
  LoginRequest,
  LoginResponse,
  MfaRequiredResponse,
  MfaVerifyRequest,
  MfaVerifyResponse,
  PasswordResetConfirmRequest,
  PasswordResetRequestRequest,
  PasswordResetRequestResponse,
  RefreshResponse,
  RegisterRequest,
  ResendVerificationRequest,
  ResendVerificationResponse,
  SessionListResponse,
  UserRead,
  VerifyEmailRequest,
  VerifyEmailResponse,
} from "./types";

export function register(payload: RegisterRequest): Promise<UserRead> {
  return httpPost<UserRead>("/auth/register", payload, { auth: false });
}

export function login(payload: LoginRequest): Promise<LoginResponse | MfaRequiredResponse> {
  return httpPost<LoginResponse | MfaRequiredResponse>("/auth/login", payload, { auth: false });
}

export function verifyMfa(payload: MfaVerifyRequest): Promise<MfaVerifyResponse> {
  return httpPost<MfaVerifyResponse>("/auth/mfa/verify", payload, { auth: false });
}

export function refresh(): Promise<RefreshResponse> {
  return httpPost<RefreshResponse>("/auth/refresh", undefined, { auth: false });
}

export function logout(): Promise<void> {
  return httpPost<void>("/auth/logout", undefined, { auth: true });
}

export function logoutAll(): Promise<void> {
  return httpPost<void>("/auth/logout-all", undefined, { auth: true });
}

export function listSessions(): Promise<SessionListResponse> {
  return httpGet<SessionListResponse>("/auth/sessions", { auth: true });
}

export function revokeSession(familyId: string): Promise<void> {
  return httpDelete<void>(`/auth/sessions/${encodeURIComponent(familyId)}`, { auth: true });
}

export function requestPasswordReset(
  payload: PasswordResetRequestRequest,
): Promise<PasswordResetRequestResponse> {
  return httpPost<PasswordResetRequestResponse>("/auth/password-reset/request", payload, { auth: false });
}

export function confirmPasswordReset(payload: PasswordResetConfirmRequest): Promise<void> {
  return httpPost<void>("/auth/password-reset/confirm", payload, { auth: false });
}

// FR-4: additive, /auth/* operations that aren't login/session-lifecycle.
export function verifyEmail(payload: VerifyEmailRequest): Promise<VerifyEmailResponse> {
  return httpPost<VerifyEmailResponse>("/auth/verify-email", payload, { auth: false });
}

export function resendVerificationEmail(
  payload: ResendVerificationRequest,
): Promise<ResendVerificationResponse> {
  return httpPost<ResendVerificationResponse>("/auth/verify-email/resend", payload, { auth: false });
}
