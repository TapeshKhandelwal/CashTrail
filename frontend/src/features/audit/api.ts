import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { qk } from "@/lib/api/query-keys";
import type { AuditLog, AuditLogFilters, ID, ListParams, Paginated } from "@/types/domain";

export type AuditListParams = AuditLogFilters & ListParams;

export const auditQueries = {
  list: (params: AuditListParams = {}) =>
    queryOptions({
      queryKey: qk.audit.list(params),
      queryFn: ({ signal }) => api.get<Paginated<AuditLog>>("audit-logs", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  detail: (id: ID) =>
    queryOptions({
      queryKey: qk.audit.detail(id),
      queryFn: ({ signal }) => api.get<AuditLog>(`audit-logs/${id}`, undefined, { signal }),
    }),
};
