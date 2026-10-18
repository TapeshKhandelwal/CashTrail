"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { DataTable } from "@/components/data-table/data-table";
import { DEPOSIT_COLUMNS } from "@/components/deposits/deposit-columns";
import { EmptyState } from "@/components/feedback/empty-state";
import { DepositCard } from "@/components/finance/deposit-card";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton } from "@/components/feedback/skeletons";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/layout/section-card";
import { Money } from "@/components/money/money";
import { MoneyInput } from "@/components/money/money-input";
import { VarianceMeter } from "@/components/money/variance-meter";
import { ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { gatewaySettlementQueries, useRecordGatewaySettlement } from "@/features/gateway/api";
import { useDataTableState } from "@/hooks/use-data-table-state";
import { formatDateTime, todayIST } from "@/lib/dates";
import { countOf } from "@/lib/format";
import { compareMoney, parseMoneyInput, subMoney, sumMoney } from "@/lib/money";
import type { ID, UnsettledUpiCollection } from "@/types/domain";

export function GatewaySettlements() {
  const router = useRouter();
  const pending = useQuery(gatewaySettlementQueries.pending());
  const state = useDataTableState({ defaultOrdering: "-settled_on", prefix: "h" });
  const history = useQuery(gatewaySettlementQueries.list(state.query));
  const [excluded, setExcluded] = useState<Set<ID>>(new Set());
  const [recording, setRecording] = useState(false);

  const rows = useMemo(() => pending.data?.collections ?? [], [pending.data]);
  const selected = useMemo(() => rows.filter((row) => !excluded.has(row.id)), [rows, excluded]);
  const gross = sumMoney(selected.map((row) => row.amount));

  return (
    <>
      <PageHeader
        eyebrow="Finance · UPI"
        title="Gateway settlements"
        description="UPI payments captured by the gateway, and the batches it paid into the settlement account net of fees and tax."
        actions={
          <Button disabled={selected.length === 0} onClick={() => setRecording(true)}>
            Record settlement
          </Button>
        }
      />
      <div className="flex flex-col gap-6">
        <SectionCard
          flush
          tone="upi"
          eyebrow={pending.data ? `${countOf(pending.data.count, "payment")} captured` : "Captured"}
          title="Awaiting settlement from the gateway"
          footer={
            <div className="flex items-center justify-between text-[13.5px]">
              <span className="text-dim">{countOf(selected.length, "payment")} selected</span>
              <Money value={gross} className="font-medium text-ink" />
            </div>
          }
        >
          {pending.isPending ? (
            <CardListSkeleton count={3} className="border-0" />
          ) : pending.isError ? (
            <ErrorState error={pending.error} onRetry={() => void pending.refetch()} compact />
          ) : rows.length === 0 ? (
            <EmptyState compact illustration="settled" title="Nothing waiting." description="Every captured UPI payment has been settled." />
          ) : (
            <ul className="divide-y divide-rule">
              {rows.map((row) => (
                <UpiRow
                  key={row.id}
                  row={row}
                  checked={!excluded.has(row.id)}
                  onToggle={() =>
                    setExcluded((current) => {
                      const next = new Set(current);
                      if (next.has(row.id)) next.delete(row.id);
                      else next.add(row.id);
                      return next;
                    })
                  }
                />
              ))}
            </ul>
          )}
        </SectionCard>

        <section className="flex flex-col gap-3">
          <h2 className="title-section">Settled batches</h2>
          <DataTable
            caption="Gateway settlements"
            columns={DEPOSIT_COLUMNS}
            data={history.data?.results}
            rowCount={history.data?.count}
            state={state}
            isLoading={history.isFetching}
            error={history.error}
            onRetry={() => void history.refetch()}
            onRowClick={(row) => router.push(`/app/finance/settlements/${row.id}`)}
            renderCard={(row) => <DepositCard deposit={row} />}
            empty={<EmptyState bordered title="No gateway settlements yet." />}
          />
        </section>
      </div>

      <RecordDialog open={recording} onOpenChange={setRecording} collectionIds={selected.map((row) => row.id)} gross={gross} />
    </>
  );
}

function UpiRow({ row, checked, onToggle }: { row: UnsettledUpiCollection; checked: boolean; onToggle: () => void }) {
  return (
    <li>
      <label className="flex cursor-pointer items-center gap-3.5 px-5 py-3 transition-colors hover:bg-sunk/50 max-sm:items-start max-sm:py-3.5">
        <Checkbox checked={checked} onCheckedChange={onToggle} aria-label={row.receipt_number} className="max-sm:mt-0.5" />
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="flex items-baseline justify-between gap-3">
            <span className="truncate text-[14px] text-ink">
              {row.customer_name}
              <span className="ml-2 font-mono text-[11.5px] text-faint">{row.branch_code}</span>
            </span>
            <Money value={row.amount} className="shrink-0 text-ink sm:hidden" />
          </span>
          <span className="truncate font-mono text-[11.5px] text-faint max-sm:hidden">
            {formatDateTime(row.collected_at)} · {row.gateway_payment_id ?? row.receipt_number}
          </span>
          <span className="truncate font-mono text-[11.5px] text-dim sm:hidden">{row.receipt_number}</span>
          <span className="flex flex-wrap gap-x-1.5 text-[12px] text-faint sm:hidden">
            <span>{formatDateTime(row.collected_at)}</span>
            {row.gateway_payment_id && <span className="font-mono text-[11px]">{row.gateway_payment_id}</span>}
          </span>
        </span>
        <Money value={row.amount} className="text-ink max-sm:hidden" />
      </label>
    </li>
  );
}

function RecordDialog({ open, onOpenChange, collectionIds, gross }: { open: boolean; onOpenChange: (open: boolean) => void; collectionIds: ID[]; gross: string }) {
  const [fee, setFee] = useState("");
  const [tax, setTax] = useState("");
  const [net, setNet] = useState("");
  const [utr, setUtr] = useState("");
  const [date, setDate] = useState(todayIST());
  const [remarks, setRemarks] = useState("");
  const record = useRecordGatewaySettlement({ successMessage: (deposit) => `${deposit.deposit_number} recorded` });

  const feeAmount = parseMoneyInput(fee || "0");
  const taxAmount = parseMoneyInput(tax || "0");
  const netAmount = parseMoneyInput(net);
  const expectedNet = feeAmount && taxAmount ? subMoney(subMoney(gross, feeAmount), taxAmount) : null;
  const mismatch = netAmount !== null && expectedNet !== null && compareMoney(netAmount, expectedNet) !== 0;
  const ready = feeAmount && taxAmount && netAmount && utr.trim().length >= 6 && (!mismatch || remarks.trim().length >= 5);

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Record a gateway settlement"
      description={`${countOf(collectionIds.length, "payment")} in this batch. Enter the gateway's fee, tax and the net credit with its UTR.`}
      footer={
        <Button
          disabled={!ready || record.isPending}
          onClick={() =>
            feeAmount &&
            taxAmount &&
            netAmount &&
            record.mutate(
              {
                collection_ids: collectionIds,
                gross_amount: gross,
                fee_amount: feeAmount,
                tax_amount: taxAmount,
                net_amount: netAmount,
                utr: utr.trim(),
                settled_on: date,
                remarks: remarks.trim() || undefined,
              },
              { onSuccess: () => onOpenChange(false) },
            )
          }
        >
          {record.isPending && <Loader2 className="animate-spin" />}
          {mismatch ? "Record with mismatch" : "Record settlement"}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between rounded-lg bg-sunk px-4 py-3 text-[13.5px]">
          <span className="text-dim">Gross captured</span>
          <Money value={gross} className="font-medium text-ink" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fee">Gateway fee</Label>
            <MoneyInput id="fee" value={fee} onValueChange={setFee} placeholder="0.00" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tax">GST on fee</Label>
            <MoneyInput id="tax" value={tax} onValueChange={setTax} placeholder="0.00" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="net">Net credited</Label>
            <MoneyInput id="net" value={net} onValueChange={setNet} placeholder={expectedNet ?? ""} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="g-date">Settled on</Label>
            <Input id="g-date" type="date" max={todayIST()} value={date} onChange={(event) => setDate(event.target.value)} />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="utr">UTR</Label>
          <Input id="utr" value={utr} onChange={(event) => setUtr(event.target.value)} className="font-mono uppercase placeholder:normal-case" placeholder="e.g. KKBKR26101663718013" />
        </div>
        {expectedNet && netAmount && <VarianceMeter expected={expectedNet} counted={netAmount} expectedLabel="Expected net" countedLabel="Credited" />}
        {mismatch && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="g-remarks">Why the credit differs</Label>
            <Textarea id="g-remarks" rows={2} value={remarks} onChange={(event) => setRemarks(event.target.value)} placeholder="e.g. Refund adjustment of ₹25 deducted from this batch." />
          </div>
        )}
      </div>
    </ResponsiveDialog>
  );
}
