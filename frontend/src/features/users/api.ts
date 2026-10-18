import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/api/query-keys";
import type {
  ID,
  ListParams,
  Paginated,
  UserCreateInput,
  UserDetail,
  UserFilters,
  UserUpdateInput,
} from "@/types/domain";

export type UserListParams = UserFilters & ListParams;

export const userQueries = {
  /** Admins see everyone; branch managers see their branch's agents; finance reads all. */
  list: (params: UserListParams = {}) =>
    queryOptions({
      queryKey: qk.users.list(params),
      queryFn: ({ signal }) => api.get<Paginated<UserDetail>>("users", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  /** Active agents for pickers ("Assign agent", agent filters). */
  agents: (branch?: ID) =>
    queryOptions({
      queryKey: qk.users.list({ role: "AGENT", branch, is_active: true, page_size: 100 }),
      queryFn: ({ signal }) =>
        api.get<Paginated<UserDetail>>(
          "users",
          { role: "AGENT", branch, is_active: true, page_size: 100 },
          { signal },
        ),
      select: (page) => page.results,
      staleTime: 5 * 60_000,
    }),
  detail: (id: ID) =>
    queryOptions({
      queryKey: qk.users.detail(id),
      queryFn: ({ signal }) => api.get<UserDetail>(`users/${id}`, undefined, { signal }),
    }),
};

export function useCreateUser(options?: ApiMutationOptions<UserDetail, UserCreateInput>) {
  return useApiMutation((body: UserCreateInput) => api.post<UserDetail>("users", body).then((r) => r.data), {
    invalidate: [qk.users.all, qk.branches.all],
    successMessage: (user) => `${user.full_name || user.username} can now sign in`,
    ...options,
  });
}

export function useUpdateUser(options?: ApiMutationOptions<UserDetail, UserUpdateInput & { id: ID }>) {
  return useApiMutation(
    ({ id, ...body }: UserUpdateInput & { id: ID }) => api.patch<UserDetail>(`users/${id}`, body).then((r) => r.data),
    { invalidate: [qk.users.all], successMessage: "User updated", ...options },
  );
}

/** Deactivating also revokes the user's sessions. */
export function useSetUserActive(options?: ApiMutationOptions<UserDetail, { id: ID; active: boolean }>) {
  return useApiMutation(
    ({ id, active }: { id: ID; active: boolean }) =>
      api.post<UserDetail>(`users/${id}/${active ? "activate" : "deactivate"}`).then((r) => r.data),
    {
      invalidate: [qk.users.all, qk.branches.all],
      successMessage: (user) => `${user.username} ${user.is_active ? "reactivated" : "deactivated"}`,
      ...options,
    },
  );
}

export function useSetUserPassword(options?: ApiMutationOptions<void, { id: ID; password: string }>) {
  return useApiMutation(
    ({ id, password }: { id: ID; password: string }) =>
      api.post<void>(`users/${id}/set-password`, { password }).then(() => undefined),
    { successMessage: "Password changed and sessions revoked", ...options },
  );
}
