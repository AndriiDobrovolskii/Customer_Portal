// AD-AC3/FR-3: /admin/users/new. Exactly email/display_name/roles — no
// password field anywhere in this form. Resolution OD-4: `roles`'s
// selectable options are sourced only from useAdminRoles.ts (GET
// /admin/roles), never free text. On 201 the admin lands on the new user's
// detail screen. XC-AC3: an invalid email shape or an empty role selection
// blocks submission with a field-level error and no API call. Composed from
// hooks/ and shared components/ only — never api/ or fetch directly
// (AGENTS.md §3).
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { useCreateAdminUser } from "../hooks/useCreateAdminUser";
import { useAdminRoles } from "../hooks/useAdminRoles";
import { ErrorState } from "../components/ErrorState";
import { FieldError } from "../components/FieldError";
import { getErrorKind, getErrorMessage, getFieldErrors } from "../components/apiErrorHelpers";
import type { CreateAdminUserRequest } from "../api/types";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface CreateUserFormValues {
  email: string;
  display_name: string;
  roles: string[];
}

export function AdminUserCreateScreen() {
  const navigate = useNavigate();
  const rolesQuery = useAdminRoles();
  const createMutation = useCreateAdminUser();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateUserFormValues>({ defaultValues: { email: "", display_name: "", roles: [] } });

  async function onSubmit(values: CreateUserFormValues) {
    const payload: CreateAdminUserRequest = {
      email: values.email,
      display_name: values.display_name,
      roles: values.roles,
    };
    try {
      const created = await createMutation.mutateAsync(payload);
      navigate(`/admin/users/${created.id}`);
    } catch {
      // surfaced via createMutation.error below
    }
  }

  const apiError = createMutation.isError ? createMutation.error : null;
  const errorKind = getErrorKind(apiError);
  const fieldErrors = getFieldErrors(apiError);

  if (rolesQuery.isPending) {
    return (
      <section>
        <h1>Create user</h1>
        <p>Loading role catalogue…</p>
      </section>
    );
  }

  if (rolesQuery.isError) {
    const rolesErrorKind = getErrorKind(rolesQuery.error);
    return (
      <section>
        <h1>Create user</h1>
        {rolesErrorKind ? (
          <ErrorState kind={rolesErrorKind} onRetry={() => rolesQuery.refetch()} />
        ) : (
          <p role="alert">{getErrorMessage(rolesQuery.error)}</p>
        )}
      </section>
    );
  }

  const roleOptions = rolesQuery.data.roles;

  return (
    <section>
      <h1>Create user</h1>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div>
          <label htmlFor="create-user-email">Email</label>
          <input
            id="create-user-email"
            type="email"
            {...register("email", {
              required: "Email is required.",
              pattern: { value: EMAIL_PATTERN, message: "Enter a valid email address." },
            })}
          />
          {errors.email && <p role="alert">{errors.email.message}</p>}
          <FieldError fieldErrors={fieldErrors} field="email" />
        </div>
        <div>
          <label htmlFor="create-user-display-name">Display name</label>
          <input
            id="create-user-display-name"
            type="text"
            {...register("display_name", { required: "Display name is required." })}
          />
          {errors.display_name && <p role="alert">{errors.display_name.message}</p>}
          <FieldError fieldErrors={fieldErrors} field="display_name" />
        </div>
        <div>
          <label htmlFor="create-user-roles">Roles</label>
          <select
            id="create-user-roles"
            multiple
            {...register("roles", {
              validate: (value) => value.length > 0 || "Select at least one role.",
            })}
          >
            {roleOptions.map((role) => (
              <option key={role.name} value={role.name}>
                {role.name}
              </option>
            ))}
          </select>
          {errors.roles && <p role="alert">{errors.roles.message}</p>}
          <FieldError fieldErrors={fieldErrors} field="roles" />
        </div>
        <button type="submit" disabled={createMutation.isPending}>
          Create user
        </button>
      </form>

      {errorKind && <ErrorState kind={errorKind} onRetry={() => handleSubmit(onSubmit)()} />}
      {apiError && !errorKind && !fieldErrors && <p role="alert">{getErrorMessage(apiError)}</p>}
    </section>
  );
}
