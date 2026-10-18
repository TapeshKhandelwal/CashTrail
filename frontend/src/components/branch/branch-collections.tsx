"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { RecordCard } from "@/components/branch/record-card";
import { createColumns } from "@/components/data-table/data-table-features";
import { DataTable } from "@/components/data-table/data-table";
import { FilterBar } from "@/components/data-table/filter-bar";
import { PageHeader } from "@/components/layout/page-header";
import { Money } from "@/components/money/money";
import { LifecycleProgress } from "@/components/status/lifecycle-stepper";
import { ModeChip } from "@/components/status/mode-chip";
import { StatusChip } from "@/components/status/status-chip";
import { collectionQueries } from "@/features/collections/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import { useDataTableState, type FilterDef } from "@/hooks/use-data-table-state";
import { COLLECTION_STATUS_OPTIONS, useAgentOptions } from "@/hooks/use-filter-options";
import { formatDateTime, formatDayMonth, formatTime } from "@/lib/dates";
import type { Collection } from "@/types/domain";

const col = createColumns<Collection>();
const COLUMNS = col.columns([
  col.accessor("receipt_number", { header: "Receipt", meta: { mono: true, card: "title" } }),
  col.accessor("customer_name", {
    header: "Customer",
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span>{row.original.customer_name}</span>
        <span className="font-mono text-[11.5px] text-faint">{row.original.loan_number}</span>
      </span>
    ),
  }),
  col.accessor("agent_name", { header: "Agent", cell: ({ getValue }) => <span className="text-dim">{getValue() ?? "Customer (UPI)"}</span> }),
  col.accessor("collected_at", {
    header: "Collected",
    enableSorting: true,
    cell: ({ getValue }) => <span className="text-dim">{formatDateTime(getValue())}</span>,
  }),
  col.accessor("mode", { header: "Mode", cell: ({ getValue }) => <ModeChip mode={getValue()} /> }),
  col.accessor("amount", {
    header: "Amount",
    enableSorting: true,
    meta: { align: "end", card: "amount" },
    cell: ({ row }) => <Money value={row.original.amount} strike={row.original.status === "VOIDED"} />,
  }),
  col.display({
    id: "progress",
    header: "Journey",
    meta: { card: "hidden", width: "w-36" },
    cell: ({ row }) => <LifecycleProgress status={row.original.status} mode={row.original.mode} />,
  }),
  col.accessor("status", {
    header: "Status",
    meta: { card: "badge" },
    cell: ({ getValue }) => <StatusChip kind="collection" status={getValue()} />,
  }),
]);

function CollectionCard({ row }: { row: Collection }) {
  return (
    <RecordCard
      mono
      title={row.receipt_number}
      subtitle={row.customer_name}
      amount={<Money value={row.amount} strike={row.status === "VOIDED"} />}
      badge={<StatusChip kind="collection" status={row.status} size="sm" />}
      meta={[
        `${formatDayMonth(row.collected_at)}, ${formatTime(row.collected_at)}`,
        row.agent_name ?? "Customer (UPI)",
        <ModeChip key="mode" mode={row.mode} className="text-[10.5px]" />,
      ]}
    />
  );
}

const FILTER_SHAPE: FilterDef[] = [
  { type: "multi", key: "status", label: "Status", options: COLLECTION_STATUS_OPTIONS },
  { type: "select", key: "agent", label: "Agent", options: [] },
  {
    type: "select",
    key: "mode",
    label: "Mode",
    options: [
      { value: "CASH", label: "Cash" },
      { value: "UPI", label: "UPI" },
    ],
  },
  { type: "dateRange", label: "Collected", from: "date_from", to: "date_to" },
];

export function BranchCollections({ detailHref = (id: number) => `/app/branch/collections/${id}` }: { detailHref?: (id: number) => string }) {
  const router = useRouter();
  const { branch } = useBranchScope();
  const agents = useAgentOptions(branch ?? undefined);
  const state = useDataTableState({ filters: FILTER_SHAPE, defaultOrdering: "-collected_at" });
  const list = useQuery(collectionQueries.list({ ...state.query, ...(branch ? { branch } : {}) }));
  const filters = FILTER_SHAPE.map((filter) => (filter.type === "select" && filter.key === "agent" ? { ...filter, options: agents } : filter));

  return (
    <>
      <PageHeader
        eyebrow="Reconciliation"
        title="Collections"
        description="Every receipt your agents recorded, cash and UPI, and how far its money has travelled."
      />
      <DataTable
        caption="Collections"
        columns={COLUMNS}
        data={list.data?.results}
        rowCount={list.data?.count}
        state={state}
        isLoading={list.isFetching}
        error={list.error}
        onRetry={() => void list.refetch()}
        onRowClick={(row) => router.push(detailHref(row.id))}
        renderCard={(row) => <CollectionCard row={row} />}
        toolbar={<FilterBar state={{ ...state, filters }} searchPlaceholder="Receipt, customer or loan" />}
      />
    </>
  );
}
