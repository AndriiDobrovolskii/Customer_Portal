// FR-1 (FE-AC1, FE-AC8, FE-AC9, FE-AC11). Composed from hooks/ and shared
// components/ only — never api/ or fetch directly (AGENTS.md §3).
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { useRegister } from "../hooks/useRegister";
import { ErrorState } from "../components/ErrorState";
import { FieldError } from "../components/FieldError";
import { getErrorKind, getErrorMessage, getFieldErrors } from "../components/apiErrorHelpers";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface RegisterFormValues {
  email: string;
  password: string;
}

// Register's confirmed policy (app/modules/users/service.py `_validate_password`,
// per docs/plans/US-5.1-implementation-plan.md Architectural Change 7, OD-5):
// min 8 chars, at least one uppercase, one lowercase, one digit, one
// punctuation character.
function validateRegisterPassword(value: string): string | true {
  const hasMinLength = value.length >= 8;
  const hasUpper = /[A-Z]/.test(value);
  const hasLower = /[a-z]/.test(value);
  const hasDigit = /[0-9]/.test(value);
  const hasPunctuation = /[!"#$%&'()*+,\-./:;<=>?@[\]^_`{|}~]/.test(value);
  if (hasMinLength && hasUpper && hasLower && hasDigit && hasPunctuation) {
    return true;
  }
  return "Password must contain at least 8 characters, including an uppercase letter, a lowercase letter, a digit, and a punctuation character.";
}

export function RegisterScreen() {
  const navigate = useNavigate();
  const registerMutation = useRegister();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<RegisterFormValues>();

  async function onSubmit(values: RegisterFormValues) {
    try {
      await registerMutation.mutateAsync(values);
      navigate("/login");
    } catch {
      // surfaced via registerMutation.error below
    }
  }

  const apiError = registerMutation.isError ? registerMutation.error : null;
  const errorKind = getErrorKind(apiError);
  const fieldErrors = getFieldErrors(apiError);

  if (registerMutation.isSuccess) {
    return (
      <section>
        <h1>Register</h1>
        <p>Registration successful. Please log in.</p>
      </section>
    );
  }

  return (
    <section>
      <h1>Register</h1>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div>
          <label htmlFor="register-email">Email</label>
          <input
            id="register-email"
            type="email"
            autoComplete="email"
            {...register("email", {
              required: "Email is required.",
              pattern: { value: EMAIL_PATTERN, message: "Enter a valid email address." },
            })}
          />
          {errors.email && <p role="alert">{errors.email.message}</p>}
          <FieldError fieldErrors={fieldErrors} field="email" />
        </div>
        <div>
          <label htmlFor="register-password">Password</label>
          <input
            id="register-password"
            type="password"
            autoComplete="new-password"
            {...register("password", {
              required: "Password is required.",
              validate: validateRegisterPassword,
            })}
          />
          {errors.password && <p role="alert">{errors.password.message}</p>}
          <FieldError fieldErrors={fieldErrors} field="password" />
        </div>
        <button type="submit" disabled={registerMutation.isPending}>
          Register
        </button>
      </form>
      {errorKind && <ErrorState kind={errorKind} onRetry={() => onSubmit(getValues())} />}
      {apiError && !errorKind && !fieldErrors && <p role="alert">{getErrorMessage(apiError)}</p>}
    </section>
  );
}
