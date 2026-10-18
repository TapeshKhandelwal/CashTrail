import { cookies } from "next/headers";

import {
  API_URL,
  COOKIE,
  isExpiring,
  refreshTokens,
  toSessionUser,
  writeSessionCookies,
  writeUserCookie,
} from "@/lib/auth/tokens";
import { clientHeaders } from "@/lib/server/request-guard";
import type { User } from "@/types/domain";

/** Current profile from Django; also refreshes the cached profile cookie. */
export async function GET(request: Request) {
  const store = await cookies();
  let access = store.get(COOKIE.access)?.value;
  const refresh = store.get(COOKIE.refresh)?.value;

  if (refresh && isExpiring(access, 10)) {
    const rotated = await refreshTokens(refresh, clientHeaders(request));
    if (rotated) {
      access = rotated.access;
      writeSessionCookies(store, rotated);
    }
  }
  if (!access) {
    return Response.json(
      { error: { code: "SESSION_EXPIRED", message: "Your session has ended. Sign in again.", details: {} } },
      { status: 401 },
    );
  }

  const upstream = await fetch(`${API_URL}/auth/me/`, {
    headers: { Authorization: `Bearer ${access}`, Accept: "application/json" },
    cache: "no-store",
  }).catch(() => null);

  if (!upstream) {
    return Response.json(
      { error: { code: "UPSTREAM_UNAVAILABLE", message: "CashTrail's server isn't responding.", details: {} } },
      { status: 502 },
    );
  }
  if (!upstream.ok) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  }

  const user = toSessionUser((await upstream.json()) as User);
  writeUserCookie(store, user, store.get(COOKIE.refresh)?.value);
  return Response.json(user, { headers: { "cache-control": "no-store" } });
}
