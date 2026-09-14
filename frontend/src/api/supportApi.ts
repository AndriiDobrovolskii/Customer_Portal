import { httpDelete, httpGet, httpPost } from "./httpClient";
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
  AgentTicketListResponse,
  AssignTicketRequest,
  AgentTicketStateRead,
  ResolveTicketRequest,
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

// US-5.5 FR-1: the agent branch of GET /support/tickets — same URL as
// listTickets, but typed to AgentTicketListResponse and accepting
// assignee_id (the backend discriminates the response shape server-side by
// caller scope, per router.py's response_model=TicketListResponse |
// AgentTicketListResponse — not by a query flag this function invents).
// Resolution OD-2: assignee_id is sent verbatim (the literal "me"/"none" or
// a raw UUID string) with no client-side substitution or validation.
export function listAgentTickets(params: {
  status?: string;
  category?: string;
  assignee_id?: string;
  cursor?: string;
  limit?: number;
}): Promise<AgentTicketListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.category) query.set("category", params.category);
  if (params.assignee_id) query.set("assignee_id", params.assignee_id);
  if (params.cursor) query.set("cursor", params.cursor);
  if (params.limit !== undefined) query.set("limit", params.limit.toString());

  const queryString = query.toString();
  const url = `/support/tickets${queryString ? `?${queryString}` : ""}`;
  return httpGet<AgentTicketListResponse>(url);
}

// FR-2: "assign to me" (data.assignee_id === caller's own id) and "assign to
// another agent" (Resolution OD-2's raw-UUID input) both call this same
// endpoint.
export function assignTicket(id: string, data: AssignTicketRequest): Promise<AgentTicketStateRead> {
  return httpPost<AgentTicketStateRead>(`/support/tickets/${id}/assign`, data);
}

// FR-2: DELETE .../assign, via the existing httpDelete<T> verb with no body.
export function unassignTicket(id: string): Promise<AgentTicketStateRead> {
  return httpDelete<AgentTicketStateRead>(`/support/tickets/${id}/assign`);
}

// FR-5: a non-empty resolution_note.
export function resolveTicket(id: string, data: ResolveTicketRequest): Promise<TicketStateRead> {
  return httpPost<TicketStateRead>(`/support/tickets/${id}/resolve`, data);
}
