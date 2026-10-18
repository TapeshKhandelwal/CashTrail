import { cookies } from "next/headers";

import { safeNextPath } from "@/lib/auth/access";
import { API_URL, toSessionUser, writeSessionCookies } from "@/lib/auth/tokens";
import { clientHeaders, isJson, rejectCrossSite } from "@/lib/server/request-guard";
import type { User } from "@/types/domain";

interface LoginBody {
  username?: unknown;
  password?: unknown;
  next?: unknown;
}

interface DjangoLogin {
  access: string;
  refresh: string;
  user: User;
}

export async function POST(request: Request) {
  const crossSite = rejectCrossSite(request);
  if (crossSite) return crossSite;
  // A cross-site form can post text/plain without a preflight; JSON it cannot.
  if (!isJson(request)) {
    return Response.json(
      { error: { code: "UNSUPPORTED_MEDIA_TYPE", message: "Send the sign-in details as JSON.", details: {} } },
      { status: 415 },
    );
  }

  const body = (await request.json().catch(() => ({}))) as LoginBody;
  if (typeof body.username !== "string" || typeof body.password !== "string") {
    return Response.json(
      { error: { code: "VALIDATION_ERROR", message: "Enter your username and password.", details: {} } },
      { status: 400 },
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}/auth/login/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...clientHeaders(request),
      },
      body: JSON.stringify({ username: body.username.trim(), password: body.password }),
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { error: { code: "UPSTREAM_UNAVAILABLE", message: "CashTrail's server isn't responding.", details: {} } },
      { status: 502 },
    );
  }

  if (!upstream.ok) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  }

  const { access, refresh, user } = (await upstream.json()) as DjangoLogin;
  const sessionUser = toSessionUser(user);
  writeSessionCookies(await cookies(), { access, refresh }, sessionUser);

  const next = typeof body.next === "string" ? body.next : null;
  return Response.json({ user: sessionUser, redirectTo: safeNextPath(next, user.role) });
}
