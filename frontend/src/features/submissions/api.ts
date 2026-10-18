import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api } from "@/lib/api/client";
import { MONEY_KEYS, qk } from "@/lib/api/query-keys";
import type {
  CashSubmission,
  CashSubmissionDetail,
  ID,
  ListParams,
  Paginated,
  SubmissionApproveInput,
  SubmissionCreateInput,
  SubmissionFilters,
  SubmissionRejectInput,
} from "@/types/domain";

export type SubmissionListParams = SubmissionFilters & ListParams;

export const submissionQueries = {
  list: (params: SubmissionListParams = {}) =>
    queryOptions({
      queryKey: qk.submissions.list(params),
      queryFn: ({ signal }) => api.get<Paginated<CashSubmission>>("submissions", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  detail: (id: ID) =>
    queryOptions({
      queryKey: qk.submissions.detail(id),
      queryFn: ({ signal }) => api.get<CashSubmissionDetail>(`submissions/${id}`, undefined, { signal }),
    }),
};

/** Agent hands cash over to the branch. `PENDING_SUBMISSION_EXISTS` means one is already waiting. */
export function useCreateSubmission(options?: ApiMutationOptions<CashSubmissionDetail, SubmissionCreateInput>) {
  return useApiMutation(
    (body: SubmissionCreateInput, { idempotencyKey }) =>
      api.post<CashSubmissionDetail>("submissions", body, { idempotencyKey }).then((r) => r.data),
    { invalidate: MONEY_KEYS, ...options },
  );
}

export function useApproveSubmission(
  options?: ApiMutationOptions<CashSubmissionDetail, SubmissionApproveInput & { id: ID }>,
) {
  return useApiMutation(
    ({ id, ...body }: SubmissionApproveInput & { id: ID }) =>
      api.post<CashSubmissionDetail>(`submissions/${id}/approve`, body).then((r) => r.data),
    { invalidate: MONEY_KEYS, ...options },
  );
}

export function useRejectSubmission(
  options?: ApiMutationOptions<CashSubmissionDetail, SubmissionRejectInput & { id: ID }>,
) {
  return useApiMutation(
    ({ id, ...body }: SubmissionRejectInput & { id: ID }) =>
      api.post<CashSubmissionDetail>(`submissions/${id}/reject`, body).then((r) => r.data),
    { invalidate: MONEY_KEYS, ...options },
  );
}
