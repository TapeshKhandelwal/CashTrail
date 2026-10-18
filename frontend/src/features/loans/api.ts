import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/api/query-keys";
import type {
  ID,
  Installment,
  ListParams,
  Loan,
  LoanCreateInput,
  LoanFilters,
  LoanTermsInput,
  Paginated,
  Repayment,
  SchedulePreview,
} from "@/types/domain";

export type LoanListParams = LoanFilters & ListParams;

export const loanQueries = {
  list: (params: LoanListParams = {}) =>
    queryOptions({
      queryKey: qk.loans.list(params),
      queryFn: ({ signal }) => api.get<Paginated<Loan>>("loans", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  detail: (id: ID) =>
    queryOptions({
      queryKey: qk.loans.detail(id),
      queryFn: ({ signal }) => api.get<Loan>(`loans/${id}`, undefined, { signal }),
    }),
  schedule: (id: ID) =>
    queryOptions({
      queryKey: qk.loans.schedule(id),
      queryFn: ({ signal }) => api.get<Installment[]>(`loans/${id}/schedule`, undefined, { signal }),
    }),
  repayments: (id: ID, params: ListParams = {}) =>
    queryOptions({
      queryKey: qk.loans.repayments(id, params),
      queryFn: ({ signal }) => api.get<Paginated<Repayment>>(`loans/${id}/repayments`, params, { signal }),
      placeholderData: keepPreviousData,
    }),
  /** Live EMI and schedule for the "New loan" form; nothing is saved. Debounce the inputs. */
  schedulePreview: (terms: LoanTermsInput) =>
    queryOptions({
      queryKey: qk.loans.schedulePreview(terms),
      queryFn: ({ signal }) => api.get<SchedulePreview>("loans/schedule-preview", terms, { signal }),
      placeholderData: keepPreviousData,
      staleTime: Infinity,
    }),
};

export function useCreateLoan(options?: ApiMutationOptions<Loan, LoanCreateInput>) {
  return useApiMutation((body: LoanCreateInput) => api.post<Loan>("loans", body).then((r) => r.data), {
    invalidate: [qk.loans.all, qk.customers.all, qk.dashboard.all],
    successMessage: (loan) => `Loan ${loan.loan_number} created`,
    ...options,
  });
}

/** Terms are editable only until the first repayment (`terms_locked`). */
export function useUpdateLoanTerms(options?: ApiMutationOptions<Loan, Partial<LoanTermsInput> & { id: ID }>) {
  return useApiMutation(
    ({ id, ...body }: Partial<LoanTermsInput> & { id: ID }) => api.patch<Loan>(`loans/${id}`, body).then((r) => r.data),
    { invalidate: [qk.loans.all, qk.customers.all, qk.dashboard.all], successMessage: "Loan terms updated", ...options },
  );
}
