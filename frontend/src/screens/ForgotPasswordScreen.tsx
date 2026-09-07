// FR-7's request half (FE-AC7, FE-AC8, FE-AC9, FE-AC11).
import { useForm } from "react-hook-form";
import { useRequestPasswordReset } from "../hooks/useRequestPasswordReset";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage } from "../components/apiErrorHelpers";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface ForgotPasswordFormValues {
  email: string;
}

export function ForgotPasswordScreen() {
  const requestMutation = useRequestPasswordReset();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<ForgotPasswordFormValues>();

  async function onSubmit(values: ForgotPasswordFormValues) {
    try {
      await requestMutation.mutateAsync(values);
    } catch {
      // surfaced via requestMutation.error below
    }
  }

  const apiError = requestMutation.isError ? requestMutation.error : null;
  const errorKind = getErrorKind(apiError);

  return (
    <section>
      <h1>Forgot password</h1>
      {requestMutation.isSuccess ? (
        <p>{requestMutation.data.message}</p>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <div>
            <label htmlFor="forgot-password-email">Email</label>
            <input
              id="forgot-password-email"
              type="email"
              autoComplete="email"
              {...register("email", {
                required: "Email is required.",
                pattern: { value: EMAIL_PATTERN, message: "Enter a valid email address." },
              })}
            />
            {errors.email && <p role="alert">{errors.email.message}</p>}
          </div>
          <button type="submit" disabled={requestMutation.isPending}>
            Send reset link
          </button>
        </form>
      )}
      {errorKind && <ErrorState kind={errorKind} onRetry={() => onSubmit(getValues())} />}
      {apiError && !errorKind && <p role="alert">{getErrorMessage(apiError)}</p>}
    </section>
  );
}
