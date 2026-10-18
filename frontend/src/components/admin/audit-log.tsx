"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { createColumns } from "@/components/data-table/data-table-features";
import { DataTable } from "@/components/data-table/data-table";
import { FilterBar } from "@/components/data-table/filter-bar";
import { PageHeader } from "@/components/layout/page-header";
import { FactList } from "@/components/layout/section-card";
import { DetailSheet } from "@/components/sheets/detail-sheet";
import { auditQueries } from "@/features/audit/api";
import { useDataTableState, type FilterDef } from "@/hooks/use-data-table-state";
import { formatDateTime } from "@/lib/dates";
import { formatINR } from "@/lib/format";
import { isMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { AuditLog } from "@/types/domain";

const col = createColumns<AuditLog>();
const COLUMNS = col.columns([
  col.accessor("created_at", {
    header: "When",
    enableSorting: true,
    meta: { width: "w-48" },
    cell: ({ getValue }) => <span className="font-mono text-[12px] text-dim">{formatDateTime(getValue())}</span>,
  }),
  col.accessor("action_label", { header: "Action", meta: { card: "title" } }),
  col.display({
    id: "entity",
    header: "Record",
    cell: ({ row }) => <RecordName entry={row.original} />,
  }),
  col.accessor("actor_name", {
    header: "By",
    cell: ({ row }) => row.original.actor_name ?? <span className="text-faint">System</span>,
  }),
  col.accessor("branch_code", {
    header: "Branch",
    cell: ({ getValue }) => <span className="font-mono text-[12px] text-faint">{getValue() ?? "—"}</span>,
  }),
]);

const FILTERS: FilterDef[] = [
  {
    type: "select",
    key: "entity_type",
    label: "Record",
    options: [
      ["collection", "Receipts"],
      ["cashsubmission", "Hand-overs"],
      ["bankdeposit", "Deposits"],
      ["discrepancy", "Discrepancies"],
      ["gatewayorder", "UPI orders"],
      ["loan", "Loans"],
      ["customer", "Customers"],
      ["user", "Users"],
      ["bankaccount", "Bank accounts"],
      ["branch", "Branches"],
    ].map(([value, label]) => ({ value, label })),
  },
  { type: "dateRange", label: "When", from: "date_from", to: "date_to" },
];

/** "Hand-over SUB-BLR01-20261017-00004", or "Discrepancy #12" when the record has no number. */
function recordName(entry: AuditLog): string {
  return `${entry.entity_label} ${entry.entity_reference ?? `#${entry.entity_id}`}`;
}

function RecordName({ entry }: { entry: AuditLog }) {
  return (
    <span className="text-[13px] text-dim">
      {entry.entity_label} <span className="font-mono text-[12px] wrap-anywhere">{entry.entity_reference ?? `#${entry.entity_id}`}</span>
    </span>
  );
}

/** Phone card: the action and its branch, the record it touched, then who and when. */
function AuditCard({ entry }: { entry: AuditLog }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 font-medium text-ink">{entry.action_label}</span>
        {entry.branch_code && <span className="shrink-0 font-mono text-[11.5px] text-faint">{entry.branch_code}</span>}
      </div>
      <span className="truncate">
        <RecordName entry={entry} />
      </span>
      <span className="truncate text-[12.5px] text-faint">
        {entry.actor_name ?? "System"} · {formatDateTime(entry.created_at)}
      </span>
    </div>
  );
}

/** Every financial change, append-only: who did what, when, and the values before and after. */
export function AuditLogView() {
  const state = useDataTableState({ filters: FILTERS, defaultOrdering: "-created_at", defaultPageSize: 25 });
  const list = useQuery(auditQueries.list(state.query));
  const [selected, setSelected] = useState<AuditLog | null>(null);

  return (
    <>
      <PageHeader
        eyebrow="Admin · Control"
        title="Audit log"
        description="Append-only. The database refuses to update or delete these rows, so this history cannot be rewritten."
      />
      <DataTable
        caption="Audit log"
        columns={COLUMNS}
        data={list.data?.results}
        rowCount={list.data?.count}
        state={state}
        isLoading={list.isFetching}
        error={list.error}
        onRetry={() => void list.refetch()}
        onRowClick={setSelected}
        renderCard={(entry) => <AuditCard entry={entry} />}
        toolbar={<FilterBar state={state} searchPlaceholder="Action, actor or record id" />}
      />
      <DetailSheet
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title={selected?.action_label ?? ""}
        description={selected ? `${recordName(selected)} · ${formatDateTime(selected.created_at)}` : undefined}
      >
        {selected && (
          <div className="flex flex-col gap-6">
            <FactList
              columns={2}
              className="max-sm:grid-cols-2"
              items={[
                ["By", selected.actor_name ?? "System"],
                ["Branch", selected.branch_code ?? "—"],
                ["IP address", <span key="ip" className="font-mono">{selected.ip_address ?? "—"}</span>],
                ["Request", <span key="r" className="font-mono text-[11.5px]">{selected.request_id?.slice(0, 8) ?? "—"}</span>],
              ]}
            />
            <Diff before={selected.before} after={selected.after} />
          </div>
        )}
      </DetailSheet>
    </>
  );
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string" && isMoney(value) && value.includes(".")) return formatINR(value);
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value)) return formatDateTime(value);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function Diff({ before, after }: { before: Record<string, unknown> | null; after: Record<string, unknown> | null }) {
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})])).sort();
  if (keys.length === 0) return <p className="text-[13px] text-dim">No field values were recorded for this action.</p>;

  const rows = keys.map((key) => {
    const from = before?.[key];
    const to = after?.[key];
    return { key, from: before ? display(from) : "—", to: after ? display(to) : "—", changed: JSON.stringify(from) !== JSON.stringify(to) };
  });

  return (
    <div className="overflow-hidden rounded-lg border border-rule">
      <ul aria-label="Changes" className="divide-y divide-rule text-[13px] sm:hidden">
        {rows.map((row) => (
          <li key={row.key} className={cn("flex flex-col gap-1 px-3.5 py-2.5", row.changed && "bg-brand-tint/50")}>
            <span className="font-mono text-[11px] text-dim">{row.key}</span>
            {row.changed && before && after ? (
              <span className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 wrap-anywhere">
                <span className="text-faint line-through decoration-1">{row.from}</span>
                <span aria-hidden className="text-faint">→</span>
                <span className="sr-only">changed to</span>
                <span className="text-ink">{row.to}</span>
              </span>
            ) : (
              <span className={cn("wrap-anywhere", row.changed ? "text-ink" : "text-dim")}>{after ? row.to : row.from}</span>
            )}
          </li>
        ))}
      </ul>
      <table className="w-full text-[12.5px] max-sm:hidden">
        <caption className="sr-only">Changes</caption>
        <thead className="bg-sunk">
          <tr>
            {["Field", "Before", "After"].map((label) => (
              <th key={label} scope="col" className="h-8 px-3 text-left font-mono text-[10.5px] font-normal tracking-[0.12em] text-faint uppercase">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {rows.map((row) => (
            <tr key={row.key} className={cn(row.changed && "bg-brand-tint/50")}>
              <td className="px-3 py-2 font-mono text-[11.5px] text-dim">{row.key}</td>
              <td className={cn("px-3 py-2 break-all", row.changed ? "text-faint line-through decoration-1" : "text-dim")}>{row.from}</td>
              <td className={cn("px-3 py-2 break-all", row.changed ? "text-ink" : "text-dim")}>{row.to}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
