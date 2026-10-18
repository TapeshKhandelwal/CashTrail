"use client";

import {
  useTable,
  type Cell,
  type Row,
  type RowData,
  type RowSelectionState,
  type SortingState,
  type Updater,
} from "@tanstack/react-table";
import { useEffect, useState, type KeyboardEvent, type ReactNode } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton, TableSkeleton } from "@/components/feedback/skeletons";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import type { DataTableState } from "@/hooks/use-data-table-state";
import { cn } from "@/lib/utils";

import { ColumnHeader } from "./column-header";
import { dataTableFeatures, type DataTableColumns, type DataTableFeatures } from "./data-table-features";
import { TablePagination } from "./pagination";
import { SelectionBar } from "./selection-bar";
import { ViewOptions } from "./view-options";

const NO_ROWS: never[] = [];
/** Longer than the row cascade in globals.css (.rows-enter). */
const CASCADE_MS = 900;

export interface DataTableSelection<TData extends RowData> {
  /** Bulk actions for the selected rows (rendered in the floating bar). */
  actions: (rows: TData[]) => ReactNode;
  /** e.g. the selected total: "₹1,42,000". */
  summary?: (rows: TData[]) => ReactNode;
  canSelect?: (row: TData) => boolean;
}

interface DataTableProps<TData extends RowData> {
  columns: DataTableColumns<TData>;
  data: TData[] | undefined;
  /** Total rows on the server (`Paginated.count`). */
  rowCount?: number;
  /** From `useDataTableState`; omit for small client-side lists without paging. */
  state?: DataTableState;
  getRowId?: (row: TData) => string;
  /** Screen-reader caption describing the table. */
  caption: string;
  isLoading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  onRowClick?: (row: TData) => void;
  /** Mobile card; defaults to one built from column `meta.card` slots. */
  renderCard?: (row: TData) => ReactNode;
  /** Filter bar etc., rendered above the table next to the column menu. */
  toolbar?: ReactNode;
  /** Empty state when there are no rows and no filters are active. */
  empty?: ReactNode;
  selection?: DataTableSelection<TData>;
  className?: string;
}

function toSorting(ordering: string | null): SortingState {
  if (!ordering) return [];
  const desc = ordering.startsWith("-");
  return [{ id: desc ? ordering.slice(1) : ordering, desc }];
}

/**
 * Server-driven table in the ledger style: sunk header with mono labels, hairline rows, money
 * right-aligned and tabular, references in mono. URL-synced sorting and paging, column menu,
 * row click, selection, and stacked cards below the `@2xl` container width. Loading, error and
 * empty states are built in.
 */
