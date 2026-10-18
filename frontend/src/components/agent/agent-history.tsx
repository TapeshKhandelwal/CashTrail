"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { parseAsString, useQueryState } from "nuqs";
import { useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton, KpiGridSkeleton } from "@/components/feedback/skeletons";
import { KpiGrid, KpiTile } from "@/components/kpi/kpi-tile";
import { PageHeader } from "@/components/layout/page-header";
import { Money } from "@/components/money/money";
import { ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { ModeChip } from "@/components/status/mode-chip";
import { StatusChip } from "@/components/status/status-chip";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { collectionQueries, useVoidCollection } from "@/features/collections/api";
import { addDays, formatLongDay, formatTime, todayIST } from "@/lib/dates";
import { countOf } from "@/lib/format";
import type { Collection } from "@/types/domain";

/** A real calendar day in "YYYY-MM-DD" form; anything else in the URL falls back to today. */
function isCalendarDay(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T12:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().startsWith(value);
}

export function AgentHistory() {
  const today = todayIST();
  const [raw, setDate] = useQueryState("date", parseAsString.withDefault(today).withOptions({ history: "replace" }));
  const date = isCalendarDay(raw) && raw <= today ? raw : today;
  const summary = useQuery(collectionQueries.dailySummary({ date }));
  const list = useQuery(collectionQueries.list({ date, page_size: 100, ordering: "-collected_at" }));
  const [voiding, setVoiding] = useState<Collection | null>(null);

  return (
    <div className="mx-auto w-full max-w-[760px]">
      <PageHeader
        eyebrow="History"
        title={date === today ? "Today's receipts" : formatLongDay(date)}
        description="Every receipt you recorded on the day, and where its money is now."
        actions={
          <div className="flex items-center gap-1">
            <Button variant="outline" size="icon-sm" aria-label="Previous day" onClick={() => void setDate(addDays(date, -1))}>
              <ChevronLeft />
            </Button>
            <Button variant="outline" size="sm" disabled={raw === today} onClick={() => void setDate(null)}>
              Today
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Next day"
              disabled={date >= today}
              onClick={() => void setDate(addDays(date, 1))}
            >
              <ChevronRight />
            </Button>
          </div>
        }
      />

      <div className="flex flex-col gap-6">
        {summary.isPending ? (
          <KpiGridSkeleton count={2} />
        ) : summary.isError ? (
          <ErrorState error={summary.error} onRetry={() => void summary.refetch()} bordered compact />
        ) : (
          <KpiGrid columns={2}>
            <KpiTile
              label="Cash"
              amount={summary.data.cash_amount}
              context={`${countOf(summary.data.cash_count, "receipt")}${summary.data.voided_count ? ` · ${summary.data.voided_count} voided` : ""}`}
            />
            <KpiTile
              label="UPI"
              tone="upi"
              amount={summary.data.upi_amount}
              context={countOf(summary.data.upi_count, "payment")}
            />
          </KpiGrid>
        )}

        {list.isPending ? (
          <CardListSkeleton count={4} />
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => void list.refetch()} bordered compact />
        ) : list.data.results.length === 0 ? (
          <EmptyState bordered compact title="No receipts on this day." />
        ) : (
          <ul className="rows-enter divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised">
            {list.data.results.map((item) => (
              <li
                key={item.id}
                className="relative flex items-start gap-3 px-4 py-3.5 transition-colors hover:bg-sunk/50 has-focus-visible:bg-sunk sm:px-5"
              >
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <Link
                    href={`/app/agent/receipts/${item.id}`}
                    className="truncate text-[14px] text-ink outline-none after:absolute after:inset-0"
                  >
                    {item.customer_name}
                  </Link>
                  <span className="truncate font-mono text-[11.5px] text-faint">{item.receipt_number}</span>
                  <span className="flex items-center gap-2 text-[12px] text-faint">
                    <span className="tabular-nums">{formatTime(item.collected_at)}</span>
                    <span aria-hidden className="text-rule-strong">·</span>
                    <ModeChip mode={item.mode} />
                  </span>
                </div>
                <div className="grid shrink-0 justify-items-end gap-1 sm:grid-cols-[auto_auto] sm:items-center sm:gap-x-4">
                  <Money value={item.amount} strike={item.status === "VOIDED"} className="text-[14px] text-ink" />
                  <StatusChip kind="collection" status={item.status} size="sm" className="sm:col-start-1" />
                  {item.status === "COLLECTED" && item.mode === "CASH" && (
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => setVoiding(item)}
                      className="relative z-10 -mr-2 text-dim sm:col-start-2 sm:row-span-2 sm:row-start-1"
                    >
                      Void
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <VoidDialog receipt={voiding} onClose={() => setVoiding(null)} />
    </div>
  );
}

function VoidDialog({ receipt, onClose }: { receipt: Collection | null; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const voidReceipt = useVoidCollection();
  const valid = reason.trim().length >= 5;

  return (
    <ResponsiveDialog
      open={receipt !== null}
      onOpenChange={(open) => {
        if (!open) {
          setReason("");
          onClose();
        }
      }}
      title="Void this receipt?"
      description="Only for a receipt recorded by mistake, before you hand the cash over. The receipt stays in the ledger, struck through."
      footer={
        <Button
          variant="destructive-solid"
          className="w-full sm:w-auto"
          disabled={!valid || voidReceipt.isPending}
          onClick={() =>
            receipt &&
            voidReceipt.mutate(
              { id: receipt.id, reason: reason.trim() },
              {
                onSuccess: () => {
                  setReason("");
                  onClose();
                },
              },
            )
          }
        >
          Void receipt
        </Button>
      }
    >
      {receipt && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-3 rounded-lg bg-sunk px-4 py-3 text-[13.5px]">
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="truncate text-ink">{receipt.customer_name}</span>
              <span className="truncate font-mono text-[11.5px] text-dim">{receipt.receipt_number}</span>
            </span>
            <Money value={receipt.amount} className="shrink-0 text-ink" />
          </div>
          <Textarea
            aria-label="Reason"
            placeholder="Why is this receipt wrong? e.g. entered on the wrong loan"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={3}
            className="text-base sm:text-[14px]"
          />
        </div>
      )}
    </ResponsiveDialog>
  );
}
