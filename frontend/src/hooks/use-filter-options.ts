"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { branchQueries } from "@/features/branches/api";
import { userQueries } from "@/features/users/api";
import type { FilterOption } from "@/hooks/use-data-table-state";
import { COLLECTION_STATUSES, type ID } from "@/types/domain";
import { collectionStatus } from "@/lib/status";

/** Active branches as filter options ("BLR01 · Bengaluru Central"); value is the branch id. */
export function useBranchOptions(enabled = true): FilterOption[] {
  const { data } = useQuery({ ...branchQueries.options(), enabled });
  return useMemo(
    () => (data ?? []).map((branch) => ({ value: String(branch.id), label: `${branch.code} · ${branch.name}` })),
    [data],
  );
}

/** Active agents (optionally one branch's) as filter options; value is the user id. */
export function useAgentOptions(branch?: ID | null, enabled = true): FilterOption[] {
  const { data } = useQuery({ ...userQueries.agents(branch ?? undefined), enabled });
  return useMemo(
    () => (data ?? []).map((agent) => ({ value: String(agent.id), label: agent.full_name || agent.username })),
    [data],
  );
}

/** Collection lifecycle statuses, labelled from lib/status. */
export const COLLECTION_STATUS_OPTIONS: FilterOption[] = COLLECTION_STATUSES.map((status) => ({
  value: status,
  label: collectionStatus(status).label,
}));
