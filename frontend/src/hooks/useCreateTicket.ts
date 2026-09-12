// FR-3/FR-4, OD-6's binding resolution (implementation_plan v2 Change 8): owns
// `Idempotency-Key` minting. A UUIDv4 is minted lazily on the first
// `mutate()`/`mutateAsync()` call for this hook instance's lifetime (one per
// mounted form — unmounting NewTicketScreen.tsx and remounting it, e.g. by
// navigating away and back, discards the key entirely, per FR-4's "not
// persisted across a full reload"). That exact key is reused verbatim on a
// resubmission whose subject/body/category are byte-identical to the
// previous attempt (TK-AC4's verbatim-retry case); any field edit before
// resubmitting mints a new key instead (OD-6's binding case), so the
// backend's IdempotencyKeyReuseError 422 is never reached for a genuinely
// different composition.
import { useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { createTicket } from "../api/supportApi";
import type { CreateTicketRequest, TicketRead } from "../api/types";

export interface CreateTicketFormValues {
  subject: string;
  body: string;
  category: string;
}

function isSamePayload(a: CreateTicketFormValues, b: CreateTicketFormValues): boolean {
  return a.subject === b.subject && a.body === b.body && a.category === b.category;
}

export function useCreateTicket() {
  const keyRef = useRef<string | null>(null);
  const previousPayloadRef = useRef<CreateTicketFormValues | null>(null);

  return useMutation<TicketRead, unknown, CreateTicketFormValues>({
    mutationFn: (values) => {
      const previous = previousPayloadRef.current;
      const isVerbatimRetry = previous !== null && isSamePayload(previous, values);
      if (keyRef.current === null || !isVerbatimRetry) {
        keyRef.current = crypto.randomUUID();
      }
      previousPayloadRef.current = values;

      const payload: CreateTicketRequest = {
        subject: values.subject,
        body: values.body,
        category: values.category,
        attachment_ids: [],
      };
      return createTicket(payload, keyRef.current);
    },
  });
}
