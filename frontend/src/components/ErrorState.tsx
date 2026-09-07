// FE-AC11: generic, retry-capable error state for a network error or a 5xx
// response — never a blank screen, never an unhandled exception. Consumed by
// every screen.
export interface ErrorStateProps {
  kind: "network" | "server";
  onRetry: () => void;
}

export function ErrorState({ kind, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" data-error-kind={kind}>
      <p>Something went wrong. Please try again.</p>
      <button type="button" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
