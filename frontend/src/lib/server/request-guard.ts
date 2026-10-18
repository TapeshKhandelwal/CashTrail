import "server-only";

/**
 * Checks shared by the BFF route handlers.
 *
 * - `rejectCrossSite`: state-changing requests must come from CashTrail's own pages, so a
 *   form on another site cannot sign a visitor in or out, or act with their session.
 * - `clientHeaders`: Django sees every browser through this server, so the browser's address
 *   travels in `X-Client-IP`, vouched for by the shared secret. The client's own
 *   X-Forwarded-For is never passed on.
 */

const IP_ADDRESS = /^[0-9a-f:.]{2,45}$/i;

function hostOf(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).host.toLowerCase();
  } catch {
    return null;
  }
}

function ownHosts(request: Request): Set<string> {
  const hosts = new Set<string>();
  const forwarded = request.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  for (const host of [forwarded, request.headers.get("host"), hostOf(process.env.NEXT_PUBLIC_APP_URL)]) {
    if (host) hosts.add(host.toLowerCase());
  }
  return hosts;
}

/**
 * Browsers label every request with Sec-Fetch-Site, and send Origin on every POST; pages
 * cannot forge either. A request with neither (and no Referer) is not from a browser, so it
 * carries no visitor's cookies by accident.
 */
export function isSameOrigin(request: Request): boolean {
  const site = request.headers.get("sec-fetch-site");
  if (site) return site === "same-origin" || site === "none";

  const origin = request.headers.get("origin") ?? request.headers.get("referer");
  if (origin === null) return true;
  const host = hostOf(origin);
  return host !== null && ownHosts(request).has(host);
}

export function rejectCrossSite(request: Request): Response | null {
  if (isSameOrigin(request)) return null;
  return Response.json(
    { error: { code: "CROSS_SITE_REQUEST", message: "This request didn't come from CashTrail.", details: {} } },
    { status: 403 },
  );
}

export function isJson(request: Request): boolean {
  const type = request.headers.get("content-type")?.split(";")[0]?.trim().toLowerCase();
  return type === "application/json";
}

/**
 * The address the hosting platform saw. Vercel overwrites X-Forwarded-For with the client's
 * address, and proxies such as Render or nginx append the peer they saw, so the last entry
 * is the trustworthy one. Next fills the header with the socket address when it is missing.
 */
export function clientIp(request: Request): string | null {
  const lastHop = request.headers.get("x-forwarded-for")?.split(",").at(-1)?.trim();
  for (const candidate of [lastHop, request.headers.get("x-real-ip")?.trim()]) {
    if (candidate && IP_ADDRESS.test(candidate)) return candidate;
  }
  return null;
}

export function clientHeaders(request: Request): Record<string, string> {
  const secret = process.env.BFF_SHARED_SECRET;
  const ip = clientIp(request);
  if (!secret || !ip) return {};
  return { "x-client-ip": ip, "x-bff-secret": secret };
}
