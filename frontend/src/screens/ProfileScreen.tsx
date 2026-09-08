// FR-1 (deferred)/FR-2/FR-3, FR-8/FR-9/FR-10. Composed from hooks/ and
// shared components/ only — never api/ or fetch directly (AGENTS.md §3).
// Two independent forms: the field-edit form (display name / locale /
// timezone / avatar URL, "Save profile") and the email-change form (new
// email + current password, "Change email") — kept separate because they hit
// the same endpoint with two different payload shapes and two different
// success outcomes (200 vs. 202, FR-2/FR-3).
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useProfileUpdate } from "../hooks/useProfileUpdate";
import { ErrorState } from "../components/ErrorState";
import { FieldError } from "../components/FieldError";
import { getErrorKind, getErrorMessage, getErrorStatus, getFieldErrors } from "../components/apiErrorHelpers";
import { SUPPORTED_LOCALES, type ProfileRead, type ProfileUpdateRequest } from "../api/types";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface ProfileFormValues {
  display_name: string;
  locale: string;
  timezone: string;
  avatar_url: string;
}

interface EmailChangeFormValues {
  email: string;
  current_password: string;
}

function isSupportedTimezone(value: string): boolean {
  return Intl.supportedValuesOf("timeZone").includes(value);
}

const BLANK_PROFILE_FORM: ProfileFormValues = { display_name: "", locale: "", timezone: "", avatar_url: "" };

export function ProfileScreen() {
  const profileUpdate = useProfileUpdate();
  const [savedProfile, setSavedProfile] = useState<ProfileRead | null>(null);
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  // FR-2: "only the changed fields" — compared against this baseline rather
  // than react-hook-form's `dirtyFields` (which requires subscribing to
  // `formState` during render to stay live; diffing against a plain ref
  // avoids that subscription gotcha entirely and is fully deterministic).
  const baselineRef = useRef<ProfileFormValues>(BLANK_PROFILE_FORM);

  const profileForm = useForm<ProfileFormValues>({
    defaultValues: BLANK_PROFILE_FORM,
  });
  const emailForm = useForm<EmailChangeFormValues>();

  async function onSaveProfile(values: ProfileFormValues) {
    const baseline = baselineRef.current;
    const payload: ProfileUpdateRequest = {};
    if (values.display_name !== baseline.display_name) payload.display_name = values.display_name;
    if (values.locale !== baseline.locale) payload.locale = values.locale;
    if (values.timezone !== baseline.timezone) payload.timezone = values.timezone;
    if (values.avatar_url !== baseline.avatar_url) payload.avatar_url = values.avatar_url;

    try {
      const response = await profileUpdate.mutateAsync(payload);
      setSavedProfile(response);
      setPendingEmail(null);
      const nextValues: ProfileFormValues = {
        display_name: response.display_name,
        locale: response.locale,
        timezone: response.timezone,
        avatar_url: response.avatar_url ?? "",
      };
      baselineRef.current = nextValues;
      profileForm.reset(nextValues);
    } catch {
      // surfaced via profileUpdate.error below
    }
  }

  async function onChangeEmail(values: EmailChangeFormValues) {
    try {
      const response = await profileUpdate.mutateAsync({
        email: values.email,
        current_password: values.current_password,
      });
      setPendingEmail(response.pending_email);
      emailForm.reset();
    } catch {
      // surfaced via profileUpdate.error below
    }
  }

  const apiError = profileUpdate.isError ? profileUpdate.error : null;
  const errorKind = getErrorKind(apiError);
  const fieldErrors = getFieldErrors(apiError);
  const isConflict = profileUpdate.conflict || getErrorStatus(apiError) === 412;

  function handleReload() {
    profileUpdate.resetConflict();
    setSavedProfile(null);
    baselineRef.current = BLANK_PROFILE_FORM;
    profileForm.reset(BLANK_PROFILE_FORM);
  }

  return (
    <section>
      <h1>Profile</h1>

      {isConflict && (
        <div role="alert">
          <p>This profile has changed elsewhere. Please reload before saving again.</p>
          <button type="button" onClick={handleReload}>
            Reload
          </button>
        </div>
      )}

      {savedProfile && <p role="status">Profile saved. Current display name: {savedProfile.display_name}</p>}

      <form onSubmit={profileForm.handleSubmit(onSaveProfile)} noValidate>
        <div>
          <label htmlFor="profile-display-name">Display name</label>
          <input id="profile-display-name" type="text" {...profileForm.register("display_name")} />
          <FieldError fieldErrors={fieldErrors} field="display_name" />
        </div>
        <div>
          <label htmlFor="profile-locale">Locale</label>
          <select id="profile-locale" {...profileForm.register("locale")}>
            <option value="">Select a locale</option>
            {SUPPORTED_LOCALES.map((locale) => (
              <option key={locale} value={locale}>
                {locale}
              </option>
            ))}
          </select>
          <FieldError fieldErrors={fieldErrors} field="locale" />
        </div>
        <div>
          <label htmlFor="profile-timezone">Timezone</label>
          <input
            id="profile-timezone"
            type="text"
            role="combobox"
            aria-expanded="false"
            list="profile-timezone-options"
            {...profileForm.register("timezone", {
              validate: (value) => value === "" || isSupportedTimezone(value) || "Enter a valid timezone.",
            })}
          />
          <datalist id="profile-timezone-options">
            {Intl.supportedValuesOf("timeZone").map((zone) => (
              <option key={zone} value={zone} />
            ))}
          </datalist>
          {profileForm.formState.errors.timezone && (
            <p role="alert">{profileForm.formState.errors.timezone.message}</p>
          )}
          <FieldError fieldErrors={fieldErrors} field="timezone" />
        </div>
        <div>
          <label htmlFor="profile-avatar-url">Avatar URL</label>
          <input id="profile-avatar-url" type="text" {...profileForm.register("avatar_url")} />
          <FieldError fieldErrors={fieldErrors} field="avatar_url" />
        </div>
        <button type="submit" disabled={profileUpdate.isPending}>
          Save profile
        </button>
      </form>

      {pendingEmail && (
        <p role="status">Confirm the link sent to {pendingEmail} to complete your email change.</p>
      )}

      <form onSubmit={emailForm.handleSubmit(onChangeEmail)} noValidate>
        <h2>Change email</h2>
        <div>
          <label htmlFor="profile-new-email">New email</label>
          <input
            id="profile-new-email"
            type="email"
            {...emailForm.register("email", {
              required: "Email is required.",
              pattern: { value: EMAIL_PATTERN, message: "Enter a valid email address." },
            })}
          />
          {emailForm.formState.errors.email && <p role="alert">{emailForm.formState.errors.email.message}</p>}
          <FieldError fieldErrors={fieldErrors} field="email" />
        </div>
        <div>
          <label htmlFor="profile-email-current-password">Current password</label>
          <input
            id="profile-email-current-password"
            type="password"
            autoComplete="current-password"
            {...emailForm.register("current_password", { required: "Current password is required." })}
          />
          {emailForm.formState.errors.current_password && (
            <p role="alert">{emailForm.formState.errors.current_password.message}</p>
          )}
          <FieldError fieldErrors={fieldErrors} field="current_password" />
        </div>
        <button type="submit" disabled={profileUpdate.isPending}>
          Change email
        </button>
      </form>

      {errorKind && <ErrorState kind={errorKind} onRetry={() => onSaveProfile(profileForm.getValues())} />}
      {apiError && !errorKind && !fieldErrors && !isConflict && (
        <p role="alert">{getErrorMessage(apiError)}</p>
      )}
    </section>
  );
}
