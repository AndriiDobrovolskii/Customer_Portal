// AD-AC2/AD-AC4/AD-AC5/AD-AC6/AD-AC7/FR-2/FR-4/FR-5/FR-6/FR-7: /admin/users/:id
// — the largest surface in this Story. Hosts the field-edit form (reason
// required, If-Match via useUpdateAdminUser.ts's cached ETag, 412 conflict,
// immutable-field detail), the independent role-replacement control
// (Resolution OD-3: a target-*replacement* multi-select with a Gained/Lost
// confirmation diff, Save disabled while the selected set equals the
// current set), deactivate (reason required, explicit confirmation), and
// resend-invite (generic confirmation only). By omission, no delete control
// anywhere (AD-AC7). XC-AC1: a forced server 403 renders an explicit "not
// permitted" state; every write control is rendered disabled (not hidden)
// without its own required scope. Composed from hooks/, store/ (read-only),
// and shared components/ only — never api/ or fetch directly (AGENTS.md §3).
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useParams } from "react-router-dom";
import { useAdminUser } from "../hooks/useAdminUser";
import { useAdminRoles } from "../hooks/useAdminRoles";
import { useUpdateAdminUser } from "../hooks/useUpdateAdminUser";
import { useReplaceUserRoles } from "../hooks/useReplaceUserRoles";
import { useDeactivateAdminUser } from "../hooks/useDeactivateAdminUser";
import { useResendInvite } from "../hooks/useResendInvite";
import { useAuthStore } from "../store/authStore";
import { ErrorState } from "../components/ErrorState";
import { FieldError } from "../components/FieldError";
import { getErrorKind, getErrorMessage, getErrorStatus, getFieldErrors } from "../components/apiErrorHelpers";

interface EditFormValues {
  display_name: string;
  locale: string;
  timezone: string;
  avatar_url: string;
  reason: string;
}

const EMPTY_EDIT_FORM: EditFormValues = {
  display_name: "",
  locale: "",
  timezone: "",
  avatar_url: "",
  reason: "",
};

interface DeactivateFormValues {
  reason: string;
}

function sameRoleSet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) {
    return false;
  }
  const bSet = new Set(b);
  return a.every((role) => bSet.has(role));
}

