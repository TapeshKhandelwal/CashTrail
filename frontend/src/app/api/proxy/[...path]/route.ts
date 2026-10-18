import { cookies } from "next/headers";
import type { NextRequest } from "next/server";

import {
  API_URL,
  COOKIE,
  isExpiring,
  refreshTokens,
  writeSessionCookies,
  type TokenPair,
} from "@/lib/auth/tokens";
import { clientHeaders, rejectCrossSite } from "@/lib/server/request-guard";

/**
 * BFF proxy: `/api/proxy/<path>` -> `${API_URL}/<path>/` with the session's bearer token.
 * Refreshes once on 401 (rotating the cookies), forwards Idempotency-Key and streams the
 * response body through untouched so CSV exports never buffer in memory. Writes must come
 * from CashTrail's own pages.
 */

const FORWARD_REQUEST_HEADERS = ["accept", "content-type", "idempotency-key", "accept-language"];
const FORWARD_RESPONSE_HEADERS = [
  "content-type",
  "content-disposition",
  "idempotent-replayed",
  "retry-after",
  "x-request-id",
];
const SEGMENT = /^[\w.@~-]+$/;

function errorResponse(status: number, code: string, message: string): Response {
  return Response.json({ error: { code, message, details: {} } }, { status });
}

function targetUrl(segments: string[], search: string): string | null {
  if (segments.some((segment) => !SEGMENT.test(segment) || segment === "." || segment === "..")) {
    return null;
  }
  const path = segments.join("/");
  // Django routes end in "/", except file-style endpoints such as reports/collections.csv.
  const suffix = /\.[a-z0-9]+$/i.test(path) ? "" : "/";
  return `${API_URL}/${path}${suffix}${search}`;
}

async function handle(request: NextRequest, ctx: RouteContext<"/api/proxy/[...path]">) {
  const { path } = await ctx.params;
  const target = targetUrl(path, request.nextUrl.search);
  if (!target) return errorResponse(400, "INVALID_PATH", "That API path is not allowed.");
  if (!["GET", "HEAD"].includes(request.method)) {
    const crossSite = rejectCrossSite(request);
    if (crossSite) return crossSite;
  }

  const store = await cookies();
  let access = store.get(COOKIE.access)?.value;
  const refresh = store.get(COOKIE.refresh)?.value;
  if (!access && !refresh) {
    return errorResponse(401, "SESSION_EXPIRED", "Your session has ended. Sign in again.");
  }

  let rotated: TokenPair | null = null;
  if (refresh && isExpiring(access, 10)) {
    rotated = await refreshTokens(refresh, clientHeaders(request));
    if (rotated) access = rotated.access;
  }

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  for (const [name, value] of Object.entries(clientHeaders(request))) headers.set(name, value);
  const userAgent = request.headers.get("user-agent");
  if (userAgent) headers.set("user-agent", userAgent);

  // Buffered so the request can be replayed after a refresh (bodies here are small JSON).
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();

  const call = (token: string | undefined) => {
    const outgoing = new Headers(headers);
    if (token) outgoing.set("authorization", `Bearer ${token}`);
    return fetch(target, {
      method: request.method,
      headers: outgoing,
      body,
      cache: "no-store",
      redirect: "manual",
      signal: request.signal,
    });
  };

  let upstream: Response;
  try {
    upstream = await call(access);
    if (upstream.status === 401 && refresh && !rotated) {
      rotated = await refreshTokens(refresh, clientHeaders(request));
      if (rotated) upstream = await call(rotated.access);
    }
  } catch (error) {
    if (request.signal.aborted) throw error;
    return errorResponse(502, "UPSTREAM_UNAVAILABLE", "CashTrail's server isn't responding.");
  }

  if (rotated) writeSessionCookies(store, rotated);

  if (upstream.status === 401) {
    return errorResponse(401, "SESSION_EXPIRED", "Your session has ended. Sign in again.");
  }

  const responseHeaders = new Headers({ "cache-control": "no-store" });
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
export const PUT = handle;
export const DELETE = handle;
