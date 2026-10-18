"use client";

import { useState, type ReactNode } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { ChartSkeleton } from "@/components/feedback/skeletons";
import { cn } from "@/lib/utils";

export interface ChartTableColumn {
  key: string;
  label: string;
  align?: "start" | "end";
}

export interface ChartTable {
  columns: ChartTableColumn[];
  rows: Record<string, ReactNode>[];
}

interface ChartCardProps {
  /** Optional mono label above the title. */
  eyebrow?: string;
  title: string;
  description?: string;
  /** One sentence that stands in for the graphic for screen readers. */
  summary: string;
  /** Accessible table of the same data ("View as table"). */
  table?: ChartTable;
  /** Header controls (range segmented control, legend). */
  actions?: ReactNode;
  height?: number;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  empty?: boolean;
  emptyTitle?: string;
  className?: string;
  /** The Recharts chart. Load each chart with next/dynamic so desk pages stay light. */
  children: ReactNode;
}

/** Frame for every chart: header, a11y summary, loading / error / empty states and a table view. */
export function ChartCard({
  eyebrow,
  title,
  description,
  summary,
  table,
  actions,
  height = 260,
  loading = false,
  error,
  onRetry,
  empty = false,
  emptyTitle = "No data for this period.",
  className,
  children,
}: ChartCardProps) {
  const [asTable, setAsTable] = useState(false);
  if (loading) return <ChartSkeleton height={height} className={className} />;

  return (
    <section className={cn("flex min-w-0 flex-col gap-5 rounded-xl border border-rule bg-raised p-4 sm:p-5", className)}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2 className="text-[15px] font-medium text-ink">{title}</h2>
          {description && <p className="text-[13px] text-dim">{description}</p>}
        </div>
        <div className="flex items-center gap-3">
          {actions}
          {table && !error && !empty && (
            <button
              type="button"
              aria-pressed={asTable}
              onClick={() => setAsTable((value) => !value)}
              className="rounded-md px-1.5 py-1 font-mono text-[10.5px] tracking-[0.12em] text-faint uppercase transition-colors outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-focus"
            >
              {asTable ? "Chart" : "Table"}
            </button>
          )}
        </div>
      </header>

      {error ? (
        <ErrorState error={error} onRetry={onRetry} compact />
      ) : empty ? (
        <EmptyState illustration="ledger" title={emptyTitle} compact />
      ) : asTable && table ? (
        <div className="overflow-auto rounded-lg border border-rule" style={{ maxHeight: Math.max(height, 240) }}>
          <table className="w-full text-[13px]">
            <caption className="sr-only">{title}</caption>
            <thead className="sticky top-0 bg-sunk">
              <tr>
                {table.columns.map((column) => (
                  <th
                    key={column.key}
                    scope="col"
                    className={cn(
                      "h-9 px-3 text-left font-mono text-[10.5px] font-normal tracking-[0.12em] text-faint uppercase",
                      column.align === "end" && "text-right",
                    )}
                  >
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {table.rows.map((row, index) => (
                <tr key={index}>
                  {table.columns.map((column) => (
                    <td key={column.key} className={cn("h-9 px-3", column.align === "end" && "text-right tabular-nums")}>
                      {row[column.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div role="img" aria-label={summary} style={{ height }}>
          {children}
        </div>
      )}
    </section>
  );
}
