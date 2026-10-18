"use client";

import { useQuery } from "@tanstack/react-query";
import { Banknote, Loader2, Smartphone } from "lucide-react";
import { useRouter } from "next/navigation";
import { parseAsInteger, useQueryState } from "nuqs";
import { useCallback, useMemo, useState } from "react";

import { ConfirmDialog, ConfirmFacts } from "@/components/feedback/confirm-dialog";
import { ErrorState } from "@/components/feedback/error-state";
import { DetailSkeleton } from "@/components/feedback/skeletons";
import { PageHeader } from "@/components/layout/page-header";
import { Segmented } from "@/components/layout/segmented";
import { StickyActionBar } from "@/components/layout/sticky-action-bar";
import { Money } from "@/components/money/money";
import { MoneyInput } from "@/components/money/money-input";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useRecordCollection } from "@/features/collections/api";
import { useCreateUpiOrder } from "@/features/gateway/api";
import { loanQueries } from "@/features/loans/api";
import { ApiError } from "@/lib/api/errors";
import { formatDateTime, formatDayMonth } from "@/lib/dates";
import { compareMoney, isZero, parseMoneyInput, toPaise, type MoneyString } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { CollectionDetail, ID, Loan, OrderCreated, PaymentMode } from "@/types/domain";

import { previewAllocation } from "./allocation-preview";
import { LoanPicker } from "./loan-picker";
import { UpiPaymentSheet } from "./upi-payment-sheet";

export function CollectFlow() {
  const [loanId, setLoanId] = useQueryState("loan", parseAsInteger.withOptions({ history: "push" }));
  const pick = useCallback((id: ID) => void setLoanId(id), [setLoanId]);

  return (
    <div className="mx-auto w-full max-w-[560px]">
      <PageHeader eyebrow="New receipt" title="Collect" description="Record cash in hand, or have the customer pay by UPI." />
      {loanId ? <CollectForm loanId={loanId} onChangeLoan={() => void setLoanId(null)} /> : <LoanPicker onPick={pick} />}
    </div>
  );
}

function suggestions(loan: Loan): { label: string; amount: MoneyString }[] {
  const options: { label: string; amount: MoneyString }[] = [];
  if (!isZero(loan.overdue_amount)) options.push({ label: "Overdue", amount: loan.overdue_amount });
  if (loan.next_due) options.push({ label: `EMI ${formatDayMonth(loan.next_due.due_date)}`, amount: loan.next_due.amount });
  options.push({ label: "Full balance", amount: loan.outstanding });
  return options.filter((option, index, all) => all.findIndex((other) => other.amount === option.amount) === index);
}

