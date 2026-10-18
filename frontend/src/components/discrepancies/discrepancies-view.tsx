"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { RecordCard } from "@/components/branch/record-card";
import { createColumns } from "@/components/data-table/data-table-features";
import { DataTable } from "@/components/data-table/data-table";
import { FilterBar } from "@/components/data-table/filter-bar";
import { EmptyState } from "@/components/feedback/empty-state";
import { KpiGrid, KpiTile } from "@/components/kpi/kpi-tile";
import { PageHeader } from "@/components/layout/page-header";
import { FactList } from "@/components/layout/section-card";
import { Segmented } from "@/components/layout/segmented";
import { Money } from "@/components/money/money";
import { useSession } from "@/components/providers/session-provider";
import { DetailSheet, ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { StatusChip } from "@/components/status/status-chip";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { discrepancyQueries, useResolveDiscrepancy } from "@/features/discrepancies/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import { useDataTableState, type FilterDef } from "@/hooks/use-data-table-state";
import { useIsMobile } from "@/hooks/use-mobile";
import { formatDate, formatDateTime } from "@/lib/dates";
import { sumMoney } from "@/lib/money";
import {
  DISCREPANCY_KIND_LABEL,
  DISCREPANCY_REASON_LABEL,
  type Discrepancy,
  type DiscrepancyKind,
  type ID,
} from "@/types/domain";

const CASH_KINDS: DiscrepancyKind[] = ["CASH_SHORTAGE", "CASH_EXCESS"];
const MONEY_KINDS: DiscrepancyKind[] = ["DEPOSIT_MISMATCH", "SETTLEMENT_MISMATCH", "GATEWAY_MISMATCH"];

const col = createColumns<Discrepancy>();
const COLUMNS = col.columns([
  col.accessor("kind", {
    header: "Discrepancy",
    meta: { card: "title" },
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span>{DISCREPANCY_KIND_LABEL[row.original.kind]}</span>
        <span className="text-[12px] text-faint">{DISCREPANCY_REASON_LABEL[row.original.reason_code]}</span>
      </span>
    ),
  }),
  col.display({
    id: "source",
    header: "Raised on",
    cell: ({ row }) => (
      <span className="font-mono text-[12px] text-dim">{row.original.submission_number ?? row.original.deposit_number ?? "—"}</span>
    ),
  }),
  col.display({
    id: "who",
    header: "Agent / branch",
    cell: ({ row }) => <span className="text-dim">{row.original.agent_name ?? row.original.branch_code ?? "Gateway"}</span>,
  }),
  col.accessor("created_at", {
    header: "Raised",
    enableSorting: true,
    cell: ({ getValue }) => <span className="text-dim">{formatDate(getValue())}</span>,
  }),
  col.accessor("amount", {
    header: "Amount",
    enableSorting: true,
    meta: { align: "end", card: "amount" },
    cell: ({ row }) => <Money value={row.original.amount} tone={row.original.direction === "SHORT" ? "short" : "excess"} />,
  }),
  col.accessor("status", {
    header: "Status",
    meta: { card: "badge" },
    cell: ({ row }) => <StatusChip kind="discrepancy" status={row.original.status} direction={row.original.direction} />,
  }),
]);

function DiscrepancyCard({ row }: { row: Discrepancy }) {
  const source = row.submission_number ?? row.deposit_number;
  return (
    <RecordCard
      title={DISCREPANCY_KIND_LABEL[row.kind]}
      subtitle={DISCREPANCY_REASON_LABEL[row.reason_code]}
      amount={<Money value={row.amount} tone={row.direction === "SHORT" ? "short" : "excess"} />}
      badge={<StatusChip kind="discrepancy" status={row.status} direction={row.direction} size="sm" />}
      meta={[
        formatDate(row.created_at),
        row.agent_name ?? row.branch_code ?? "Gateway",
        source && (
          <span key="source" className="font-mono text-[11.5px]">
            {source}
          </span>
        ),
      ]}
    />
  );
}

