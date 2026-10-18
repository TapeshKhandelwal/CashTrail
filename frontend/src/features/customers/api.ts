import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/api/query-keys";
import type {
  AgentRouteDue,
  Customer,
  CustomerCreateInput,
  CustomerDetail,
  CustomerFilters,
  CustomerUpdateInput,
  ID,
  ListParams,
  LoanSummary,
  Paginated,
} from "@/types/domain";

export type CustomerListParams = CustomerFilters & ListParams;

export const customerQueries = {
  list: (params: CustomerListParams = {}) =>
    queryOptions({
      queryKey: qk.customers.list(params),
      queryFn: ({ signal }) => api.get<Paginated<Customer>>("customers", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  detail: (id: ID) =>
    queryOptions({
      queryKey: qk.customers.detail(id),
      queryFn: ({ signal }) => api.get<CustomerDetail>(`customers/${id}`, undefined, { signal }),
    }),
  loans: (id: ID) =>
    queryOptions({
      queryKey: qk.customers.loans(id),
      queryFn: ({ signal }) => api.get<Paginated<LoanSummary>>(`customers/${id}/loans`, undefined, { signal }),
    }),
  /** The signed-in agent's route: overdue first, then due today. `due` narrows the list. */
  agentRoute: (params: { due?: AgentRouteDue; search?: string; page?: number; page_size?: number } = {}) =>
    queryOptions({
      queryKey: qk.customers.agentRoute(params),
      queryFn: ({ signal }) => api.get<Paginated<Customer>>("agent/customers", params, { signal }),
      placeholderData: keepPreviousData,
    }),
};

export function useCreateCustomer(options?: ApiMutationOptions<CustomerDetail, CustomerCreateInput>) {
  return useApiMutation(
    (body: CustomerCreateInput) => api.post<CustomerDetail>("customers", body).then((r) => r.data),
    {
      invalidate: [qk.customers.all],
      successMessage: (customer) => `${customer.full_name} added as ${customer.customer_code}`,
      ...options,
    },
  );
}

export function useUpdateCustomer(options?: ApiMutationOptions<CustomerDetail, CustomerUpdateInput & { id: ID }>) {
  return useApiMutation(
    ({ id, ...body }: CustomerUpdateInput & { id: ID }) =>
      api.patch<CustomerDetail>(`customers/${id}`, body).then((r) => r.data),
    { invalidate: [qk.customers.all], successMessage: "Customer updated", ...options },
  );
}

/** `agentId: null` removes the assignment. */
export function useAssignCustomer(options?: ApiMutationOptions<CustomerDetail, { id: ID; agentId: ID | null }>) {
  return useApiMutation(
    ({ id, agentId }: { id: ID; agentId: ID | null }) =>
      api.post<CustomerDetail>(`customers/${id}/assign`, { agent_id: agentId }).then((r) => r.data),
    {
      invalidate: [qk.customers.all, qk.loans.all],
      successMessage: (customer) =>
        customer.assigned_agent_name ? `Assigned to ${customer.assigned_agent_name}` : "Assignment removed",
      ...options,
    },
  );
}