function CollectForm({ loanId, onChangeLoan }: { loanId: ID; onChangeLoan: () => void }) {
  const router = useRouter();
  const loan = useQuery(loanQueries.detail(loanId));
  const schedule = useQuery(loanQueries.schedule(loanId));
  const [mode, setMode] = useState<PaymentMode>("CASH");
  const [amount, setAmount] = useState<string | null>(null);
  const [remarks, setRemarks] = useState("");
  const [duplicate, setDuplicate] = useState<{ receipt: string; amount: string; at: string } | null>(null);
  const [upiOrder, setUpiOrder] = useState<OrderCreated | null>(null);

  const record = useRecordCollection();
  const createOrder = useCreateUpiOrder();

  const toReceipt = useCallback(
    (receipt: CollectionDetail) => router.push(`/app/agent/receipts/${receipt.id}?new=1`),
    [router],
  );
  const closeUpi = useCallback(() => setUpiOrder(null), []);
  // Close the sheet before leaving: this page stays mounted in the router's history, and
  // going back must not reopen a finished payment.
  const upiPaid = useCallback(
    (receipt: CollectionDetail) => {
      setUpiOrder(null);
      toReceipt(receipt);
    },
    [toReceipt],
  );

  const firstSuggestion = loan.data ? suggestions(loan.data)[0]?.amount : undefined;
  const raw = amount ?? firstSuggestion ?? "";
  const parsed = parseMoneyInput(raw);
  const preview = useMemo(
    () => (parsed && schedule.data ? previewAllocation(schedule.data, parsed) : []),
    [parsed, schedule.data],
  );

  if (loan.isPending) return <DetailSkeleton />;
  if (loan.isError) return <ErrorState error={loan.error} onRetry={() => void loan.refetch()} bordered />;
  const data = loan.data;

  const overLimit = parsed !== null && compareMoney(parsed, data.outstanding) > 0;
  const zero = parsed !== null && isZero(parsed);
  // Cash is counted in notes and coins; only UPI can carry paise.
  const cashPaise = mode === "CASH" && parsed !== null && toPaise(parsed) % 100n !== 0n;
  const serverError = record.error ?? createOrder.error;
  const overCollection = serverError instanceof ApiError && serverError.is("OVER_COLLECTION");
  const invalid = raw !== "" && (parsed === null || zero || overLimit || cashPaise);
  const busy = record.isPending || createOrder.isPending;

  const submit = (confirmDuplicate = false) => {
    if (!parsed || invalid) return;
    if (mode === "UPI") {
      createOrder.mutate({ loan_id: data.id, amount: parsed }, { onSuccess: setUpiOrder });
      return;
    }
    record.mutate(
      { loan_id: data.id, amount: parsed, remarks: remarks.trim() || undefined, confirm_duplicate: confirmDuplicate || undefined },
      {
        onSuccess: toReceipt,
        onError: (error) => {
          if (error.is("POSSIBLE_DUPLICATE")) {
            const details = error.details as { receipt_number?: string; amount?: string; collected_at?: string };
            setDuplicate({ receipt: details.receipt_number ?? "", amount: details.amount ?? parsed, at: details.collected_at ?? "" });
          }
        },
      },
    );
  };

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <section className="flex items-center justify-between gap-3 rounded-xl border border-rule bg-raised py-3.5 pr-3 pl-4 sm:px-5 sm:py-4">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-[15px] text-ink">{data.customer_name}</span>
          <span className="truncate font-mono text-[11.5px] text-faint">
            {data.loan_number}
            <span className="max-sm:hidden">
              {" · "}
              <Money value={data.outstanding} /> outstanding
            </span>
          </span>
          <span className="text-[12.5px] text-dim sm:hidden">
            <Money value={data.outstanding} /> outstanding
          </span>
        </div>
        <Button type="button" variant="ghost" size="sm" className="shrink-0" onClick={onChangeLoan}>
          Change
        </Button>
      </section>

      <section className="flex flex-col items-center gap-4 rounded-xl border border-rule bg-raised px-5 pt-7 pb-6">
        <label htmlFor="amount" className="eyebrow">
          Amount received
        </label>
        <MoneyInput
          id="amount"
          size="hero"
          value={raw}
          onValueChange={(value) => {
            setAmount(value);
            record.reset();
            createOrder.reset();
          }}
          invalid={invalid || overCollection}
          aria-describedby="amount-help"
          autoFocus
        />
        <div className="flex flex-wrap justify-center gap-2">
          {suggestions(data).map((option) => (
            <button
              key={option.label}
              type="button"
              onClick={() => setAmount(option.amount)}
              aria-pressed={raw === option.amount}
              className={cn(
                "rounded-full border px-3 py-1.5 text-[12.5px] transition-colors",
                raw === option.amount ? "border-ink bg-ink text-paper" : "border-rule-strong bg-raised text-dim hover:border-ink/30 hover:text-ink",
              )}
            >
              {option.label} · <Money value={option.amount} whole={false} />
            </button>
          ))}
        </div>
        <p id="amount-help" aria-live="polite" className={cn("text-center text-[12.5px]", invalid || overCollection ? "text-st-rejected-fg" : "text-dim")}>
          {overLimit || overCollection ? (
            <>
              That is more than the <Money value={data.outstanding} /> still owed. Collect at most the balance.
            </>
          ) : raw !== "" && parsed === null ? (
            mode === "CASH" ? "Enter an amount like 2450." : "Enter an amount like 2450 or 2450.50."
          ) : zero ? (
            "Enter an amount greater than zero."
          ) : cashPaise ? (
            "Cash is collected in whole rupees."
          ) : parsed && compareMoney(parsed, data.emi_amount) < 0 ? (
            "Part payment: it goes to the oldest unpaid instalment."
          ) : (
            "Applied to the oldest unpaid instalment first."
          )}
        </p>
      </section>

      {preview.length > 0 && !invalid && (
        <section aria-label="Where this payment goes" className="flex flex-col gap-2">
          <h2 className="eyebrow">This payment covers</h2>
          <ul className="divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised">
            {preview.map((line) => (
              <li key={line.installmentNo} className="flex items-center justify-between px-5 py-3 text-[13.5px]">
                <span className="text-ink">
                  Instalment {line.installmentNo}
                  <span className="ml-2 text-[12.5px] text-faint">due {formatDayMonth(line.dueDate)}</span>
                </span>
                <span className="flex items-center gap-2.5">
                  <span className={cn("text-[12px]", line.clears ? "text-st-settled-fg" : "text-st-collected-fg")}>
                    {line.clears ? "cleared" : "part"}
                  </span>
                  <Money value={line.applied} className="text-ink" />
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="eyebrow">How the customer paid</h2>
        <Segmented<PaymentMode>
          label="Payment mode"
          block
          value={mode}
          onChange={setMode}
          options={[
            { value: "CASH", label: <span className="inline-flex items-center gap-2"><Banknote className="size-4" /> Cash</span> },
            { value: "UPI", label: <span className="inline-flex items-center gap-2"><Smartphone className="size-4" /> UPI</span> },
          ]}
        />
        {mode === "CASH" ? (
          <Textarea
            aria-label="Remarks"
            placeholder="Remarks (optional): who paid, anything unusual"
            value={remarks}
            onChange={(event) => setRemarks(event.target.value)}
            rows={2}
            maxLength={255}
            className="text-base sm:text-[14px]"
          />
        ) : (
          <p className="text-[13px] leading-relaxed text-dim">
            The customer pays from their own phone. The receipt is issued when the gateway confirms, and this money never
            enters your cash in hand.
          </p>
        )}
      </section>

      <StickyActionBar>
        <Button type="submit" size="xl" disabled={!parsed || invalid || busy} className="w-full">
          {busy && <Loader2 className="animate-spin" />}
          {mode === "CASH" ? (
            <span>Record {parsed && !invalid ? <Money value={parsed} /> : "payment"} in cash</span>
          ) : (
            <span>Request {parsed && !invalid ? <Money value={parsed} /> : "payment"} by UPI</span>
          )}
        </Button>
      </StickyActionBar>

      <ConfirmDialog
        open={duplicate !== null}
        onOpenChange={(open) => !open && setDuplicate(null)}
        title="This looks like a repeat"
        description="A receipt for the same amount was recorded on this loan a few minutes ago. Record another only if the customer really paid twice."
        confirmLabel="Record another receipt"
        loading={record.isPending}
        onConfirm={() => {
          setDuplicate(null);
          submit(true);
        }}
      >
        {duplicate && (
          <ConfirmFacts
            rows={[
              ["Earlier receipt", <span key="r" className="font-mono">{duplicate.receipt}</span>],
              ["Amount", <Money key="a" value={duplicate.amount} />],
              ["Recorded", duplicate.at ? formatDateTime(duplicate.at) : "moments ago"],
            ]}
          />
        )}
      </ConfirmDialog>

      <UpiPaymentSheet created={upiOrder} onClose={closeUpi} onPaid={upiPaid} />
    </form>
  );
}
