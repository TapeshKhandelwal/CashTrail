import "server-only";

import { cookies } from "next/headers";
import { forbidden, redirect } from "next/navigation";
import { cache } from "react";

import type { Role } from "@/types/domain";

import { LOGIN_PATH } from "./access";
import { COOKIE, decodeAccess, decodeUser, type SessionUser } from "./tokens";

export interface Session {
  user: SessionUser;
  accessToken: string;
}

/**
 * The signed-in user for Server Components, read from cookies once per request.
 * `proxy.ts` refreshes tokens before rendering, so a valid session always has an access token.
 * Reading cookies is request-time data: call this only inside a <Suspense> boundary.
 */
export const getSession = cache(async (): Promise<Session | null> => {
  const store = await cookies();
  const accessToken = store.get(COOKIE.access)?.value;
  const claims = decodeAccess(accessToken);
  if (!accessToken || !claims) return null;

  const profile = decodeUser(store.get(COOKIE.user)?.value);
  // The access token is authoritative for identity and role; the profile only adds names.
  const user: SessionUser =
    profile && profile.id === claims.userId
      ? { ...profile, role: claims.role, branch: claims.branchId, branch_code: claims.branchCode }
      : {
          id: claims.userId,
          username: "",
          first_name: "",
          full_name: "",
          email: "",
          role: claims.role,
          branch: claims.branchId,
          branch_code: claims.branchCode,
          branch_name: null,
        };
  return { user, accessToken };
});

export async function requireSession(): Promise<Session> {
  const session = await getSession();
  if (!session) redirect(LOGIN_PATH);
  return session;
}

/** Renders the nearest `forbidden.tsx` when the signed-in role is not allowed. */
export async function requireRole(...roles: Role[]): Promise<Session> {
  const session = await requireSession();
  if (!roles.includes(session.user.role)) forbidden();
  return session;
}
