"use client";

import type { LucideIcon } from "lucide-react";
import {
  parseAsArrayOf,
  parseAsBoolean,
  parseAsInteger,
  parseAsString,
  useQueryStates,
  type ParserMap,
} from "nuqs";
import { useCallback, useMemo } from "react";

export interface FilterOption {
  value: string;
  label: string;
  icon?: LucideIcon;
}

/**
 * A filter the FilterBar renders and the URL stores. The URL key doubles as the API query
 * param unless `param` says otherwise (date ranges use their `from`/`to` keys directly).
 */
export type FilterDef =
  | { type: "multi"; key: string; label: string; options: readonly FilterOption[]; param?: string }
  | { type: "select"; key: string; label: string; options: readonly FilterOption[]; param?: string }
  | { type: "boolean"; key: string; label: string; param?: string }
  | { type: "dateRange"; label: string; from: string; to: string };

export type FilterValue = string | string[] | boolean | null;

export interface DataTableStateOptions {
  /** Declare at module scope so parsers stay stable. */
  filters?: readonly FilterDef[];
  /** Backend ordering, e.g. "-collected_at". */
  defaultOrdering?: string;
  defaultPageSize?: number;
  /** Namespaces URL keys when two tables share a page. */
  prefix?: string;
}

export const PAGE_SIZES = [10, 25, 50, 100] as const;

const EMPTY: readonly FilterDef[] = [];

function filterKeys(filter: FilterDef): string[] {
  return filter.type === "dateRange" ? [filter.from, filter.to] : [filter.key];
}

function parserFor(filter: FilterDef) {
  switch (filter.type) {
    case "multi":
      return parseAsArrayOf(parseAsString);
    case "boolean":
      return parseAsBoolean;
    default:
      return parseAsString;
  }
}

/**
 * URL-synced state for a server-paginated table: page, page size, ordering, search and filters.
 * `query` is ready to pass to a `features/*` list query.
 *
 *   const state = useDataTableState({ filters: COLLECTION_FILTERS, defaultOrdering: "-collected_at" });
 *   const collections = useQuery(collectionQueries.list(state.query));
 *   <DataTable state={state} … toolbar={<FilterBar state={state} />} />
 */
export function useDataTableState({
  filters = EMPTY,
  defaultOrdering,
  defaultPageSize = 25,
  prefix,
}: DataTableStateOptions = {}) {
  const urlKey = useCallback((key: string) => (prefix ? `${prefix}_${key}` : key), [prefix]);

  const parsers = useMemo(() => {
    const map: ParserMap = {
      [urlKey("page")]: parseAsInteger.withDefault(1),
      [urlKey("size")]: parseAsInteger.withDefault(defaultPageSize),
      [urlKey("sort")]: parseAsString,
      [urlKey("q")]: parseAsString,
    };
    for (const filter of filters) {
      for (const key of filterKeys(filter)) map[urlKey(key)] = parserFor(filter);
    }
    return map;
  }, [filters, defaultPageSize, urlKey]);

  const [params, setParams] = useQueryStates(parsers, { history: "replace", clearOnDefault: true });

  const page = (params[urlKey("page")] as number) ?? 1;
  const pageSize = (params[urlKey("size")] as number) ?? defaultPageSize;
  const ordering = (params[urlKey("sort")] as string | null) ?? defaultOrdering ?? null;
  const search = (params[urlKey("q")] as string | null) ?? "";

  const values = useMemo(() => {
    const result: Record<string, FilterValue> = {};
    for (const filter of filters) {
      for (const key of filterKeys(filter)) result[key] = (params[urlKey(key)] as FilterValue) ?? null;
    }
    return result;
  }, [filters, params, urlKey]);

  const setFilters = useCallback(
    (changes: Record<string, FilterValue>) => {
      const update: Record<string, FilterValue> = { [urlKey("page")]: null };
      for (const [key, value] of Object.entries(changes)) {
        update[urlKey(key)] = Array.isArray(value) && value.length === 0 ? null : value === false ? null : value;
      }
      void setParams(update);
    },
    [setParams, urlKey],
  );

  const resetFilters = useCallback(() => {
    const cleared: Record<string, null> = { [urlKey("page")]: null, [urlKey("q")]: null };
    for (const filter of filters) for (const key of filterKeys(filter)) cleared[urlKey(key)] = null;
    void setParams(cleared);
  }, [filters, setParams, urlKey]);

  const activeFilterCount =
    filters.filter((filter) =>
      filterKeys(filter).some((key) => {
        const value = values[key];
        return Array.isArray(value) ? value.length > 0 : value !== null && value !== false;
      }),
    ).length + (search ? 1 : 0);

  const query = useMemo(() => {
    const result: Record<string, string | string[] | number | boolean> = { page, page_size: pageSize };
    if (ordering) result.ordering = ordering;
    if (search) result.search = search;
    for (const filter of filters) {
      if (filter.type === "dateRange") {
        if (values[filter.from]) result[filter.from] = values[filter.from] as string;
        if (values[filter.to]) result[filter.to] = values[filter.to] as string;
        continue;
      }
      const value = values[filter.key];
      if (value === null || value === false || (Array.isArray(value) && value.length === 0)) continue;
      result[filter.param ?? filter.key] = value;
    }
    return result;
  }, [filters, ordering, page, pageSize, search, values]);

  return {
    filters,
    page,
    pageSize,
    ordering,
    search,
    values,
    activeFilterCount,
    query,
    setPage: (next: number) => void setParams({ [urlKey("page")]: next }),
    setPageSize: (next: number) => void setParams({ [urlKey("size")]: next, [urlKey("page")]: null }),
    setOrdering: (next: string | null) => void setParams({ [urlKey("sort")]: next, [urlKey("page")]: null }),
    setSearch: (next: string) => void setParams({ [urlKey("q")]: next || null, [urlKey("page")]: null }),
    setFilters,
    resetFilters,
  };
}

export type DataTableState = ReturnType<typeof useDataTableState>;
