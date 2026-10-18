import "server-only";

import { redirect } from "next/navigation";

import { LOGIN_PATH } from "@/lib/auth/access";
import { requireSession } from "@/lib/auth/session";
import { API_URL } from "@/lib/auth/tokens";

import { networkError, toApiError } from "./errors";
import { trimPath, withQuery } from "./query-string";

/**
 * Server Component data access: calls Django directly with the session's access token.
 * Use for initial data in Server Components (inside <Suspense>); client screens use `api`.
 *
 *   const customer = await serverApi.get<CustomerDetail>(`customers/${id}`);
 */
export const serverApi = {
  async get<T>(path: string, params?: object): Promise<T> {
    const { accessToken } = await requireSession();
    const trimmed = trimPath(path);
    const target = /\.[a-z]+$/i.test(trimmed) ? trimmed : `${trimmed}/`;

    let response: Response;
    try {
      response = await fetch(withQuery(`${API_URL}/${target}`, params), {
        headers: { Authorization: `Bearer ${accessToken}`, Accept: "application/json" },
        cache: "no-store",
      });
    } catch {
      throw networkError();
    }
    if (response.status === 401) redirect(LOGIN_PATH);
    if (!response.ok) throw await toApiError(response);
    return (await response.json()) as T;
  },
};
