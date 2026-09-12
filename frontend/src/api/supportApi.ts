import { httpGet, httpPost } from "./httpClient";
import type {
  TicketListResponse,
  CreateTicketRequest,
  TicketRead,
  TicketDetailRead,
  CreateReplyRequest,
  ReplyRead,
  CloseTicketRequest,
  TicketStateRead,
  ReopenTicketRequest,
} from "./types";

export function listTickets(params: {
  status?: string;
  cursor?: string;
  limit?: number;
}): Promise<TicketListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.cursor) query.set("cursor", params.cursor);
  if (params.limit !== undefined) query.set("limit", params.limit.toString());

  const queryString = query.toString();
  const url = `/support/tickets${queryString ? `?${queryString}` : ""}`;
  return httpGet<TicketListResponse>(url);
}

export function createTicket(data: CreateTicketRequest, idempotencyKey: string): Promise<TicketRead> {
  return httpPost<TicketRead>("/support/tickets", data, { idempotencyKey });
}

export function getTicketDetail(
  id: string,
  params?: { cursor?: string; limit?: number },
): Promise<TicketDetailRead> {
  const query = new URLSearchParams();
  if (params?.cursor) query.set("cursor", params.cursor);
  if (params?.limit !== undefined) query.set("limit", params.limit.toString());

  const queryString = query.toString();
  const url = `/support/tickets/${id}${queryString ? `?${queryString}` : ""}`;
  return httpGet<TicketDetailRead>(url);
}

export function replyToTicket(id: string, data: CreateReplyRequest): Promise<ReplyRead> {
  return httpPost<ReplyRead>(`/support/tickets/${id}/replies`, data);
}

export function closeTicket(id: string, data: CloseTicketRequest): Promise<TicketStateRead> {
  return httpPost<TicketStateRead>(`/support/tickets/${id}/close`, data);
}

export function reopenTicket(id: string, data: ReopenTicketRequest): Promise<TicketStateRead> {
  return httpPost<TicketStateRead>(`/support/tickets/${id}/reopen`, data);
}