export function DataTable<TData extends RowData>({
  columns,
  data,
  rowCount,
  state,
  getRowId,
  caption,
  isLoading = false,
  error,
  onRetry,
  onRowClick,
  renderCard,
  toolbar,
  empty,
  selection,
  className,
}: DataTableProps<TData>) {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const rows = data ?? (NO_ROWS as TData[]);
  const sorting = toSorting(state?.ordering ?? null);

  const sortFieldFor = (id: string) =>
    columns.find((column) => (column.id ?? ("accessorKey" in column ? String(column.accessorKey) : "")) === id)?.meta
      ?.sortField ?? id;

  const table = useTable({
    features: dataTableFeatures,
    columns,
    data: rows,
    getRowId: getRowId ? (row) => getRowId(row) : undefined,
    rowCount: rowCount ?? rows.length,
    manualPagination: true,
    manualSorting: true,
    enableMultiSort: false,
    enableSortingRemoval: true,
    enableRowSelection: selection ? (row) => selection.canSelect?.(row.original) ?? true : false,
    defaultColumn: { enableSorting: false },
    state: {
      sorting,
      rowSelection,
      pagination: { pageIndex: (state?.page ?? 1) - 1, pageSize: state?.pageSize ?? Math.max(rows.length, 1) },
    },
    onSortingChange: (updater: Updater<SortingState>) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      const first = next[0];
      state?.setOrdering(first ? `${first.desc ? "-" : ""}${sortFieldFor(first.id)}` : null);
    },
    onRowSelectionChange: setRowSelection,
  });

  const selectedRows = table.getSelectedRowModel().rows.map((row) => row.original);
  const hasFilters = (state?.activeFilterCount ?? 0) > 0;
  const tableRows = table.getRowModel().rows;

  // Rows cascade in on the first load only; once it has played, later pages swap in place.
  const [cascade, setCascade] = useState(true);
  const hasRows = rows.length > 0;
  useEffect(() => {
    if (!hasRows || !cascade) return;
    const timer = setTimeout(() => setCascade(false), CASCADE_MS);
    return () => clearTimeout(timer);
  }, [hasRows, cascade]);

  const toggleable = table
    .getAllLeafColumns()
    .filter((column) => column.getCanHide() && column.columnDef.meta?.card !== "hidden" && column.id !== "select")
    .map((column) => ({
      id: column.id,
      label: column.columnDef.meta?.label ?? (typeof column.columnDef.header === "string" ? column.columnDef.header : column.id),
      visible: column.getIsVisible(),
      toggle: (visible: boolean) => column.toggleVisibility(visible),
    }));

  const activate = (row: Row<DataTableFeatures, TData>) => onRowClick?.(row.original);
  const onRowKey = (event: KeyboardEvent, row: Row<DataTableFeatures, TData>) => {
    if (event.key === "Enter" && event.target === event.currentTarget) activate(row);
  };

  let body: ReactNode;
  if (isLoading && !data) {
    body = (
      <>
        <TableSkeleton className="@max-2xl:hidden" columns={Math.min(columns.length, 6)} />
        <CardListSkeleton className="@2xl:hidden" />
      </>
    );
  } else if (error && !data) {
    body = <ErrorState error={error} onRetry={onRetry} bordered />;
  } else if (rows.length === 0) {
    body = hasFilters ? (
      <EmptyState
        illustration="search"
        title="No results match these filters."
        bordered
        action={
          <Button variant="outline" onClick={state?.resetFilters}>
            Reset filters
          </Button>
        }
      />
    ) : (
      (empty ?? <EmptyState title="Nothing here yet." bordered />)
    );
  } else {
    body = (
      <>
        <div
          className={cn(
            "relative max-h-[calc(100dvh-13rem)] overflow-auto rounded-xl border border-rule bg-raised @max-2xl:hidden",
            isLoading && "opacity-60 transition-opacity",
          )}
        >
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <caption className="sr-only">{caption}</caption>
            <thead className="sticky top-0 z-10">
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id}>
                  {selection && (
                    <th scope="col" className="w-10 border-b border-rule bg-sunk px-4">
                      <Checkbox
                        aria-label="Select all rows on this page"
                        checked={
                          table.getIsAllPageRowsSelected() ? true : table.getIsSomePageRowsSelected() ? "indeterminate" : false
                        }
                        onCheckedChange={(checked) => table.toggleAllPageRowsSelected(checked === true)}
                      />
                    </th>
                  )}
                  {group.headers.map((header) => {
                    const meta = header.column.columnDef.meta;
                    const sorted = header.column.getIsSorted();
                    return (
                      <th
                        key={header.id}
                        scope="col"
                        aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined}
                        className={cn(
                          "h-10 border-b border-rule bg-sunk px-4 text-left align-middle font-mono text-[10.5px] font-normal tracking-[0.12em] whitespace-nowrap text-faint uppercase",
                          meta?.align === "end" && "text-right",
                          meta?.width,
                        )}
                      >
                        {header.isPlaceholder ? null : (
                          <ColumnHeader header={header}>
                            <table.FlexRender header={header} />
                          </ColumnHeader>
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody className={cn(cascade && "rows-enter")}>
              {tableRows.map((row) => (
                <tr
                  key={row.id}
                  data-state={row.getIsSelected() ? "selected" : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  onClick={onRowClick ? () => activate(row) : undefined}
                  onKeyDown={onRowClick ? (event) => onRowKey(event, row) : undefined}
                  className={cn(
                    "group/row transition-colors duration-150 hover:bg-sunk/70 data-[state=selected]:bg-brand-tint",
                    onRowClick && "cursor-pointer outline-none focus-visible:bg-sunk",
                  )}
                >
                  {selection && (
                    <td className="w-10 border-b border-rule px-4 group-last/row:border-b-0" onClick={(event) => event.stopPropagation()}>
                      <Checkbox
                        aria-label="Select row"
                        checked={row.getIsSelected()}
                        disabled={!row.getCanSelect()}
                        onCheckedChange={(checked) => row.toggleSelected(checked === true)}
                      />
                    </td>
                  )}
                  {row.getVisibleCells().map((cell) => {
                    const meta = cell.column.columnDef.meta;
                    return (
                      <td
                        key={cell.id}
                        className={cn(
                          "h-11 border-b border-rule px-4 py-2 align-middle text-ink group-last/row:border-b-0",
                          meta?.align === "end" && "text-right tabular-nums",
                          meta?.mono && "font-mono text-[12.5px] tracking-[0.01em]",
                        )}
                      >
                        <table.FlexRender cell={cell} />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <ul
          className={cn(
            "divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised @2xl:hidden",
            cascade && "rows-enter",
            isLoading && "opacity-60",
          )}
        >
          {tableRows.map((row) => (
            <li key={row.id}>
              {renderCard ? (
                <CardFrame onClick={onRowClick ? () => activate(row) : undefined}>{renderCard(row.original)}</CardFrame>
              ) : (
                <AutoCard
                  cells={row.getVisibleCells()}
                  onClick={onRowClick ? () => activate(row) : undefined}
                  FlexRender={table.FlexRender}
                />
              )}
            </li>
          ))}
        </ul>
      </>
    );
  }

  return (
    <div className={cn("@container flex flex-col gap-3", className)}>
      {(toolbar || toggleable.length > 0) && (
        <div className="flex flex-wrap items-start gap-2">
          <div className="min-w-0 flex-1">{toolbar}</div>
          <ViewOptions columns={toggleable} />
        </div>
      )}
      {body}
      {state && rows.length > 0 && rowCount !== undefined && (
        <TablePagination
          page={state.page}
          pageSize={state.pageSize}
          rowCount={rowCount}
          onPageChange={state.setPage}
          onPageSizeChange={state.setPageSize}
        />
      )}
      {selection && (
        <SelectionBar
          count={selectedRows.length}
          summary={selection.summary?.(selectedRows)}
          actions={selection.actions(selectedRows)}
          onClear={() => setRowSelection({})}
        />
      )}
    </div>
  );
}

function CardFrame({ onClick, children }: { onClick?: () => void; children: ReactNode }) {
  const className = "block w-full px-4 py-3.5 text-left";
  if (!onClick) return <div className={className}>{children}</div>;
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(className, "touch-manipulation transition-colors outline-none hover:bg-sunk/70 focus-visible:bg-sunk active:bg-sunk")}
    >
      {children}
    </button>
  );
}

type FlexRenderComponent<TData extends RowData> = (props: { cell: Cell<DataTableFeatures, TData> }) => ReactNode;

function AutoCard<TData extends RowData>({
  cells,
  onClick,
  FlexRender,
}: {
  cells: Cell<DataTableFeatures, TData>[];
  onClick?: () => void;
  FlexRender: FlexRenderComponent<TData>;
}) {
  const slot = (name: "title" | "badge" | "amount") => cells.find((cell) => cell.column.columnDef.meta?.card === name);
  const title = slot("title") ?? cells[0];
  const badge = slot("badge");
  const amount = slot("amount");
  const rest = cells.filter(
    (cell) => cell !== title && cell !== badge && cell !== amount && cell.column.columnDef.meta?.card !== "hidden",
  );
  const labelOf = (cell: Cell<DataTableFeatures, TData>) =>
    cell.column.columnDef.meta?.label ??
    (typeof cell.column.columnDef.header === "string" ? cell.column.columnDef.header : cell.column.id);

  return (
    <CardFrame onClick={onClick}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col items-start gap-1.5">
          <span className={cn("max-w-full truncate font-medium text-ink", title?.column.columnDef.meta?.mono && "font-mono text-[13px] font-normal")}>
            {title && <FlexRender cell={title} />}
          </span>
          {badge && <FlexRender cell={badge} />}
        </div>
        {amount && (
          <span className="shrink-0 text-right text-[15px] font-medium text-ink tabular-nums">
            <FlexRender cell={amount} />
          </span>
        )}
      </div>
      {rest.length > 0 && (
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px] [&>:last-child:nth-child(odd)]:col-span-2">
          {rest.map((cell) => (
            <div key={cell.id} className="flex min-w-0 flex-col gap-0.5">
              <dt className="font-mono text-[10px] tracking-[0.12em] text-faint uppercase">{labelOf(cell)}</dt>
              <dd className={cn("text-ink wrap-anywhere", cell.column.columnDef.meta?.mono && "font-mono text-[12px]")}>
                <FlexRender cell={cell} />
              </dd>
            </div>
          ))}
        </dl>
      )}
    </CardFrame>
  );
}
