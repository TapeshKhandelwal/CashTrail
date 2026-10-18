"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { DataTable } from "@/components/data-table/data-table";
import { FilterBar } from "@/components/data-table/filter-bar";
import { DEPOSIT_COLUMNS, DEPOSIT_FILTERS, DepositCard } from "@/components/deposits/deposit-columns";
import { EmptyState } from "@/components/feedback/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { Money } from "@/components/money/money";
import { useSession } from "@/components/providers/session-provider";
import { Button } from "@/components/ui/button";
import { depositQueries } from "@/features/deposits/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import { useDataTableState } from "@/hooks/use-data-table-state";
import { formatCount } from "@/lib/format";

export function BranchDeposits() {
  const user = useSession();
  const router = useRouter();
  const { branch } = useBranchScope();
  const scope = branch ? { branch } : {};
  const state = useDataTableState({ filters: DEPOSIT_FILTERS, defaultOrdering: "-deposit_date" });
  const list = useQuery(depositQueries.list({ ...state.query, ...scope, source: "CASH" }));
  const pending = useQuery(depositQueries.pendingCash(scope));

  return (
    <>
      <PageHeader
        eyebrow={user.branch_code ? `${user.branch_code} · Money` : "Money"}
        title="Deposits"
        description="Counted cash taken to the bank, and whether the bank has confirmed it."
        actions={
          <Button asChild>
            <Link href="/app/branch/deposits/new">
              <Plus data-icon="inline-start" />
              New deposit
            </Link>
          </Button>
        }
      />
      <div className="flex flex-col gap-6">
        {pending.data && pending.data.count > 0 && (
          <Link
            href="/app/branch/deposits/new"
            className="group flex flex-wrap items-center justify-between gap-4 rounded-xl border border-st-received/30 bg-st-received/6 px-5 py-4 transition-colors hover:bg-st-received/10"
          >
            <span className="flex flex-col gap-0.5">
              <span className="text-[14.5px] text-ink">
                <Money value={pending.data.total_amount} /> counted and waiting to be banked
              </span>
              <span className="text-[12.5px] text-dim">
                {formatCount(pending.data.count)} accepted hand-overs. Deposit them together on one slip.
              </span>
            </span>
            <span className="inline-flex items-center gap-1.5 text-[13.5px] text-st-received-fg">
              Prepare deposit <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </span>
          </Link>
        )}
        <DataTable
          caption="Bank deposits"
          columns={DEPOSIT_COLUMNS}
          data={list.data?.results}
          rowCount={list.data?.count}
          state={state}
          isLoading={list.isFetching}
          error={list.error}
          onRetry={() => void list.refetch()}
          onRowClick={(row) => router.push(`/app/branch/deposits/${row.id}`)}
          renderCard={(row) => <DepositCard deposit={row} />}
          toolbar={<FilterBar state={state} searchPlaceholder="Deposit or bank reference" />}
          empty={<EmptyState bordered title="No deposits yet." description="Counted cash becomes a deposit once it reaches the bank." />}
        />
      </div>
    </>
  );
}
