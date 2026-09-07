// FR-2 / FR-3's initial submission (FE-AC2, FE-AC3's first branch, FE-AC9,
// FE-AC11).
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";
import { useLogin } from "../hooks/useLogin";
import { ErrorState } from "../components/ErrorState";
import { getErrorKind, getErrorMessage } from "../components/apiErrorHelpers";

interface LoginFormValues {
  email: string;
  password: string;
}

interface LocationState {
  from?: { pathname?: string };
}

export function LoginScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const loginMutation = useLogin();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<LoginFormValues>();

  const returnTo = (location.state as LocationState | null)?.from?.pathname ?? "/";

  async function onSubmit(values: LoginFormValues) {
    try {
      const response = await loginMutation.mutateAsync(values);
      if ("mfa_token" in response) {
        navigate("/mfa-verify");
      } else {
        navigate(returnTo, { replace: true });
      }
    } catch {
      // surfaced via loginMutation.error below
    }
  }

  const apiError = loginMutation.isError ? loginMutation.error : null;
  const errorKind = getErrorKind(apiError);

  return (
    <section>
      <h1>Log in</h1>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div>
          <label htmlFor="login-email">Email</label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            {...register("email", { required: "Email is required." })}
          />
          {errors.email && <p role="alert">{errors.email.message}</p>}
        </div>
        <div>
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            {...register("password", { required: "Password is required." })}
          />
          {errors.password && <p role="alert">{errors.password.message}</p>}
        </div>
        <button type="submit" disabled={loginMutation.isPending}>
          Log in
        </button>
      </form>
      {errorKind && <ErrorState kind={errorKind} onRetry={() => onSubmit(getValues())} />}
      {apiError && !errorKind && <p role="alert">{getErrorMessage(apiError)}</p>}
    </section>
  );
}
