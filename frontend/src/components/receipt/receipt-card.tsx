import type { ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { Money } from "@/components/money/money";
import { collectionTimelineItems, LifecycleTimeline } from "@/components/status/lifecycle-timeline";
import { ModeChip } from "@/components/status/mode-chip";
import { StatusChip } from "@/components/status/status-chip";
import { formatDateTime, formatDayMonth } from "@/lib/dates";
import { amountInWords } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CollectionDetail } from "@/types/domain";

interface ReceiptCardProps {
  receipt: CollectionDetail;
  /** Share / Print / Void row under the ticket; never printed. */
  actions?: ReactNode;
  showTimeline?: boolean;
  /** Slide up on arrival (the success moment after recording). */
  arriving?: boolean;
  className?: string;
}

/**
 * The payment receipt: a paper ticket with perforated edges, mono receipt number, IST time,
 * the amount with words, allocation and where the money is now. Prints on white in the light
 * palette with the app chrome hidden.
 */
export function ReceiptCard({ receipt, actions, showTimeline = true, arriving = false, className }: ReceiptCardProps) {
  const voided = receipt.status === "VOIDED";
  const allocations = receipt.allocations.filter((allocation) => !allocation.reversed_at);

  return (
    <div className={cn("flex flex-col gap-5", arriving && "animate-rise", className)}>
      <article
        aria-label={`Receipt ${receipt.receipt_number}`}
        data-print="plain"
        className="perforated relative flex flex-col bg-raised px-5 pt-9 pb-10 shadow-float sm:px-8"
      >
        <header className="flex items-start justify-between gap-4">
          <Logo size="sm" />
          <StatusChip kind="collection" status={receipt.status} size="sm" />
        </header>

        <div className="mt-7 flex flex-col gap-1">
          <p className="eyebrow">Payment receipt</p>
          <p className="font-mono text-[13px] tracking-[0.02em] wrap-anywhere text-ink">{receipt.receipt_number}</p>
          <time dateTime={receipt.collected_at} className="font-mono text-[11.5px] text-faint">
            {formatDateTime(receipt.collected_at)} IST
          </time>
        </div>

        <div className="mt-6 flex flex-col gap-2 border-y border-dashed border-rule-strong py-6">
          <Money
            value={receipt.amount}
            strike={voided}
            quietSymbol
            className={cn("text-[40px] leading-none font-medium tracking-[-0.025em]", voided ? "text-faint" : "text-ink")}
          />
          <p className="text-[13px] leading-relaxed text-dim">{amountInWords(receipt.amount)}</p>
          <ModeChip mode={receipt.mode} className="mt-1" />
        </div>

        <dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2.5 text-[13.5px]">
          <dt className="text-dim">Customer</dt>
          <dd className="text-right text-ink">
            {receipt.customer_name}
            <span className="ml-2 inline-block font-mono text-[11.5px] whitespace-nowrap text-faint">{receipt.customer_code}</span>
          </dd>
          <dt className="text-dim">Loan</dt>
          <dd className="text-right font-mono text-[12.5px] wrap-anywhere text-ink">{receipt.loan_number}</dd>
          {receipt.agent_name && (
            <>
              <dt className="text-dim">Collected by</dt>
              <dd className="text-right text-ink">{receipt.agent_name}</dd>
            </>
          )}
          {!voided && receipt.balance_after !== null && (
            <>
              <dt className="text-dim">Balance after</dt>
              <dd className="text-right">
                <Money value={receipt.balance_after} className="text-ink" />
              </dd>
            </>
          )}
          {receipt.remarks && (
            <>
              <dt className="text-dim">Remarks</dt>
              <dd className="text-right text-ink">{receipt.remarks}</dd>
            </>
          )}
        </dl>

        {allocations.length > 0 && (
          <table className="mt-5 w-full text-[13px]">
            <caption className="sr-only">Applied to installments</caption>
            <thead>
              <tr className="border-b border-rule">
                <th scope="col" className="pb-2 text-left font-mono text-[10.5px] font-normal tracking-[0.12em] text-faint uppercase">
                  Installment
                </th>
                <th scope="col" className="pb-2 text-left font-mono text-[10.5px] font-normal tracking-[0.12em] text-faint uppercase">
                  Due
                </th>
                <th scope="col" className="pb-2 text-right font-mono text-[10.5px] font-normal tracking-[0.12em] text-faint uppercase">
                  Applied
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {allocations.map((allocation) => (
                <tr key={allocation.id}>
                  <td className="py-2 text-ink tabular-nums">No. {allocation.installment_no}</td>
                  <td className="py-2 text-dim">{formatDayMonth(allocation.due_date)}</td>
                  <td className="py-2 text-right">
                    <Money value={allocation.amount} className="text-ink" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {voided && (
          <p role="note" className="mt-5 rounded-lg bg-st-voided/8 px-3.5 py-2.5 text-[13px] text-st-voided-fg">
            Voided{receipt.voided_by_name ? ` by ${receipt.voided_by_name}` : ""}
            {receipt.voided_at ? ` on ${formatDateTime(receipt.voided_at)}` : ""}
            {receipt.void_reason ? `: ${receipt.void_reason}` : ""}
          </p>
        )}

        {showTimeline && (
          <section aria-label="Where this money is now" className="mt-7 flex flex-col gap-3.5 border-t border-rule pt-5">
            <h2 className="eyebrow">Where it is now</h2>
            <LifecycleTimeline items={collectionTimelineItems(receipt.timeline, receipt.mode)} />
          </section>
        )}
      </article>
      {actions && (
        <div data-print="hide" className="flex flex-wrap justify-center gap-2">
          {actions}
        </div>
      )}
    </div>
  );
}
