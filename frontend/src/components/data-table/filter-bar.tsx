"use client";

import { Search, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/toggle";
import type { DataTableState } from "@/hooks/use-data-table-state";
import { cn } from "@/lib/utils";

import { DateRangeFilter } from "./date-range-filter";
import { FacetedFilter } from "./faceted-filter";

interface FilterBarProps {
  state: DataTableState;
  /** Omit to hide the search box. */
  searchPlaceholder?: string;
  /** Right-aligned extras, e.g. an "Export CSV" button. */
  actions?: ReactNode;
  className?: string;
}

/**
 * One quiet bar of search, filters and reset above a table; every value lives in the URL via
 * `useDataTableState`. Option lists for branch, agent and status come from hooks/use-filter-options.
 * On phones the search takes the full width and the filters scroll sideways in one row.
 *
 *   const FILTERS = [
 *     { type: "multi", key: "status", label: "Status", options: STATUS_OPTIONS },
 *     { type: "select", key: "agent", label: "Agent", options: agentOptions },
 *     { type: "dateRange", label: "Collected", from: "date_from", to: "date_to" },
 *   ] as const satisfies readonly FilterDef[];
 */
export function FilterBar({ state, searchPlaceholder, actions, className }: FilterBarProps) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)} role="search">
      {searchPlaceholder !== undefined && (
        <SearchBox value={state.search} onChange={state.setSearch} placeholder={searchPlaceholder} />
      )}
      <div className="flex items-center gap-2 max-sm:-my-1.5 max-sm:w-full max-sm:scrollbar-none max-sm:overflow-x-auto max-sm:py-1.5 max-sm:pr-6 max-sm:mask-r-from-[calc(100%-1.5rem)] sm:contents">
        {state.filters.map((filter) => {
          switch (filter.type) {
            case "multi":
            case "select": {
              const value = state.values[filter.key];
              const selected = Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
              return (
                <FacetedFilter
                  key={filter.key}
                  label={filter.label}
                  options={filter.options}
                  selected={selected}
                  single={filter.type === "select"}
                  onChange={(next) =>
                    state.setFilters({ [filter.key]: filter.type === "select" ? (next[0] ?? null) : next })
                  }
                />
              );
            }
            case "boolean":
              return (
                <Toggle
                  key={filter.key}
                  variant="outline"
                  size="sm"
                  className="shrink-0 font-normal text-dim aria-pressed:border-ink/25 aria-pressed:text-ink"
                  pressed={state.values[filter.key] === true}
                  onPressedChange={(pressed) => state.setFilters({ [filter.key]: pressed })}
                >
                  {filter.label}
                </Toggle>
              );
            case "dateRange":
              return (
                <DateRangeFilter
                  key={`${filter.from}-${filter.to}`}
                  label={filter.label}
                  value={{
                    from: (state.values[filter.from] as string | null) ?? undefined,
                    to: (state.values[filter.to] as string | null) ?? undefined,
                  }}
                  onChange={({ from, to }) => state.setFilters({ [filter.from]: from, [filter.to]: to })}
                />
              );
          }
        })}
        {state.activeFilterCount > 0 && (
          <Button variant="ghost" size="sm" onClick={state.resetFilters} className="font-normal">
            Reset
            <X data-icon="inline-end" />
          </Button>
        )}
      </div>
      {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
    </div>
  );
}

function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) {
  const [draft, setDraft] = useState(value);
  const [synced, setSynced] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // The URL changed from elsewhere (reset, back button): show it.
  if (value !== synced) {
    setSynced(value);
    setDraft(value);
  }

  useEffect(() => () => clearTimeout(timer.current), []);

  return (
    <InputGroup className="h-10 w-full sm:h-8 sm:w-64">
      <InputGroupAddon>
        <Search aria-hidden className="text-faint" />
      </InputGroupAddon>
      <InputGroupInput
        type="search"
        inputMode="search"
        enterKeyHint="search"
        aria-label={placeholder}
        placeholder={placeholder}
        value={draft}
        onChange={(event) => {
          const next = event.target.value;
          setDraft(next);
          clearTimeout(timer.current);
          timer.current = setTimeout(() => onChange(next), 300);
        }}
        className="text-base sm:text-[13px]"
      />
    </InputGroup>
  );
}
