import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api } from "@/lib/api/client";
import { MONEY_KEYS, qk } from "@/lib/api/query-keys";
import type {
  Discrepancy,
  DiscrepancyCreateInput,
  DiscrepancyFilters,
  DiscrepancyResolveInput,
  ID,
  ListParams,
  Paginated,
} from "@/types/domain";

export type DiscrepancyListParams = DiscrepancyFilters & ListParams;

export const discrepancyQueries = {
  list: (params: DiscrepancyListParams = {}) =>
    queryOptions({
      queryKey: qk.discrepancies.list(params),
      queryFn: ({ signal }) => api.get<Paginated<Discrepancy>>("discrepancies", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  detail: (id: ID) =>
    queryOptions({
      queryKey: qk.discrepancies.detail(id),
      queryFn: ({ signal }) => api.get<Discrepancy>(`discrepancies/${id}`, undefined, { signal }),
    }),
};

export function useRaiseDiscrepancy(options?: ApiMutationOptions<Discrepancy, DiscrepancyCreateInput>) {
  return useApiMutation(
    (body: DiscrepancyCreateInput) => api.post<Discrepancy>("discrepancies", body).then((r) => r.data),
    { invalidate: MONEY_KEYS, successMessage: "Discrepancy logged", ...options },
  );
}

/** Resolve or write off; cash ones by the branch, deposit/gateway ones by finance (admin: all). */
export function useResolveDiscrepancy(
  options?: ApiMutationOptions<Discrepancy, DiscrepancyResolveInput & { id: ID }>,
) {
  return useApiMutation(
    ({ id, ...body }: DiscrepancyResolveInput & { id: ID }) =>
      api.post<Discrepancy>(`discrepancies/${id}/resolve`, body).then((r) => r.data),
    {
      invalidate: MONEY_KEYS,
      successMessage: (_, { outcome }) => (outcome === "RESOLVED" ? "Discrepancy resolved" : "Discrepancy written off"),
      ...options,
    },
  );
}
