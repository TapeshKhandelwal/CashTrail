import { cookies } from "next/headers";

import { API_URL, COOKIE, clearSessionCookies } from "@/lib/auth/tokens";
import { clientHeaders, rejectCrossSite } from "@/lib/server/request-guard";

export async function POST(request: Request) {
  const crossSite = rejectCrossSite(request);
  if (crossSite) return crossSite;

  const store = await cookies();
  const refresh = store.get(COOKIE.refresh)?.value;

  if (refresh) {
    // Blacklist the refresh token; the session ends locally even if Django is unreachable.
    await fetch(`${API_URL}/auth/logout/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", ...clientHeaders(request) },
      body: JSON.stringify({ refresh }),
      cache: "no-store",
    }).catch(() => undefined);
  }

  clearSessionCookies(store);
  return new Response(null, { status: 204 });
}