const FILTERS: FilterDef[] = [
  { type: "multi", key: "status", label: "Status", options: [
    { value: "OPEN", label: "Open" },
    { value: "RESOLVED", label: "Resolved" },
    { value: "WRITTEN_OFF", label: "Written off" },
  ] },
  { type: "multi", key: "kind", label: "Kind", options: (Object.keys(DISCREPANCY_KIND_LABEL) as DiscrepancyKind[]).map((kind) => ({ value: kind, label: DISCREPANCY_KIND_LABEL[kind] })) },
  { type: "dateRange", label: "Raised", from: "date_from", to: "date_to" },
];

/** Shared by the branch desk (cash counts) and finance (deposits, settlements, gateway). */
export function DiscrepanciesView({ description }: { description: string }) {
  const user = useSession();
  const { branch } = useBranchScope();
  const state = useDataTableState({ filters: FILTERS, defaultOrdering: "-created_at" });
  const scope = branch ? { branch } : {};
  const list = useQuery(discrepancyQueries.list({ ...state.query, ...scope }));
  const open = useQuery(discrepancyQueries.list({ ...scope, status: ["OPEN"], page_size: 100 }));
  const [selected, setSelected] = useState<Discrepancy | null>(null);

  const openRows = open.data?.results ?? [];
  const short = sumMoney(openRows.filter((row) => row.direction === "SHORT").map((row) => row.amount));
  const excess = sumMoney(openRows.filter((row) => row.direction === "EXCESS").map((row) => row.amount));
  const statusFilter = (state.values.status as string[] | null) ?? [];

  return (
    <>
      <PageHeader eyebrow={user.branch_code ? `${user.branch_code} · Control` : "Control"} title="Discrepancies" description={description}>
        <Segmented
          label="Show"
          className="w-fit"
          value={statusFilter.join() === "OPEN" ? "open" : statusFilter.length === 0 ? "all" : "custom"}
          onChange={(value) => state.setFilters({ status: value === "open" ? ["OPEN"] : [] })}
          options={[
            { value: "open", label: "Open", count: open.data?.count },
            { value: "all", label: "All" },
          ]}
        />
      </PageHeader>
      <div className="flex flex-col gap-6">
        <KpiGrid columns={3}>
          <KpiTile label="Open items" count={open.data?.count ?? 0} loading={open.isPending} context="awaiting a decision" />
          <KpiTile label="Open shortages" tone="short" amount={short} loading={open.isPending} context="money missing" />
          <KpiTile label="Open excess" tone="excess" amount={excess} loading={open.isPending} context="money over" />
        </KpiGrid>
        <DataTable
          caption="Discrepancies"
          columns={COLUMNS}
          data={list.data?.results}
          rowCount={list.data?.count}
          state={state}
          isLoading={list.isFetching}
          error={list.error}
          onRetry={() => void list.refetch()}
          onRowClick={setSelected}
          renderCard={(row) => <DiscrepancyCard row={row} />}
          toolbar={<FilterBar state={state} />}
          empty={<EmptyState bordered illustration="settled" title="No discrepancies." description="Every count and deposit has reconciled." />}
        />
      </div>
      <DiscrepancySheet discrepancy={selected} onClose={() => setSelected(null)} />
    </>
  );
}

