// FR-3/FR-4/FR-10 (TK-AC3, TK-AC4, TK-AC10, TK-AC12, TK-AC13, TK-AC14's 403
// clause, TK-AC11's 422 clause), OD-2/OD-5. Subject/body/category via
// react-hook-form's built-in required/maxLength rules (LoginScreen.tsx's
// existing validation pattern) — no new validation/UI/component library.
// `category` is a plain text <input maxLength={50}> (OD-2), no <select>.
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { useCreateTicket, type CreateTicketFormValues } from "../hooks/useCreateTicket";
import { useRetryAfterCountdown } from "../hooks/useRetryAfterCountdown";
import { ErrorState } from "../components/ErrorState";
import { FieldError } from "../components/FieldError";
import {
  getErrorKind,
  getErrorMessage,
  getFieldErrors,
  getRetryAfterSeconds,
} from "../components/apiErrorHelpers";

export function NewTicketScreen() {
  const navigate = useNavigate();
  const createTicketMutation = useCreateTicket();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<CreateTicketFormValues>();

  async function onSubmit(values: CreateTicketFormValues) {
    try {
      const ticket = await createTicketMutation.mutateAsync(values);
      navigate(`/tickets/${ticket.id}`);
    } catch {
      // surfaced via createTicketMutation.error below
    }
  }

  const apiError = createTicketMutation.isError ? createTicketMutation.error : null;
  const errorKind = getErrorKind(apiError);
  const fieldErrors = getFieldErrors(apiError);
  const retryAfterSeconds = getRetryAfterSeconds(apiError);
  const { secondsRemaining, isBlocked } = useRetryAfterCountdown(retryAfterSeconds);

  return (
    <section>
      <h1>New ticket</h1>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div>
          <label htmlFor="new-ticket-subject">Subject</label>
          <input
            id="new-ticket-subject"
            type="text"
            {...register("subject", {
              required: "Subject is required.",
              maxLength: { value: 150, message: "Subject must be 150 characters or fewer." },
            })}
          />
          {errors.subject && <p role="alert">{errors.subject.message}</p>}
          <FieldError fieldErrors={fieldErrors} field="subject" />
        </div>
        <div>
          <label htmlFor="new-ticket-body">Body</label>
          <textarea
            id="new-ticket-body"
            {...register("body", {
              required: "Body is required.",
              maxLength: { value: 5000, message: "Body must be 5000 characters or fewer." },
            })}
          />
          {errors.body && <p role="alert">{errors.body.message}</p>}
          <FieldError fieldErrors={fieldErrors} field="body" />
        </div>
        <div>
          <label htmlFor="new-ticket-category">Category</label>
          <input
            id="new-ticket-category"
            type="text"
            maxLength={50}
            {...register("category", {
              required: "Category is required.",
              maxLength: { value: 50, message: "Category must be 50 characters or fewer." },
            })}
          />
          {errors.category && <p role="alert">{errors.category.message}</p>}
          <FieldError fieldErrors={fieldErrors} field="category" />
        </div>
        <button type="submit" disabled={createTicketMutation.isPending || isBlocked}>
          Create ticket
        </button>
      </form>

      {isBlocked && <p role="alert">You can try again in {secondsRemaining} seconds.</p>}

      {errorKind && <ErrorState kind={errorKind} onRetry={() => onSubmit(getValues())} />}
      {Boolean(apiError) && !errorKind && !fieldErrors && !isBlocked && (
        <p role="alert">{getErrorMessage(apiError)}</p>
      )}
    </section>
  );
}
