"use client";

import { useQuery } from "@tanstack/react-query";

import { useSession } from "@/components/providers/session-provider";
import { reconciliationQueries } from "@/features/reconciliation/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import type { NavBadge } from "@/lib/nav";

/**
 * Live counts for nav badges and the notifications bell (not shown to agents). Across all
 * branches the discrepancy count includes gateway mismatches, which belong to no branch, so it
 * matches the discrepancies list.
 */
export function useNavBadges(): Partial<Record<NavBadge, number>> {
  const user = useSession();
  const { branch } = useBranchScope();
  const { data } = useQuery({
    ...reconciliationQueries.branchSummary(branch ? { branch } : {}),
    enabled: user.role !== "AGENT",
    refetchInterval: 60_000,
  });
  if (!data) return {};
  return {
    pendingSubmissions: data.totals.pending_submissions,
    openDiscrepancies: data.totals.open_discrepancies,
    delayedDeposits: data.totals.delayed_deposits,
  };
}
