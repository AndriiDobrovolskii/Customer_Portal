// FR-12, OD-1: a small, non-network local-state hook shared by
// NewTicketScreen.tsx (POST /support/tickets) and TicketDetailScreen.tsx's
// reply composer (POST /support/tickets/{id}/replies) — both 429 call sites
// need identical behavior: disable submit, show the remaining time, never
// re-issue the request itself. Ticks `secondsRemaining` down to zero from a
// supplied `retryAfterSeconds` (read via `getRetryAfterSeconds`, never by
// importing `api/httpClient.ts`'s `ApiError` class directly).
import { useEffect, useState } from "react";

export interface RetryAfterCountdown {
  secondsRemaining: number;
  isBlocked: boolean;
}

export function useRetryAfterCountdown(retryAfterSeconds: number | undefined): RetryAfterCountdown {
  const [secondsRemaining, setSecondsRemaining] = useState(retryAfterSeconds ?? 0);

  useEffect(() => {
    setSecondsRemaining(retryAfterSeconds ?? 0);

    if (!retryAfterSeconds || retryAfterSeconds <= 0) {
      return;
    }

    const interval = setInterval(() => {
      setSecondsRemaining((current) => {
        if (current <= 1) {
          clearInterval(interval);
          return 0;
        }
        return current - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [retryAfterSeconds]);

  return { secondsRemaining, isBlocked: secondsRemaining > 0 };
}
