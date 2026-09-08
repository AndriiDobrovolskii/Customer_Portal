// FR-7: POST /account/deactivate. `current_password` unconditionally
// required per OD-4's resolution.
import { httpPost } from "./httpClient";
import type { AccountDeactivateRequest, AccountDeactivateResponse } from "./types";

export function deactivateAccount(payload: AccountDeactivateRequest): Promise<AccountDeactivateResponse> {
  return httpPost<AccountDeactivateResponse>("/account/deactivate", payload, { auth: true });
}
