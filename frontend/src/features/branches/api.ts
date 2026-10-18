import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/api/query-keys";
import type { Branch, BranchCreateInput, BranchUpdateInput, ID, ListParams, Paginated } from "@/types/domain";

export const branchQueries = {
  list: (params: { is_active?: boolean; city?: string } & ListParams = {}) =>
    queryOptions({
      queryKey: qk.branches.list(params),
      queryFn: ({ signal }) => api.get<Paginated<Branch>>("branches", params, { signal }),
      placeholderData: keepPreviousData,
      staleTime: 5 * 60_000,
    }),
  /** All active branches for pickers (branch switcher, filters). */
  options: () =>
    queryOptions({
      queryKey: qk.branches.list({ is_active: true, page_size: 100 }),
      queryFn: ({ signal }) =>
        api.get<Paginated<Branch>>("branches", { is_active: true, page_size: 100 }, { signal }),
      select: (page) => page.results,
      staleTime: 5 * 60_000,
    }),
  detail: (id: ID) =>
    queryOptions({
      queryKey: qk.branches.detail(id),
      queryFn: ({ signal }) => api.get<Branch>(`branches/${id}`, undefined, { signal }),
    }),
};

export function useCreateBranch(options?: ApiMutationOptions<Branch, BranchCreateInput>) {
  return useApiMutation((body: BranchCreateInput) => api.post<Branch>("branches", body).then((r) => r.data), {
    invalidate: [qk.branches.all],
    successMessage: (branch) => `Branch ${branch.code} created`,
    ...options,
  });
}

export function useUpdateBranch(options?: ApiMutationOptions<Branch, BranchUpdateInput & { id: ID }>) {
  return useApiMutation(
    ({ id, ...body }: BranchUpdateInput & { id: ID }) => api.patch<Branch>(`branches/${id}`, body).then((r) => r.data),
    { invalidate: [qk.branches.all], successMessage: "Branch updated", ...options },
  );
}
