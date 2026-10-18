import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { qk } from "@/lib/api/query-keys";
import type {
  AgentRow,
  BranchRow,
  DashboardParams,
  DashboardSummary,
  Lifecycle,
  ListParams,
  Paginated,
  TrendPoint,
} from "@/types/domain";

/** All dashboard endpoints share filters; branch/agent must be inside the caller's scope. */
export const dashboardQueries = {
  summary: (params: DashboardParams = {}) =>
    queryOptions({
      queryKey: qk.dashboard.summary(params),
      queryFn: ({ signal }) => api.get<DashboardSummary>("dashboard/summary", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  /** Daily expected / collected / settled. The range may span at most 366 days. */
  trend: (params: DashboardParams = {}) =>
    queryOptions({
      queryKey: qk.dashboard.trend(params),
      queryFn: ({ signal }) => api.get<TrendPoint[]>("dashboard/trend", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  lifecycle: (params: DashboardParams = {}) =>
    queryOptions({
      queryKey: qk.dashboard.lifecycle(params),
      queryFn: ({ signal }) => api.get<Lifecycle>("dashboard/lifecycle", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  /** Supervisors only. */
  branches: (params: DashboardParams & ListParams = {}) =>
    queryOptions({
      queryKey: qk.dashboard.branches(params),
      queryFn: ({ signal }) => api.get<Paginated<BranchRow>>("dashboard/branches", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  /** Supervisors only. */
  agents: (params: DashboardParams & ListParams = {}) =>
    queryOptions({
      queryKey: qk.dashboard.agents(params),
      queryFn: ({ signal }) => api.get<Paginated<AgentRow>>("dashboard/agents", params, { signal }),
      placeholderData: keepPreviousData,
    }),
};
