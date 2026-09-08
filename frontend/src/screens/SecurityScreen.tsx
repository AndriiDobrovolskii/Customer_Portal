// FR-5 (enroll -> activate -> one-time recovery codes) / FR-6 (disable),
// Plan Change 6. `authStore.mfaEnabled` (read-only) is the real,
// session-scoped signal this screen uses to choose between the enroll and
// disable flows — never a blind default (Plan Architectural Change 6).
//
// Local phase state: `recoveryCodes` takes rendering precedence over
// `authStore.mfaEnabled` so the one-time codes stay visible even though
// useMfaActivate's onSuccess has already flipped `mfaEnabled` to true —
// the screen only "completes" enrollment (and falls through to the
// mfaEnabled-driven branch) once the user explicitly confirms via
// RecoveryCodesDisplay's onConfirmed.
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useMfaEnroll } from "../hooks/useMfaEnroll";
import { useMfaActivate } from "../hooks/useMfaActivate";
import { useMfaDisable } from "../hooks/useMfaDisable";
import { useAuthStore } from "../store/authStore";
import { QrCode } from "../components/QrCode";
import { RecoveryCodesDisplay } from "../components/RecoveryCodesDisplay";
import { ErrorState } from "../components/ErrorState";
import { FieldError } from "../components/FieldError";
import { getErrorKind, getErrorMessage, getFieldErrors } from "../components/apiErrorHelpers";

const CODE_PATTERN = /^\d{6}$/;

interface EnrollFormValues {
  current_password: string;
}

interface ActivateFormValues {
  code: string;
}

interface DisableFormValues {
  current_password: string;
  code: string;
}

