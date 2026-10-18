"use client";

import { X } from "lucide-react";

import { DateRangeFilter } from "@/components/data-table/date-range-filter";
import { FacetedFilter } from "@/components/data-table/faceted-filter";
import { Button } from "@/components/ui/button";
import { COLLECTION_STATUS_OPTIONS, useAgentOptions, useBranchOptions } from "@/hooks/use-filter-options";

import type { DashboardFilters } from "./use-dashboard-filters";

/** Voided receipts are counted on their own, outside every total, so they are not a cut. */
const RECEIPT_STATUS_OPTIONS = COLLECTION_STATUS_OPTIONS.filter((option) => option.value !== "VOIDED");

/**
 * Date, branch (global roles) and agent cut every figure on the page. Receipt status narrows only
 * the figures made of receipts; the page says which while it is set.
 */
export function DashboardFilterBar({ filters }: { filters: DashboardFilters }) {
  const branchOptions = useBranchOptions(filters.canSwitch);
  const agentOptions = useAgentOptions(filters.branch ?? undefined);
  const { values } = filters;

  return (
    <div
      className="flex flex-wrap items-center gap-2 max-sm:-my-1.5 max-sm:flex-nowrap max-sm:scrollbar-none max-sm:overflow-x-auto max-sm:py-1.5 max-sm:pr-6 max-sm:mask-r-from-[calc(100%-1.5rem)]"
      role="search"
      aria-label="Dashboard filters"
    >
      <DateRangeFilter
        label="This month"
        value={{ from: values.date_from ?? undefined, to: values.date_to ?? undefined }}
        onChange={filters.setRange}
      />
      {filters.canSwitch && (
        <FacetedFilter
          label="Branch"
          single
          options={branchOptions}
          selected={filters.branch ? [String(filters.branch)] : []}
          onChange={(next) => filters.setBranch(next[0] ? Number(next[0]) : null)}
        />
      )}
      <FacetedFilter
        label="Agent"
        single
        options={agentOptions}
        selected={values.agent ? [String(values.agent)] : []}
        onChange={(next) => filters.setAgent(next[0] ? Number(next[0]) : null)}
      />
      <FacetedFilter
        label="Receipt status"
        single
        options={RECEIPT_STATUS_OPTIONS}
        selected={values.status ? [values.status] : []}
        onChange={(next) => filters.setStatus(next[0] ?? null)}
      />
      {filters.active && (
        <Button variant="ghost" size="sm" onClick={filters.reset} className="font-normal">
          Reset
          <X data-icon="inline-end" />
        </Button>
      )}
    </div>
  );
}
