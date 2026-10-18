"use client";

import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { ApiError, networkError, toApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/query-keys";
import type { SessionUser } from "@/lib/auth/tokens";
import { clearRuntimeCaches } from "@/lib/pwa";

export interface LoginInput {
  username: string;
  password: string;
  next?: string | null;
}

export interface LoginResult {
  user: SessionUser;
  redirectTo: string;
}

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    });
  } catch {
    throw networkError();
  }
  if (!response.ok) throw await toApiError(response);
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const authQueries = {
  /** Fresh profile from Django (the shell renders from the session cookie without this). */
  me: () =>
    queryOptions({
      queryKey: qk.me,
      queryFn: async ({ signal }) => {
        const response = await fetch("/api/auth/me", { signal, credentials: "same-origin" });
        if (!response.ok) throw await toApiError(response);
        return (await response.json()) as SessionUser;
      },
      staleTime: 5 * 60_000,
    }),
};

/** Signs in through the BFF (cookies are set server-side), then navigates to the role's home. */
export function useLogin() {
  const router = useRouter();
  return useMutation<LoginResult, ApiError, LoginInput>({
    mutationFn: (input) => postJson<LoginResult>("/api/auth/login", input),
    onSuccess: ({ redirectTo }) => {
      router.replace(redirectTo);
      router.refresh();
    },
  });
}

/** Blacklists the refresh token, clears cookies, cached queries and SW runtime caches. */
export function useLogout() {
  const router = useRouter();
  const queryClient = useQueryClient();
  return useMutation<void, ApiError>({
    mutationFn: () => postJson<void>("/api/auth/logout"),
    onSettled: () => {
      clearRuntimeCaches();
      queryClient.clear();
      router.replace("/login");
      router.refresh();
    },
  });
}
