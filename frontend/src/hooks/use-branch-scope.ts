"use client";

import { parseAsInteger, useQueryState } from "nuqs";

import { useSession } from "@/components/providers/session-provider";

/**
 * The branch a global user (admin, finance) is looking at, kept in `?branch=` so views are
 * shareable; sidebar links carry it between pages. Branch roles are always scoped to their
 * own branch by the server, so for them this returns their branch and cannot change.
 *
 *   const { branch } = useBranchScope();
 *   useQuery(dashboardQueries.summary({ branch: branch ?? undefined, ...range }));
 */
export function useBranchScope() {
  const user = useSession();
  const [selected, setSelected] = useQueryState("branch", parseAsInteger.withOptions({ history: "replace" }));
  const global = user.role === "ADMIN" || user.role === "FINANCE";
  return {
    branch: global ? selected : user.branch,
    canSwitch: global,
    setBranch: (branch: number | null) => void setSelected(global ? branch : null),
  };
}