export function AdminUserDetailScreen() {
  const { id } = useParams<{ id: string }>();
  const userId = id ?? "";
  const { scopes } = useAuthStore();
  const canEditUsers = scopes.includes("users:write");
  const canEditRoles = scopes.includes("roles:write");

  const userQuery = useAdminUser(userId);
  const rolesQuery = useAdminRoles();
  const updateMutation = useUpdateAdminUser(userId);
  const replaceRolesMutation = useReplaceUserRoles(userId);
  const deactivateMutation = useDeactivateAdminUser(userId);
  const resendMutation = useResendInvite(userId);

  const editBaselineRef = useRef<EditFormValues>(EMPTY_EDIT_FORM);
  const editForm = useForm<EditFormValues>({ defaultValues: EMPTY_EDIT_FORM });

  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const rolesInitializedRef = useRef(false);
  const [roleConfirming, setRoleConfirming] = useState(false);
  const [deactivateConfirming, setDeactivateConfirming] = useState(false);
  const [resendConfirmed, setResendConfirmed] = useState(false);

  const user = userQuery.data;

  useEffect(() => {
    if (user) {
      const next: EditFormValues = {
        display_name: user.display_name,
        locale: "",
        timezone: "",
        avatar_url: "",
        reason: "",
      };
      editBaselineRef.current = next;
      editForm.reset(next);
    }
  }, [user, editForm]);

  useEffect(() => {
    if (user && !rolesInitializedRef.current) {
      setSelectedRoles(user.roles);
      rolesInitializedRef.current = true;
    }
  }, [user]);

  const {
    register: registerEdit,
    handleSubmit: handleEditSubmit,
    formState: { errors: editErrors },
  } = editForm;

  async function onSubmitEdit(values: EditFormValues) {
    const baseline = editBaselineRef.current;
    const payload: {
      display_name?: string;
      locale?: string;
      timezone?: string;
      avatar_url?: string;
      reason: string;
    } = { reason: values.reason };
    if (values.display_name !== baseline.display_name) payload.display_name = values.display_name;
    if (values.locale !== baseline.locale) payload.locale = values.locale;
    if (values.timezone !== baseline.timezone) payload.timezone = values.timezone;
    if (values.avatar_url !== baseline.avatar_url) payload.avatar_url = values.avatar_url;

    try {
      await updateMutation.mutateAsync(payload);
      editForm.reset({ ...values, reason: "" });
    } catch {
      // surfaced via updateMutation.error below
    }
  }

  const {
    register: registerDeactivate,
    handleSubmit: handleDeactivateSubmit,
    formState: { errors: deactivateErrors },
  } = useForm<DeactivateFormValues>();

  async function onSubmitDeactivate(values: DeactivateFormValues) {
    try {
      await deactivateMutation.mutateAsync(values);
      setDeactivateConfirming(false);
    } catch {
      // surfaced via deactivateMutation.error below
    }
  }

  async function handleConfirmRoleSave() {
    try {
      await replaceRolesMutation.mutateAsync({ roles: selectedRoles });
      setRoleConfirming(false);
    } catch {
      // surfaced via replaceRolesMutation.error below
    }
  }

  async function handleResendInvite() {
    setResendConfirmed(false);
    try {
      await resendMutation.mutateAsync();
      setResendConfirmed(true);
    } catch {
      // surfaced via resendMutation.error below
    }
  }

  if (userQuery.isPending) {
    return (
      <section>
        <h1>User</h1>
        <p>Loading user…</p>
      </section>
    );
  }

  const userErrorStatus = getErrorStatus(userQuery.error);
  if (userQuery.isError && userErrorStatus === 403) {
    return (
      <section>
        <h1>User</h1>
        <p role="alert">You do not have permission to view this page.</p>
      </section>
    );
  }

  if (userQuery.isError) {
    const kind = getErrorKind(userQuery.error);
    return (
      <section>
        <h1>User</h1>
        {kind ? (
          <ErrorState kind={kind} onRetry={() => userQuery.refetch()} />
        ) : (
          <p role="alert">{getErrorMessage(userQuery.error)}</p>
        )}
      </section>
    );
  }

  if (!user) {
    return null;
  }

  const editApiError = updateMutation.isError ? updateMutation.error : null;
  const editErrorKind = getErrorKind(editApiError);
  const editFieldErrors = getFieldErrors(editApiError);
  const isConflict = updateMutation.conflict;

  const roleOptions = rolesQuery.data?.roles ?? [];
  const gainedRoles = selectedRoles.filter((role) => !user.roles.includes(role));
  const lostRoles = user.roles.filter((role) => !selectedRoles.includes(role));
  const rolesUnchanged = sameRoleSet(selectedRoles, user.roles);
  const rolesEmpty = selectedRoles.length === 0;
  const roleSaveDisabled = !canEditRoles || rolesUnchanged || rolesEmpty || replaceRolesMutation.isPending;

  const roleApiError = replaceRolesMutation.isError ? replaceRolesMutation.error : null;
  const roleErrorKind = getErrorKind(roleApiError);

  const deactivateApiError = deactivateMutation.isError ? deactivateMutation.error : null;
  const deactivateErrorKind = getErrorKind(deactivateApiError);
  const deactivateFieldErrors = getFieldErrors(deactivateApiError);

  const resendApiError = resendMutation.isError ? resendMutation.error : null;

  return (
    <section>
      <h1>{user.email}</h1>
      <dl>
        <dt>Status</dt>
        <dd>{user.status}</dd>
      </dl>

      {isConflict && (
        <div role="alert">
          <p>This user has changed elsewhere. Please reload before saving again.</p>
          <button type="button" onClick={() => userQuery.refetch()}>
            Reload
          </button>
        </div>
      )}

      {updateMutation.immutableFieldDetail && <p role="alert">{updateMutation.immutableFieldDetail}</p>}

      <form aria-label="Edit user details" onSubmit={handleEditSubmit(onSubmitEdit)} noValidate>
        <h2>Edit user</h2>
        <div>
          <label htmlFor="user-detail-display-name">Display name</label>
          <input id="user-detail-display-name" type="text" {...registerEdit("display_name")} />
          <FieldError fieldErrors={editFieldErrors} field="display_name" />
        </div>
        <div>
          <label htmlFor="user-detail-locale">Locale</label>
          <input id="user-detail-locale" type="text" {...registerEdit("locale")} />
          <FieldError fieldErrors={editFieldErrors} field="locale" />
        </div>
        <div>
          <label htmlFor="user-detail-timezone">Timezone</label>
          <input id="user-detail-timezone" type="text" {...registerEdit("timezone")} />
          <FieldError fieldErrors={editFieldErrors} field="timezone" />
        </div>
        <div>
          <label htmlFor="user-detail-avatar-url">Avatar URL</label>
          <input id="user-detail-avatar-url" type="text" {...registerEdit("avatar_url")} />
          <FieldError fieldErrors={editFieldErrors} field="avatar_url" />
        </div>
        <div>
          <label htmlFor="user-detail-edit-reason">Reason</label>
          <input
            id="user-detail-edit-reason"
            type="text"
            {...registerEdit("reason", { required: "Reason is required." })}
          />
          {editErrors.reason && <p role="alert">{editErrors.reason.message}</p>}
          <FieldError fieldErrors={editFieldErrors} field="reason" />
        </div>
        <button type="submit" disabled={!canEditUsers || updateMutation.isPending}>
          Save changes
        </button>
      </form>
      {editErrorKind && <ErrorState kind={editErrorKind} onRetry={() => handleEditSubmit(onSubmitEdit)()} />}
      {editApiError &&
        !editErrorKind &&
        !editFieldErrors &&
        !isConflict &&
        !updateMutation.immutableFieldDetail && <p role="alert">{getErrorMessage(editApiError)}</p>}

      <div>
        <h2>Roles</h2>
        <label htmlFor="user-detail-roles">Roles</label>
        <select
          id="user-detail-roles"
          multiple
          disabled={!canEditRoles}
          value={selectedRoles}
          onChange={(event) =>
            setSelectedRoles(Array.from(event.target.selectedOptions).map((option) => option.value))
          }
        >
          {roleOptions.map((role) => (
            <option key={role.name} value={role.name}>
              {role.name}
            </option>
          ))}
        </select>
        {rolesEmpty && <p role="alert">Select at least one role.</p>}

        <button type="button" disabled={roleSaveDisabled} onClick={() => setRoleConfirming(true)}>
          Save role changes
        </button>

        {roleConfirming && (
          <div>
            <h3>Gained roles</h3>
            {gainedRoles.length > 0 ? (
              <ul>
                {gainedRoles.map((role) => (
                  <li key={role}>{role}</li>
                ))}
              </ul>
            ) : (
              <p>None</p>
            )}
            <h3>Lost roles</h3>
            {lostRoles.length > 0 ? (
              <ul>
                {lostRoles.map((role) => (
                  <li key={role}>{role}</li>
                ))}
              </ul>
            ) : (
              <p>None</p>
            )}
            <button type="button" onClick={handleConfirmRoleSave}>
              Confirm role changes
            </button>
            <button type="button" onClick={() => setRoleConfirming(false)}>
              Cancel
            </button>
          </div>
        )}

        {roleErrorKind && <ErrorState kind={roleErrorKind} onRetry={() => handleConfirmRoleSave()} />}
        {roleApiError && !roleErrorKind && <p role="alert">{getErrorMessage(roleApiError)}</p>}
      </div>

      <div>
        <h2>Deactivate user</h2>
        {!deactivateConfirming && (
          <button type="button" disabled={!canEditUsers} onClick={() => setDeactivateConfirming(true)}>
            Deactivate
          </button>
        )}
        {deactivateConfirming && (
          <div>
            <p>Deactivating this user will prevent them from signing in until reactivated.</p>
            <form
              aria-label="Deactivate user"
              onSubmit={handleDeactivateSubmit(onSubmitDeactivate)}
              noValidate
            >
              <div>
                <label htmlFor="user-detail-deactivate-reason">Reason</label>
                <input
                  id="user-detail-deactivate-reason"
                  type="text"
                  {...registerDeactivate("reason", { required: "Reason is required." })}
                />
                {deactivateErrors.reason && <p role="alert">{deactivateErrors.reason.message}</p>}
                <FieldError fieldErrors={deactivateFieldErrors} field="reason" />
              </div>
              <button type="submit" disabled={deactivateMutation.isPending}>
                Confirm deactivation
              </button>
              <button type="button" onClick={() => setDeactivateConfirming(false)}>
                Cancel
              </button>
            </form>
          </div>
        )}
        {deactivateErrorKind && (
          <ErrorState kind={deactivateErrorKind} onRetry={() => deactivateMutation.reset()} />
        )}
        {deactivateApiError && !deactivateErrorKind && !deactivateFieldErrors && (
          <p role="alert">{getErrorMessage(deactivateApiError)}</p>
        )}
      </div>

      <div>
        <h2>Resend invite</h2>
        <button
          type="button"
          disabled={!canEditUsers || resendMutation.isPending}
          onClick={handleResendInvite}
        >
          Resend invite
        </button>
        {resendConfirmed && <p role="status">Invite resent.</p>}
        {resendApiError && <p role="alert">{getErrorMessage(resendApiError)}</p>}
      </div>
    </section>
  );
}
