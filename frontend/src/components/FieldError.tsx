// FE-AC9's 422 errors[] -> per-field renderer. Consumed by every form.
export interface FieldErrorProps {
  fieldErrors?: Record<string, string>;
  field: string;
}

export function FieldError({ fieldErrors, field }: FieldErrorProps) {
  const message = fieldErrors?.[field];
  if (!message) {
    return null;
  }
  return (
    <p role="alert" data-field={field}>
      {message}
    </p>
  );
}
