"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { parseAsStringLiteral, useQueryState } from "nuqs";

import { DataTable } from "@/components/data-table/data-table";
import { FilterBar } from "@/components/data-table/filter-bar";
import { DEPOSIT_COLUMNS, DEPOSIT_FILTERS } from "@/components/deposits/deposit-columns";
import { EmptyState } from "@/components/feedback/empty-state";
import { DepositCard } from "@/components/finance/deposit-card";
import { KpiGrid, KpiTile } from "@/components/kpi/kpi-tile";
import { PageHeader } from "@/components/layout/page-header";
import { Segmented } from "@/components/layout/segmented";
import { depositQueries } from "@/features/deposits/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import { useDataTableState } from "@/hooks/use-data-table-state";
import { countOf } from "@/lib/format";
import { sumMoney } from "@/lib/money";

const VIEWS = ["pending", "all"] as const;
// The work queue already fixes the status, so its filter bar leaves that one out.
const QUEUE_FILTERS = DEPOSIT_FILTERS.filter((filter) => filter.type === "dateRange" || filter.key !== "status");

/** Opens on the work: deposits awaiting the statement, oldest first. "All deposits" is the history. */
export function SettlementQueue() {
  const router = useRouter();
  const { branch } = useBranchScope();
  const scope = branch ? { branch } : {};
  const [view, setView] = useQueryState("view", parseAsStringLiteral(VIEWS).withDefault("pending").withOptions({ history: "replace", clearOnDefault: true }));
  const queue = view === "pending";
  const state = useDataTableState({ filters: DEPOSIT_FILTERS, defaultOrdering: queue ? "deposit_date" : "-deposit_date" });
  const list = useQuery(depositQueries.list({ ...state.query, ...(queue ? { status: ["PENDING"] } : {}), ...scope, source: "CASH" }));
  const pending = useQuery(depositQueries.list({ ...scope, source: "CASH", status: ["PENDING"], page_size: 100 }));
  const pendingRows = pending.data?.results ?? [];
  const delayedRows = pendingRows.filter((row) => row.is_delayed);
  const status = (state.values.status as string[] | null) ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Finance · Money"
        title="Settlement queue"
        description="Branch deposits waiting to be matched to the bank statement. Confirm each credit, or mark a returned deposit failed."
      >
        <Segmented
          label="Show"
          className="w-fit"
          value={queue ? "pending" : status.length === 0 ? "all" : "custom"}
          onChange={(next) => {
            void setView(next === "pending" ? "pending" : "all");
            state.setFilters({ status: [] });
          }}
          options={[
            { value: "pending", label: "Awaiting statement", count: pending.data?.count },
            { value: "all", label: "All deposits" },
          ]}
        />
      </PageHeader>
      <div className="flex flex-col gap-6">
        <KpiGrid columns={3}>
          <KpiTile
            label="Awaiting settlement"
            tone="deposited"
            amount={sumMoney(pendingRows.map((row) => row.deposited_amount))}
            loading={pending.isPending}
            context={countOf(pendingRows.length, "deposit")}
          />
          <KpiTile
            label="Past SLA"
            tone="delayed"
            amount={sumMoney(delayedRows.map((row) => row.deposited_amount))}
            loading={pending.isPending}
            context={delayedRows.length ? `${countOf(delayedRows.length, "deposit")} older than 2 days` : "Nothing late"}
          />
          <KpiTile
            label="Oldest pending"
            count={Math.max(0, ...pendingRows.map((row) => row.days_pending ?? 0))}
            loading={pending.isPending}
            context="days since deposit"
          />
        </KpiGrid>
        <DataTable
          caption={queue ? "Deposits awaiting settlement" : "All deposits"}
          columns={DEPOSIT_COLUMNS}
          data={list.data?.results}
          rowCount={list.data?.count}
          state={state}
          isLoading={list.isFetching}
          error={list.error}
          onRetry={() => void list.refetch()}
          onRowClick={(row) => router.push(`/app/finance/settlements/${row.id}`)}
          renderCard={(row) => <DepositCard deposit={row} />}
          toolbar={<FilterBar state={queue ? { ...state, filters: QUEUE_FILTERS } : state} searchPlaceholder="Deposit or bank reference" />}
          empty={
            queue ? (
              <EmptyState bordered illustration="settled" title="Every deposit is settled." description="New deposits appear here as branches bank their cash." />
            ) : (
              <EmptyState bordered title="No deposits match these filters." />
            )
          }
        />
      </div>
    </>
  );
}
