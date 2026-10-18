import { isServer, QueryClient } from "@tanstack/react-query";

import { ApiError } from "./errors";

declare module "@tanstack/react-query" {
  interface Register {
    defaultError: ApiError;
  }
}

/** Client errors (4xx) are final; only network and 5xx failures are worth retrying. */
function shouldRetry(failureCount: number, error: ApiError): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  return failureCount < 2;
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: shouldRetry,
        refetchOnWindowFocus: true,
      },
      mutations: {
        // Money moves are never retried automatically; the user retries with the same key.
        retry: false,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

export function getQueryClient(): QueryClient {
  if (isServer) return makeQueryClient();
  browserQueryClient ??= makeQueryClient();
  return browserQueryClient;
}