function DiscrepancySheet({ discrepancy, onClose }: { discrepancy: Discrepancy | null; onClose: () => void }) {
  const user = useSession();
  const isMobile = useIsMobile();
  // The sheet stays mounted between rows, so notes belong to the discrepancy they were typed for.
  const [draft, setDraft] = useState<{ id: ID | null; notes: string }>({ id: null, notes: "" });
  const notes = discrepancy && draft.id === discrepancy.id ? draft.notes : "";
  const setNotes = (value: string) => setDraft({ id: discrepancy?.id ?? null, notes: value });
  const resolve = useResolveDiscrepancy();
  const canResolve =
    discrepancy?.status === "OPEN" &&
    (user.role === "ADMIN" ||
      (user.role === "BRANCH_MANAGER" && CASH_KINDS.includes(discrepancy.kind)) ||
      (user.role === "FINANCE" && MONEY_KINDS.includes(discrepancy.kind)));

  const act = (outcome: "RESOLVED" | "WRITTEN_OFF") =>
    discrepancy &&
    resolve.mutate(
      { id: discrepancy.id, outcome, resolution_notes: notes.trim() },
      {
        onSuccess: () => {
          setDraft({ id: null, notes: "" });
          onClose();
        },
      },
    );

  const sourceHref =
    discrepancy?.submission && user.role !== "FINANCE"
      ? `/app/branch/submissions/${discrepancy.submission}`
      : discrepancy?.deposit
        ? user.role === "BRANCH_MANAGER"
          ? `/app/branch/deposits/${discrepancy.deposit}`
          : `/app/finance/settlements/${discrepancy.deposit}`
        : null;

  // Phones get a content-height sheet so the resolve actions show without dragging it up.
  const Overlay = isMobile ? ResponsiveDialog : DetailSheet;

  return (
    <Overlay
      open={discrepancy !== null}
      onOpenChange={(open) => {
        if (open) return;
        setDraft({ id: null, notes: "" });
        onClose();
      }}
      title={discrepancy ? DISCREPANCY_KIND_LABEL[discrepancy.kind] : ""}
      description={discrepancy ? `Raised ${formatDateTime(discrepancy.created_at)}${discrepancy.raised_by_name ? ` by ${discrepancy.raised_by_name}` : ""}` : undefined}
      footer={
        canResolve && (
          <div className="flex w-full flex-col gap-2 sm:flex-row-reverse">
            <Button disabled={notes.trim().length < 5 || resolve.isPending} onClick={() => act("RESOLVED")}>
              {resolve.isPending && <Loader2 className="animate-spin" />}
              Mark recovered
            </Button>
            <Button variant="outline" disabled={notes.trim().length < 5 || resolve.isPending} onClick={() => act("WRITTEN_OFF")}>
              Write off
            </Button>
          </div>
        )
      }
    >
      {discrepancy && (
        <div className="flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <Money
              value={discrepancy.amount}
              quietSymbol
              tone={discrepancy.direction === "SHORT" ? "short" : "excess"}
              className="text-[30px] font-medium tracking-[-0.02em]"
            />
            <StatusChip kind="discrepancy" status={discrepancy.status} direction={discrepancy.direction} wash />
          </div>
          <FactList
            columns={2}
            items={[
              ["Reason", DISCREPANCY_REASON_LABEL[discrepancy.reason_code]],
              [
                "Raised on",
                sourceHref ? (
                  <Link key="s" href={sourceHref} className="font-mono underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
                    {discrepancy.submission_number ?? discrepancy.deposit_number}
                  </Link>
                ) : (
                  <span key="s" className="font-mono">{discrepancy.submission_number ?? discrepancy.deposit_number ?? "—"}</span>
                ),
              ],
              ["Agent", discrepancy.agent_name ?? "—"],
              ["Branch", discrepancy.branch_code ?? "Gateway"],
            ]}
          />
          {discrepancy.notes && (
            <div className="flex flex-col gap-1.5">
              <p className="eyebrow">Notes</p>
              <p className="text-[14px] leading-relaxed text-ink">{discrepancy.notes}</p>
            </div>
          )}
          {discrepancy.status !== "OPEN" ? (
            <div className="flex flex-col gap-1.5 rounded-lg bg-sunk px-4 py-3">
              <p className="eyebrow">
                {discrepancy.status === "RESOLVED" ? "Recovered" : "Written off"}
                {discrepancy.resolved_at && ` · ${formatDateTime(discrepancy.resolved_at)}`}
                {discrepancy.resolved_by_name && ` · ${discrepancy.resolved_by_name}`}
              </p>
              <p className="text-[14px] text-ink">{discrepancy.resolution_notes}</p>
            </div>
          ) : canResolve ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="resolution">How it was settled</Label>
              <Textarea
                id="resolution"
                rows={3}
                placeholder="e.g. Agent paid in the shortfall against branch receipt BR-1182."
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
              <p className="text-[12.5px] text-dim">The original count and receipts are never changed; this records how the gap was closed.</p>
            </div>
          ) : (
            <p className="text-[13px] text-dim">
              {CASH_KINDS.includes(discrepancy.kind) ? "The branch manager resolves cash discrepancies." : "Finance resolves deposit and settlement discrepancies."}
            </p>
          )}
        </div>
      )}
    </Overlay>
  );
}
