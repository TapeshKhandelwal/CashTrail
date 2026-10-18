"use client";

import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton, TableSkeleton } from "@/components/feedback/skeletons";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionCard } from "@/components/layout/section-card";
import { Money } from "@/components/money/money";
import { dashboardQueries } from "@/features/dashboard/api";
import { formatPercent } from "@/lib/format";
import { formatRelative } from "@/lib/dates";
import { isZero } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { AgentRow, BranchRow, DashboardParams, Tally } from "@/types/domain";

interface Column<T> {
  label: string;
  align?: "end";
  render: (row: T) => ReactNode;
  /** Slot in the phone card: the name, the headline amount, the line under it; the rest form a grid. */
  card?: "title" | "amount" | "note";
}

const quiet = (tally: Tally, tone?: string) =>
  isZero(tally.amount) ? <span className="text-faint">—</span> : <Money value={tally.amount} whole className={tone} />;

const AGENT_COLUMNS: Column<AgentRow>[] = [
  {
    label: "Agent",
    card: "title",
    render: (row) => (
      <div className="flex flex-col">
        <span className="text-ink">{row.agent.full_name}</span>
        <span className="font-mono text-[11px] text-faint">{row.agent.username}</span>
      </div>
    ),
  },
  { label: "Collected", align: "end", card: "amount", render: (row) => quiet(row.collected) },
  { label: "Efficiency", align: "end", card: "note", render: (row) => <Efficiency value={row.collection_efficiency} /> },
  {
    label: "Cash in hand",
    align: "end",
    render: (row) => (
      <div className="flex flex-col items-end">
        {quiet(row.cash_with_agents, "text-st-collected-fg")}
        {row.oldest_cash_held_at && (
          <span className="text-[11.5px] text-faint">since {formatRelative(row.oldest_cash_held_at)}</span>
        )}
      </div>
    ),
  },
  { label: "Overdue", align: "end", render: (row) => quiet(row.overdue) },
  { label: "Open short", align: "end", render: (row) => quiet(row.open_discrepancies, "text-st-short-fg") },
];

const BRANCH_COLUMNS: Column<BranchRow>[] = [
  {
    label: "Branch",
    card: "title",
    render: (row) => (
      <div className="flex flex-col">
        <span className="text-ink">{row.branch.name}</span>
        <span className="font-mono text-[11px] text-faint">{row.branch.code}</span>
      </div>
    ),
  },
  { label: "Collected", align: "end", card: "amount", render: (row) => quiet(row.collected) },
  { label: "Efficiency", align: "end", card: "note", render: (row) => <Efficiency value={row.collection_efficiency} /> },
  { label: "At branch", align: "end", render: (row) => quiet(row.at_branch, "text-st-received-fg") },
  { label: "Settled", align: "end", render: (row) => quiet(row.settled, "text-st-settled-fg") },
  { label: "Delayed", align: "end", render: (row) => quiet(row.delayed_settlements, "text-st-delayed-fg") },
  { label: "Open", align: "end", render: (row) => quiet(row.open_discrepancies, "text-st-short-fg") },
];

function Efficiency({ value }: { value: string | null }) {
  if (value == null) return <span className="text-faint">—</span>;
  const below = Number(value) < 90;
  return <span className={cn("tabular-nums", below ? "text-st-short-fg" : "text-ink")}>{formatPercent(value, 0)}</span>;
}

interface TableProps<T> {
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
}

/** A ruled table where there is room for it, and one card per row in a narrow column or on a phone. */
function Table<T>(props: TableProps<T>) {
  return (
    <div className="@container">
      <div className="@max-xl:hidden">
        <WideTable {...props} />
      </div>
      <CardList {...props} />
    </div>
  );
}

function CardList<T>({ caption, columns, rows, rowKey }: TableProps<T>) {
  const slot = (name: Column<T>["card"]) => columns.find((column) => column.card === name);
  const [title, amount, note] = [slot("title"), slot("amount"), slot("note")];
  const rest = columns.filter((column) => !column.card);

  return (
    <ul aria-label={caption} className="rows-enter divide-y divide-rule @xl:hidden">
      {rows.map((row) => (
        <li key={rowKey(row)} className="flex flex-col gap-3 px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 text-[14px] [&_span]:wrap-break-word">{title?.render(row)}</div>
            <div className="flex shrink-0 flex-col items-end gap-0.5 text-right">
              {amount && <span className="font-mono text-[10px] tracking-[0.12em] text-faint uppercase">{amount.label}</span>}
              {amount && <span className="text-[15px] font-medium text-ink tabular-nums">{amount.render(row)}</span>}
              {note && (
                <span className="text-[12px] text-faint">
                  {note.render(row)} {note.label.toLowerCase()}
                </span>
              )}
            </div>
          </div>
          <dl className={cn("grid gap-x-3 gap-y-2.5 border-t border-dashed border-rule pt-3", rest.length % 3 === 0 ? "grid-cols-3" : "grid-cols-2")}>
            {rest.map((column) => (
              <div key={column.label} className="flex min-w-0 flex-col gap-0.5">
                <dt className="font-mono text-[10px] tracking-[0.12em] text-faint uppercase">{column.label}</dt>
                <dd className="text-[13px] tabular-nums [&>div]:items-start">{column.render(row)}</dd>
              </div>
            ))}
          </dl>
        </li>
      ))}
    </ul>
  );
}

function WideTable<T>({ caption, columns, rows, rowKey }: TableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-[13.5px]">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-sunk">
          <tr>
            {columns.map((column) => (
              <th
                key={column.label}
                scope="col"
                className={cn(
                  "h-9 px-5 text-left font-mono text-[10.5px] font-normal tracking-[0.12em] whitespace-nowrap text-faint uppercase",
                  column.align === "end" && "text-right",
                )}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="rows-enter divide-y divide-rule">
          {rows.map((row) => (
            <tr key={rowKey(row)} className="transition-colors hover:bg-sunk/50">
              {columns.map((column) => (
                <td key={column.label} className={cn("h-13 px-5", column.align === "end" && "text-right tabular-nums")}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Branch managers compare their agents; finance and admin compare branches. */
export function TeamTable({ scope, params }: { scope: "agents" | "branches"; params: DashboardParams }) {
  const agents = useQuery({ ...dashboardQueries.agents({ ...params, page_size: 50 }), enabled: scope === "agents" });
  const branches = useQuery({ ...dashboardQueries.branches({ ...params, page_size: 50 }), enabled: scope === "branches" });
  const query = scope === "agents" ? agents : branches;

  return (
    <SectionCard
      eyebrow={scope === "agents" ? "Field team" : "Branches"}
      title={scope === "agents" ? "How each agent is doing" : "How each branch is doing"}
      flush
    >
      {query.isPending ? (
        <div className="@container">
          <TableSkeleton rows={4} columns={6} className="rounded-none border-0 @max-xl:hidden" />
          <CardListSkeleton count={3} className="border-0 p-2 @xl:hidden" />
        </div>
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} compact />
      ) : query.data.results.length === 0 ? (
        <EmptyState compact title="Nobody to show for this filter." />
      ) : scope === "agents" ? (
        <Table caption="Agents" columns={AGENT_COLUMNS} rows={agents.data?.results ?? []} rowKey={(row) => String(row.agent.id)} />
      ) : (
        <Table caption="Branches" columns={BRANCH_COLUMNS} rows={branches.data?.results ?? []} rowKey={(row) => String(row.branch.id)} />
      )}
    </SectionCard>
  );
}