export function SecurityScreen() {
  const { mfaEnabled } = useAuthStore();
  const enrollMutation = useMfaEnroll();
  const activateMutation = useMfaActivate();
  const disableMutation = useMfaDisable();

  const [enrollment, setEnrollment] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [disableConfirming, setDisableConfirming] = useState(false);

  const enrollForm = useForm<EnrollFormValues>();
  const activateForm = useForm<ActivateFormValues>();
  const disableForm = useForm<DisableFormValues>();

  async function onEnroll(values: EnrollFormValues) {
    try {
      const response = await enrollMutation.mutateAsync(values);
      setEnrollment(response);
    } catch {
      // surfaced via enrollMutation.error below
    }
  }

  async function onActivate(values: ActivateFormValues) {
    try {
      const response = await activateMutation.mutateAsync(values);
      setRecoveryCodes(response.recovery_codes);
    } catch {
      // surfaced via activateMutation.error below
    }
  }

  function onRecoveryCodesConfirmed() {
    setRecoveryCodes(null);
    setEnrollment(null);
    enrollForm.reset();
    activateForm.reset();
  }

  async function onDisable(values: DisableFormValues) {
    try {
      await disableMutation.mutateAsync(values);
      setDisableConfirming(false);
      disableForm.reset();
    } catch {
      // surfaced via disableMutation.error below
    }
  }

  if (recoveryCodes) {
    return <RecoveryCodesDisplay codes={recoveryCodes} onConfirmed={onRecoveryCodesConfirmed} />;
  }

  if (mfaEnabled) {
    const apiError = disableMutation.isError ? disableMutation.error : null;
    const errorKind = getErrorKind(apiError);
    const fieldErrors = getFieldErrors(apiError);

    return (
      <section>
        <h1>Security</h1>
        <p>Multi-factor authentication is enabled on your account.</p>
        {!disableConfirming && (
          <button type="button" onClick={() => setDisableConfirming(true)}>
            Disable MFA
          </button>
        )}
        {disableConfirming && (
          <div>
            <p>
              Disabling multi-factor authentication will revoke every other active session on your account.
            </p>
            <form onSubmit={disableForm.handleSubmit(onDisable)} noValidate>
              <div>
                <label htmlFor="disable-mfa-current-password">Current password</label>
                <input
                  id="disable-mfa-current-password"
                  type="password"
                  autoComplete="current-password"
                  {...disableForm.register("current_password", {
                    required: "Current password is required.",
                  })}
                />
                {disableForm.formState.errors.current_password && (
                  <p role="alert">{disableForm.formState.errors.current_password.message}</p>
                )}
                <FieldError fieldErrors={fieldErrors} field="current_password" />
              </div>
              <div>
                <label htmlFor="disable-mfa-code">Code</label>
                <input
                  id="disable-mfa-code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  {...disableForm.register("code", {
                    required: "Code is required.",
                    pattern: { value: CODE_PATTERN, message: "Enter a 6-digit code." },
                  })}
                />
                {disableForm.formState.errors.code && (
                  <p role="alert">{disableForm.formState.errors.code.message}</p>
                )}
                <FieldError fieldErrors={fieldErrors} field="code" />
              </div>
              <button type="submit" disabled={disableMutation.isPending}>
                Yes, disable MFA
              </button>
            </form>
          </div>
        )}
        {errorKind && <ErrorState kind={errorKind} onRetry={() => onDisable(disableForm.getValues())} />}
        {apiError && !errorKind && !fieldErrors && <p role="alert">{getErrorMessage(apiError)}</p>}
      </section>
    );
  }

  if (enrollment) {
    const apiError = activateMutation.isError ? activateMutation.error : null;
    const errorKind = getErrorKind(apiError);
    const fieldErrors = getFieldErrors(apiError);

    return (
      <section>
        <h1>Security</h1>
        <p>Scan this QR code with your authenticator app, or enter the code manually.</p>
        <QrCode value={enrollment.otpauth_uri} />
        <p>Secret: {enrollment.secret}</p>
        <form onSubmit={activateForm.handleSubmit(onActivate)} noValidate>
          <div>
            <label htmlFor="mfa-activate-code">Code</label>
            <input
              id="mfa-activate-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              {...activateForm.register("code", {
                required: "Code is required.",
                pattern: { value: CODE_PATTERN, message: "Enter a 6-digit code." },
              })}
            />
            {activateForm.formState.errors.code && (
              <p role="alert">{activateForm.formState.errors.code.message}</p>
            )}
            <FieldError fieldErrors={fieldErrors} field="code" />
          </div>
          <button type="submit" disabled={activateMutation.isPending}>
            Activate
          </button>
        </form>
        {errorKind && <ErrorState kind={errorKind} onRetry={() => onActivate(activateForm.getValues())} />}
        {apiError && !errorKind && !fieldErrors && <p role="alert">{getErrorMessage(apiError)}</p>}
      </section>
    );
  }

  const apiError = enrollMutation.isError ? enrollMutation.error : null;
  const errorKind = getErrorKind(apiError);
  const fieldErrors = getFieldErrors(apiError);

  return (
    <section>
      <h1>Security</h1>
      <p>Multi-factor authentication is not enabled on your account.</p>
      <form onSubmit={enrollForm.handleSubmit(onEnroll)} noValidate>
        <div>
          <label htmlFor="enroll-mfa-current-password">Current password</label>
          <input
            id="enroll-mfa-current-password"
            type="password"
            autoComplete="current-password"
            {...enrollForm.register("current_password", { required: "Current password is required." })}
          />
          {enrollForm.formState.errors.current_password && (
            <p role="alert">{enrollForm.formState.errors.current_password.message}</p>
          )}
          <FieldError fieldErrors={fieldErrors} field="current_password" />
        </div>
        <button type="submit" disabled={enrollMutation.isPending}>
          Start enrollment
        </button>
      </form>
      {errorKind && <ErrorState kind={errorKind} onRetry={() => onEnroll(enrollForm.getValues())} />}
      {apiError && !errorKind && !fieldErrors && <p role="alert">{getErrorMessage(apiError)}</p>}
    </section>
  );
}
