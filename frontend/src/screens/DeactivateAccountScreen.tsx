// FR-7: current_password unconditionally required (OD-4's resolution), an
// explicit non-accidental confirmation step naming the consequence, and on
// 200 all in-memory auth state clears and the user lands on /login with a
// confirmation message.
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { useAccountDeactivate } from "../hooks/useAccountDeactivate";
import { ErrorState } from "../components/ErrorState";
import { FieldError } from "../components/FieldError";
import { getErrorKind, getErrorMessage, getFieldErrors } from "../components/apiErrorHelpers";

interface DeactivateFormValues {
  current_password: string;
}

export function DeactivateAccountScreen() {
  const navigate = useNavigate();
  const deactivateMutation = useAccountDeactivate();
  const [confirming, setConfirming] = useState(false);
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<DeactivateFormValues>();

  async function onSubmit(values: DeactivateFormValues) {
    try {
      await deactivateMutation.mutateAsync(values);
      navigate("/login", {
        state: { message: "Your account has been deactivated." },
        replace: true,
      });
    } catch {
      // surfaced via deactivateMutation.error below
    }
  }

  const apiError = deactivateMutation.isError ? deactivateMutation.error : null;
  const errorKind = getErrorKind(apiError);
  const fieldErrors = getFieldErrors(apiError);

  return (
    <section>
      <h1>Deactivate account</h1>

      {!confirming && (
        <button type="button" onClick={() => setConfirming(true)}>
          Deactivate account
        </button>
      )}

      {confirming && (
        <div>
          <p>
            Deactivating your account will sign you out and prevent you from accessing the Customer Portal
            until it is reactivated. This action requires your current password.
          </p>
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <div>
              <label htmlFor="deactivate-current-password">Current password</label>
              <input
                id="deactivate-current-password"
                type="password"
                autoComplete="current-password"
                {...register("current_password", { required: "Current password is required." })}
              />
              {errors.current_password && <p role="alert">{errors.current_password.message}</p>}
              <FieldError fieldErrors={fieldErrors} field="current_password" />
            </div>
            <button type="submit" disabled={deactivateMutation.isPending}>
              Yes, deactivate my account
            </button>
          </form>
        </div>
      )}

      {errorKind && <ErrorState kind={errorKind} onRetry={() => onSubmit(getValues())} />}
      {apiError && !errorKind && !fieldErrors && <p role="alert">{getErrorMessage(apiError)}</p>}
    </section>
  );
}
