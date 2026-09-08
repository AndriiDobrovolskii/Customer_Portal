// FR-5/FR-6's enroll/activate/disable sub-domain. Kept separate from
// authApi.ts's existing `verifyMfa` (the login *challenge* flow, untouched by
// this Story) — enroll/activate accept an enrollment-scoped access token,
// while disable is a normal Bearer call re-verified by password+code (Plan
// Architectural Change 5).
import { httpDelete, httpPost } from "./httpClient";
import type {
  MfaActivateRequest,
  MfaActivateResponse,
  MfaDisableRequest,
  MfaEnrollRequest,
  MfaEnrollResponse,
} from "./types";

export function enrollMfa(payload: MfaEnrollRequest): Promise<MfaEnrollResponse> {
  return httpPost<MfaEnrollResponse>("/auth/mfa/enroll", payload, { auth: true });
}

export function activateMfa(payload: MfaActivateRequest): Promise<MfaActivateResponse> {
  return httpPost<MfaActivateResponse>("/auth/mfa/activate", payload, { auth: true });
}

// FR-6: DELETE /auth/mfa carries a request body (current_password + code,
// per OD-2's resolution) — httpClient.ts's httpDelete gained an additive
// `body` option for exactly this call.
export function disableMfa(payload: MfaDisableRequest): Promise<void> {
  return httpDelete<void>("/auth/mfa", { auth: true, body: payload });
}
