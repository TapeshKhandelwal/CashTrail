import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { qk } from "@/lib/api/query-keys";
import type { AgentsSummary, BranchSummary, SummaryParams } from "@/types/domain";

export const reconciliationQueries = {
  /** Flows over the date range plus positions as of now. Managers see their own branch. */
  branchSummary: (params: SummaryParams = {}) =>
    queryOptions({
      queryKey: qk.reconciliation.branchSummary(params),
      queryFn: ({ signal }) => api.get<BranchSummary>("reconciliation/branch-summary", params, { signal }),
    }),
  /** Per-agent collections, hand-overs and cash-in-hand ageing. Agents see themselves. */
  agentsSummary: (params: SummaryParams = {}) =>
    queryOptions({
      queryKey: qk.reconciliation.agentsSummary(params),
      queryFn: ({ signal }) => api.get<AgentsSummary>("reconciliation/agents-summary", params, { signal }),
    }),
};
