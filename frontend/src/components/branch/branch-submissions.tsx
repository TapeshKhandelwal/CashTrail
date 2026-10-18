"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { RecordCard } from "@/components/branch/record-card";
import { createColumns } from "@/components/data-table/data-table-features";
import { DataTable } from "@/components/data-table/data-table";
import { FilterBar } from "@/components/data-table/filter-bar";
import { EmptyState } from "@/components/feedback/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { Segmented } from "@/components/layout/segmented";
import { Money } from "@/components/money/money";
import { useSession } from "@/components/providers/session-provider";
import { StatusChip } from "@/components/status/status-chip";
import { countedVariance } from "@/components/submissions/submission-summary";
import { submissionQueries } from "@/features/submissions/api";
import { useDataTableState, type FilterDef } from "@/hooks/use-data-table-state";
import { useAgentOptions } from "@/hooks/use-filter-options";
import { formatDateTime, formatDayMonth, formatTime } from "@/lib/dates";
import { countOf } from "@/lib/format";
import { compareMoney, isZero } from "@/lib/money";
import type { CashSubmission } from "@/types/domain";

const col = createColumns<CashSubmission>();
const COLUMNS = col.columns([
  col.accessor("submission_number", { header: "Hand-over", meta: { mono: true, card: "title" } }),
  col.accessor("agent_name", {
    header: "Agent",
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span>{row.original.agent_name}</span>
        <span className="text-[12px] text-faint">{countOf(row.original.collection_count, "receipt")}</span>
      </span>
    ),
  }),
  col.accessor("submitted_at", {
    header: "Handed over",
    enableSorting: true,
    cell: ({ getValue }) => <span className="text-dim">{formatDateTime(getValue())}</span>,
  }),
  col.accessor("expected_amount", {
    header: "Receipted",
    enableSorting: true,
    meta: { align: "end" },
    cell: ({ getValue }) => <Money value={getValue()} />,
  }),
  col.accessor("received_amount", {
    header: "Counted",
    meta: { align: "end", card: "amount" },
    cell: ({ row }) =>
      row.original.received_amount ? (
        <Money value={row.original.received_amount} />
      ) : (
        <span className="text-faint">Not counted</span>
      ),
  }),
  col.accessor("difference", {
    header: "Difference",
    meta: { align: "end" },
    cell: ({ getValue }) => {
      const value = getValue();
      if (!value || isZero(value)) return <span className="text-faint">—</span>;
      return <Money value={countedVariance(value)} signed tone="direction" />;
    },
  }),
  col.accessor("status", {
    header: "Status",
    meta: { card: "badge" },
    cell: ({ row }) => <StatusChip kind="submission" status={row.original.status} difference={row.original.difference} />,
  }),
]);

function SubmissionCard({ row }: { row: CashSubmission }) {
  const counted = row.received_amount;
  return (
    <RecordCard
      mono
      title={row.submission_number}
      subtitle={`${row.agent_name} · ${countOf(row.collection_count, "receipt")}`}
      amount={<Money value={counted ?? row.expected_amount} />}
      badge={<StatusChip kind="submission" status={row.status} difference={row.difference} size="sm" />}
      meta={[
        `Handed over ${formatDayMonth(row.submitted_at)}, ${formatTime(row.submitted_at)}`,
        counted !== null && compareMoney(counted, row.expected_amount) !== 0 && (
          <span key="r">
            Receipted <Money value={row.expected_amount} />
          </span>
        ),
      ]}
    />
  );
}

const VIEWS = {
  pending: ["SUBMITTED"],
  counted: ["APPROVED", "APPROVED_WITH_DISCREPANCY"],
  rejected: ["REJECTED"],
  all: [],
} as const;
type View = keyof typeof VIEWS;

function useFilters(): FilterDef[] {
  const agents = useAgentOptions();
  return [
    { type: "select", key: "agent", label: "Agent", options: agents },
    { type: "dateRange", label: "Handed over", from: "date_from", to: "date_to" },
  ];
}

const STATIC_FILTERS: FilterDef[] = [
  { type: "multi", key: "status", label: "Status", options: [] },
  { type: "select", key: "agent", label: "Agent", options: [] },
  { type: "dateRange", label: "Handed over", from: "date_from", to: "date_to" },
];

export function BranchSubmissions() {
  const user = useSession();
  const router = useRouter();
  const filters = useFilters();
  const state = useDataTableState({ filters: STATIC_FILTERS, defaultOrdering: "-submitted_at" });
  const status = (state.values.status as string[] | null) ?? [];
  const view = (Object.keys(VIEWS) as View[]).find((key) => VIEWS[key].join() === [...status].sort().join()) ?? "all";
  const list = useQuery(submissionQueries.list(state.query));
  const pending = useQuery(submissionQueries.list({ status: ["SUBMITTED"], page_size: 1 }));

  return (
    <>
      <PageHeader
        eyebrow={user.branch_code ? `${user.branch_code} · Reconciliation` : "Reconciliation"}
        title="Submissions"
        description="Cash handed over by agents. Count each one before it joins the branch's cash."
      >
        <Segmented<View>
          label="Show"
          value={view}
          onChange={(next) => state.setFilters({ status: [...VIEWS[next]] })}
          options={[
            { value: "pending", label: "To count", count: pending.data?.count },
            { value: "counted", label: "Counted" },
            { value: "rejected", label: "Rejected" },
            { value: "all", label: "All" },
          ]}
          className="w-fit"
        />
      </PageHeader>
      <DataTable
        caption="Cash submissions"
        columns={COLUMNS}
        data={list.data?.results}
        rowCount={list.data?.count}
        state={state}
        isLoading={list.isFetching}
        error={list.error}
        onRetry={() => void list.refetch()}
        onRowClick={(row) => router.push(`/app/branch/submissions/${row.id}`)}
        renderCard={(row) => <SubmissionCard row={row} />}
        toolbar={<FilterBar state={{ ...state, filters }} />}
        empty={
          <EmptyState
            bordered
            illustration="settled"
            title={view === "pending" ? "Nothing waiting to be counted." : "No hand-overs yet."}
            description="Agents' hand-overs appear here the moment they submit."
          />
        }
      />
    </>
  );
}
