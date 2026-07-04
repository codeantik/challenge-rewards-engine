import { API_BASE_URL } from "@/lib/config";

export interface Envelope<T> {
  data: T;
  meta?: Record<string, unknown> | null;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string;
}

/** Mirrors the error envelope's `error` object from CLAUDE.md — thrown by
 * `apiRequest` for every non-2xx response so callers can branch on `code`
 * instead of parsing `message` strings. */
export class ApiError extends Error {
  code: string;
  status: number;
  details: unknown;
  requestId?: string;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
    this.requestId = body.request_id;
  }
}

/** Dispatched whenever a request comes back 401 so a single listener
 * (`AuthProvider`) can clear the stored session and redirect — keeps token
 * expiry handling out of every individual query/mutation. */
export const AUTH_UNAUTHORIZED_EVENT = "cre:unauthorized";

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
}

/** Returns the full `{data, meta}` envelope — for callers (e.g. paginated
 * lists) that need `meta` alongside `data`. `apiRequest` below is the common
 * case that just wants `data`. */
export async function apiRequestEnvelope<T>(
  path: string,
  options: RequestOptions = {},
): Promise<Envelope<T>> {
  const { method = "GET", body, token, signal } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (response.status === 204) {
    return { data: undefined as T };
  }

  const json = (await response.json()) as Envelope<T> | { error: ApiErrorBody };

  if (!response.ok) {
    const errorBody = (json as { error: ApiErrorBody }).error;
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(AUTH_UNAUTHORIZED_EVENT));
    }
    throw new ApiError(response.status, errorBody);
  }

  return json as Envelope<T>;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const envelope = await apiRequestEnvelope<T>(path, options);
  return envelope.data;
}
