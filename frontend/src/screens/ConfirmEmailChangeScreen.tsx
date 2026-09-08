// FR-3's confirmation-link landing target, /confirm-email-change. "Works
// signed-in and signed-out": on mount, the `?token=` query param drives an
// automatic POST /profile/confirm-email-change call regardless of the
// visitor's current auth state.
import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useConfirmEmailChange } from "../hooks/useConfirmEmailChange";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage } from "../components/apiErrorHelpers";

export function ConfirmEmailChangeScreen() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const confirmMutation = useConfirmEmailChange();
  const { mutate: confirmEmailChange } = confirmMutation;
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current || !token) {
      return;
    }
    attempted.current = true;
    confirmEmailChange({ token });
  }, [token, confirmEmailChange]);

  function retry() {
    confirmEmailChange({ token });
  }

  const apiError = confirmMutation.isError ? confirmMutation.error : null;
  const errorKind = getErrorKind(apiError);

  return (
    <section>
      <h1>Confirm email change</h1>
      {confirmMutation.isSuccess && (
        <p role="status">Your new email address, {confirmMutation.data.email}, has been confirmed.</p>
      )}
      {apiError && !errorKind && <p role="alert">{getErrorMessage(apiError)}</p>}
      {errorKind && <ErrorState kind={errorKind} onRetry={retry} />}
    </section>
  );
}
