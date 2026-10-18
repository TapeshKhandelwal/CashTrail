"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { toast } from "sonner";

import { useIdempotencyKey } from "@/hooks/use-idempotency-key";
import { ApiError, type ApiErrorCode } from "@/lib/api/errors";

/** `useQuery` typed with `ApiError`; prefer passing a `queryOptions` factory from `features/*`. */
export function useApiQuery<TData, TKey extends QueryKey = QueryKey>(
  options: UseQueryOptions<TData, ApiError, TData, TKey>,
) {
  return useQuery(options);
}

export interface MutationContext {
  /** Stable for this mutation instance until a call succeeds. */
  idempotencyKey: string;
}

export interface ApiMutationOptions<TData, TVariables>
  extends Omit<UseMutationOptions<TData, ApiError, TVariables>, "mutationFn"> {
  /** Query keys (prefixes) to invalidate after success. */
  invalidate?: readonly QueryKey[];
  /** Toast on success. */
  successMessage?: string | ((data: TData, variables: TVariables) => string);
  /**
   * Error codes the screen handles itself (inline field errors, duplicate dialogs, ...);
   * these never raise a toast. Pass `true` to silence every error toast.
   */
  handledErrors?: readonly ApiErrorCode[] | true;
}

/**
 * `useMutation` with the app's conventions: an Idempotency-Key per mutation instance (rotated
 * after success), invalidation, and a friendly error toast unless the screen handles the code.
 *
 *   const record = useApiMutation(
 *     (body: CollectionCreateInput, { idempotencyKey }) =>
 *       api.post<CollectionDetail>("collections", body, { idempotencyKey }).then((r) => r.data),
 *     { invalidate: MONEY_KEYS, handledErrors: ["POSSIBLE_DUPLICATE", "OVER_COLLECTION"] },
 *   );
 */
export function useApiMutation<TData, TVariables = void>(
  mutationFn: (variables: TVariables, context: MutationContext) => Promise<TData>,
  {
    invalidate,
    successMessage,
    handledErrors,
    onSuccess,
    onError,
    ...options
  }: ApiMutationOptions<TData, TVariables> = {},
) {
  const queryClient = useQueryClient();
  const { key, rotate } = useIdempotencyKey();

  const mutation = useMutation<TData, ApiError, TVariables>({
    ...options,
    mutationFn: (variables) => mutationFn(variables, { idempotencyKey: key }),
    onSuccess: async (data, variables, onMutateResult, context) => {
      rotate();
      if (invalidate?.length) {
        await Promise.all(invalidate.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
      }
      if (successMessage) {
        toast.success(typeof successMessage === "function" ? successMessage(data, variables) : successMessage);
      }
      await onSuccess?.(data, variables, onMutateResult, context);
    },
    onError: async (error, variables, onMutateResult, context) => {
      const handled =
        handledErrors === true || (error instanceof ApiError && handledErrors?.some((code) => error.is(code)));
      if (!handled) notifyError(error);
      await onError?.(error, variables, onMutateResult, context);
    },
  });

  return { ...mutation, idempotencyKey: key, resetIdempotencyKey: rotate };
}

/** Error toast with the friendly message; errors that need action stay until dismissed. */
export function notifyError(error: unknown, fallback = "That didn't go through."): void {
  if (error instanceof ApiError) {
    toast.error(error.friendlyMessage, {
      description: error.requestId ? `Reference ${error.requestId}` : undefined,
      duration: error.status === 409 || error.status === 422 ? Infinity : 6_000,
    });
    return;
  }
  toast.error(fallback);
}
