// FR-3's second step (FE-AC3, FE-AC9, FE-AC11). Reads `mfaToken` from the
// store read-only (AGENTS.md §3) — it was set by useLogin's onSuccess, never
// by this screen itself.
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { useMfaVerify } from "../hooks/useMfaVerify";
import { useAuthStore } from "../store/authStore";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage } from "../components/apiErrorHelpers";

interface MfaVerifyFormValues {
  code: string;
}

export function MfaVerifyScreen() {
  const navigate = useNavigate();
  const { mfaToken } = useAuthStore();
  const verifyMutation = useMfaVerify();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<MfaVerifyFormValues>();

  async function onSubmit(values: MfaVerifyFormValues) {
    if (!mfaToken) {
      return;
    }
    try {
      await verifyMutation.mutateAsync({ mfa_token: mfaToken, code: values.code });
      navigate("/");
    } catch {
      // surfaced via verifyMutation.error below
    }
  }

  const apiError = verifyMutation.isError ? verifyMutation.error : null;
  const errorKind = getErrorKind(apiError);

  return (
    <section>
      <h1>Verify your identity</h1>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div>
          <label htmlFor="mfa-code">Code</label>
          <input
            id="mfa-code"
            type="text"
            autoComplete="one-time-code"
            {...register("code", { required: "Code is required." })}
          />
          {errors.code && <p role="alert">{errors.code.message}</p>}
        </div>
        <button type="submit" disabled={verifyMutation.isPending}>
          Verify
        </button>
      </form>
      {errorKind && <ErrorState kind={errorKind} onRetry={() => onSubmit(getValues())} />}
      {apiError && !errorKind && <p role="alert">{getErrorMessage(apiError)}</p>}
    </section>
  );
}
