"use client";

import { parseAsInteger, parseAsString, useQueryStates } from "nuqs";
import { useMemo } from "react";

import { useBranchScope } from "@/hooks/use-branch-scope";
import type { DashboardParams } from "@/types/domain";

const PARSERS = {
  date_from: parseAsString,
  date_to: parseAsString,
  agent: parseAsInteger,
  status: parseAsString,
};

/**
 * Dashboard filters, all in the URL so a view can be shared. Branch comes from the shared
 * branch scope (global roles pick it; branch roles are pinned to their own). With no dates the
 * server defaults to month-to-date.
 */
export function useDashboardFilters() {
  const { branch, canSwitch, setBranch } = useBranchScope();
  const [values, setValues] = useQueryStates(PARSERS, { history: "replace", clearOnDefault: true });

  const params = useMemo<DashboardParams>(() => {
    const result: DashboardParams = {};
    if (values.date_from) result.date_from = values.date_from;
    if (values.date_to) result.date_to = values.date_to;
    if (canSwitch && branch) result.branch = branch;
    if (values.agent) result.agent = values.agent;
    // Voided receipts sit outside every total, so the server does not accept them as a cut.
    if (values.status && values.status !== "VOIDED") result.status = values.status as DashboardParams["status"];
    return result;
  }, [branch, canSwitch, values]);

  const active = Boolean(values.date_from || values.agent || values.status || (canSwitch && branch));

  return {
    params,
    values,
    branch,
    canSwitch,
    active,
    setBranch: (next: number | null) => {
      setBranch(next);
      void setValues({ agent: null });
    },
    setRange: (range: { from: string | null; to: string | null }) =>
      void setValues({ date_from: range.from, date_to: range.to }),
    setAgent: (agent: number | null) => void setValues({ agent }),
    setStatus: (status: string | null) => void setValues({ status }),
    reset: () => {
      if (canSwitch) setBranch(null);
      void setValues({ date_from: null, date_to: null, agent: null, status: null });
    },
  };
}

export type DashboardFilters = ReturnType<typeof useDashboardFilters>;
