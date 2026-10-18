import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api } from "@/lib/api/client";
import { MONEY_KEYS, qk } from "@/lib/api/query-keys";
import type {
  CollectionCreateInput,
  CollectionDetail,
  CollectionFilters,
  Collection,
  DailySummary,
  ID,
  ISODate,
  ListParams,
  Paginated,
} from "@/types/domain";

export type CollectionListParams = CollectionFilters & ListParams;

export const collectionQueries = {
  list: (params: CollectionListParams = {}) =>
    queryOptions({
      queryKey: qk.collections.list(params),
      queryFn: ({ signal }) => api.get<Paginated<Collection>>("collections", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  /** The receipt: allocations, lifecycle timeline and loan balance after it. */
  detail: (id: ID) =>
    queryOptions({
      queryKey: qk.collections.detail(id),
      queryFn: ({ signal }) => api.get<CollectionDetail>(`collections/${id}`, undefined, { signal }),
    }),
  /** Agents: own totals; managers: branch totals (optionally one agent). */
  dailySummary: (params: { date?: ISODate; branch?: ID; agent?: ID } = {}) =>
    queryOptions({
      queryKey: qk.collections.dailySummary(params),
      queryFn: ({ signal }) => api.get<DailySummary>("collections/daily-summary", params, { signal }),
    }),
};

/**
 * Records a cash repayment. Handle `POSSIBLE_DUPLICATE` (retry with `confirm_duplicate: true`,
 * same key) and `OVER_COLLECTION` (inline) in the screen.
 */
export function useRecordCollection(options?: ApiMutationOptions<CollectionDetail, CollectionCreateInput>) {
  return useApiMutation(
    (body: CollectionCreateInput, { idempotencyKey }) =>
      api.post<CollectionDetail>("collections", { mode: "CASH", ...body }, { idempotencyKey }).then((r) => r.data),
    { invalidate: MONEY_KEYS, handledErrors: ["POSSIBLE_DUPLICATE", "OVER_COLLECTION"], ...options },
  );
}

export function useVoidCollection(options?: ApiMutationOptions<CollectionDetail, { id: ID; reason: string }>) {
  return useApiMutation(
    ({ id, reason }: { id: ID; reason: string }) =>
      api.post<CollectionDetail>(`collections/${id}/void`, { reason }).then((r) => r.data),
    { invalidate: MONEY_KEYS, successMessage: (receipt) => `Receipt ${receipt.receipt_number} voided`, ...options },
  );
}
