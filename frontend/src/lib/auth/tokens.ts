/**
 * Token plumbing shared by `proxy.ts` and the BFF route handlers (Node runtime only).
 * Tokens live exclusively in httpOnly cookies; the browser never sees them.
 */
import type { Role, User } from "@/types/domain";

import { isRole } from "./access";

export const API_URL = (process.env.API_URL ?? "http://localhost:8000/api").replace(/\/+$/, "");

export const COOKIE = {
  access: "ct_access",
  refresh: "ct_refresh",
  user: "ct_user",
} as const;

export interface TokenPair {
  access: string;
  refresh: string;
}

export interface AccessClaims {
  userId: number;
  role: Role;
  branchId: number | null;
  branchCode: string | null;
  /** Expiry, seconds since epoch. */
  exp: number;
}

/** The profile kept in the `ct_user` cookie for rendering the shell without a round trip. */
export type SessionUser = Pick<
  User,
  "id" | "username" | "first_name" | "full_name" | "email" | "role" | "branch" | "branch_code" | "branch_name"
>;

export function toSessionUser(user: User): SessionUser {
  const { id, username, first_name, full_name, email, role, branch, branch_code, branch_name } = user;
  return { id, username, first_name, full_name: full_name || username, email, role, branch, branch_code, branch_name };
}

function decodeSegment(segment: string): unknown {
  try {
    return JSON.parse(Buffer.from(segment, "base64url").toString("utf8"));
  } catch {
    return null;
  }
}

/** Reads (does not verify) the access token's claims; Django verifies on every API call. */
export function decodeAccess(token: string | undefined): AccessClaims | null {
  const payload = token?.split(".")[1];
  if (!payload) return null;
  const claims = decodeSegment(payload) as Record<string, unknown> | null;
  if (!claims || !isRole(claims.role) || typeof claims.exp !== "number") return null;
  return {
    userId: Number(claims.user_id),
    role: claims.role,
    branchId: typeof claims.branch_id === "number" ? claims.branch_id : null,
    branchCode: typeof claims.branch_code === "string" ? claims.branch_code : null,
    exp: claims.exp,
  };
}

/** True when the token is missing, unreadable or expires within `skewSeconds`. */
export function isExpiring(token: string | undefined, skewSeconds = 60): boolean {
  const claims = decodeAccess(token);
  return !claims || claims.exp * 1000 <= Date.now() + skewSeconds * 1000;
}

function tokenExpiry(token: string): number | null {
  const payload = token.split(".")[1];
  const claims = payload ? (decodeSegment(payload) as { exp?: unknown } | null) : null;
  return typeof claims?.exp === "number" ? claims.exp : null;
}

export function encodeUser(user: SessionUser): string {
  return Buffer.from(JSON.stringify(user), "utf8").toString("base64url");
}

export function decodeUser(value: string | undefined): SessionUser | null {
  if (!value) return null;
  const user = decodeSegment(value) as SessionUser | null;
  return user && isRole(user.role) && typeof user.id === "number" ? user : null;
}

interface CookieWriter {
  set(name: string, value: string, options: CookieOptions): unknown;
}

interface CookieOptions {
  httpOnly: boolean;
  secure: boolean;
  sameSite: "lax";
  path: string;
  maxAge: number;
}

function cookieOptions(expiresAt: number | null): CookieOptions {
  const maxAge = expiresAt ? Math.max(0, expiresAt - Math.floor(Date.now() / 1000)) : 60 * 60 * 24;
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge,
  };
}

export function writeSessionCookies(
  cookies: CookieWriter,
  tokens: TokenPair,
  user?: SessionUser,
): void {
  cookies.set(COOKIE.access, tokens.access, cookieOptions(tokenExpiry(tokens.access)));
  cookies.set(COOKIE.refresh, tokens.refresh, cookieOptions(tokenExpiry(tokens.refresh)));
  if (user) writeUserCookie(cookies, user, tokens.refresh);
}

/** The profile cookie lives as long as the refresh token it belongs to. */
export function writeUserCookie(cookies: CookieWriter, user: SessionUser, refresh?: string): void {
  cookies.set(COOKIE.user, encodeUser(user), cookieOptions(refresh ? tokenExpiry(refresh) : null));
}

export function clearSessionCookies(cookies: { delete(name: string): unknown }): void {
  for (const name of Object.values(COOKIE)) cookies.delete(name);
}

/*
 * Refresh tokens rotate and the old one is blacklisted on first use, so concurrent requests
 * holding the same refresh token must share a single refresh call. The map lives on
 * globalThis because proxy.ts and each route handler are bundled separately but share the
 * Node process; results are kept briefly so stragglers with the old cookie still succeed.
 */
const REFRESH_REUSE_MS = 30_000;
type RefreshStore = Map<string, Promise<TokenPair | null>>;
const store = globalThis as typeof globalThis & { __ctRefreshes?: RefreshStore };
const inflight: RefreshStore = (store.__ctRefreshes ??= new Map());

/** `headers` carries the browser's address for Django's throttle (see `clientHeaders`). */
export function refreshTokens(refresh: string, headers: Record<string, string> = {}): Promise<TokenPair | null> {
  const existing = inflight.get(refresh);
  if (existing) return existing;

  const attempt = fetch(`${API_URL}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", ...headers },
    body: JSON.stringify({ refresh }),
    cache: "no-store",
  })
    .then(async (response) => {
      if (!response.ok) return null;
      const body = (await response.json()) as Partial<TokenPair>;
      return body.access ? { access: body.access, refresh: body.refresh ?? refresh } : null;
    })
    .catch(() => null);

  inflight.set(refresh, attempt);
  setTimeout(() => inflight.delete(refresh), REFRESH_REUSE_MS);
  return attempt;
}
