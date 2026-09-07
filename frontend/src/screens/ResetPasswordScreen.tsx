// FR-7's confirm half (FE-AC7, FE-AC8's 12-char client rule — OD-5's
// server-only breach/differs-from-current checks are deliberately NOT
// simulated client-side, per implementation-plan Architectural Change 7 —
// FE-AC9, FE-AC11).
import { useForm } from "react-hook-form";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useConfirmPasswordReset } from "../hooks/useConfirmPasswordReset";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage } from "../components/apiErrorHelpers";

const MIN_LENGTH = 12;

interface ResetPasswordFormValues {
  newPassword: string;
}

export function ResetPasswordScreen() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const confirmMutation = useConfirmPasswordReset();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>();

  async function onSubmit(values: ResetPasswordFormValues) {
    try {
      await confirmMutation.mutateAsync({ token, new_password: values.newPassword });
      navigate("/login");
    } catch {
      // surfaced via confirmMutation.error below
    }
  }

  const apiError = confirmMutation.isError ? confirmMutation.error : null;
  const errorKind = getErrorKind(apiError);

  if (confirmMutation.isSuccess) {
    return (
      <section>
        <h1>Reset password</h1>
        <p>Your password has been reset. Please log in.</p>
      </section>
    );
  }

  return (
    <section>
      <h1>Reset password</h1>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div>
          <label htmlFor="reset-password-new-password">New password</label>
          <input
            id="reset-password-new-password"
            type="password"
            autoComplete="new-password"
            {...register("newPassword", {
              required: "New password is required.",
              minLength: { value: MIN_LENGTH, message: "Password must be at least 12 characters." },
            })}
          />
          {errors.newPassword && <p role="alert">{errors.newPassword.message}</p>}
        </div>
        <button type="submit" disabled={confirmMutation.isPending}>
          Reset password
        </button>
      </form>
      {errorKind && <ErrorState kind={errorKind} onRetry={() => onSubmit(getValues())} />}
      {apiError && !errorKind && <p role="alert">{getErrorMessage(apiError)}</p>}
    </section>
  );
}
