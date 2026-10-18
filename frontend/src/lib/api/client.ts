/**
 * Browser API client. Every call goes through the BFF (`/api/proxy/*`), which attaches the
 * httpOnly session and refreshes it; components never handle tokens.
 *
 *   api.get<Paginated<Collection>>("collections", { status: ["COLLECTED"], page: 2 })
 *   api.post<CollectionDetail>("collections", body, { idempotencyKey })
 */
import { ApiError, networkError, toApiError } from "./errors";
import { trimPath, withQuery } from "./query-string";

const BASE = "/api/proxy";

export interface RequestOptions {
  /** Required by money-moving creates; reuse the same key when retrying the same form. */
  idempotencyKey?: string;
  signal?: AbortSignal;
  headers?: HeadersInit;
}

export interface ApiResponse<T> {
  data: T;
  /** True when the server returned the original result of an earlier identical request. */
  replayed: boolean;
}

function url(path: string, params?: object): string {
  return withQuery(`${BASE}/${trimPath(path)}`, params);
}

async function send(path: string, init: RequestInit, params?: object): Promise<Response> {
  const attempt = () =>
    fetch(url(path, params), { ...init, credentials: "same-origin", cache: "no-store" });
  let response: Response;
  try {
    response = await attempt();
    // A parallel request may have just rotated the session; the browser now holds the new cookie.
    if (response.status === 401) response = await attempt();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw networkError();
  }
  if (response.status === 401) redirectToLogin();
  if (!response.ok) throw await toApiError(response);
  return response;
}

/** Fired when the session can't be refreshed; the app shell sends the user to /login. */
export const SESSION_EXPIRED_EVENT = "cashtrail:session-expired";

function redirectToLogin(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

function headers(options: RequestOptions, json: boolean): Headers {
  const result = new Headers(options.headers);
  result.set("Accept", "application/json");
  if (json) result.set("Content-Type", "application/json");
  if (options.idempotencyKey) result.set("Idempotency-Key", options.idempotencyKey);
  return result;
}

async function parse<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function request<T>(
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  path: string,
  body: unknown,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const response = await send(path, {
    method,
    headers: headers(options, body !== undefined),
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: options.signal,
  });
  return { data: await parse<T>(response), replayed: response.headers.get("idempotent-replayed") === "true" };
}

export interface Download {
  blob: Blob;
  filename: string;
}

export const api = {
  async get<T>(path: string, params?: object, options: RequestOptions = {}): Promise<T> {
    const response = await send(
      path,
      { method: "GET", headers: headers(options, false), signal: options.signal },
      params,
    );
    return parse<T>(response);
  },

  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, body ?? {}, options),
  patch: <T>(path: string, body: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, body, options),
  delete: <T = void>(path: string, options?: RequestOptions) =>
    request<T>("DELETE", path, undefined, options),

  /** Streams a CSV (or any attachment) and returns it with the server-suggested filename. */
  async download(path: string, params?: object, options: RequestOptions = {}): Promise<Download> {
    const response = await send(path, { method: "GET", signal: options.signal }, params);
    const disposition = response.headers.get("content-disposition") ?? "";
    const filename = /filename="?([^";]+)"?/i.exec(disposition)?.[1] ?? trimPath(path).split("/").at(-1) ?? "download";
    return { blob: await response.blob(), filename };
  },
};

/** Triggers a browser download for a fetched file. */
export function saveFile({ blob, filename }: Download): void {
  const href = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1_000);
}

export { ApiError };
