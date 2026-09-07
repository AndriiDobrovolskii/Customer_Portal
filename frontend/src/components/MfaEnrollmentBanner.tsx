// Story Assumption #6 / OD-7 (docs/decisions/US-5.1-open-decisions.md, still
// OPEN): surfaces LoginResponse/RefreshResponse's own `mfa_enrollment_deadline`
// as a dismissible informational banner. OD-7 gates the exact copy/tone and
// re-appearance rule only — this component implements the structural default
// docs/plans/US-5.1-implementation-plan.md fixes: dismissible, dismissal
// persisted via sessionStorage (non-sensitive, per the spec's own Client
// State Notes).
import { useState } from "react";

const DISMISS_KEY = "mfaEnrollmentBannerDismissed";

function readDismissed(): boolean {
  try {
    return sessionStorage.getItem(DISMISS_KEY) === "true";
  } catch {
    return false;
  }
}

function persistDismissed(): void {
  try {
    sessionStorage.setItem(DISMISS_KEY, "true");
  } catch {
    // sessionStorage may be unavailable (private browsing, disabled) — the
    // banner still dismisses for this render, it just won't persist.
  }
}

export interface MfaEnrollmentBannerProps {
  deadline: string | null;
}

export function MfaEnrollmentBanner({ deadline }: MfaEnrollmentBannerProps) {
  const [dismissed, setDismissed] = useState(readDismissed);

  if (!deadline || dismissed) {
    return null;
  }

  return (
    <div role="status">
      <p>Multi-factor authentication enrollment is required by {deadline}.</p>
      <button
        type="button"
        onClick={() => {
          setDismissed(true);
          persistDismissed();
        }}
      >
        Dismiss
      </button>
    </div>
  );
}
