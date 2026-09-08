// FR-2/FR-3. `patchProfile` covers both PATCH /profile payload shapes (field
// edit, email change) and returns the full `{data, status, headers}` result
// so `useProfileUpdate.ts` can disambiguate 200/202/412 by status and read
// the `ETag` header — the policy of *which* `If-Match` value to send belongs
// to the caller (OD-1), not this file, which stays transport-only (AGENTS.md
// §3's `api/` row: no React, no TanStack Query).
import { httpPatch, httpPost, type HttpResult } from "./httpClient";
import type {
  ConfirmEmailChangeRequest,
  ConfirmEmailChangeResponse,
  EmailChangeRequest,
  ProfileRead,
  ProfileUpdateRequest,
} from "./types";

export function patchProfile(
  payload: ProfileUpdateRequest | EmailChangeRequest,
  ifMatch: string,
): Promise<HttpResult<ProfileRead>> {
  return httpPatch<ProfileRead>("/profile", payload, { ifMatch });
}

// FR-3: "succeeds whether or not they are signed in" — never assumes an
// authenticated caller.
export function confirmEmailChange(payload: ConfirmEmailChangeRequest): Promise<ConfirmEmailChangeResponse> {
  return httpPost<ConfirmEmailChangeResponse>("/profile/confirm-email-change", payload, { auth: false });
}
