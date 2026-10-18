import { NextResponse, type NextRequest } from "next/server";

import { canAccess, LOGIN_PATH, ROLE_HOME, safeNextPath } from "@/lib/auth/access";
import {
  COOKIE,
  decodeAccess,
  isExpiring,
  refreshTokens,
  writeSessionCookies,
  type AccessClaims,
  type TokenPair,
} from "@/lib/auth/tokens";
import { clientHeaders } from "@/lib/server/request-guard";

/**
 * Optimistic route guard. Refreshes an expiring access token before the page renders (Server
 * Components cannot set cookies), sends signed-out visitors to /login and keeps each role in
 * its own section. Django still authorises every API call.
 */
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const inApp = pathname === "/app" || pathname.startsWith("/app/");
  const onLogin = pathname === LOGIN_PATH;

  const access = request.cookies.get(COOKIE.access)?.value;
  const refresh = request.cookies.get(COOKIE.refresh)?.value;

  let claims: AccessClaims | null = isExpiring(access) ? null : decodeAccess(access);
  let rotated: TokenPair | null = null;
  if (!claims && refresh && (inApp || onLogin)) {
    rotated = await refreshTokens(refresh, clientHeaders(request));
    claims = rotated ? decodeAccess(rotated.access) : null;
  }

  if (inApp && !claims) {
    const login = new URL(LOGIN_PATH, request.url);
    login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }

  let redirectTo: string | null = null;
  if (claims && onLogin) {
    redirectTo = safeNextPath(request.nextUrl.searchParams.get("next"), claims.role);
  } else if (claims && inApp && (pathname === "/app" || !canAccess(claims.role, pathname))) {
    redirectTo = ROLE_HOME[claims.role];
  }

  if (redirectTo) {
    const response = NextResponse.redirect(new URL(redirectTo, request.url));
    if (rotated) writeSessionCookies(response.cookies, rotated);
    return response;
  }

  if (!rotated) return NextResponse.next();

  // Let this render see the new tokens, and hand them to the browser.
  request.cookies.set(COOKIE.access, rotated.access);
  request.cookies.set(COOKIE.refresh, rotated.refresh);
  const response = NextResponse.next({ request: { headers: request.headers } });
  writeSessionCookies(response.cookies, rotated);
  return response;
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|serwist|manifest.webmanifest|icons|splash|screenshots|landing|~offline|favicon.ico|icon.svg|apple-icon.png|.*\\.(?:png|svg|webp|avif|jpg|ico|txt|xml)$).*)",
  ],
};
