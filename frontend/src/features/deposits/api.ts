import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api } from "@/lib/api/client";
import { MONEY_KEYS, qk } from "@/lib/api/query-keys";
import type {
  BankAccount,
  BankAccountWriteInput,
  Deposit,
  DepositCreateInput,
  DepositDetail,
  DepositFailInput,
  DepositFilters,
  DepositSettleInput,
  ID,
  ListParams,
  Paginated,
  PendingCash,
} from "@/types/domain";

export type DepositListParams = DepositFilters & ListParams;

export const depositQueries = {
  list: (params: DepositListParams = {}) =>
    queryOptions({
      queryKey: qk.deposits.list(params),
      queryFn: ({ signal }) => api.get<Paginated<Deposit>>("deposits", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  /** Deposit with its submissions, discrepancies and reconciliation chain. */
  detail: (id: ID) =>
    queryOptions({
      queryKey: qk.deposits.detail(id),
      queryFn: ({ signal }) => api.get<DepositDetail>(`deposits/${id}`, undefined, { signal }),
    }),
  /** Approved branch cash awaiting deposit ("Cash at branch to deposit"). */
  pendingCash: (params: { branch?: ID } = {}) =>
    queryOptions({
      queryKey: qk.deposits.pendingCash(params),
      queryFn: ({ signal }) => api.get<PendingCash>("deposits/pending-cash", params, { signal }),
    }),
};

export const bankAccountQueries = {
  list: (params: { is_active?: boolean; is_gateway?: boolean } & ListParams = {}) =>
    queryOptions({
      queryKey: qk.bankAccounts.list(params),
      queryFn: ({ signal }) => api.get<Paginated<BankAccount>>("bank-accounts", params, { signal }),
      staleTime: 5 * 60_000,
    }),
};

/** `DUPLICATE_BANK_REFERENCE` (409) should be shown inline on the slip reference field. */
export function useCreateDeposit(options?: ApiMutationOptions<DepositDetail, DepositCreateInput>) {
  return useApiMutation(
    (body: DepositCreateInput, { idempotencyKey }) =>
      api.post<DepositDetail>("deposits", body, { idempotencyKey }).then((r) => r.data),
    { invalidate: MONEY_KEYS, handledErrors: ["DUPLICATE_BANK_REFERENCE"], ...options },
  );
}

export function useSettleDeposit(options?: ApiMutationOptions<DepositDetail, DepositSettleInput & { id: ID }>) {
  return useApiMutation(
    ({ id, ...body }: DepositSettleInput & { id: ID }) =>
      api.post<DepositDetail>(`deposits/${id}/settle`, body).then((r) => r.data),
    { invalidate: MONEY_KEYS, ...options },
  );
}

export function useFailDeposit(options?: ApiMutationOptions<DepositDetail, DepositFailInput & { id: ID }>) {
  return useApiMutation(
    ({ id, ...body }: DepositFailInput & { id: ID }) =>
      api.post<DepositDetail>(`deposits/${id}/fail`, body).then((r) => r.data),
    { invalidate: MONEY_KEYS, successMessage: (deposit) => `${deposit.deposit_number} marked failed`, ...options },
  );
}

export function useCreateBankAccount(options?: ApiMutationOptions<BankAccount, BankAccountWriteInput>) {
  return useApiMutation(
    (body: BankAccountWriteInput) => api.post<BankAccount>("bank-accounts", body).then((r) => r.data),
    { invalidate: [qk.bankAccounts.all], successMessage: "Bank account added", ...options },
  );
}

export function useUpdateBankAccount(
  options?: ApiMutationOptions<BankAccount, Partial<BankAccountWriteInput> & { id: ID }>,
) {
  return useApiMutation(
    ({ id, ...body }: Partial<BankAccountWriteInput> & { id: ID }) =>
      api.patch<BankAccount>(`bank-accounts/${id}`, body).then((r) => r.data),
    { invalidate: [qk.bankAccounts.all], successMessage: "Bank account updated", ...options },
  );
}
