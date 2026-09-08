// FR-4: /verify-email landing target. On mount, the `?token=` query param
// drives an automatic POST /auth/verify-email call (same convention as
// ResetPasswordScreen's `?token=` read); success/expired/invalid each render
// a distinct outcome. A separate resend form calls POST /auth/verify-email/resend
// and shows one generic confirmation regardless of whether the address
// exists (anti-enumeration is the server's own responsibility).
import { useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { useVerifyEmail } from "../hooks/useVerifyEmail";
import { useResendVerificationEmail } from "../hooks/useResendVerificationEmail";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage } from "../components/apiErrorHelpers";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface ResendFormValues {
  email: string;
}

export function EmailVerificationScreen() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const verifyMutation = useVerifyEmail();
  const { mutate: verifyEmail } = verifyMutation;
  const resendMutation = useResendVerificationEmail();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<ResendFormValues>();

  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current || !token) {
      return;
    }
    attempted.current = true;
    verifyEmail({ token });
  }, [token, verifyEmail]);

  function retryVerification() {
    verifyEmail({ token });
  }

  async function onResend(values: ResendFormValues) {
    try {
      await resendMutation.mutateAsync(values);
    } catch {
      // surfaced via resendMutation.error below
    }
  }

  const verifyError = verifyMutation.isError ? verifyMutation.error : null;
  const verifyErrorKind = getErrorKind(verifyError);

  const resendError = resendMutation.isError ? resendMutation.error : null;
  const resendErrorKind = getErrorKind(resendError);

  return (
    <section>
      <h1>Verify your email</h1>

      {verifyMutation.isSuccess && <p role="status">Your email has been verified.</p>}

      {verifyError && !verifyErrorKind && <p role="alert">{getErrorMessage(verifyError)}</p>}

      {verifyErrorKind && <ErrorState kind={verifyErrorKind} onRetry={retryVerification} />}

      <section>
        <h2>Resend verification email</h2>
        <form onSubmit={handleSubmit(onResend)} noValidate>
          <div>
            <label htmlFor="resend-verification-email">Email</label>
            <input
              id="resend-verification-email"
              type="email"
              {...register("email", {
                required: "Email is required.",
                pattern: { value: EMAIL_PATTERN, message: "Enter a valid email address." },
              })}
            />
            {errors.email && <p role="alert">{errors.email.message}</p>}
          </div>
          <button type="submit" disabled={resendMutation.isPending}>
            Resend verification email
          </button>
        </form>
        {resendMutation.isSuccess && <p role="status">{resendMutation.data.message}</p>}
        {resendErrorKind && <ErrorState kind={resendErrorKind} onRetry={() => onResend(getValues())} />}
        {resendError && !resendErrorKind && <p role="alert">{getErrorMessage(resendError)}</p>}
      </section>
    </section>
  );
}
