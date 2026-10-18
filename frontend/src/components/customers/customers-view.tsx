"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { RecordCard } from "@/components/branch/record-card";
import { createColumns } from "@/components/data-table/data-table-features";
import { DataTable } from "@/components/data-table/data-table";
import { FilterBar } from "@/components/data-table/filter-bar";
import { EmptyState } from "@/components/feedback/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { Money } from "@/components/money/money";
import { useSession } from "@/components/providers/session-provider";
import { Button } from "@/components/ui/button";
import { customerQueries } from "@/features/customers/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import { useDataTableState, type FilterDef } from "@/hooks/use-data-table-state";
import { useAgentOptions } from "@/hooks/use-filter-options";
import { countOf } from "@/lib/format";
import { isZero } from "@/lib/money";
import type { Customer } from "@/types/domain";

import { CustomerFormDialog } from "./customer-form-dialog";

const col = createColumns<Customer>();
const COLUMNS = col.columns([
  col.accessor("full_name", {
    header: "Customer",
    enableSorting: true,
    meta: { card: "title" },
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span className={row.original.is_active ? "" : "text-faint line-through decoration-1"}>{row.original.full_name}</span>
        <span className="font-mono text-[11.5px] text-faint">{row.original.customer_code}</span>
      </span>
    ),
  }),
  col.accessor("phone", { header: "Phone", meta: { mono: true }, cell: ({ getValue }) => <span className="text-dim">{getValue()}</span> }),
  col.accessor("assigned_agent_name", {
    header: "Agent",
    cell: ({ getValue }) => getValue() ?? <span className="text-st-collected-fg">Unassigned</span>,
  }),
  col.accessor("active_loans", { header: "Loans", meta: { align: "end" } }),
  col.accessor("outstanding", {
    header: "Outstanding",
    meta: { align: "end", card: "amount" },
    cell: ({ getValue }) => <Money value={getValue()} whole />,
  }),
  col.accessor("overdue_amount", {
    header: "Overdue",
    meta: { align: "end" },
    cell: ({ getValue }) => (isZero(getValue()) ? <span className="text-faint">—</span> : <Money value={getValue()} tone="short" />),
  }),
]);

function CustomerCard({ row }: { row: Customer }) {
  return (
    <RecordCard
      title={<span className={row.is_active ? "" : "text-faint line-through decoration-1"}>{row.full_name}</span>}
      subtitle={
        <span className="font-mono text-[12px]">
          {row.customer_code} · {row.phone}
        </span>
      }
      amount={<Money value={row.outstanding} whole />}
      badge={
        !isZero(row.overdue_amount) && (
          <span className="text-[12px] text-st-short-fg">
            <Money value={row.overdue_amount} /> overdue
          </span>
        )
      }
      meta={[
        row.assigned_agent_name ?? <span key="agent" className="text-st-collected-fg">Unassigned</span>,
        countOf(row.active_loans, "active loan"),
      ]}
    />
  );
}

const FILTER_SHAPE: FilterDef[] = [
  { type: "select", key: "agent", label: "Agent", options: [] },
  { type: "boolean", key: "unassigned", label: "Unassigned" },
];

export function CustomersView({ basePath }: { basePath: string }) {
  const user = useSession();
  const router = useRouter();
  const { branch } = useBranchScope();
  const agents = useAgentOptions(branch ?? undefined);
  const [creating, setCreating] = useState(false);
  const state = useDataTableState({ filters: FILTER_SHAPE, defaultOrdering: "full_name" });
  const list = useQuery(customerQueries.list({ ...state.query, ...(branch ? { branch } : {}) }));
  const filters = FILTER_SHAPE.map((filter) => (filter.type === "select" ? { ...filter, options: agents } : filter));
  const canWrite = user.role === "ADMIN" || user.role === "BRANCH_MANAGER";

  return (
    <>
      <PageHeader
        eyebrow={user.branch_code ? `${user.branch_code} · Money` : "Money"}
        title="Customers"
        description="Borrowers, the agent who visits them, and what they still owe."
        actions={
          canWrite && (
            <>
              <Button variant="outline" asChild>
                <Link href={`${basePath}/loans/new`}>New loan</Link>
              </Button>
              <Button onClick={() => setCreating(true)}>
                <Plus data-icon="inline-start" />
                New customer
              </Button>
            </>
          )
        }
      />
      <DataTable
        caption="Customers"
        columns={COLUMNS}
        data={list.data?.results}
        rowCount={list.data?.count}
        state={state}
        isLoading={list.isFetching}
        error={list.error}
        onRetry={() => void list.refetch()}
        onRowClick={(row) => router.push(`${basePath}/customers/${row.id}`)}
        renderCard={(row) => <CustomerCard row={row} />}
        toolbar={<FilterBar state={{ ...state, filters }} searchPlaceholder="Name, phone or code" />}
        empty={<EmptyState bordered title="No customers yet." description="Add the first borrower to start a loan." />}
      />
      {canWrite && (
        <CustomerFormDialog open={creating} onOpenChange={setCreating} onCreated={(customer) => router.push(`${basePath}/customers/${customer.id}`)} />
      )}
    </>
  );
}
