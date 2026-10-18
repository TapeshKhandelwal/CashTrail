"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { RecordCard } from "@/components/branch/record-card";
import { createColumns } from "@/components/data-table/data-table-features";
import { DataTable } from "@/components/data-table/data-table";
import { FilterBar } from "@/components/data-table/filter-bar";
import { EmptyState } from "@/components/feedback/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { Money } from "@/components/money/money";
import { useSession } from "@/components/providers/session-provider";
import { StatusChip } from "@/components/status/status-chip";
import { Button } from "@/components/ui/button";
import { loanQueries } from "@/features/loans/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import { useDataTableState, type FilterDef } from "@/hooks/use-data-table-state";
import { useAgentOptions } from "@/hooks/use-filter-options";
import { formatDate, formatDayMonth, todayIST } from "@/lib/dates";
import { isZero } from "@/lib/money";
import type { Loan } from "@/types/domain";

const col = createColumns<Loan>();
const COLUMNS = col.columns([
  col.accessor("loan_number", {
    header: "Loan",
    enableSorting: true,
    meta: { mono: true, card: "title" },
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span>{row.original.loan_number}</span>
        <span className="font-sans text-[11.5px] text-faint">
          {row.original.tenure_months} months at {row.original.annual_interest_rate}%
        </span>
      </span>
    ),
  }),
  col.accessor("customer_name", {
    header: "Customer",
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span>{row.original.customer_name}</span>
        <span className="font-mono text-[11.5px] text-faint">{row.original.customer_code}</span>
      </span>
    ),
  }),
  col.accessor("agent_name", {
    header: "Agent",
    cell: ({ getValue }) => getValue() ?? <span className="text-st-collected-fg">Unassigned</span>,
  }),
  col.accessor("principal", {
    header: "Principal",
    enableSorting: true,
    meta: { align: "end" },
    cell: ({ getValue }) => <Money value={getValue()} whole tone="dim" />,
  }),
  col.accessor("outstanding", {
    header: "Outstanding",
    meta: { align: "end", card: "amount" },
    cell: ({ getValue }) => <Money value={getValue()} whole />,
  }),
  col.accessor("overdue_amount", {
    header: "Overdue",
    enableSorting: true,
    meta: { align: "end" },
    cell: ({ getValue }) => (isZero(getValue()) ? <span className="text-faint">—</span> : <Money value={getValue()} tone="short" />),
  }),
  col.accessor("next_due", {
    header: "Next due",
    enableSorting: true,
    meta: { sortField: "next_due_date" },
    cell: ({ getValue }) => {
      const due = getValue();
      if (!due) return <span className="text-faint">—</span>;
      return (
        <span className="flex flex-col">
          <span>{formatDate(due.due_date)}</span>
          <span className="text-[11.5px] text-faint">
            EMI {due.installment_no} · <Money value={due.amount} />
          </span>
        </span>
      );
    },
  }),
  col.accessor("status", {
    header: "Status",
    meta: { card: "badge" },
    cell: ({ getValue }) => <StatusChip kind="loan" status={getValue()} />,
  }),
]);

function LoanCard({ row }: { row: Loan }) {
  return (
    <RecordCard
      mono
      title={row.loan_number}
      subtitle={`${row.customer_name} · ${row.customer_code}`}
      amount={<Money value={row.outstanding} whole />}
      badge={
        isZero(row.overdue_amount) ? (
          <StatusChip kind="loan" status={row.status} size="sm" />
        ) : (
          <span className="text-[12px] text-st-short-fg">
            <Money value={row.overdue_amount} /> overdue
          </span>
        )
      }
      meta={[
        row.next_due
          ? `${row.next_due.due_date < todayIST() ? "Due" : "Next"} ${formatDayMonth(row.next_due.due_date)}`
          : null,
        row.agent_name ?? <span key="agent" className="text-st-collected-fg">Unassigned</span>,
        `${row.tenure_months} months at ${row.annual_interest_rate}%`,
      ]}
    />
  );
}

const FILTER_SHAPE: FilterDef[] = [
  {
    type: "select",
    key: "status",
    label: "Status",
    options: [
      { value: "ACTIVE", label: "Active" },
      { value: "CLOSED", label: "Closed" },
    ],
  },
  { type: "boolean", key: "overdue", label: "Overdue" },
  { type: "select", key: "agent", label: "Agent", options: [] },
];

/** Every loan in the branch: what is still owed, what is overdue and when the next EMI falls due. */
export function LoansView({ basePath }: { basePath: string }) {
  const user = useSession();
  const router = useRouter();
  const { branch } = useBranchScope();
  const agents = useAgentOptions(branch ?? undefined);
  const state = useDataTableState({ filters: FILTER_SHAPE, defaultOrdering: "-created_at" });
  const list = useQuery(loanQueries.list({ ...state.query, ...(branch ? { branch } : {}) }));
  const filters = FILTER_SHAPE.map((filter) => (filter.type === "select" && filter.key === "agent" ? { ...filter, options: agents } : filter));
  const canWrite = user.role === "ADMIN" || user.role === "BRANCH_MANAGER";

  return (
    <>
      <PageHeader
        eyebrow={user.branch_code ? `${user.branch_code} · Money` : "Money"}
        title="Loans"
        description="Every loan, what is still owed and when the next EMI falls due. Open one to see its schedule."
        actions={
          canWrite && (
            <Button asChild>
              <Link href={`${basePath}/loans/new`}>
                <Plus data-icon="inline-start" />
                New loan
              </Link>
            </Button>
          )
        }
      />
      <DataTable
        caption="Loans"
        columns={COLUMNS}
        data={list.data?.results}
        rowCount={list.data?.count}
        state={state}
        isLoading={list.isFetching}
        error={list.error}
        onRetry={() => void list.refetch()}
        onRowClick={(row) => router.push(`${basePath}/customers/${row.customer}`)}
        renderCard={(row) => <LoanCard row={row} />}
        toolbar={<FilterBar state={{ ...state, filters }} searchPlaceholder="Loan, customer or phone" />}
        empty={<EmptyState bordered title="No loans yet." description="Create one from a customer's page." />}
      />
    </>
  );
}
